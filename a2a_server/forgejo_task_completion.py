"""Terminal orchestration for native Forgejo automation workflows."""

from __future__ import annotations

from contextlib import suppress
from urllib.parse import quote

from a2a_server.forgejo_agent_client import (
    publish_session_events,
    update_task,
)
from a2a_server.forgejo_automation import (
    _mark_review_reconciled,
    create_forgejo_fix_followup,
    create_forgejo_review_task,
    publish_forgejo_review,
    reviewer_verdict,
)
from a2a_server.forgejo_progress_events import forget
from a2a_server.forgejo_webhooks import forgejo_json
from a2a_server.session_view import _task_messages, build_task_session_url
from a2a_server.temporal import client as temporal_client
from a2a_server.temporal.models import ForgejoTaskTerminalSignal


def _task_footer(task_id: str, metadata: dict | None = None) -> str:
    footer = f'\n\nTask: `{task_id}`'
    native_url = str((metadata or {}).get('forgejo_agent_task_url') or '')
    session_url = native_url or build_task_session_url(task_id)
    if session_url:
        footer += f' · [View session]({session_url})'
    return footer


async def sync_forgejo_agent_task(
    task: dict, *, workflow_terminal: bool = True
) -> None:
    """Publish lifecycle and complete transcript to Forgejo.

    Temporal owns native lifecycle status. A late stage completion must not
    reopen a native task that its workflow already cancelled or finalized.
    """
    metadata = task.get('metadata') or {}
    forgejo_task_id = int(metadata.get('forgejo_agent_task_id') or 0)
    repo = str(metadata.get('repo') or '')
    if not forgejo_task_id or not repo:
        return

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
    with suppress(Exception):
        forget(str(task.get('id') or ''))
    session_id, messages = await _task_messages(task, 10_000)
    lifecycle = {
        'external_task_id': str(task.get('id') or ''),
        'external_session_id': session_id,
        'head_sha': str(metadata.get('pr_head_sha') or ''),
        'branch': str(metadata.get('branch_name') or ''),
    }
    if workflow_terminal:
        lifecycle.update(
            status=forgejo_status,
            result=str(task.get('result') or ''),
            error=str(task.get('error') or ''),
        )
    await update_task(
        repo=repo,
        task_id=forgejo_task_id,
        base_url=str(metadata.get('forgejo_api_url') or ''),
        **lifecycle,
    )
    await publish_session_events(
        repo=repo,
        forgejo_task_id=forgejo_task_id,
        codetether_task_id=str(task.get('id') or ''),
        messages=messages,
        base_url=str(metadata.get('forgejo_api_url') or ''),
    )


async def _notify_temporal_completion(
    task: dict, metadata: dict, stage: str
) -> None:
    """Signal one terminal stage projection into its durable workflow."""
    if stage not in {'prepare', 'code', 'fix', 'review', 'remediate'}:
        return
    await sync_forgejo_agent_task(task, workflow_terminal=False)
    await temporal_client.signal_task_terminal(
        int(metadata.get('forgejo_agent_task_id') or 0),
        ForgejoTaskTerminalSignal(
            task_id=str(task.get('id') or ''),
            stage=stage,
            status=str(task.get('status') or 'failed'),
            session_id=str(
                task.get('session_id') or metadata.get('session_id') or ''
            ),
            # The dataclass field is `str`; Temporal's converter rejects None
            # and drops the whole signal, which strands the workflow after a
            # review whose result has no parseable verdict.
            verdict=(
                (reviewer_verdict(task) or '') if stage == 'review' else ''
            ),
            head_sha=str(metadata.get('pr_head_sha') or ''),
            pull_request_number=int(metadata.get('pr_number') or 0),
        ),
    )


async def _legacy_followup(
    task: dict, stage: str, status: str, task_id: str
) -> tuple[dict | None, str | None]:
    """Run the legacy review/fix handoff for a terminal stage."""
    review_evidence: dict | None = None
    followup_task_id: str | None = None
    if stage == 'code' and status == 'completed':
        followup_task_id = await create_forgejo_review_task(task)
    elif stage == 'review' and status == 'completed':
        review_evidence = await publish_forgejo_review(task)
        followup_task_id = await create_forgejo_fix_followup(task)
        await _mark_review_reconciled(task_id)
    return review_evidence, followup_task_id


def _legacy_terminal_message(
    stage: str,
    status: str,
    review_evidence: dict | None,
    followup_task_id: str | None,
) -> str:
    """Render the terminal comment for a non-Temporal legacy stage."""
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
        return message
    if status == 'completed':
        message = (
            '## 🛠️ CodeTether task\n\n'
            'The worker reported completion. This alone does not prove '
            'that changes were pushed or that CI succeeded.'
        )
        if followup_task_id:
            message += f'\n\nQueued review task `{followup_task_id}`.'
        return message
    return (
        f'## ⚠️ CodeTether {stage.title()}\n\nTask ended with status `{status}`.'
    )


async def notify_forgejo_task_completion(task: dict) -> None:
    """Advance one Forgejo workflow stage and post one terminal comment."""
    metadata = task.get('metadata') or {}
    if metadata.get('source') != 'forgejo-webhook':
        return

    stage = str(metadata.get('workflow_stage') or '')
    if metadata.get('temporal_orchestrated'):
        await _notify_temporal_completion(task, metadata, stage)
        return

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
    review_evidence, followup_task_id = await _legacy_followup(
        task, stage, status, task_id
    )

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

    message = _legacy_terminal_message(
        stage, status, review_evidence, followup_task_id
    )
    # Full narration belongs in the linked run, not in the PR conversation.
    message += _task_footer(task_id, metadata)
    message += f'\n\n{marker}'
    await forgejo_json('POST', base, issue_path, {'body': message})
