"""Background monitoring for GitHub App-driven PR fix tasks."""

import asyncio
import logging
from typing import Any

from .auth import github_json
from .build_task import create_build_task
from .context import MentionContext
from .workspace import ensure_workspace

logger = logging.getLogger(__name__)


async def wait_for_task(task_id: str, attempts: int, delay_seconds: int) -> dict[str, Any]:
    """Poll the task row until it reaches a terminal status."""
    from .. import database as db

    for _ in range(attempts):
        task = await db.db_get_task(task_id)
        if task and task.get('status') in {'completed', 'failed', 'cancelled', 'rejected'}:
            return task
        await asyncio.sleep(delay_seconds)
    return {'id': task_id, 'status': 'timeout', 'error': 'Timed out waiting for task completion'}


async def post_issue_comment(repo_full_name: str, issue_number: int, token: str, body: str) -> None:
    """Post a status update back onto the PR issue timeline."""
    await github_json('POST', f'/repos/{repo_full_name}/issues/{issue_number}/comments', token, {'body': body[:65000]})


async def monitor_pr_fix(context: MentionContext, pr: dict[str, Any], clone_task_id: str, head_sha_before: str, token: str) -> None:
    """Run the clone→build→comment loop after a webhook request returns."""
    try:
        wid = await ensure_workspace(context, pr)
        clone_task = await wait_for_task(clone_task_id, 120, 5)
        logger.info('GitHub App clone task finished: id=%s status=%s', clone_task_id, clone_task.get('status'))
        if clone_task.get('status') != 'completed':
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the repository workspace. Task `{clone_task_id}` ended with status `{clone_task.get('status')}`.")
            return
        clone_worker_id = clone_task.get('worker_id') or (clone_task.get('metadata') or {}).get('worker_id')
        build_task_id = await create_build_task(context, pr, wid, clone_worker_id)
        logger.info('GitHub App build task created: id=%s clone_worker_id=%s', build_task_id, clone_worker_id)
        build_task = await wait_for_task(build_task_id, 240, 5)
        if build_task.get('status') != 'completed':
            body = build_task.get('error') or build_task.get('result') or f"I couldn't apply the requested changes automatically. Task `{build_task_id}` ended with status `{build_task.get('status')}`."
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f'## 🛠️ CodeTether Fix\n\n{body}')
            return
        updated_pr = await github_json('GET', f"/repos/{context.repo_full_name}/pulls/{context.pr_number}", token)
        if updated_pr['head']['sha'] == head_sha_before:
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nThe build task completed, but the PR head did not change. I did not confirm a pushed fix on `{pr['head']['ref']}`.")
            return
        await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\n{(build_task.get('result') or 'Applied the requested changes.').strip()}")
    except Exception as exc:
        logger.exception('GitHub App PR-fix monitor failed for %s#%s', context.repo_full_name, context.pr_number)
        await post_issue_comment(context.repo_full_name, context.issue_number, token, f'## 🛠️ CodeTether Fix\n\nThe follow-up monitor failed before I could apply the requested changes: `{exc}`')
