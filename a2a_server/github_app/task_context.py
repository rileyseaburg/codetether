"""Shared GitHub App task context lookup."""

from .auth import installation_token


async def issue_task_context(task: dict) -> tuple[str, int, str, str] | None:
    """Resolve repo, issue, branch, and installation token for an issue task."""
    from .. import database as db

    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'github-app' or metadata.get('pr_number'):
        return None
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    workspace = await db.db_get_workspace(workspace_id)
    github_app = (((workspace or {}).get('agent_config') or {}).get('git_auth') or {}).get('github_app') or {}
    installation_id = github_app.get('installation_id')
    if not installation_id:
        return None
    token, _ = await installation_token(int(str(installation_id)))
    return (
        str(metadata.get('repo') or '').strip(),
        int(metadata['issue_number']),
        str(metadata.get('branch_name') or '').strip(),
        token,
    )
