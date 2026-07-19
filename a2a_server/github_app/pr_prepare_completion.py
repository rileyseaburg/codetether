"""Follow-up creation for GitHub App PR prepare tasks."""

import json
import logging
from datetime import datetime

from .settings import MODEL_REF, TASK_PRIORITY
from .task_context import github_app_task_context
from .watch import post_issue_comment

DEFAULT_TASK_TIMEOUT = 604800  # 7 days
logger = logging.getLogger(__name__)


async def _claim_pr_followup_creation(task_id: str | None) -> bool:
    """Atomically claim follow-up creation for one prepare task."""
    if not task_id:
        return True

    from .. import database as db

    pool = await db.get_pool()
    if not pool:
        return True

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE tasks
            SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                updated_at = NOW()
            WHERE id = $1
              AND NOT (
                COALESCE(metadata, '{}'::jsonb)
                ? 'post_clone_followup_claimed_at'
              )
              AND NOT (
                COALESCE(metadata, '{}'::jsonb)
                ? 'post_clone_followup_task_id'
              )
            RETURNING id
            """,
            task_id,
            json.dumps(
                {
                    'post_clone_followup_claimed_at': datetime.utcnow().isoformat(),
                    'post_clone_followup_source_task_id': task_id,
                }
            ),
        )
    return row is not None


async def _record_pr_followup_task(
    task_id: str | None, followup_task_id: str
) -> None:
    if not task_id:
        return

    from .. import database as db

    pool = await db.get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tasks
            SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            json.dumps({'post_clone_followup_task_id': followup_task_id}),
        )


async def _acquire_followup_lock(repo: str, number: int, kind: str):
    """Acquire a DB-backed process-wide lock for one GitHub item follow-up."""
    from .. import database as db

    pool = await db.get_pool()
    if not pool:
        return None

    key = f'github-app-followup:{kind}:{repo}:{number}'
    conn = await pool.acquire()
    try:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1, 0))',
            key,
        )
        return pool, conn, key
    except Exception:
        await pool.release(conn)
        raise


async def _release_followup_lock(lock) -> None:
    if not lock:
        return
    pool, conn, key = lock
    try:
        await conn.execute(
            'SELECT pg_advisory_unlock(hashtextextended($1, 0))',
            key,
        )
    finally:
        await pool.release(conn)


async def _active_followup_task_id(
    repo: str,
    number: int,
    kind: str,
) -> str | None:
    """Return an active non-prepare GitHub App task for this issue or PR."""
    from .. import database as db

    pool = await db.get_pool()
    if not pool:
        return None

    number_key = 'pr_number' if kind == 'pr' else 'issue_number'
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT id
            FROM tasks
            WHERE status IN ('pending', 'queued', 'running', 'working')
              AND COALESCE(metadata, '{{}}'::jsonb)->>'source' = 'github-app'
              AND COALESCE(metadata, '{{}}'::jsonb)->>'repo' = $1
              AND COALESCE(metadata, '{{}}'::jsonb)->>'{number_key}' = $2
              AND title NOT ILIKE 'Prepare %'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            repo,
            str(number),
        )
    return str(row['id']) if row else None


async def _release_pr_followup_claim(
    task_id: str | None, error: Exception
) -> None:
    if not task_id:
        return

    from .. import database as db

    pool = await db.get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tasks
            SET metadata = (
                    COALESCE(metadata, '{}'::jsonb)
                    - 'post_clone_followup_claimed_at'
                    - 'post_clone_followup_source_task_id'
                ) || $2::jsonb,
                updated_at = NOW()
            WHERE id = $1
              AND NOT (
                COALESCE(metadata, '{}'::jsonb)
                ? 'post_clone_followup_task_id'
              )
            """,
            task_id,
            json.dumps({'post_clone_followup_error': str(error)[:500]}),
        )


async def handle_pr_prepare_completion(
    task: dict, worker_id: str | None = None
) -> None:
    """Create the PR branch edit task or post a prepare failure."""
    from ..persistent_worker_pool import create_and_dispatch_task

    metadata = task.get('metadata') or {}
    context = await github_app_task_context(task)
    if context is None:
        return
    repo, pr_number, _, token = context
    if str(task.get('status')) != 'completed':
        body = str(
            task.get('error')
            or task.get('result')
            or f'Task `{task.get("id")}` ended with status `{task.get("status")}`.'
        ).strip()
        await post_issue_comment(
            repo,
            pr_number,
            token,
            f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the PR workspace.\n\n{body}",
        )
        return

    followup = metadata.get('post_clone_task') or {}
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    prompt = str(followup.get('prompt') or '').strip()
    if not workspace_id or not prompt:
        await post_issue_comment(
            repo,
            pr_number,
            token,
            '## 🛠️ CodeTether Fix\n\nI prepared the PR workspace, but the follow-up task metadata was incomplete.',
        )
        return

    followup_metadata = dict(followup.get('metadata') or {})

    # Propagate GitHub metadata for progress reporting and Checks API updates.
    for key in (
        'github_issue_url',
        'github_installation_id',
        'github_check_head_sha',
        'github_check_run_id',
    ):
        if key in metadata and key not in followup_metadata:
            followup_metadata[key] = metadata[key]

    source_task_id = str(task.get('id') or '').strip() or None
    if not await _claim_pr_followup_creation(source_task_id):
        logger.info(
            'Skipping duplicate PR follow-up creation for prepare task %s',
            source_task_id,
        )
        return

    github_issue_url = followup_metadata.get(
        'github_issue_url'
    ) or metadata.get('github_issue_url')
    lock = await _acquire_followup_lock(repo, pr_number, 'pr')
    try:
        existing_task_id = await _active_followup_task_id(repo, pr_number, 'pr')
        if existing_task_id:
            logger.info(
                'Skipping duplicate PR follow-up for %s#%s; active task %s exists',
                repo,
                pr_number,
                existing_task_id,
            )
            await _record_pr_followup_task(source_task_id, existing_task_id)
            return

        followup_task_id = await create_and_dispatch_task(
            workspace_id=workspace_id,
            title=str(followup.get('title') or f'Apply PR fix #{pr_number}'),
            prompt=prompt,
            agent_type=str(followup.get('agent_type') or 'build'),
            priority=TASK_PRIORITY,
            model_ref=MODEL_REF,
            metadata=followup_metadata,
            task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
            github_issue_url=github_issue_url,
        )
    except Exception as exc:
        await _release_pr_followup_claim(source_task_id, exc)
        raise
    finally:
        await _release_followup_lock(lock)
    await _record_pr_followup_task(source_task_id, followup_task_id)
