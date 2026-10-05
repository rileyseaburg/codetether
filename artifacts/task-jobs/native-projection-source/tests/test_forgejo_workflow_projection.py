"""Mocked local checks for stale lifecycle repair, never live signals."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from temporalio.client import WorkflowExecutionStatus as Status

from a2a_server import forgejo_inbox_dispatch as effects
from a2a_server import forgejo_webhooks as hooks
from a2a_server import forgejo_workflow_projection as projection
from a2a_server import persistent_worker_pool as pool
from a2a_server.temporal import client, config


@pytest.fixture
def runtime(monkeypatch):
    """Provide fixed workflow metadata and native API effects."""
    task = {'id': 534, 'status': 'running', 'operation': 'fix'}
    closed = SimpleNamespace(run_id='run-a', status=Status.TERMINATED)
    handle = SimpleNamespace(describe=AsyncMock(return_value=closed))
    temporal = SimpleNamespace(
        workflow_handle=AsyncMock(return_value=handle),
        temporal_settings=lambda: SimpleNamespace(enabled=True),
    )
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=None))
    get_task = AsyncMock(return_value=dict(task))
    update = AsyncMock(return_value={**task, 'status': 'cancelled'})
    monkeypatch.setattr(projection, 'import_module', lambda name: temporal)
    monkeypatch.setattr(projection.native, 'get_task', get_task)
    monkeypatch.setattr(projection.native, 'update_task', update)
    return SimpleNamespace(
        task=task,
        closed=closed,
        handle=handle,
        temporal=temporal,
        conn=conn,
        get=get_task,
        update=update,
    )


@pytest.mark.asyncio
async def test_terminated_workflow_releases_stale_native_running(runtime):
    result = await projection.reconcile_native(
        runtime.conn, 'owner/repo', runtime.task, 'https://forge/api/v1'
    )
    assert result['status'] == 'cancelled'
    runtime.update.assert_awaited_once_with(
        repo='owner/repo',
        task_id=534,
        base_url='https://forge/api/v1',
        status='cancelled',
        error='workflow_terminated',
    )
    sql = runtime.conn.fetchval.await_args.args[0]
    assert 'recovery_native_request' in sql
    assert "'running'" in sql and "'pending'" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status', [Status.RUNNING, Status.CONTINUED_AS_NEW, Status.COMPLETED]
)
async def test_no_inferred_completion_or_repair_of_a_live_workflow(
    runtime,
    status,
):
    runtime.closed.status = status
    assert (
        await projection.reconcile_native(
            runtime.conn, 'owner/repo', runtime.task, 'base'
        )
        == runtime.task
    )
    runtime.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_followup_prompt_keeps_issue_dod_and_ci_instruction(monkeypatch):
    """A clarification must not replace the issue's original requirements."""

    create = AsyncMock(
        return_value={
            'id': 7,
            'html_url': 'https://forge.example/o/r/agent/tasks/7',
        }
    )
    monkeypatch.setattr(projection.native, 'create_task', create)
    monkeypatch.setattr(projection.native, 'update_task', AsyncMock())
    monkeypatch.setattr(
        hooks, 'resolve_task_target', AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        hooks, '_ensure_workspace', AsyncMock(return_value='ws')
    )
    monkeypatch.setattr(hooks, '_token', lambda: 'test-credential')
    monkeypatch.setattr(
        config, 'temporal_settings', lambda: SimpleNamespace(enabled=True)
    )
    monkeypatch.setattr(
        client,
        'start_forgejo_workflow',
        AsyncMock(return_value='forgejo-agent-task-7'),
    )
    monkeypatch.setattr(pool, 'create_and_dispatch_task', AsyncMock())
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    await effects.dispatch(
        {
            'repo': 'o/r',
            'number': 5853,
            'is_pr': False,
            'comment_id': 17509,
            'repo_data': {},
            'body': (
                '@codetether update code and validate using Forgejo Actions'
            ),
            'issue': {
                'title': 'Cargo workspace pilot',
                'body': 'Implement tools/test-console; preserve binary names',
            },
        },
        'https://forge.example/api/v1',
        {
            'repo_data': {'clone_url': 'https://forge.example/o/r.git'},
            'default_branch': 'main',
            'branch': 'main',
            'head_sha': '',
        },
    )
    prompt = create.await_args.kwargs['prompt']
    assert 'Implement tools/test-console; preserve binary names' in prompt
    assert 'validate using Forgejo Actions' in prompt
    assert 'Reuse its existing remote branch and PR' in prompt
    assert 'lack of a local compiler is not by itself a blocker' in prompt


@pytest.mark.asyncio
async def test_live_related_task_blocks_projection(runtime):
    runtime.conn.fetchval.return_value = 'still-running-task'
    await projection.reconcile_native(
        runtime.conn, 'owner/repo', runtime.task, 'base'
    )
    runtime.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_restart_race_does_not_overwrite_new_run(runtime):
    runtime.handle.describe.side_effect = [
        runtime.closed,
        SimpleNamespace(run_id='run-b', status=Status.RUNNING),
    ]
    await projection.reconcile_native(
        runtime.conn, 'owner/repo', runtime.task, 'base'
    )
    runtime.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_native_state_is_preserved(runtime):
    runtime.get.return_value = {**runtime.task, 'status': 'pending'}
    result = await projection.reconcile_native(
        runtime.conn, 'owner/repo', runtime.task, 'base'
    )
    assert result['status'] == 'pending'
    runtime.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_unavailable_temporal_fails_closed(runtime):
    runtime.handle.describe.side_effect = TimeoutError()
    assert (
        await projection.reconcile_native(
            runtime.conn, 'owner/repo', runtime.task, 'base'
        )
        == runtime.task
    )
    runtime.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_terminal_native_state_needs_no_remote_calls(runtime):
    runtime.task['status'] = 'completed'
    await projection.reconcile_native(
        runtime.conn, 'owner/repo', runtime.task, 'base'
    )
    runtime.handle.describe.assert_not_awaited()
    runtime.update.assert_not_awaited()
