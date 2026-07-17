"""Final issue comments for GitHub App build tasks."""

import logging
import os

from urllib.parse import quote

from a2a_server import database as db
from a2a_server.github_app import auth as github_app_auth
from a2a_server.github_app import issue_review_task
from a2a_server.github_app.issue_pr import open_issue_pr
from a2a_server.github_app.issue_review_task import (
    issue_pr_provenance,
    provenance_footer,
)
from a2a_server.github_app.task_context import issue_task_context
from a2a_server.github_app.watch import post_issue_comment


logger = logging.getLogger(__name__)


def _github_repo_migrated_to_forgejo(repo: str) -> bool:
    """Return true when GitHub issue finalization should be skipped.

    Some repos are now worked in Forgejo while legacy/open issues still exist on
    GitHub. In that mode the harvester pushes branches to Forgejo, so verifying
    the branch/PR against GitHub produces false 404 failures and noisy GitHub
    email comments. The Forgejo/Rudder path owns issue publication for these
    repositories.
    """
    configured = os.environ.get(
        'CODETETHER_FORGEJO_MIGRATED_REPOS',
        'rileyseaburg/spotlessbinco,spotlessbinco/spotlessbinco',
    )
    migrated = {
        item.strip().lower() for item in configured.split(',') if item.strip()
    }
    return str(repo or '').strip().lower() in migrated


async def _verify_branch_and_commits(
    repo: str,
    branch: str,
    token: str,
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
    encoded_branch = quote(branch, safe='')
    try:
        ref = await github_app_auth.github_json(
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
            'error': None
            if has_commit
            else f'Branch {branch} did not resolve to a commit ref',
        }
    except Exception as exc:
        logger.warning(
            'Branch ref verification failed for %s/%s: %s',
            repo,
            branch,
            exc,
        )
        return {
            'branch_exists': False,
            'has_commits': False,
            'head_sha': '',
            'error': str(exc),
        }


async def normalize_issue_task_terminal_status(task: dict) -> dict:
    """Fail completed issue tasks when branch/PR proof is missing."""
    if str(task.get('status')) != 'completed':
        return task
    context = await issue_task_context(task)
    if context is None:
        return task
    repo, issue_number, branch, token = context
    if _github_repo_migrated_to_forgejo(repo):
        logger.info(
            'Skipping GitHub branch/PR finalization for Forgejo-migrated '
            'repo %s issue #%s branch %s',
            repo,
            issue_number,
            branch,
        )
        return task
    branch_info = await _verify_branch_and_commits(repo, branch, token)
    if not branch_info['branch_exists']:
        error = (
            'Branch verification failed after worker completion. '
            f'Expected branch `{branch}` for issue #{issue_number}; '
            f'GET /repos/{repo}/git/ref/heads/{quote(branch, safe="")} '
            f'failed: {branch_info.get("error", "unknown reason")}. '
            'Recovery: retry or investigate worker commit/push/auth before '
            'marking the check successful.'
        )
        return await _mark_task_failed(task, error)
    pr = await open_issue_pr(repo, branch, token)
    if not pr:
        error = (
            'Pull request publication verification failed after worker '
            'completion. '
            f'Branch `{branch}` exists at `{branch_info.get("head_sha", "")}`, '
            'but no open PR was found for that head branch. '
            'Recovery: retry PR creation or investigate GitHub App permissions '
            'before marking the check successful.'
        )
        return await _mark_task_failed(task, error)
    return task


async def _mark_task_failed(task: dict, error: str) -> dict:
    """Persist a failed terminal state and return the refreshed task."""
    try:
        task_id = str(task.get('id') or '')
        if task_id:
            await db.db_update_task_status(task_id, 'failed', error=error)
            refreshed = await db.db_get_task(task_id)
            if refreshed:
                return refreshed
    except Exception as exc:
        logger.warning(
            'Could not persist GitHub issue task protocol failure for %s: %s',
            task.get('id'),
            exc,
        )
    return {**task, 'status': 'failed', 'error': error}


async def notify_issue_final_comment(task: dict) -> None:
    """Post the final issue update after the build task ends."""
    task = await normalize_issue_task_terminal_status(task)
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, branch, token = context
    if _github_repo_migrated_to_forgejo(repo):
        logger.info(
            'Skipping GitHub final comment for Forgejo-migrated repo %s '
            'issue #%s branch %s',
            repo,
            issue_number,
            branch,
        )
        return

    task_id = task.get('id', 'unknown')
    task_status = str(task.get('status'))

    if task_status == 'completed':
        # ── Verify branch exists and has commits ─────────────────────
        await _verify_branch_and_commits(repo, branch, token)

        # ── Check for open PR ────────────────────────────────────────
        pr = await open_issue_pr(repo, branch, token)
        body = str(task.get('result') or '').strip()

        if pr:
            metadata = task.get('metadata') or {}
            review_task_id = None
            review_status = ''
            try:
                review_task_id = (
                    await issue_review_task.create_issue_review_task(
                        workspace_id=str(metadata.get('workspace_id') or ''),
                        repo=repo,
                        issue_number=issue_number,
                        branch=branch,
                        pr=pr,
                        github_issue_url=metadata.get('github_issue_url'),
                        github_installation_id=metadata.get(
                            'github_installation_id',
                        ),
                        token=token,
                        parent_task_id=str(task_id),
                        trigger_actor_login=str(
                            metadata.get('trigger_actor_login') or ''
                        ),
                    )
                )
                if review_task_id:
                    review_status = (
                        '\n\nQueued CodeTether reviewer task '
                        f'`{review_task_id}`. If review passes and GitHub '
                        'feedback is resolved, CodeTether will auto-merge '
                        'the PR.'
                    )
                else:
                    review_status = (
                        '\n\nCodeTether review automation was not queued '
                        'because the local provenance/policy gate denied it.'
                    )
                provenance = issue_pr_provenance(
                    repo=repo,
                    issue_number=issue_number,
                    branch=branch,
                    pr=pr,
                    installation_id=metadata.get('github_installation_id'),
                    action='github:review_pr',
                    parent_task_id=str(task_id),
                )
                review_status += provenance_footer(
                    provenance,
                    action='github:review_pr',
                )
            except Exception as exc:
                logger.exception(
                    'Failed to enqueue issue PR review for task %s: %s',
                    task_id,
                    exc,
                )
                review_status = (
                    '\n\n⚠️ CodeTether could not queue the reviewer task: '
                    f'`{exc}`'
                )

            message = (
                '## 🛠️ CodeTether Fix\n\n'
                f'Opened PR #{pr["number"]}: {pr["html_url"]}'
            )
            if body:
                message += f'\n\n{body}'
            message += review_status
            await post_issue_comment(repo, issue_number, token, message)
            return

        # Task completed, branch has commits, but no PR was opened.
        no_pr_message = (
            f'The build task completed and branch `{branch}` has commits, '
            'but no pull request was opened. This may indicate the agent '
            'finished without creating a PR. Check the branch manually: '
            f'https://github.com/{repo}/tree/{branch}'
        )
        await post_issue_comment(
            repo,
            issue_number,
            token,
            f'## 🛠️ CodeTether Fix\n\n{body or no_pr_message}',
        )
        logger.warning(
            'Task %s completed with branch %s but no PR opened in %s',
            task_id,
            branch,
            repo,
        )
        return

    # ── Non-completed status (failed, cancelled, etc.) ───────────────
    body = str(
        task.get('error')
        or task.get('result')
        or f'Task `{task_id}` ended with status `{task_status}`.'
    ).strip()

    await post_issue_comment(
        repo,
        issue_number,
        token,
        f'## 🛠️ CodeTether Fix\n\n{body}',
    )
