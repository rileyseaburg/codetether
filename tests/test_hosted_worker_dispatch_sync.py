"""Regression tests for hosted-worker execution of dispatch tasks."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from a2a_server.hosted_worker import HostedWorker


class FakeConnection:
    def __init__(self, row=None, complete_result=True):
        self.row = row
        self.complete_result = complete_result
        self.fetchrow_calls = []
        self.fetchval_calls = []
        self.execute_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return self.row

    async def fetchval(self, query, *args):
        self.fetchval_calls.append((query, args))
        if 'complete_task_run' in query:
            return self.complete_result
        return True

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return 'UPDATE 1'


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)


def _worker(conn):
    return HostedWorker(
        worker_id='worker-1',
        db_pool=FakePool(conn),
        api_base_url='http://localhost:8000',
    )


@pytest.mark.asyncio
async def test_get_task_details_reads_workspace_id_schema_for_dispatch_task():
    row = {
        'id': 'task-1',
        'title': 'PR Review',
        'prompt': 'review diff',
        'agent_type': 'code-review',
        'workspace_id': None,
        'status': 'pending',
        'metadata': {'source': 'github-actions'},
        'created_at': None,
    }
    details = await _worker(FakeConnection(row=row))._get_task_details('task-1')

    assert details['codebase_id'] is None
    assert details['workspace_id'] is None
    assert details['metadata']['source'] == 'github-actions'


@pytest.mark.asyncio
async def test_complete_run_updates_canonical_task_for_action_polling():
    conn = FakeConnection()
    worker = _worker(conn)
    worker._current_task_id = 'task-1'

    await worker._complete_run(
        'run-1',
        status='completed',
        result_summary='review result',
        result_full={'result': 'full review'},
    )

    assert any('complete_task_run' in call[0] for call in conn.fetchval_calls)
    update_calls = [call for call in conn.execute_calls if 'UPDATE tasks SET' in call[0]]
    assert update_calls, 'canonical tasks row must be updated for /v1/tasks/dispatch polling'
    args = update_calls[0][1]
    assert args[:4] == ('task-1', 'completed', 'review result', None)


@pytest.mark.asyncio
async def test_run_llm_task_sandbox_path_has_exit_code(monkeypatch):
    conn = FakeConnection()
    worker = _worker(conn)
    monkeypatch.setattr(worker, '_find_agent_binary', lambda: '/bin/codetether')
    monkeypatch.setattr(worker, '_normalize_model', lambda model: model)
    monkeypatch.setattr(
        'a2a_server.sandbox.is_sandbox_available',
        lambda: True,
    )
    monkeypatch.setattr(
        'a2a_server.sandbox.execute_sandboxed',
        AsyncMock(return_value=(0, json.dumps({'type': 'text', 'part': {'text': 'ok'}}), '')),
    )

    result = await worker._run_llm_task('task-1', 'prompt', model='zai/glm-5.1')

    assert result['result'] == 'ok'
    assert result['exit_code'] == 0
