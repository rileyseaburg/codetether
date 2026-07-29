"""Publish Forgejo session transcripts while a task is still running.

The Forgejo task page renders a "Session transcript" panel from agent-task
events. Those events were only published by the terminal-task hook, so for the
entire life of a run the panel said "No session events have been published yet"
and `external_session_id` stayed null. Operators could see that a task was
`running` but had no visibility into what it was doing.

This module publishes the same normalized transcript incrementally, throttled so
a chatty worker cannot flood the Forgejo API. Publishing is idempotent:
`publish_session_events` skips events whose `external_id` already exists.
"""

from __future__ import annotations

import logging
import os
import time
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
