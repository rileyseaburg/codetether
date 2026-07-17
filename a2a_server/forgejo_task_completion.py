"""Terminal orchestration for native Forgejo automation workflows."""

from __future__ import annotations

from urllib.parse import quote

from a2a_server.forgejo_automation import (
    _mark_review_reconciled,
    create_forgejo_fix_followup,
    create_forgejo_review_task,
    publish_forgejo_review,
)
from a2a_server.forgejo_webhooks import forgejo_json


async def notify_forgejo_task_completion(task: dict) -> None:
    """Advance one Forgejo workflow stage and post one terminal comment."""
    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'forgejo-webhook':
        return

    stage = str(metadata.get('workflow_stage') or '')
    if stage not in {'code', 'fix', 'review'}:
        return

    repo = str(metadata.get('repo') or '')
    number = int(metadata.get('issue_number') or metadata.get('pr_number') or 0)
    base = str(metadata.get('forgejo_api_url') or '').rstrip('/')
    task_id = str(task.get('id') or '')
    if not repo or not number or not base or not task_id:
        return

    status = str(task.get('status') or 'unknown')
    review_evidence: dict | None = None
    followup_task_id: str | None = None
    if stage == 'code' and status == 'completed':
        followup_task_id = await create_forgejo_review_task(task)
    elif stage == 'review' and status == 'completed':
        review_evidence = await publish_forgejo_review(task)
        followup_task_id = await create_forgejo_fix_followup(task)
        await _mark_review_reconciled(task_id)

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

    detail = str(task.get('result') or task.get('error') or '').strip()
    if stage == 'review' and status == 'completed':
        event = str((review_evidence or {}).get('event') or 'COMMENT')
        review_id = (review_evidence or {}).get('review_id')
        message = (
            '## 🔎 CodeTether Review\n\n'
            f'Published Forgejo review event `{event}`.'
        )
        if review_id is not None:
            message += f' Review: `{review_id}`.'
        if followup_task_id:
            message += f'\n\nQueued fix follow-up task `{followup_task_id}`.'
    elif status == 'completed':
        message = (
            '## 🛠️ CodeTether Fix\n\nCompleted and pushed the requested changes.'
        )
        if followup_task_id:
            message += f'\n\nQueued review task `{followup_task_id}`.'
    else:
        message = f'## ⚠️ CodeTether {stage.title()}\n\nTask ended with status `{status}`.'
    if detail:
        message += f'\n\n{detail}'
    message += f'\n\nTask: `{task_id}`\n\n{marker}'
    await forgejo_json('POST', base, issue_path, {'body': message})
