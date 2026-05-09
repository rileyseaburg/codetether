"""Final PR comments for GitHub App branch edit tasks."""

import logging

from .task_context import github_app_task_context
from .watch import post_issue_comment

logger = logging.getLogger(__name__)


async def notify_pr_final_comment(task: dict) -> None:
    """Post the final PR update after the branch edit task ends."""
    context = await github_app_task_context(task)
    if context is None:
        return
    repo, pr_number, _, token = context
    body = str(
        task.get('result')
        or task.get('error')
        or f"Task `{task.get('id')}` ended with status `{task.get('status')}`."
    ).strip()
    if str(task.get('status')) == 'completed':
        message = "## 🛠️ CodeTether Fix\n\nPushed changes to this PR branch."
        if body:
            message += f"\n\n{body}"
        metadata = task.get('metadata') or {}
        try:
            from .auth import github_json
            from .issue_review_task import create_issue_review_task, issue_pr_provenance, provenance_footer

            pr = await github_json('GET', f'/repos/{repo}/pulls/{pr_number}', token)
            review_task_id = await create_issue_review_task(
                workspace_id=str(metadata.get('workspace_id') or ''),
                repo=repo,
                issue_number=int(metadata.get('issue_number') or pr_number),
                branch=str((pr.get('head') or {}).get('ref') or metadata.get('pr_head') or branch),
                pr=pr,
                github_issue_url=metadata.get('github_issue_url') or f'https://github.com/{repo}/pull/{pr_number}',
                github_installation_id=metadata.get('github_installation_id'),
                parent_task_id=str(task.get('id') or ''),
            )
            if review_task_id:
                message += f"\n\nQueued CodeTether reviewer task `{review_task_id}`. If review passes and GitHub feedback is resolved, CodeTether will auto-merge the PR."
            else:
                message += "\n\nCodeTether review automation was not queued because the local provenance/policy gate denied it."
            provenance = issue_pr_provenance(
                repo=repo,
                issue_number=int(metadata.get('issue_number') or pr_number),
                branch=str((pr.get('head') or {}).get('ref') or metadata.get('pr_head') or branch),
                pr=pr,
                installation_id=metadata.get('github_installation_id'),
                action='github:review_pr',
                parent_task_id=str(task.get('id') or ''),
            )
            message += provenance_footer(provenance, action='github:review_pr')
        except Exception as exc:
            logger.exception('Failed to enqueue PR review for task %s: %s', task.get('id'), exc)
            message += f"\n\n⚠️ CodeTether could not queue the reviewer task: `{exc}`"
        await post_issue_comment(repo, pr_number, token, message)
        return
    await post_issue_comment(repo, pr_number, token, f"## 🛠️ CodeTether Fix\n\n{body}")
