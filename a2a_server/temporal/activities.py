"""Temporal activities for Forgejo agent orchestration.

Activity inputs and results deliberately exclude prompts, transcripts, tool
payloads, credentials, and repository clone URLs. Those values are loaded and
used inside activity execution only, so they are not persisted in workflow
history.
"""

from __future__ import annotations

import logging
import os

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable
from urllib.parse import quote

from temporalio import activity
from temporalio.exceptions import ApplicationError

from a2a_server.github_app.settings import MODEL_REF

from .models import ForgejoStageRequest, ForgejoStageResult


logger = logging.getLogger(__name__)


def safe_activity(error_type: str) -> Callable:
    """Prevent upstream exception text from entering Temporal history."""

    def decorate(function: Callable) -> Callable:
        @wraps(function)
        async def wrapped(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except ApplicationError:
                raise
            except Exception:
                raise ApplicationError(
                    error_type,
                    type=error_type,
                ) from None

        return wrapped

    return decorate


_FAILURE_EXPLANATIONS = {
    'prepare_failed': 'The workspace preparation task did not complete.',
    'code_failed': 'The implementation task did not complete.',
    'forgejo_dispatch_review_failed': (
        'CodeTether could not dispatch the review. This does not establish '
        'that the pull request is missing.'
    ),
    'review_blocked': 'The reviewer could not complete the review because required access, tools, or evidence were unavailable. No coding remediation was scheduled.',
    'review_fix_no_progress': 'The remediation task returned without advancing the PR head. The existing PR remains available; another review of the same commit was not scheduled.',
    'review_recovery_no_progress': 'The coding harvester could not establish a new commit or newly successful exact-head validation. The existing review remains blocked; inspect the recovery task for the required operator action.',
    'review_already_exists': 'A review task already exists for this PR head. No duplicate review was scheduled.',
    'review_pr_closed': 'The pull request is closed; no further review was scheduled.',
    'review_pr_missing': 'No pull request was found for the requested branch.',
    'review_failed': 'The pull-request review task did not complete.',
    'review_unresolved': (
        'The review finished without an approve or request-changes verdict.'
    ),
    'fix_failed': 'The review remediation task did not complete.',
    'fix_attempts_exhausted': (
        'The review still requested changes after the maximum number of '
        'remediation attempts.'
    ),
    'workflow_exhausted': 'The workflow ran out of review/fix attempts.',
    'review_remediation_failed': 'The author remediation task did not complete.',
}


def _failure_explanation(payload: dict[str, Any]) -> str:
    """Render a human-readable reason for a terminal `failed` comment.

    A bare "finished with status `failed`" left operators with nothing to act
    on (riley/spotlessbinco#5847). Only identifiers and fixed strings are
    used, so no prompt or exception text reaches Forgejo.
    """
    if str(payload.get('status')) != 'failed':
        return ''
    error_type = str(payload.get('error_type') or '')
    explanation = _FAILURE_EXPLANATIONS.get(error_type)
    parts = []
    if explanation:
        parts.append(f'\n\n**Why:** {explanation}')
    elif error_type:
        parts.append(f'\n\n**Why:** stage error `{error_type}`.')
    stages = [str(s) for s in payload.get('completed_stages') or [] if s]
    if stages:
        parts.append(f'\n\nCompleted stages: {", ".join(stages)}.')
    active = str(payload.get('active_task_id') or '')
    if active:
        parts.append(f'\n\nLast CodeTether task: `{active}`.')
    return ''.join(parts)


async def _codetether_task(task_id: str) -> dict[str, Any]:
    from a2a_server import database as db

    task = await db.db_get_task(task_id)
    if not task:
        raise RuntimeError(f'CodeTether task {task_id} was not found')
    return task


def _issue_url(repository: str, number: int) -> str:
    api = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
    origin = api.removesuffix('/api/v1')
    owner, name = repository.split('/', 1)
    issue_url = f'{origin}/{quote(owner, safe="")}/{quote(name, safe="")}'
    return f'{issue_url}/issues/{number}' if origin and number else ''


def _transcript_url(task_id: str, workspace_id: str) -> str:
    """Deep link to the live agent transcript for a CodeTether task.

    Worker narration is persisted under the deterministic session id
    `task-<task_id>` (see forgejo_progress_events), so the link is valid before
    the worker has produced any output. Unset CODETETHER_DASHBOARD_URL disables it.
    """
    dashboard = os.environ.get('CODETETHER_DASHBOARD_URL', '').rstrip('/')
    if not dashboard or not task_id:
        return ''
    query = {'session': f'task-{task_id}'}
    if workspace_id:
        query['workspace'] = workspace_id
    return f'{dashboard}/dashboard/sessions?' + '&'.join(
        f'{k}={quote(v, safe="")}' for k, v in query.items()
    )


async def _report_stage_progress(
    request: ForgejoStageRequest,
    *,
    task_id: str,
    stage: str,
    branch: str,
    head_sha: str = '',
) -> bool:
    """Post one idempotent, operator-visible stage update to Forgejo."""
    issue_number = int(request.workflow.issue_number or 0)
    if not issue_number:
        return False

    from a2a_server.forgejo_webhooks import _comment, forgejo_json

    repository = request.workflow.repository
    forgejo_task_id = request.workflow.forgejo_task_id
    attempt = request.workflow.attempt
    base = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
    owner, name = repository.split('/', 1)
    marker = (
        f'<!-- codetether-temporal-progress:{forgejo_task_id}:'
        f'{attempt}:{stage}:{task_id} -->'
    )
    comments = await forgejo_json(
        'GET',
        base,
        f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
        f'/issues/{issue_number}/comments?limit=100',
    )
    if not isinstance(comments, list):
        comments = []
    if any(
        marker in str((comment or {}).get('body') or '') for comment in comments
    ):
        return False

    labels = {
        'prepare': 'workspace preparation',
        'code': 'implementation',
        'review': 'pull-request review',
        'fix': 'review remediation',
        'remediate': 'author remediation',
    }
    label = labels.get(stage, stage)
    origin = base.removesuffix('/api/v1')
    task_url = (
        f'{origin}/{repository}/agent/tasks/{forgejo_task_id}' if origin else ''
    )
    body = (
        '## CodeTether progress\n\n'
        f'Temporal attempt `{attempt}` entered **{label}**.\n\n'
        f'- CodeTether task: `{task_id}`\n'
        f'- Branch: `{branch}`'
    )
    if head_sha:
        body += f'\n- Head: `{head_sha}`'
    if task_url:
        body += f'\n- [Native task #{forgejo_task_id}]({task_url})'
    transcript = _transcript_url(task_id, request.workflow.workspace_id)
    if transcript and stage in {'code', 'fix', 'remediate'}:
        body += f'\n- [Live agent transcript]({transcript})'
    body += f'\n\n{marker}'
    await _comment(base, repository, issue_number, body)
    return True


async def _report_stage_progress_safely(
    request: ForgejoStageRequest,
    *,
    task_id: str,
    stage: str,
    branch: str,
    head_sha: str = '',
) -> None:
    """Report progress without turning a comment outage into duplicate work."""
    try:
        await _report_stage_progress(
            request,
            task_id=task_id,
            stage=stage,
            branch=branch,
            head_sha=head_sha,
        )
    except Exception as exc:
        logger.warning(
            'Could not report Forgejo stage %s for task %s: %s',
            stage,
            task_id,
            exc,
        )


@asynccontextmanager
async def _execution_ownership(
    request: ForgejoStageRequest,
) -> AsyncIterator[None]:
    """Fence execution against newer inbox owners through durable handoff.

    Import intake lazily so workflow sandbox loading never imports its database
    integration. Ownership rejection must propagate rather than dispatch work.
    """
    from a2a_server.forgejo_inbox import execution_ownership  # noqa: PLC0415

    workflow = request.workflow
    async with execution_ownership(
        workflow.repository,
        workflow.issue_number,
        workflow.forgejo_task_id,
        os.environ.get('FORGEJO_API_URL', '').rstrip('/'),
        attempt=workflow.attempt,
    ):
        yield


async def _legacy_stage_task_id(request: ForgejoStageRequest) -> str | None:
    """Find an unambiguous pre-rollout direct-stage invocation, across statuses.

    Legacy keys have one SHA/branch suffix, with no further colon components.
    Match only immutable metadata; even the saved head may change at completion.
    Missing storage or ambiguous history must not turn into fresh dispatch.
    """
    from a2a_server import database as db  # noqa: PLC0415

    pool = await db.get_pool()
    if pool is None:
        raise RuntimeError('Stage migration lookup requires database storage')
    workflow = request.workflow
    prefix = (
        f'forgejo-temporal:{workflow.forgejo_task_id}:'
        f'{workflow.attempt}:{request.stage}:'
    )
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """SELECT id FROM tasks
               WHERE metadata->>'source' = 'forgejo-webhook'
                 AND metadata->>'temporal_orchestrated' = 'true'
                 AND metadata->>'repo' = $1
                 AND metadata->>'issue_number' = $2
                 AND metadata->>'forgejo_agent_task_id' = $3
                 AND metadata->>'temporal_attempt' = $4
                 AND metadata->>'workflow_stage' = $5
                 AND COALESCE(NULLIF(metadata->>'fix_attempt', ''), '0') = $6
                 AND COALESCE(metadata->>'parent_task_id', '') = $7
                 AND COALESCE(metadata->>'review_task_id', '') = $8
                 AND left(metadata->>'forgejo_work_key',
                     length($9::text)) = $9
                 AND length(metadata->>'forgejo_work_key') > length($9::text)
                 AND strpos(substring(metadata->>'forgejo_work_key'
                     FROM length($9::text) + 1), ':') = 0
               ORDER BY id LIMIT 2""",
            workflow.repository,
            str(workflow.issue_number),
            str(workflow.forgejo_task_id),
            str(workflow.attempt),
            request.stage,
            str(request.fix_attempt),
            request.parent_task_id or '',
            request.review_task_id or '',
            prefix,
        )
    if len(candidates) > 1:
        raise RuntimeError('Ambiguous legacy Temporal stage invocation')
    return str(candidates[0]['id']) if candidates else None


async def _reuse_legacy_stage(request: ForgejoStageRequest) -> str | None:
    """Reuse legacy work under both issue and original work-key locks.

    The caller holds execution ownership. Do not rewrite the legacy work key:
    older activity workers and partial-run recovery must serialize on that key.
    """
    from a2a_server.persistent_worker_pool import (  # noqa: PLC0415
        _github_work_dedupe_lock,
        _reconcile_forgejo_dispatch,
    )

    task_id = await _legacy_stage_task_id(request)
    if task_id is None:
        return None
    task = await _codetether_task(task_id)
    metadata = task.get('metadata') or {}
    async with _github_work_dedupe_lock(metadata):
        # Recheck after waiting for an old worker's in-flight creation/repair.
        if await _legacy_stage_task_id(request) != task_id:
            raise RuntimeError('Legacy Temporal stage changed during migration')
        await _reconcile_forgejo_dispatch(
            task_id,
            604800,
            metadata.get('forgejo_issue_url') or None,
        )
    return task_id


def _temporal_metadata(
    request: ForgejoStageRequest,
    *,
    branch: str,
    head_sha: str,
    pull_request_number: int,
) -> dict[str, Any]:
    workflow = request.workflow
    return {
        'workspace_id': workflow.workspace_id,
        'source': 'forgejo-webhook',
        'platform': 'forgejo',
        'workflow_stage': request.stage,
        'repo': workflow.repository,
        'issue_number': workflow.issue_number,
        'pr_number': pull_request_number or None,
        'branch_name': branch,
        'pr_head_sha': head_sha,
        'forgejo_api_url': os.environ.get('FORGEJO_API_URL', '').rstrip('/'),
        'forgejo_issue_url': _issue_url(
            workflow.repository,
            pull_request_number or workflow.issue_number,
        ),
        'forgejo_agent_task_id': workflow.forgejo_task_id,
        'temporal_orchestrated': True,
        'temporal_workflow_id': request.workflow_id,
        'temporal_attempt': workflow.attempt,
        'parent_task_id': request.parent_task_id or None,
        'review_task_id': request.review_task_id or None,
        'fix_attempt': request.fix_attempt or None,
        'forgejo_work_key': (
            f'forgejo-temporal:{workflow.forgejo_task_id}:'
            # Bind the invocation, not the mutable PR head, across retries.
            f'{workflow.attempt}:{request.stage}:{request.fix_attempt}:'
            f'{request.parent_task_id}:{request.review_task_id}'
        ),
    }


async def _forgejo_context(
    request: ForgejoStageRequest,
) -> tuple[dict[str, Any], str, str, int, str, str]:
    from a2a_server.forgejo_agent_client import get_task
    from a2a_server.forgejo_webhooks import forgejo_json

    workflow = request.workflow
    forgejo_task = await get_task(
        repo=workflow.repository,
        task_id=workflow.forgejo_task_id,
    )
    owner, name = workflow.repository.split('/', 1)
    repo_path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    repository = await forgejo_json(
        'GET', os.environ.get('FORGEJO_API_URL', '').rstrip('/'), repo_path
    )
    default_branch = str(repository.get('default_branch') or 'main')
    branch = workflow.branch or default_branch
    clone_branch = default_branch
    clone_url = str(repository.get('clone_url') or '')
    head_sha = workflow.head_sha
    pull_number = workflow.pull_request_number
    if pull_number:
        pull = await forgejo_json(
            'GET',
            os.environ.get('FORGEJO_API_URL', '').rstrip('/'),
            f'{repo_path}/pulls/{pull_number}',
        )
        head = (pull or {}).get('head') or {}
        branch = str(head.get('ref') or branch)
        clone_branch = branch
        head_sha = str(head.get('sha') or head_sha)
        clone_url = str(
            ((head.get('repo') or {}).get('clone_url')) or clone_url
        )
    if not clone_url:
        raise RuntimeError('Forgejo repository has no clone URL')
    return (
        forgejo_task,
        branch,
        head_sha,
        pull_number,
        clone_url,
        clone_branch,
    )


@activity.defn(name='forgejo_dispatch_stage')
@safe_activity('forgejo_dispatch_stage_failed')
async def dispatch_stage(request: ForgejoStageRequest) -> ForgejoStageResult:
    """Dispatch one existing CodeTether execution stage."""
    from a2a_server.forgejo_agent_client import update_task
    from a2a_server.github_app.routing import resolve_task_target
    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    (
        forgejo_task,
        branch,
        head_sha,
        pull_number,
        clone_url,
        clone_branch,
    ) = await _forgejo_context(request)
    routing = await resolve_task_target()
    metadata = _temporal_metadata(
        request,
        branch=branch,
        head_sha=head_sha,
        pull_request_number=pull_number,
    )
    metadata.update(routing)

    if request.stage == 'remediate':
        task_metadata = forgejo_task.get('metadata') or {}
        for key in (
            'target_agent_name',
            'resume_session_id',
            'context_id',
            'conversation_id',
            'author_provenance_id',
            'forgejo_author_login',
            'git_signer',
            'review_blocking_findings',
            'review_nonblocking_findings',
            'review_finding_ids',
            'preserve_session_workspace',
            'provenance_verified',
        ):
            if key in task_metadata:
                metadata[key] = task_metadata[key]
        title = f'Address Forgejo review for PR #{pull_number}'
        prompt = str(forgejo_task.get('prompt') or '')
        agent_type = 'build'
    elif request.stage == 'prepare':
        metadata['git_url'] = clone_url
        metadata['git_branch'] = clone_branch
        title = f'Prepare Forgejo task #{request.workflow.issue_number}'
        prompt = (
            f'Clone or refresh {request.workflow.repository} '
            f'on branch {branch} '
            'for Forgejo automation.'
        )
        agent_type = 'clone_repo'
    elif request.stage == 'code':
        title = f'Work Forgejo task #{request.workflow.issue_number}'
        prompt = str(forgejo_task.get('prompt') or '')
        agent_type = 'build'
    else:
        raise ValueError(f'unsupported direct stage: {request.stage}')

    async with _execution_ownership(request):
        task_id = await _reuse_legacy_stage(request)
        if task_id is None:
            task_id = await create_and_dispatch_task(
                workspace_id=request.workflow.workspace_id,
                title=title,
                prompt=prompt,
                agent_type=agent_type,
                priority=500 if request.stage == 'remediate' else 100,
                model_ref=MODEL_REF,
                metadata=metadata,
                task_timeout_seconds=604800,
                github_issue_url=metadata.get('forgejo_issue_url') or None,
            )
    # A deduplicated task may belong to an earlier activity attempt. Its saved
    # checkpoint is authoritative, even if the PR advanced after dispatch.
    # Missing checkpoint values must not fall back to today's mutable PR head.
    task = await _codetether_task(str(task_id))
    checkpoint = task.get('metadata') or {}
    branch = str(checkpoint.get('branch_name') or '')
    head_sha = str(checkpoint.get('pr_head_sha') or '')
    pull_number = int(checkpoint.get('pr_number') or 0)
    await update_task(
        repo=request.workflow.repository,
        task_id=request.workflow.forgejo_task_id,
        status='running',
        external_task_id=str(task_id),
        head_sha=head_sha,
        branch=branch,
    )
    await _report_stage_progress_safely(
        request,
        task_id=str(task_id),
        stage=request.stage,
        branch=branch,
        head_sha=head_sha,
    )
    return ForgejoStageResult(
        task_id=str(task_id),
        stage=request.stage,
        pull_request_number=pull_number,
        branch=branch,
        head_sha=head_sha,
    )


@activity.defn(name='forgejo_dispatch_review')
@safe_activity('forgejo_dispatch_review_failed')
async def dispatch_review(request: ForgejoStageRequest) -> ForgejoStageResult:
    """Create a head-bound review task using the existing safety checks."""
    from a2a_server.forgejo_automation import (
        ForgejoReviewNotReady,
        create_forgejo_review_task,
    )

    parent = await _codetether_task(request.parent_task_id)
    if (parent.get('metadata') or {}).get(
        'workflow_stage'
    ) == 'review_recovery':
        from a2a_server.forgejo_review_owner.recovery import reconcile_recovery
        from a2a_server import database

        owner_id = parent['metadata']['review_owner_id']
        owner = await database.db_get_task(owner_id)
        await reconcile_recovery(owner, str(parent['id']))
        parent = await database.db_get_task(str(parent['id']))
        progress = parent['metadata'].get('recovery_state')
        if progress == 'needs_input' or parent['metadata'].get(
            'recovery_blocker'
        ):
            raise ApplicationError(
                'review_recovery_no_progress',
                type='review_recovery_no_progress',
                non_retryable=True,
            )
        if progress not in {'new_head_review', 'validation_review'}:
            raise ApplicationError(
                'review_recovery_progress_pending',
                type='review_recovery_progress_pending',
            )
    async with _execution_ownership(request):
        try:
            task_id = await create_forgejo_review_task(parent)
        except ForgejoReviewNotReady as error:
            raise ApplicationError(
                error.reason, type=error.reason, non_retryable=True
            ) from None
    if not task_id:
        raise RuntimeError('Forgejo review task was not created')
    task = await _codetether_task(str(task_id))
    metadata = task.get('metadata') or {}
    await _report_stage_progress_safely(
        request,
        task_id=str(task_id),
        stage='review',
        branch=str(metadata.get('branch_name') or ''),
        head_sha=str(metadata.get('pr_head_sha') or ''),
    )
    return ForgejoStageResult(
        task_id=str(task_id),
        stage='review',
        pull_request_number=int(metadata.get('pr_number') or 0),
        branch=str(metadata.get('branch_name') or ''),
        head_sha=str(metadata.get('pr_head_sha') or ''),
    )


@activity.defn(name='forgejo_publish_review')
@safe_activity('forgejo_publish_review_failed')
async def publish_review(review_task_id: str) -> str:
    """Publish a formal Forgejo review and return only its verdict enum."""
    from a2a_server.forgejo_automation import (
        publish_forgejo_review,
        reviewer_verdict,
    )

    task = await _codetether_task(review_task_id)
    publication = await publish_forgejo_review(task)
    if publication.get('event') == 'SUPERSEDED':
        raise ApplicationError(
            'review_superseded', type='review_superseded', non_retryable=True
        )
    if (task.get('metadata') or {}).get('review_owner'):
        return task['metadata']['review_verdict']
    return reviewer_verdict(task)


@activity.defn(name='forgejo_dispatch_fix')
@safe_activity('forgejo_dispatch_fix_failed')
async def dispatch_fix(request: ForgejoStageRequest) -> ForgejoStageResult:
    """Create one bounded fix task after a blocking review."""
    from a2a_server.forgejo_automation import create_forgejo_fix_followup

    review_task = await _codetether_task(request.review_task_id)
    if (review_task.get('metadata') or {}).get('review_owner'):
        review_task = {
            **review_task,
            'metadata': {
                **review_task['metadata'],
                'workspace_id': request.workflow.workspace_id,
                'forgejo_agent_task_id': request.workflow.forgejo_task_id,
                'issue_number': request.workflow.issue_number,
                'temporal_orchestrated': True,
                'temporal_workflow_id': request.workflow_id,
                'temporal_attempt': request.workflow.attempt,
            },
        }
    async with _execution_ownership(request):
        if (review_task.get('metadata') or {}).get('review_owner'):
            task_id = await create_forgejo_fix_followup(
                review_task, ownership_held=True
            )
        else:
            task_id = await create_forgejo_fix_followup(review_task)
    if not task_id:
        raise RuntimeError('Forgejo fix task was not created')
    task = await _codetether_task(str(task_id))
    metadata = task.get('metadata') or {}
    await _report_stage_progress_safely(
        request,
        task_id=str(task_id),
        stage='fix',
        branch=str(metadata.get('branch_name') or ''),
        head_sha=str(metadata.get('pr_head_sha') or ''),
    )
    return ForgejoStageResult(
        task_id=str(task_id),
        stage='fix',
        pull_request_number=int(metadata.get('pr_number') or 0),
        branch=str(metadata.get('branch_name') or ''),
        head_sha=str(metadata.get('pr_head_sha') or ''),
    )


@activity.defn(name='forgejo_cancel_task')
@safe_activity('forgejo_cancel_task_failed')
async def cancel_task(task_id: str) -> bool:
    """Cancel the active CodeTether task and revoke its run lease."""
    from a2a_server.forgejo_agent_controls import _cancel_codetether_task

    task = await _codetether_task(task_id)
    if (task.get('metadata') or {}).get('review_owner'):
        from .config import get_temporal_client

        client = await get_temporal_client()
        await client.get_workflow_handle(
            task['metadata']['review_workflow_id']
        ).signal('cancel')
        from a2a_server import database

        await database.db_update_task_status(
            task_id, 'cancelled', error='review_cancel_requested'
        )
        return True
    return await _cancel_codetether_task(task_id)


@activity.defn(name='forgejo_finalize_workflow')
@safe_activity('forgejo_finalize_workflow_failed')
async def finalize_workflow(payload: dict[str, Any]) -> None:
    """Project a terminal workflow status into Forgejo and post one comment."""
    from a2a_server.forgejo_agent_client import update_task
    from a2a_server.forgejo_webhooks import _comment

    repository = str(payload['repository'])
    forgejo_task_id = int(payload['forgejo_task_id'])
    status = str(payload['status'])
    active_task_id = str(payload.get('active_task_id') or '')
    await update_task(
        repo=repository,
        task_id=forgejo_task_id,
        status=status,
        external_task_id=active_task_id,
    )
    issue_number = int(payload.get('issue_number') or 0)
    if issue_number:
        base = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
        task_url = str(payload.get('task_url') or '')
        marker = (
            f'<!-- codetether-temporal:{forgejo_task_id}:'
            f'{payload.get("attempt", 1)} -->'
        )
        body = (
            f'## CodeTether Agent\n\nTemporal workflow finished with '
            f'status `{status}`.'
        )
        body += _failure_explanation(payload)
        if task_url:
            body += f'\n\n[View native session]({task_url})'
        from a2a_server.forgejo_webhooks import forgejo_json

        owner, name = repository.split('/', 1)
        comments = await forgejo_json(
            'GET',
            base,
            f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
            f'/issues/{issue_number}/comments',
        )
        if not isinstance(comments, list):
            comments = []
        if not any(
            marker in str((comment or {}).get('body') or '')
            for comment in comments
        ):
            body += f'\n\n{marker}'
            await _comment(base, repository, issue_number, body)
