"""Shared GitHub App task context lookup."""

from .auth import installation_token


async def github_app_task_context(task: dict) -> tuple[str, int, str, str] | None:
    """Resolve repo, issue/PR number, branch, and installation token."""
    from .. import database as db

    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'github-app':
        return None
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    workspace = await db.db_get_workspace(workspace_id)
    agent_config = (workspace or {}).get('agent_config') or {}
    github_app = (
        ((agent_config.get('git_auth') or {}).get('github_app'))
        or (((workspace or {}).get('git_auth') or {}).get('github_app'))
        or {}
    )
    installation_id = github_app.get('installation_id')
    if not installation_id:
        return None
    token, _ = await installation_token(int(str(installation_id)))
    issue_number = metadata.get('issue_number') or metadata.get('pr_number')
    branch = metadata.get('branch_name') or metadata.get('pr_head') or metadata.get('git_branch')
    if not issue_number or not branch:
        return None
    return (
        str(metadata.get('repo') or '').strip(),
        int(issue_number),
        str(branch).strip(),
        token,
    )


async def issue_task_context(task: dict) -> tuple[str, int, str, str] | None:
    """Resolve repo, issue, branch, and installation token for an issue task."""
    metadata = task.get('metadata') or {}
    if metadata.get('pr_number'):
        return None
    return await github_app_task_context(task)
