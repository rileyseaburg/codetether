"""Background monitoring for GitHub App issue automation."""

import logging

from .context import MentionContext
from .issue_build_task import create_issue_build_task
from .watch import post_issue_comment, wait_for_task

logger = logging.getLogger(__name__)


async def monitor_issue_fix(
    context: MentionContext,
    issue: dict,
    repo: dict,
    wid: str,
    clone_task_id: str,
    branch: str,
    token: str,
) -> None:
    """Wait for clone completion and enqueue the issue build task."""
    try:
        clone_task = await wait_for_task(clone_task_id, 120, 5)
        if clone_task.get('status') != 'completed':
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the issue workspace. Task `{clone_task_id}` ended with status `{clone_task.get('status')}`.")
            return
        clone_worker_id = clone_task.get('worker_id') or (clone_task.get('metadata') or {}).get('worker_id')
        build_task_id = await create_issue_build_task(context, issue, repo, wid, branch, clone_worker_id)
        logger.info('GitHub App issue build task created: id=%s clone_worker_id=%s', build_task_id, clone_worker_id)
    except Exception as exc:
        logger.exception('GitHub App issue monitor failed for %s#%s', context.repo_full_name, context.issue_number)
        await post_issue_comment(context.repo_full_name, context.issue_number, token, f'## 🛠️ CodeTether Fix\n\nThe follow-up monitor failed before I could open a PR: `{exc}`')
