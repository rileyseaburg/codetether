"""Final issue comments for GitHub App build tasks."""

import logging

from .issue_pr import open_issue_pr
from .task_context import issue_task_context
from .watch import post_issue_comment

logger = logging.getLogger(__name__)


async def _verify_branch_and_commits(
    repo: str, branch: str, token: str,
) -> dict:
    """
    Verify that the expected branch exists and has commits.

    Returns a dict with:
        branch_exists: bool
        commit_count: int or None
        error: str or None
    """
    from .auth import github_json

    try:
        ref = await github_json(
            'GET',
            f'/repos/{repo}/commits?sha={branch}&per_page=1',
            token,
        )
        if ref and isinstance(ref, list):
            return {
                'branch_exists': True,
                'commit_count': len(ref),
                'error': None,
            }
        return {
            'branch_exists': False,
            'commit_count': 0,
            'error': f'Branch {branch} not found or has no commits',
        }
    except Exception as exc:
        logger.warning('Branch verification failed for %s/%s: %s', repo, branch, exc)
        return {
            'branch_exists': False,
            'commit_count': 0,
            'error': str(exc),
        }


async def notify_issue_final_comment(task: dict) -> None:
    """Post the final issue update after the build task ends."""
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, branch, token = context

    task_id = task.get('id', 'unknown')
    task_status = str(task.get('status'))

    if task_status == 'completed':
        # ── Verify branch exists and has commits ─────────────────────
        branch_info = await _verify_branch_and_commits(repo, branch, token)

        if not branch_info['branch_exists']:
            body = str(task.get('result') or '').strip()
            failure_detail = branch_info.get('error', 'unknown reason')
            message = (
                f"## 🛠️ CodeTether Fix\n\n"
                f"⚠️ **Task completed but branch verification failed.**\n\n"
                f"- Task `{task_id}` status: `{task_status}`\n"
                f"- Expected branch: `{branch}`\n"
                f"- Verification error: {failure_detail}\n"
            )
            if body:
                message += f"\n**Task output:**\n> {body[:800]}"
            message += (
                f"\n\nThis usually means the agent finished but did not push "
                f"commits to the expected branch. The task may need to be re-run."
            )
            await post_issue_comment(repo, issue_number, token, message)
            logger.error(
                'Task %s completed but branch %s missing in %s',
                task_id, branch, repo,
            )
            return

        # ── Check for open PR ────────────────────────────────────────
        pr = await open_issue_pr(repo, branch, token)
        body = str(task.get('result') or '').strip()

        if pr:
            message = f"## 🛠️ CodeTether Fix\n\nOpened PR #{pr['number']}: {pr['html_url']}"
            if body:
                message += f"\n\n{body}"
            await post_issue_comment(repo, issue_number, token, message)
            return

        # Task completed, branch has commits, but no PR was opened
        no_pr_message = (
            f"The build task completed and branch `{branch}` has commits, "
            f"but no pull request was opened. This may indicate the agent "
            f"finished without creating a PR. Check the branch manually: "
            f"https://github.com/{repo}/tree/{branch}"
        )
        await post_issue_comment(
            repo, issue_number, token,
            f"## 🛠️ CodeTether Fix\n\n{body or no_pr_message}",
        )
        logger.warning(
            'Task %s completed with branch %s but no PR opened in %s',
            task_id, branch, repo,
        )
        return

    # ── Non-completed status (failed, cancelled, etc.) ───────────────
    body = str(
        task.get('error') or task.get('result')
        or f"Task `{task_id}` ended with status `{task_status}`."
    ).strip()

    await post_issue_comment(
        repo, issue_number, token,
        f"## 🛠️ CodeTether Fix\n\n{body}",
    )
