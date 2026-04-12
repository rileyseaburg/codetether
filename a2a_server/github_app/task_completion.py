"""Task-status routing for GitHub App issue workflows."""

from .issue_final_comment import notify_issue_final_comment
from .issue_prepare_completion import handle_issue_prepare_completion


async def notify_issue_task_completion(task: dict) -> None:
    """Advance or finish a GitHub App issue workflow."""
    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'github-app' or metadata.get('pr_number'):
        return
    title = str(task.get('title') or '')
    if title.startswith('Prepare issue workspace #'):
        await handle_issue_prepare_completion(task)
    elif title.startswith('Work issue #'):
        await notify_issue_final_comment(task)
