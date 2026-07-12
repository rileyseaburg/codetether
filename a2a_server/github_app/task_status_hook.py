"""Shared terminal-task hook for GitHub App workflows."""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_RECONCILER_TASK: asyncio.Task | None = None


async def handle_github_app_terminal_task(task_id: str, worker_id: str | None = None) -> None:
    """Load a terminal task and run any GitHub App follow-up logic."""
    from .. import database as db
    from .checks import ensure_task_check_run
    from .task_completion import notify_issue_task_completion

    task = await db.db_get_task(task_id)
    metadata = (task or {}).get('metadata') or {}
    if metadata.get('source') == 'forgejo-webhook':
        from ..forgejo_task_completion import notify_forgejo_task_completion

        await notify_forgejo_task_completion(task)
        return
    if metadata.get('source') == 'github-app':
        try:
            if metadata.get('workflow_stage') == 'fix':
                from .pr_final_comment import normalize_pr_fix_terminal_status

                task = await normalize_pr_fix_terminal_status(task)
            elif metadata.get('workflow_stage') == 'code' and not metadata.get('pr_number'):
                from .issue_final_comment import normalize_issue_task_terminal_status

                task = await normalize_issue_task_terminal_status(task)
        except Exception as exc:
            logger.warning('GitHub terminal protocol normalization failed for task %s: %s', task_id, exc)
        try:
            await ensure_task_check_run(task, status='completed')
        except Exception as exc:
            logger.warning('GitHub Checks terminal update failed for task %s: %s', task_id, exc)
        await notify_issue_task_completion(task, worker_id)


async def reconcile_github_app_terminal_tasks(limit: int = 20) -> int:
    """Run missed GitHub App review completions that have no merge decision yet."""
    from .. import database as db
    from .issue_review_task import reviewer_allows_merge
    from .task_completion import notify_issue_task_completion

    pool = await db.get_pool()
    if not pool:
        return 0

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id
            FROM tasks t
            WHERE t.status = 'completed'
              AND t.completed_at >= NOW() - INTERVAL '2 days'
              AND t.metadata->>'source' = 'github-app'
              AND t.metadata->>'workflow_stage' = 'review'
              AND t.result ILIKE '%APPROVED%'
              AND NOT EXISTS (
                  SELECT 1
                  FROM github_automation_decisions d
                  WHERE d.task_id = t.id
                    AND d.action = 'github:merge_pr'
              )
            ORDER BY t.completed_at ASC
            LIMIT $1
            """,
            limit,
        )

    handled = 0
    for row in rows:
        task = await db.db_get_task(str(row['id']))
        if not task or not reviewer_allows_merge(task):
            continue
        await notify_issue_task_completion(task)
        handled += 1
    if handled:
        logger.info('Reconciled %s missed GitHub App terminal review task(s)', handled)
    return handled


def start_github_app_terminal_reconciler() -> None:
    """Start a lightweight reconciliation loop for missed terminal hooks."""
    global _RECONCILER_TASK
    enabled = os.environ.get('GITHUB_APP_TERMINAL_RECONCILER_ENABLED', 'true').lower()
    if enabled in {'0', 'false', 'no'} or _RECONCILER_TASK is not None:
        return

    interval = max(30, int(os.environ.get('GITHUB_APP_TERMINAL_RECONCILER_INTERVAL_SECONDS', '60')))

    async def _loop() -> None:
        await asyncio.sleep(30)
        while True:
            try:
                await reconcile_github_app_terminal_tasks()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning('GitHub App terminal reconciler failed: %s', exc)
            await asyncio.sleep(interval)

    _RECONCILER_TASK = asyncio.create_task(_loop())


async def stop_github_app_terminal_reconciler() -> None:
    """Stop the GitHub App terminal reconciliation loop."""
    global _RECONCILER_TASK
    task = _RECONCILER_TASK
    _RECONCILER_TASK = None
    if not task:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
