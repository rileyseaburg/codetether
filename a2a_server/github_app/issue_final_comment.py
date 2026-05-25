"""Final issue comments for GitHub App build tasks."""

import logging
from urllib.parse import quote

from .issue_pr import open_issue_pr
from .task_context import issue_task_context
from .watch import post_issue_comment

logger = logging.getLogger(__name__)


async def _verify_branch_and_commits(
    repo: str, branch: str, token: str,
) -> dict:
    """Verify that the expected branch ref exists and points at a commit.

    Use the Git ref endpoint instead of ``commits?sha=<branch>`` so branch
    names containing slashes are checked as refs and GitHub App installation
    access failures are not conflated with an empty commit list.

    Returns a dict with:
        branch_exists: bool
        has_commits: bool
        head_sha: str
        error: str or None
    """
    from .auth import github_json

    encoded_branch = quote(branch, safe='')
    try:
        ref = await github_json(
            'GET',
            f'/repos/{repo}/git/ref/heads/{encoded_branch}',
            token,
        )
        obj = (ref or {}).get('object') if isinstance(ref, dict) else {}
        head_sha = str((obj or {}).get('sha') or '')
        object_type = str((obj or {}).get('type') or '')
        has_commit = bool(head_sha) and object_type in ('commit', '')
        return {
            'branch_exists': bool(head_sha),
            'has_commits': has_commit,
            'head_sha': head_sha,
            'error': None if has_commit else f'Branch {branch} did not resolve to a commit ref',
        }
    except Exception as exc:
        logger.warning('Branch ref verification failed for %s/%s: %s', repo, branch, exc)
        return {
            'branch_exists': False,
            'has_commits': False,
            'head_sha': '',
            'error': str(exc),
        }


async def normalize_issue_task_terminal_status(task: dict) -> dict:
    """Fail completed issue tasks when branch/PR publication proof is missing.

    Internal worker completion is not the GitHub workflow terminal state. The
    protocol gate is: expected branch ref exists and an open PR points at it.
    """
    if str(task.get('status')) != 'completed':
        return task
    context = await issue_task_context(task)
    if context is None:
        return task
    repo, issue_number, branch, token = context
    branch_info = await _verify_branch_and_commits(repo, branch, token)
    if not branch_info['branch_exists']:
        error = (
            'Branch verification failed after worker completion. '
            f'Expected branch `{branch}` for issue #{issue_number}; '
            f"GET /repos/{repo}/git/ref/heads/{quote(branch, safe='')} failed: "
            f"{branch_info.get('error', 'unknown reason')}. "
            'Recovery: retry or investigate worker commit/push/auth before marking the check successful.'
        )
        return await _mark_task_failed(task, error)
    pr = await open_issue_pr(repo, branch, token)
    if not pr:
        error = (
            'Pull request publication verification failed after worker completion. '
            f'Branch `{branch}` exists at `{branch_info.get("head_sha", "")}`, '
            'but no open PR was found for that head branch. '
            'Recovery: retry PR creation or investigate GitHub App permissions before marking the check successful.'
        )
        return await _mark_task_failed(task, error)
    return task


async def _mark_task_failed(task: dict, error: str) -> dict:
    """Persist a failed terminal state and return the refreshed task when possible."""
    try:
        from .. import database as db

        task_id = str(task.get('id') or '')
        if task_id:
            await db.db_update_task_status(task_id, 'failed', error=error)
            refreshed = await db.db_get_task(task_id)
            if refreshed:
                return refreshed
    except Exception as exc:
        logger.warning('Could not persist GitHub issue task protocol failure for %s: %s', task.get('id'), exc)
    return {**task, 'status': 'failed', 'error': error}


async def notify_issue_final_comment(task: dict) -> None:
    """Post the final issue update after the build task ends."""
    task = await normalize_issue_task_terminal_status(task)
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, branch, token = context

    task_id = task.get('id', 'unknown')
    task_status = str(task.get('status'))

    if task_status == 'completed':
        # ── Verify branch exists and has commits ─────────────────────
        branch_info = await _verify_branch_and_commits(repo, branch, token)

        # ── Check for open PR ────────────────────────────────────────
        pr = await open_issue_pr(repo, branch, token)
        body = str(task.get('result') or '').strip()

        if pr:
            metadata = task.get('metadata') or {}
            review_task_id = None
            review_status = ''
            try:
                from .issue_review_task import create_issue_review_task, provenance_footer, issue_pr_provenance

                review_task_id = await create_issue_review_task(
                    workspace_id=str(metadata.get('workspace_id') or ''),
                    repo=repo,
                    issue_number=issue_number,
                    branch=branch,
                    pr=pr,
                    github_issue_url=metadata.get('github_issue_url'),
                    github_installation_id=metadata.get('github_installation_id'),
                    parent_task_id=str(task_id),
                )
                if review_task_id:
                    review_status = f"\n\nQueued CodeTether reviewer task `{review_task_id}`. If review passes and GitHub feedback is resolved, CodeTether will auto-merge the PR."
                else:
                    review_status = "\n\nCodeTether review automation was not queued because the local provenance/policy gate denied it."
                provenance = issue_pr_provenance(
                    repo=repo,
                    issue_number=issue_number,
                    branch=branch,
                    pr=pr,
                    installation_id=metadata.get('github_installation_id'),
                    action='github:review_pr',
                    parent_task_id=str(task_id),
                )
                review_status += provenance_footer(provenance, action='github:review_pr')
            except Exception as exc:
                logger.exception('Failed to enqueue issue PR review for task %s: %s', task_id, exc)
                review_status = f"\n\n⚠️ CodeTether could not queue the reviewer task: `{exc}`"

            message = f"## 🛠️ CodeTether Fix\n\nOpened PR #{pr['number']}: {pr['html_url']}"
            if body:
                message += f"\n\n{body}"
            message += review_status
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
