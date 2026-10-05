"""Mocked-local rollout coverage for pre-immutable Temporal task keys."""
# ruff: noqa: SLF001, PLR2004, PLC0415

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from temporalio.exceptions import ApplicationError

from a2a_server.temporal import activities
from a2a_server.temporal.models import (
    ForgejoAgentWorkflowInput,
    ForgejoStageRequest,
)


@pytest.fixture
def invocation():
    return ForgejoStageRequest(
        workflow=ForgejoAgentWorkflowInput(
            forgejo_task_id=42,
            repository='owner/repo',
            issue_number=12,
            pull_request_number=12,
            workspace_id='workspace',
            branch='feature',
            head_sha='original-sha',
            operation='fix',
            attempt=2,
        ),
        workflow_id='forgejo-agent-task-42',
        stage='code',
        fix_attempt=1,
        parent_task_id='parent',
        review_task_id='review',
    )


def _assert_legacy_query(sql, params) -> None:
    assert params == (
        'owner/repo',
        '12',
        '42',
        '2',
        'code',
        '1',
        'parent',
        'review',
        'forgejo-temporal:42:2:code:',
    )
    # Bind metadata identity, not a candidate PR head passed by the activity.
    assert "COALESCE(NULLIF(metadata->>'fix_attempt', ''), '0') = $6" in sql
    assert "COALESCE(metadata->>'parent_task_id', '') = $7" in sql
    assert "COALESCE(metadata->>'review_task_id', '') = $8" in sql
    assert "left(metadata->>'forgejo_work_key'," in sql
    assert 'length($9::text)) = $9' in sql
    assert "length(metadata->>'forgejo_work_key') > length($9::text)" in sql
    assert 'pr_head_sha' not in sql and 'branch_name' not in sql
    assert "strpos(substring(metadata->>'forgejo_work_key'" in sql
    assert 'LIMIT 2' in sql


@pytest.fixture
def legacy(monkeypatch, invocation):
    from a2a_server import (
        database,
        forgejo_agent_client,
        persistent_worker_pool,
    )
    from a2a_server.github_app import routing

    metadata = activities._temporal_metadata(
        invocation,
        branch='original-branch',
        head_sha='original-sha',
        pull_request_number=12,
    )
    metadata['forgejo_work_key'] = 'forgejo-temporal:42:2:code:original-sha'
    task = {'id': 'legacy-task', 'metadata': metadata, 'status': 'pending'}
    state = {'issue_locked': False, 'work_locked': False, 'runs': set()}

    @asynccontextmanager
    async def ownership(request):
        state['issue_locked'] = True
        try:
            yield
        finally:
            state['issue_locked'] = False

    @asynccontextmanager
    async def work_lock(saved):
        assert state['issue_locked']
        assert saved['forgejo_work_key'] == metadata['forgejo_work_key']
        state['work_locked'] = True
        try:
            yield saved['forgejo_work_key']
        finally:
            state['work_locked'] = False

    async def fetch(sql, *params):
        assert state['issue_locked'], (
            'legacy discovery must hold issue ownership'
        )
        _assert_legacy_query(sql, params)
        return [{'id': 'legacy-task'}]

    async def repair(task_id, timeout, issue_url):
        assert state['issue_locked'] and state['work_locked']
        assert task_id == task['id']
        if task['status'] == 'pending':
            state['runs'].add(task_id)

    conn = AsyncMock()
    conn.fetch.side_effect = fetch
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(activities, '_execution_ownership', ownership)
    monkeypatch.setattr(
        activities, '_codetether_task', AsyncMock(return_value=task)
    )
    monkeypatch.setattr(
        persistent_worker_pool, '_github_work_dedupe_lock', work_lock
    )
    repair_mock = AsyncMock(side_effect=repair)
    monkeypatch.setattr(
        persistent_worker_pool, '_reconcile_forgejo_dispatch', repair_mock
    )
    create = AsyncMock()
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', create
    )
    monkeypatch.setattr(
        activities,
        '_forgejo_context',
        AsyncMock(
            return_value=(
                {'prompt': 'sensitive prompt'},
                'advanced-branch',
                'advanced-sha',
                12,
                'https://forge.example/owner/repo.git',
                'advanced-branch',
            )
        ),
    )
    monkeypatch.setattr(
        routing, 'resolve_task_target', AsyncMock(return_value={})
    )
    update = AsyncMock()
    monkeypatch.setattr(forgejo_agent_client, 'update_task', update)
    progress = AsyncMock()
    monkeypatch.setattr(activities, '_report_stage_progress_safely', progress)
    return task, state, conn, create, repair_mock, update, progress


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'completed', 'cancelled'])
async def test_legacy_stage_survives_rollout_and_pr_advance(
    invocation, legacy, status
):
    task, state, conn, create, repair, update, progress = legacy
    task['status'] = status
    first = await activities.dispatch_stage(invocation)
    second = await activities.dispatch_stage(invocation)
    create.assert_not_awaited()
    assert first == second
    assert first.task_id == 'legacy-task'
    assert first.branch == 'original-branch'
    assert first.head_sha == 'original-sha'
    assert first.pull_request_number == 12
    assert conn.fetch.await_count == 4
    assert repair.await_count == 2
    assert len(state['runs']) == (1 if status == 'pending' else 0)
    assert update.call_args.kwargs['head_sha'] == 'original-sha'
    assert progress.call_args.kwargs['head_sha'] == 'original-sha'
    assert not state['issue_locked'] and not state['work_locked']


@pytest.mark.asyncio
@pytest.mark.parametrize('after_work_lock', [False, True])
async def test_ambiguous_legacy_invocation_fails_closed(
    invocation, legacy, after_work_lock
):
    _, state, conn, create, repair, update, _ = legacy
    duplicates = [{'id': 'legacy-task'}, {'id': 'other-old-task'}]
    conn.fetch.side_effect = (
        [[{'id': 'legacy-task'}], duplicates] if after_work_lock else None
    )
    conn.fetch.return_value = duplicates
    with pytest.raises(ApplicationError):
        await activities.dispatch_stage(invocation)
    create.assert_not_awaited()
    repair.assert_not_awaited()
    update.assert_not_awaited()
    assert not state['issue_locked'] and not state['work_locked']


@pytest.mark.asyncio
async def test_missing_legacy_storage_never_falls_back_to_new_creation(
    monkeypatch, invocation, legacy
):
    from a2a_server import database

    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=None))
    with pytest.raises(ApplicationError):
        await activities.dispatch_stage(invocation)
    legacy[3].assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_run_recovery_failure_never_reports_handoff(
    invocation, legacy
):
    legacy[4].side_effect = RuntimeError('run storage unavailable')
    with pytest.raises(ApplicationError):
        await activities.dispatch_stage(invocation)
    legacy[3].assert_not_awaited()
    legacy[5].assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_checkpoint_can_change_without_changing_legacy_identity(
    invocation,
    legacy,
):
    task, _, _, create, _, update, _ = legacy
    task['status'] = 'completed'
    task['metadata']['pr_head_sha'] = 'completed-checkpoint-sha'
    assert task['metadata']['forgejo_work_key'].endswith(':original-sha')
    result = await activities.dispatch_stage(invocation)
    create.assert_not_awaited()
    assert result.head_sha == 'completed-checkpoint-sha'
    assert update.call_args.kwargs['head_sha'] == 'completed-checkpoint-sha'


@pytest.mark.asyncio
async def test_missing_candidate_allows_only_normal_immutable_dispatch(
    monkeypatch,
    invocation,
    legacy,
):
    _, _, conn, create, repair, _, _ = legacy
    conn.fetch.side_effect = None
    conn.fetch.return_value = []
    create.return_value = 'new-task'
    metadata = activities._temporal_metadata(
        invocation,
        branch='advanced-branch',
        head_sha='advanced-sha',
        pull_request_number=12,
    )
    monkeypatch.setattr(
        activities,
        '_codetether_task',
        AsyncMock(
            return_value={'id': 'new-task', 'metadata': metadata},
        ),
    )
    result = await activities.dispatch_stage(invocation)
    create.assert_awaited_once()
    repair.assert_not_awaited()
    assert (
        create.call_args.kwargs['metadata']['forgejo_work_key']
        == metadata['forgejo_work_key']
    )
    assert result.task_id == 'new-task'
