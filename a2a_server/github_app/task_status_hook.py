"""Shared terminal-task hook for GitHub App workflows."""


async def handle_github_app_terminal_task(task_id: str) -> None:
    """Load a terminal task and run any GitHub App follow-up logic."""
    from .. import database as db
    from .task_completion import notify_issue_task_completion

    task = await db.db_get_task(task_id)
    metadata = (task or {}).get('metadata') or {}
    if metadata.get('source') == 'github-app':
        await notify_issue_task_completion(task)
