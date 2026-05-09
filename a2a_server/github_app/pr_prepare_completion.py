"""Follow-up creation for GitHub App PR prepare tasks."""

import json
import logging
from datetime import datetime

from .settings import MODEL_REF
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


async def _record_pr_followup_task(task_id: str | None, followup_task_id: str) -> None:
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


async def _release_pr_followup_claim(task_id: str | None, error: Exception) -> None:
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


async def handle_pr_prepare_completion(task: dict, worker_id: str | None = None) -> None:
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
            or f"Task `{task.get('id')}` ended with status `{task.get('status')}`."
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
            "## 🛠️ CodeTether Fix\n\nI prepared the PR workspace, but the follow-up task metadata was incomplete.",
        )
        return

    followup_metadata = dict(followup.get('metadata') or {})

    # Propagate github_issue_url and github_installation_id for progress reporting
    for key in ('github_issue_url', 'github_installation_id'):
        if key in metadata and key not in followup_metadata:
            followup_metadata[key] = metadata[key]

    source_task_id = str(task.get('id') or '').strip() or None
    if not await _claim_pr_followup_creation(source_task_id):
        logger.info(
            'Skipping duplicate PR follow-up creation for prepare task %s',
            source_task_id,
        )
        return

    target_worker_id = str(worker_id or task.get('worker_id') or '').strip()
    if target_worker_id:
        followup_metadata['target_worker_id'] = target_worker_id

    github_issue_url = followup_metadata.get('github_issue_url') or metadata.get(
        'github_issue_url'
    )
    try:
        followup_task_id = await create_and_dispatch_task(
            workspace_id=workspace_id,
            title=str(followup.get('title') or f'Apply PR fix #{pr_number}'),
            prompt=prompt,
            agent_type=str(followup.get('agent_type') or 'build'),
            model_ref=MODEL_REF,
            metadata=followup_metadata,
            task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
            github_issue_url=github_issue_url,
        )
    except Exception as exc:
        await _release_pr_followup_claim(source_task_id, exc)
        raise
    await _record_pr_followup_task(source_task_id, followup_task_id)
