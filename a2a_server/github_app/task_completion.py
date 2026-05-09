"""Task-status routing for GitHub App issue workflows."""

from .issue_final_comment import notify_issue_final_comment
from .issue_prepare_completion import handle_issue_prepare_completion
from .pr_final_comment import notify_pr_final_comment
from .pr_prepare_completion import handle_pr_prepare_completion


async def notify_issue_task_completion(task: dict, worker_id: str | None = None) -> None:
    """Advance or finish a GitHub App issue workflow."""
    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'github-app':
        return
    title = str(task.get('title') or '')
    stage = metadata.get('workflow_stage')
    if stage == 'review' or title.startswith('Review issue PR #'):
        from .issue_review_task import create_issue_merge_task
        from .task_context import github_app_task_context

        if str(task.get('status')) != 'completed':
            return
        context = await github_app_task_context(task)
        if context is None:
            return
        _, _, _, token = context
        await create_issue_merge_task(review_task=task, token=token)
        return
    if metadata.get('pr_number'):
        if title.startswith('Prepare PR workspace #'):
            await handle_pr_prepare_completion(task, worker_id)
        elif title.startswith('Apply PR fix #'):
            await notify_pr_final_comment(task)
        return
    if title.startswith('Prepare issue workspace #'):
        await handle_issue_prepare_completion(task, worker_id)
    elif title.startswith('Work issue #'):
        await notify_issue_final_comment(task)
