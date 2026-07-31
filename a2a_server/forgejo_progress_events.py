"""Publish Forgejo session transcripts while a task is still running.

The Forgejo task page renders a "Session transcript" panel from agent-task
events. Those events were only published by the terminal-task hook, so for the
entire life of a run the panel said "No session events have been published yet"
and `external_session_id` stayed null. Operators could see that a task was
`running` but had no visibility into what it was doing.

Workers stream their narration to `/v1/agent/tasks/{id}/output` but never call
the session-message sync endpoint, so no transcript rows existed to publish.
`record_output_chunk` persists those streamed chunks as session messages, which
gives both this publisher and the terminal hook real content to work with.

This module publishes the same normalized transcript incrementally, throttled so
a chatty worker cannot flood the Forgejo API. Publishing is idempotent:
`publish_session_events` skips events whose `external_id` already exists.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Minimum seconds between transcript publishes for one task.
DEFAULT_MIN_INTERVAL_SECONDS = 20.0

# Transcript window fetched for in-flight publishes. Smaller than the terminal
# publish because this runs repeatedly during a task.
PROGRESS_MESSAGE_LIMIT = 400

_LAST_PUBLISH: Dict[str, float] = {}

# Bound the throttle map so a long-lived server cannot grow it without limit.
_MAX_TRACKED_TASKS = 2048


def min_interval_seconds() -> float:
    """Return the minimum delay between in-flight publishes for a task."""
    raw = os.environ.get('CODETETHER_FORGEJO_PROGRESS_INTERVAL_SECONDS', '')
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_MIN_INTERVAL_SECONDS
    return parsed if parsed >= 0 else DEFAULT_MIN_INTERVAL_SECONDS


def progress_publishing_enabled() -> bool:
    """Return whether in-flight transcript publishing is active."""
    raw = os.environ.get('CODETETHER_FORGEJO_PROGRESS_EVENTS', 'true')
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def should_publish(task_id: str, now: Optional[float] = None) -> bool:
    """Return true when this task is due for another in-flight publish."""
    if not task_id:
        return False
    current = time.monotonic() if now is None else now
    interval = min_interval_seconds()
    last = _LAST_PUBLISH.get(task_id)
    if last is not None and (current - last) < interval:
        return False
    if len(_LAST_PUBLISH) >= _MAX_TRACKED_TASKS:
        _LAST_PUBLISH.clear()
    _LAST_PUBLISH[task_id] = current
    return True


def forget(task_id: str) -> None:
    """Drop throttle state for a task that reached a terminal status."""
    _LAST_PUBLISH.pop(task_id, None)


def reset() -> None:
    """Clear all throttle state (used by tests)."""
    _LAST_PUBLISH.clear()


def is_forgejo_agent_task(task: Optional[Dict[str, Any]]) -> bool:
    """Return true when `task` is a native Forgejo agent task with a task id."""
    metadata = (task or {}).get('metadata') or {}
    if metadata.get('source') != 'forgejo-webhook':
        return False
    try:
        return int(metadata.get('forgejo_agent_task_id') or 0) > 0
    except (TypeError, ValueError):
        return False


async def record_output_chunk(
    task_id: str, output: str, worker_id: str = ''
) -> bool:
    """Persist one streamed worker output chunk as a session message.

    The Forgejo transcript is built from `session_messages`. Workers stream
    progress narration to the task-output endpoint but never sync session
    messages, so without this the transcript had no rows to publish even once a
    `session_id` was known.

    Returns:
        True when a message row was written.
    """
    text = (output or '').strip()
    if not task_id or not text:
        return False

    from . import database as db

    try:
        task = await db.db_get_task(task_id)
    except Exception as exc:
        logger.debug('Output persist skipped for %s: %s', task_id, exc)
        return False

    if not is_forgejo_agent_task(task):
        return False

    metadata = task.get('metadata') or {}
    session_id = str(
        task.get('session_id') or metadata.get('session_id') or ''
    ).strip()
    if not session_id:
        # Derive a stable session id from the task so progress is recorded even
        # before the worker reports its own session on release.
        session_id = f'task-{task_id}'
        try:
            await _persist_derived_session_id(task_id, session_id)
        except Exception as exc:
            logger.debug('Derived session persist failed for %s: %s', task_id, exc)

    # `session_messages.session_id` is a foreign key to `sessions(id)`, so the
    # parent row must exist before any transcript row can be written.
    if not await _ensure_session_row(session_id, task):
        return False

    try:
        return await db.db_upsert_message(
            {
                'id': str(uuid.uuid4()),
                'session_id': session_id,
                'role': 'assistant',
                'content': text,
                'model': str(metadata.get('model_ref') or ''),
            }
        )
    except Exception as exc:
        logger.debug('Session message write failed for %s: %s', task_id, exc)
        return False


async def _session_workspace_fk_target(conn: Any) -> Optional[str]:
    """Return the table that `sessions.workspace_id` must reference.

    The constraint is historically named `sessions_codebase_id_fkey` and points
    at the legacy `codebases` table on some deployments and `workspaces` on
    others. Ask the catalog instead of guessing.
    """
    return await conn.fetchval(
        """
        SELECT confrelid::regclass::text
        FROM pg_constraint
        WHERE conrelid = 'sessions'::regclass
          AND contype = 'f'
          AND 'workspace_id' = ANY (
              SELECT a.attname FROM pg_attribute a
              WHERE a.attrelid = conrelid AND a.attnum = ANY (conkey)
          )
        LIMIT 1
        """
    )


async def _workspace_is_referenceable(conn: Any, workspace_id: str) -> bool:
    """Return true when `sessions.workspace_id` can reference this workspace.

    Only the table the foreign key actually targets may be consulted. Accepting
    a match from any candidate table reported success for an id that lived in
    `workspaces` but not in `codebases`, and the insert then failed on the
    constraint, so no transcript row was ever written.
    """
    try:
        target = await _session_workspace_fk_target(conn)
    except Exception as exc:
        logger.debug('Could not resolve session workspace FK target: %s', exc)
        return False
    if not target:
        # No foreign key on the column: any value is acceptable.
        return True
    try:
        return bool(
            await conn.fetchval(
                f'SELECT 1 FROM {target} WHERE id = $1', workspace_id
            )
        )
    except Exception as exc:
        logger.debug('Workspace reference check failed for %s: %s', target, exc)
        return False


async def _ensure_session_row(
    session_id: str, task: Dict[str, Any]
) -> bool:
    """Create the parent `sessions` row when it does not already exist.

    `sessions.workspace_id` is a foreign key (to the legacy `codebases` table),
    so the workspace is only referenced when that row actually exists. A
    transcript is more valuable than the workspace back-reference, so an
    unreferenceable workspace yields a session with a null workspace rather than
    no session at all.
    """
    from .database import get_pool

    metadata = task.get('metadata') or {}
    try:
        pool = await get_pool()
        if not pool:
            return False
        async with pool.acquire() as conn:
            workspace_id = (
                str(
                    task.get('workspace_id')
                    or metadata.get('workspace_id')
                    or ''
                )
                or None
            )
            if workspace_id is not None and not await _workspace_is_referenceable(
                conn, workspace_id
            ):
                workspace_id = None
            await conn.execute(
                """
                INSERT INTO sessions (id, workspace_id, title, last_activity_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (id) DO UPDATE SET last_activity_at = now()
                """,
                session_id,
                workspace_id,
                str(task.get('title') or '')[:200] or None,
            )
    except Exception as exc:
        logger.debug('Session row ensure failed for %s: %s', session_id, exc)
        return False
    return True


async def _persist_derived_session_id(task_id: str, session_id: str) -> None:
    """Record a task-derived session id so later reads resolve the transcript."""
    from .database import get_pool

    pool = await get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tasks
            SET metadata = coalesce(metadata, '{}'::jsonb)
                           || jsonb_build_object('session_id', $2::text)
            WHERE id = $1
              AND coalesce(metadata->>'session_id', '') = ''
            """,
            task_id,
            session_id,
        )


async def publish_task_progress(task_id: str) -> int:
    """Publish the current transcript for an in-flight Forgejo task.

    Returns:
        The number of newly published events; 0 when publishing is disabled,
        throttled, not applicable, or nothing new was available.
    """
    if not progress_publishing_enabled():
        return 0
    if not should_publish(task_id):
        return 0

    from . import database as db

    try:
        task = await db.db_get_task(task_id)
    except Exception as exc:
        logger.debug('Progress publish skipped for %s: %s', task_id, exc)
        return 0

    if not is_forgejo_agent_task(task):
        return 0

    metadata = task.get('metadata') or {}
    status = str(task.get('status') or '').lower()
    if status in {'completed', 'failed', 'cancelled'}:
        # The terminal hook owns the final transcript.
        forget(task_id)
        return 0

    from .forgejo_agent_client import publish_session_events, update_task
    from .session_view import _task_messages

    repo = str(metadata.get('repo') or '')
    base_url = str(metadata.get('forgejo_api_url') or '')
    forgejo_task_id = int(metadata.get('forgejo_agent_task_id') or 0)

    try:
        session_id, messages = await _task_messages(
            task, PROGRESS_MESSAGE_LIMIT
        )
    except Exception as exc:
        logger.debug('Transcript read failed for %s: %s', task_id, exc)
        return 0

    if not messages:
        return 0

    published = 0
    try:
        published = await publish_session_events(
            repo=repo,
            forgejo_task_id=forgejo_task_id,
            codetether_task_id=task_id,
            messages=messages,
            base_url=base_url,
        )
        if session_id:
            # Surface the session link on the Forgejo task page as soon as the
            # agent has one, instead of only after the task finishes.
            await update_task(
                repo=repo,
                task_id=forgejo_task_id,
                base_url=base_url,
                status='running',
                external_task_id=task_id,
                external_session_id=session_id,
            )
    except Exception as exc:
        logger.warning(
            'Forgejo progress publish failed for task %s: %s', task_id, exc
        )
        return 0

    if published:
        logger.info(
            'Published %s in-flight session event(s) for Forgejo task %s',
            published,
            forgejo_task_id,
        )
    return published