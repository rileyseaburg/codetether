"""Mocked-local regression coverage for Temporal stage replay and ownership."""
# ruff: noqa: SLF001, PLR2004, PLC0415

import copy
import sys

from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from temporalio.exceptions import ApplicationError

from a2a_server.temporal import activities
from a2a_server.temporal.models import (
    ForgejoAgentWorkflowInput,
    ForgejoStageRequest,
)


def request(stage='code', **kwargs):
    return ForgejoStageRequest(
        workflow=ForgejoAgentWorkflowInput(
            forgejo_task_id=42,
            repository='owner/repo',
            issue_number=12,
            pull_request_number=12,
            workspace_id='workspace',
            branch='feature',
            head_sha='initial',
            operation='fix',
        ),
        workflow_id='forgejo-agent-task-42',
        stage=stage,
        **kwargs,
    )


def work_key(value, branch='feature', head='first'):
    return activities._temporal_metadata(
        value,
        branch=branch,
        head_sha=head,
        pull_request_number=12,
    )['forgejo_work_key']


def test_stage_identity_excludes_mutable_checkpoint_and_separates_invocations():
    value = request(parent_task_id='parent', review_task_id='review')
    key = work_key(value)
    assert key == work_key(value, branch='renamed', head='advanced')
    variants = [
        replace(value, workflow=replace(value.workflow, forgejo_task_id=43)),
        replace(value, workflow=replace(value.workflow, attempt=2)),
        replace(value, stage='prepare'),
        replace(value, stage='remediate'),
        replace(value, fix_attempt=1),
        replace(value, parent_task_id='next-parent'),
        replace(value, review_task_id='next-review'),
    ]
    keys = [work_key(other) for other in variants]
    assert key not in keys
    assert len(set(keys)) == len(keys)


@pytest.fixture
def ownership(monkeypatch):
    monkeypatch.setattr(
        activities, '_legacy_stage_task_id', AsyncMock(return_value=None)
    )
    state = {'held': False, 'calls': []}

    @asynccontextmanager
    async def guard(
        repository, issue_number, native_task_id, api_base, attempt=1
    ):
        assert not state['held']
        state['calls'].append(
            (repository, issue_number, native_task_id, api_base, attempt)
        )
        state['held'] = True
        try:
            yield
        finally:
            state['held'] = False

    # Parent supplies this module. Exercise the real lazy wrapper without
    # importing another worktree's inbox or connecting to PostgreSQL.
    monkeypatch.setitem(
        sys.modules,
        'a2a_server.forgejo_inbox',
        SimpleNamespace(execution_ownership=guard),
    )
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1/')
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['prepare', 'code', 'remediate'])
@pytest.mark.parametrize(
    'failure_point', ['dispatch_response', 'native_update']
)
async def test_retry_after_head_advance_reuses_task_and_persisted_checkpoint(
    monkeypatch,
    ownership,
    stage,
    failure_point,
):
    from a2a_server import (
        forgejo_agent_client,
        forgejo_webhooks,
        persistent_worker_pool,
    )
    from a2a_server.github_app import routing

    saved = {}
    calls = []
    current = {'ref': 'original-branch', 'sha': 'original-sha'}

    async def forgejo_json(method, base, path):
        if '/pulls/' in path:
            return {'head': dict(current)}
        return {
            'default_branch': 'main',
            'clone_url': 'https://forge.example/owner/repo.git',
        }

    async def create(**kwargs):
        assert ownership['held'], 'durable row/run creation must remain fenced'
        key = kwargs['metadata']['forgejo_work_key']
        calls.append(copy.deepcopy(kwargs))
        if key not in saved:
            saved[key] = {
                'id': 'stage-task',
                'metadata': copy.deepcopy(kwargs['metadata']),
            }
            if failure_point == 'dispatch_response':
                raise RuntimeError(
                    'response lost after durable task/run creation'
                )
        return saved[key]['id']

    async def lookup(task_id):
        assert task_id == 'stage-task'
        return next(iter(saved.values()))

    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', forgejo_json)
    monkeypatch.setattr(
        forgejo_agent_client,
        'get_task',
        AsyncMock(return_value={'prompt': 'private prompt'}),
    )
    update = AsyncMock(
        side_effect=[RuntimeError('update lost'), {}]
        if failure_point == 'native_update'
        else None
    )
    monkeypatch.setattr(forgejo_agent_client, 'update_task', update)
    monkeypatch.setattr(
        routing, 'resolve_task_target', AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', create
    )
    monkeypatch.setattr(activities, '_codetether_task', lookup)
    progress = AsyncMock()
    monkeypatch.setattr(activities, '_report_stage_progress_safely', progress)

    invocation = request(stage)
    with pytest.raises(ApplicationError):
        await activities.dispatch_stage(invocation)
    assert not ownership['held']
    # Completed work is also deduped by the parent worker pool; never relabel it
    # with a new PR checkpoint simply because the activity acknowledgement died.
    next(iter(saved.values()))['status'] = 'completed'
    current.update(ref='new-branch', sha='new-sha')
    result = await activities.dispatch_stage(invocation)

    assert len(saved) == 1
    assert len(calls) == 2
    assert calls[1]['metadata']['pr_head_sha'] == 'new-sha'
    assert (
        calls[0]['metadata']['forgejo_work_key']
        == calls[1]['metadata']['forgejo_work_key']
    )
    assert result.task_id == 'stage-task'
    assert (result.branch, result.head_sha, result.pull_request_number) == (
        'original-branch',
        'original-sha',
        12,
    )
    assert update.call_args.kwargs['head_sha'] == 'original-sha'
    assert update.call_args.kwargs['branch'] == 'original-branch'
    assert progress.call_args.kwargs['head_sha'] == 'original-sha'
    assert progress.call_args.kwargs['branch'] == 'original-branch'
    assert 'private prompt' not in repr(result)
    assert not ownership['held']


@pytest.mark.asyncio
@pytest.mark.parametrize('attempt', [1, 2])
async def test_wrapper_forwards_native_attempt_and_scope(ownership, attempt):
    value = request()
    value = replace(value, workflow=replace(value.workflow, attempt=attempt))
    async with activities._execution_ownership(value):
        assert ownership['held']
    assert ownership['calls'] == [
        ('owner/repo', 12, 42, 'https://forge.example/api/v1', attempt)
    ]
    assert not ownership['held']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'stage', ['prepare', 'code', 'remediate', 'review', 'fix']
)
async def test_ownership_rejection_prevents_every_creation_path(
    monkeypatch, stage
):
    from a2a_server import forgejo_automation, persistent_worker_pool
    from a2a_server.github_app import routing

    @asynccontextmanager
    async def reject(value):
        raise RuntimeError('newer actionable inbox owner')
        yield

    monkeypatch.setattr(activities, '_execution_ownership', reject)
    monkeypatch.setattr(
        activities,
        '_forgejo_context',
        AsyncMock(
            return_value=(
                {'prompt': 'work'},
                'feature',
                'sha',
                12,
                'https://forge.example/owner/repo.git',
                'feature',
            )
        ),
    )
    monkeypatch.setattr(
        activities, '_codetether_task', AsyncMock(return_value={'metadata': {}})
    )
    monkeypatch.setattr(
        routing, 'resolve_task_target', AsyncMock(return_value={})
    )
    direct, review, fix = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', direct
    )
    monkeypatch.setattr(
        forgejo_automation, 'create_forgejo_review_task', review
    )
    monkeypatch.setattr(forgejo_automation, 'create_forgejo_fix_followup', fix)
    fn = {
        'review': activities.dispatch_review,
        'fix': activities.dispatch_fix,
    }.get(stage, activities.dispatch_stage)
    with pytest.raises(ApplicationError):
        await fn(
            request(stage, parent_task_id='parent', review_task_id='review')
        )
    for create in (direct, review, fix):
        create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['review', 'fix'])
async def test_review_and_fix_handoff_hold_ownership(
    monkeypatch, ownership, stage
):
    from a2a_server import forgejo_automation

    async def create(parent):
        assert ownership['held']
        return 'task'

    monkeypatch.setattr(
        forgejo_automation, 'create_forgejo_review_task', create
    )
    monkeypatch.setattr(
        forgejo_automation, 'create_forgejo_fix_followup', create
    )
    monkeypatch.setattr(
        activities,
        '_codetether_task',
        AsyncMock(
            return_value={
                'metadata': {
                    'branch_name': 'branch',
                    'pr_head_sha': 'sha',
                    'pr_number': 12,
                }
            }
        ),
    )
    monkeypatch.setattr(
        activities, '_report_stage_progress_safely', AsyncMock()
    )
    fn = (
        activities.dispatch_review
        if stage == 'review'
        else activities.dispatch_fix
    )
    result = await fn(
        request(stage, parent_task_id='parent', review_task_id='review')
    )
    assert result.task_id == 'task'
    assert not ownership['held']


def test_transcript_url_targets_deterministic_task_session(monkeypatch):
    """Operators can open the live transcript from the issue comment."""
    monkeypatch.setenv('CODETETHER_DASHBOARD_URL', 'https://codetether.run/')
    url = activities._transcript_url('abc-123', 'ws/1')
    assert url == (
        'https://codetether.run/dashboard/sessions'
        '?session=task-abc-123&workspace=ws%2F1'
    )
    assert activities._transcript_url('abc-123', '') == (
        'https://codetether.run/dashboard/sessions?session=task-abc-123'
    )
    monkeypatch.delenv('CODETETHER_DASHBOARD_URL')
    assert activities._transcript_url('abc-123', 'ws') == ''


@pytest.mark.asyncio
async def test_progress_comment_links_transcript_only_for_agent_stages(
    monkeypatch,
):
    monkeypatch.setenv('CODETETHER_DASHBOARD_URL', 'https://codetether.run')
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    from a2a_server import forgejo_webhooks

    posted = []

    async def comment(base, repo, number, body):
        posted.append(body)

    monkeypatch.setattr(forgejo_webhooks, '_comment', comment)
    monkeypatch.setattr(
        forgejo_webhooks, 'forgejo_json', AsyncMock(return_value=[])
    )
    for stage in ('prepare', 'code'):
        await activities._report_stage_progress(
            request(stage), task_id='t1', stage=stage, branch='b'
        )
    prepare_body, code_body = posted
    assert 'Live agent transcript' not in prepare_body
    assert 'sessions?session=task-t1' in code_body
