"""Final PR comments for GitHub App branch edit tasks."""

from .task_context import github_app_task_context
from .watch import post_issue_comment


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
        await post_issue_comment(repo, pr_number, token, message)
        return
    await post_issue_comment(repo, pr_number, token, f"## 🛠️ CodeTether Fix\n\n{body}")
