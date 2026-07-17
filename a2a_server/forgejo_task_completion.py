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
from a2a_server.session_view import build_task_session_url


def _task_footer(task_id: str, metadata: dict | None = None) -> str:
    footer = f'\n\nTask: `{task_id}`'
    native_url = str((metadata or {}).get('forgejo_agent_task_url') or '')
    session_url = native_url or build_task_session_url(task_id)
    if session_url:
        footer += f' · [View session]({session_url})'
    return footer


async def sync_forgejo_agent_task(task: dict) -> None:
    """Publish terminal lifecycle and complete transcript to Forgejo."""
    metadata = task.get('metadata') or {}
    forgejo_task_id = int(metadata.get('forgejo_agent_task_id') or 0)
    repo = str(metadata.get('repo') or '')
    if not forgejo_task_id or not repo:
        return

    from a2a_server.forgejo_agent_client import (
        publish_session_events,
        update_task,
    )
    from a2a_server.session_view import _task_messages

    status = str(task.get('status') or 'failed').lower()
    forgejo_status = {
        'queued': 'pending',
        'in_progress': 'running',
    }.get(status, status)
    if forgejo_status not in {
        'pending',
        'accepted',
        'running',
        'completed',
        'failed',
        'cancelled',
    }:
        forgejo_status = 'failed'
    session_id, messages = await _task_messages(task, 10_000)
    await update_task(
        repo=repo,
        task_id=forgejo_task_id,
        base_url=str(metadata.get('forgejo_api_url') or ''),
        status=forgejo_status,
        external_task_id=str(task.get('id') or ''),
        external_session_id=session_id,
        head_sha=str(metadata.get('pr_head_sha') or ''),
        branch=str(metadata.get('branch_name') or ''),
        result=str(task.get('result') or ''),
        error=str(task.get('error') or ''),
    )
    await publish_session_events(
        repo=repo,
        forgejo_task_id=forgejo_task_id,
        codetether_task_id=str(task.get('id') or ''),
        messages=messages,
        base_url=str(metadata.get('forgejo_api_url') or ''),
    )


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

    await sync_forgejo_agent_task(task)

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
    message += _task_footer(task_id, metadata)
    message += f'\n\n{marker}'
    await forgejo_json('POST', base, issue_path, {'body': message})
