"""Temporal activities for Forgejo agent orchestration.

Activity inputs and results deliberately exclude prompts, transcripts, tool
payloads, credentials, and repository clone URLs. Those values are loaded and
used inside activity execution only, so they are not persisted in workflow
history.
"""

from __future__ import annotations

import os

from functools import wraps
from typing import Any, Callable
from urllib.parse import quote

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .models import ForgejoStageRequest, ForgejoStageResult


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
    return (
        f'{origin}/{quote(owner, safe="")}/{quote(name, safe="")}/issues/{number}'
        if origin and number
        else ''
    )


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
            f'{workflow.attempt}:{request.stage}:{head_sha or branch}'
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

    if request.stage == 'prepare':
        metadata['git_url'] = clone_url
        metadata['git_branch'] = clone_branch
        title = f'Prepare Forgejo task #{request.workflow.issue_number}'
        prompt = (
            f'Clone or refresh {request.workflow.repository} on branch {branch} '
            'for Forgejo automation.'
        )
        agent_type = 'clone_repo'
    elif request.stage == 'code':
        title = f'Work Forgejo task #{request.workflow.issue_number}'
        prompt = str(forgejo_task.get('prompt') or '')
        agent_type = 'build'
    else:
        raise ValueError(f'unsupported direct stage: {request.stage}')

    task_id = await create_and_dispatch_task(
        workspace_id=request.workflow.workspace_id,
        title=title,
        prompt=prompt,
        agent_type=agent_type,
        priority=100,
        model_ref='zai:glm-5.1',
        metadata=metadata,
        task_timeout_seconds=604800,
        github_issue_url=metadata.get('forgejo_issue_url') or None,
    )
    await update_task(
        repo=request.workflow.repository,
        task_id=request.workflow.forgejo_task_id,
        status='running',
        external_task_id=str(task_id),
        head_sha=head_sha,
        branch=branch,
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
    from a2a_server.forgejo_automation import create_forgejo_review_task

    parent = await _codetether_task(request.parent_task_id)
    task_id = await create_forgejo_review_task(parent)
    if not task_id:
        raise RuntimeError('Forgejo review task was not created')
    task = await _codetether_task(str(task_id))
    metadata = task.get('metadata') or {}
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
    await publish_forgejo_review(task)
    return reviewer_verdict(task)


@activity.defn(name='forgejo_dispatch_fix')
@safe_activity('forgejo_dispatch_fix_failed')
async def dispatch_fix(request: ForgejoStageRequest) -> ForgejoStageResult:
    """Create one bounded fix task after a blocking review."""
    from a2a_server.forgejo_automation import create_forgejo_fix_followup

    review_task = await _codetether_task(request.review_task_id)
    task_id = await create_forgejo_fix_followup(review_task)
    if not task_id:
        raise RuntimeError('Forgejo fix task was not created')
    task = await _codetether_task(str(task_id))
    metadata = task.get('metadata') or {}
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
        if not any(
            marker in str((comment or {}).get('body') or '')
            for comment in comments or []
        ):
            body += f'\n\n{marker}'
            await _comment(base, repository, issue_number, body)
