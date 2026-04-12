"""Final issue comments for GitHub App build tasks."""

from .issue_pr import open_issue_pr
from .task_context import issue_task_context
from .watch import post_issue_comment


async def notify_issue_final_comment(task: dict) -> None:
    """Post the final issue update after the build task ends."""
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, branch, token = context
    if str(task.get('status')) == 'completed':
        pr = await open_issue_pr(repo, branch, token)
        body = str(task.get('result') or '').strip()
        if pr:
            message = f"## 🛠️ CodeTether Fix\n\nOpened PR #{pr['number']}: {pr['html_url']}"
            if body:
                message += f"\n\n{body}"
            await post_issue_comment(repo, issue_number, token, message)
            return
        fallback = "The build task completed, but I couldn't find the open PR for this branch."
        await post_issue_comment(repo, issue_number, token, f"## 🛠️ CodeTether Fix\n\n{body or fallback}")
        return
    body = str(task.get('error') or task.get('result') or f"Task `{task.get('id')}` ended with status `{task.get('status')}`.").strip()
    await post_issue_comment(repo, issue_number, token, f"## 🛠️ CodeTether Fix\n\n{body}")
