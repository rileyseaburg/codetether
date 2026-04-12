"""Background monitoring for GitHub App issue automation."""

import logging

from .context import MentionContext
from .issue_build_task import create_issue_build_task
from .issue_pr import open_issue_pr, pr_state
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
    """Wait for clone/build completion and then link the created PR back to the issue."""
    try:
        prior_pr = await open_issue_pr(context.repo_full_name, branch, token)
        clone_task = await wait_for_task(clone_task_id, 120, 5)
        if clone_task.get('status') != 'completed':
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the issue workspace. Task `{clone_task_id}` ended with status `{clone_task.get('status')}`.")
            return
        clone_worker_id = clone_task.get('worker_id') or (clone_task.get('metadata') or {}).get('worker_id')
        build_task_id = await create_issue_build_task(context, issue, repo, wid, branch, clone_worker_id)
        logger.info('GitHub App issue build task created: id=%s clone_worker_id=%s', build_task_id, clone_worker_id)
        build_task = await wait_for_task(build_task_id, 240, 5)
        if build_task.get('status') != 'completed':
            body = build_task.get('error') or build_task.get('result') or f"I couldn't apply the requested changes automatically. Task `{build_task_id}` ended with status `{build_task.get('status')}`."
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f'## 🛠️ CodeTether Fix\n\n{body}')
            return
        pr = await open_issue_pr(context.repo_full_name, branch, token)
        if not pr:
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nThe build task completed, but I did not find an open PR for branch `{branch}`.")
            return
        if pr_state(prior_pr) == pr_state(pr):
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nThe build task completed, but the branch `{branch}` did not produce a new PR update.")
            return
        body = build_task.get('result') or f"Opened PR #{pr['number']}: {pr['html_url']}"
        await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nOpened PR #{pr['number']}: {pr['html_url']}\n\n{body.strip()}")
    except Exception as exc:
        logger.exception('GitHub App issue monitor failed for %s#%s', context.repo_full_name, context.issue_number)
        await post_issue_comment(context.repo_full_name, context.issue_number, token, f'## 🛠️ CodeTether Fix\n\nThe follow-up monitor failed before I could open a PR: `{exc}`')
