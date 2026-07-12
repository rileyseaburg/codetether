"""Terminal task comments for Forgejo webhook workflows."""

from __future__ import annotations

from urllib.parse import quote

from a2a_server.forgejo_webhooks import forgejo_json


async def notify_forgejo_task_completion(task: dict) -> None:
    """Post one final Forgejo issue/PR comment for a terminal build task."""
    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'forgejo-webhook':
        return
    if metadata.get('workflow_stage') != 'code':
        return

    repo = str(metadata.get('repo') or '')
    number = int(metadata.get('issue_number') or metadata.get('pr_number') or 0)
    base = str(metadata.get('forgejo_api_url') or '').rstrip('/')
    task_id = str(task.get('id') or '')
    if not repo or not number or not base or not task_id:
        return

    owner, name = repo.split('/', 1)
    issue_path = (
        f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
        f'/issues/{number}/comments'
    )
    marker = f'<!-- codetether-forgejo-terminal:{task_id} -->'
    comments = await forgejo_json('GET', base, issue_path)
    if isinstance(comments, list) and any(
        marker in str((comment or {}).get('body') or '') for comment in comments
    ):
        return

    status = str(task.get('status') or 'unknown')
    detail = str(task.get('result') or task.get('error') or '').strip()
    if status == 'completed':
        message = (
            '## 🛠️ CodeTether Fix\n\n'
            'Completed and pushed the requested changes.'
        )
    else:
        message = f'## ⚠️ CodeTether Fix\n\nTask ended with status `{status}`.'
    if detail:
        message += f'\n\n{detail}'
    message += f'\n\nTask: `{task_id}`\n\n{marker}'
    await forgejo_json('POST', base, issue_path, {'body': message})
