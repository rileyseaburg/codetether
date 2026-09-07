"""Mocked-local regression coverage for the task-row/run crash boundary."""
# ruff: noqa: SLF001

import asyncio
import copy
import sys

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import a2a_server

from a2a_server import persistent_worker_pool as worker


@pytest.fixture
def harness(monkeypatch):
    """Exercise the real reconciliation under a simulated advisory work lock."""
    state = {
        'task': {
            'status': 'pending',
            'worker_id': None,
            'started_at': None,
            'completed_at': None,
            'priority': 9,
            'tenant_id': 'tenant-1',
            'dispatch_mode': 'polling',
        },
        'runs': [],
        'calls': [],
        'locked': False,
        'transaction': False,
        'fail_once': False,
    }
    mutex = asyncio.Lock()

    @asynccontextmanager
    async def lock(metadata):
        async with mutex:
            state['locked'] = True
            try:
                yield worker._github_work_key(metadata)
            finally:
                state['locked'] = False

    class Connection:
        @asynccontextmanager
        async def transaction(self):
            assert state['locked']
            snapshot = copy.deepcopy((state['task'], state['runs']))
            state['transaction'] = True
            try:
                yield
            except BaseException:
                state['task'], state['runs'] = snapshot
                raise
            finally:
                state['transaction'] = False

        async def fetchrow(self, sql, task_id):
            assert state['transaction'] and state['locked']
            assert 'FOR UPDATE' in sql
            assert "metadata->>'source' = 'forgejo-webhook'" in sql
            assert task_id == 'existing-task'
            return state['task']

        async def fetchval(self, sql, *args):
            assert state['transaction'] and state['locked']
            state['calls'].append((sql, args))
            if 'SELECT EXISTS' in sql:
                assert 'WHERE task_id = $1' in sql
                assert (
                    'status' not in sql
                )  # Terminal runs also suppress inserts.
                return bool(state['runs'])
            assert sql.startswith('SELECT create_fire_and_forget_run(')
            await asyncio.sleep(0)
            state['runs'].append({'id': 'run-1', 'status': 'queued'})
            state['task']['dispatch_mode'] = 'fire_and_forget'
            if state['fail_once']:
                state['fail_once'] = False
                raise RuntimeError('run transaction failed')
            return 'run-1'

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()

    db = SimpleNamespace(get_pool=AsyncMock(return_value=Pool()))
    # Capture the real lazy package attribute before replacing sys.modules.
    monkeypatch.setattr(a2a_server, 'database', db, raising=False)
    monkeypatch.setitem(sys.modules, 'a2a_server.database', db)
    bridge = SimpleNamespace(
        get_workspace=lambda wid: {'id': wid},
        create_task=AsyncMock(
            side_effect=AssertionError('must reuse task row')
        ),
    )
    monitor = SimpleNamespace(get_agent_bridge=lambda: bridge)
    monkeypatch.setattr(a2a_server, 'monitor_api', monitor, raising=False)
    monkeypatch.setitem(sys.modules, 'a2a_server.monitor_api', monitor)
    monkeypatch.setattr(worker, '_github_work_dedupe_lock', lock)
    monkeypatch.setattr(
        worker,
        '_active_github_work_task_id',
        AsyncMock(return_value='existing-task'),
    )
    state['db'] = db
    return state


async def reuse(source='forgejo-webhook'):
    """Replay a delivery with different priority to check stored-value reuse."""
    return await worker.create_and_dispatch_task(
        workspace_id='workspace-1',
        title='Prepare issue',
        prompt='clone',
        agent_type='clone_repo',
        priority=1,
        task_timeout_seconds=9999999,
        github_issue_url='https://forge.example/o/r/issues/1',
        metadata={
            'source': source,
            'forgejo_work_key': 'forgejo:o/r:1:clone:main:0',
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'queued'])
@pytest.mark.parametrize('mode', ['polling', 'fire_and_forget'])
async def test_missing_run_repaired_once(harness, status, mode):
    harness['task'].update(status=status, dispatch_mode=mode)
    assert await reuse() == 'existing-task'
    assert await reuse() == 'existing-task'
    assert len(harness['runs']) == 1
    assert harness['task']['dispatch_mode'] == 'fire_and_forget'
    inserts = [
        args
        for sql, args in harness['calls']
        if 'create_fire_and_forget_run' in sql
    ]
    assert inserts == [
        (
            'existing-task',
            None,
            'tenant-1',
            9,
            worker.PERSISTENT_WORKER_MAX_TIMEOUT,
            'https://forge.example/o/r/issues/1',
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status', ['queued', 'running', 'completed', 'failed', 'cancelled']
)
async def test_any_existing_run_suppresses_creation(harness, status):
    harness['runs'] = [
        {'id': 'old-run', 'status': status, 'dispatch_mode': 'polling'}
    ]
    assert await reuse() == 'existing-task'
    assert len(harness['runs']) == 1
    assert not any(
        'create_fire_and_forget_run' in sql for sql, _ in harness['calls']
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'updates',
    [
        {'status': 'completed'},
        {'status': 'failed'},
        {'status': 'cancelled'},
        {'status': 'running'},
        {'status': 'working'},
        {'status': 'needs_input'},
        {'worker_id': 'worker-1'},
        {'started_at': 'started'},
        {'completed_at': 'ended'},
    ],
)
async def test_terminal_or_started_work_is_never_requeued(harness, updates):
    harness['task'].update(updates)
    assert await reuse() == 'existing-task'
    assert harness['runs'] == []
    assert harness['calls'] == []


@pytest.mark.asyncio
async def test_concurrent_replays_share_work_lock(harness):
    assert await asyncio.gather(reuse(), reuse()) == [
        'existing-task',
        'existing-task',
    ]
    assert len(harness['runs']) == 1


@pytest.mark.asyncio
async def test_failed_recovery_is_not_reported_as_success(harness):
    harness['fail_once'] = True
    with pytest.raises(RuntimeError, match='run transaction failed'):
        await reuse()
    assert harness['runs'] == []
    assert harness['task']['dispatch_mode'] == 'polling'
    assert await reuse() == 'existing-task'
    assert len(harness['runs']) == 1


@pytest.mark.asyncio
async def test_missing_task_fails_closed(harness):
    harness['task'] = None
    with pytest.raises(RuntimeError, match='task missing'):
        await reuse()


@pytest.mark.asyncio
async def test_missing_database_fails_closed(harness):
    harness['db'].get_pool.return_value = None
    with pytest.raises(RuntimeError, match='Database unavailable'):
        await reuse()


@pytest.mark.asyncio
async def test_github_dedupe_behavior_is_unchanged(harness):
    assert await reuse(source='github-app') == 'existing-task'
    harness['db'].get_pool.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_task_keeps_normal_dispatch_path(harness, monkeypatch):
    bridge = sys.modules['a2a_server.monitor_api'].get_agent_bridge()
    bridge.create_task.side_effect = None
    bridge.create_task.return_value = SimpleNamespace(id='new-task')
    monkeypatch.setattr(
        worker, '_active_github_work_task_id', AsyncMock(return_value=None)
    )
    dispatch = AsyncMock()
    monkeypatch.setattr(worker, 'dispatch_fire_and_forget', dispatch)
    assert await reuse() == 'new-task'
    bridge.create_task.assert_awaited_once()
    dispatch.assert_awaited_once()
    assert dispatch.call_args.kwargs['task_id'] == 'new-task'
    harness['db'].get_pool.assert_not_awaited()
