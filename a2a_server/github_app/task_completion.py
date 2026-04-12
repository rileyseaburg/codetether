"""Final task notifications for GitHub App issue automation."""

from .auth import installation_token
from .issue_pr import open_issue_pr
from .watch import post_issue_comment


async def notify_issue_task_completion(task: dict) -> None:
    """Post the final issue update when a GitHub App issue task finishes."""
    from .. import database as db

    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'github-app' or metadata.get('pr_number'):
        return
    if not str(task.get('title') or '').startswith('Work issue #'):
        return
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    workspace = await db.db_get_workspace(workspace_id)
    github_app = (((workspace or {}).get('agent_config') or {}).get('git_auth') or {}).get('github_app') or {}
    installation_id = github_app.get('installation_id')
    if not installation_id:
        return
    token, _ = await installation_token(int(str(installation_id)))
    repo = str(metadata.get('repo') or '').strip()
    issue_number = int(metadata['issue_number'])
    branch = str(metadata.get('branch_name') or '').strip()
    if str(task.get('status')) == 'completed':
        pr = await open_issue_pr(repo, branch, token)
        if pr:
            body = str(task.get('result') or '').strip()
            message = f"## 🛠️ CodeTether Fix\n\nOpened PR #{pr['number']}: {pr['html_url']}"
            if body:
                message += f"\n\n{body}"
            await post_issue_comment(repo, issue_number, token, message)
            return
    body = str(task.get('error') or task.get('result') or f"Task `{task.get('id')}` ended with status `{task.get('status')}`.").strip()
    await post_issue_comment(repo, issue_number, token, f'## 🛠️ CodeTether Fix\n\n{body}')
