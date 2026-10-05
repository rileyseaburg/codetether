"""Mocked-local authorization and durable-output query contracts."""

import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

# Required at import time. All storage operations in this module are mocked.
os.environ.setdefault(
    'DATABASE_URL', 'postgresql://localhost/task_output_test'
)

from a2a_server import database, policy, task_output


def request_for(user=None, spiffe=None):
    request = Request({'type': 'http', 'headers': []})
    if user is not None:
        request.state.user = user
    if spiffe is not None:
        request.state.spiffe = SimpleNamespace(spiffe_id=spiffe)
    return request


@asynccontextmanager
async def transaction(**kwargs):
    yield


@pytest.fixture
def storage(monkeypatch):
    task = {
        'id': 'task-a', 'tenant_id': 'tenant-a',
        'worker_id': 'worker-a', 'status': 'running',
    }
    conn = SimpleNamespace(
        fetchrow=AsyncMock(return_value=task),
        fetchval=AsyncMock(return_value=1),
        execute=AsyncMock(), fetch=AsyncMock(return_value=[]),
        transaction=MagicMock(side_effect=transaction),
    )

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = SimpleNamespace(acquire=acquire)
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))
    enforce = AsyncMock()
    monkeypatch.setattr(policy, 'enforce_policy', enforce)
    return SimpleNamespace(conn=conn, task=task, enforce=enforce)


def chunk(worker_id='worker-a', event=None):
    return SimpleNamespace(
        worker_id=worker_id, output='hello', timestamp=None, event=event,
    )


@pytest.mark.asyncio
async def test_read_uses_verified_tenant_not_routing_state(storage):
    user = {'id': 'user-a', 'tenant_id': 'tenant-a', 'roles': ['viewer']}
    request = request_for(user)
    request.state.tenant_id = 'tenant-b'
    page = await task_output.read_output(request, 'task-a', 9)
    assert page['next_cursor'] == 9
    assert page['outputs'] == []
    storage.enforce.assert_awaited_once_with(
        user=user, action='task:read', resource=storage.task,
    )
    query, task_id, cursor = storage.conn.fetch.call_args.args
    assert 'WHERE task_id = $1 AND cursor > $2' in query
    assert 'ORDER BY cursor LIMIT 1001' in query
    assert (task_id, cursor) == ('task-a', 9)
    storage.conn.transaction.assert_called_once_with(isolation='repeatable_read')


@pytest.mark.asyncio
@pytest.mark.parametrize('user,status', [
    ({'tenant_id': 'tenant-b', 'roles': ['admin']}, 404),
    ({'roles': ['viewer']}, 403),
])
async def test_unauthorized_reads_never_fetch_output(storage, user, status):
    with pytest.raises(HTTPException) as exc:
        await task_output.read_output(request_for(user), 'task-a')
    assert exc.value.status_code == status
    storage.conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_task_returns_404(storage):
    storage.conn.fetchrow.return_value = None
    with pytest.raises(HTTPException) as exc:
        await task_output.read_output(request_for(), 'unknown')
    assert exc.value.status_code == 404
    storage.conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, RuntimeError('storage down')])
async def test_storage_outage_fails_closed(storage, monkeypatch, failure):
    monkeypatch.setattr(database, 'get_pool', AsyncMock(
        return_value=None, side_effect=failure,
    ))
    with pytest.raises(HTTPException) as exc:
        await task_output.read_output(request_for(), 'task-a')
    assert exc.value.status_code == 503
    storage.conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_cursor_replay_decodes_typed_events_and_pages(storage):
    event = {'type': 'tool.start', 'name': 'read'}
    storage.conn.fetch.return_value = [
        {'cursor': index, 'output': 'hello', 'timestamp': 'now',
         'worker_id': 'worker-a', 'event': json.dumps(event)}
        for index in range(100, 1101)
    ]
    page = await task_output.read_output(request_for(), 'task-a', 99)
    assert len(page['outputs']) == 1000
    assert page['has_more'] is True
    assert page['next_cursor'] == 1099
    assert page['outputs'][0]['event'] == event


@pytest.mark.asyncio
async def test_negative_cursor_is_rejected_before_storage(storage):
    with pytest.raises(HTTPException) as exc:
        await task_output.read_output(request_for(), 'task-a', -1)
    assert exc.value.status_code == 422
    storage.conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_append_rejects_unassigned_worker(storage):
    with pytest.raises(HTTPException) as exc:
        await task_output.append_output(request_for(), 'task-a', chunk('foreign'))
    assert exc.value.status_code == 403
    storage.conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['completed', 'failed', 'cancelled', 'pending'])
async def test_append_never_resurrects_nonrunning_tasks(storage, status):
    storage.task['status'] = status
    with pytest.raises(HTTPException) as exc:
        await task_output.append_output(request_for(), 'task-a', chunk())
    assert exc.value.status_code == 409
    storage.conn.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('binding', [None, 'spiffe://example/foreign'])
async def test_spiffe_append_requires_exact_durable_worker_binding(storage, binding):
    storage.conn.fetchval.return_value = binding
    with pytest.raises(HTTPException) as exc:
        await task_output.append_output(
            request_for(spiffe='spiffe://example/worker-a'), 'task-a', chunk(),
        )
    assert exc.value.status_code == 403
    storage.conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_append_commits_typed_event_under_task_lock(storage):
    event = {'type': 'tool.result', 'status': 'success'}
    receipt = await task_output.append_output(request_for(), 'task-a', chunk(event=event))
    assert receipt['cursor'] == 1
    assert 'FOR UPDATE' in storage.conn.fetchrow.call_args.args[0]
    insert = storage.conn.execute.call_args_list[0].args
    assert 'INSERT INTO task_output_chunks' in insert[0]
    assert insert[1:5] == ('task-a', 1, 'worker-a', 'hello')
    assert json.loads(insert[6]) == event
    assert 'UPDATE tasks' in storage.conn.execute.call_args_list[1].args[0]


@pytest.mark.asyncio
async def test_insert_failure_does_not_acknowledge_or_update_heartbeat(storage):
    storage.conn.execute.side_effect = RuntimeError('disk unavailable')
    with pytest.raises(HTTPException) as exc:
        await task_output.append_output(request_for(), 'task-a', chunk())
    assert exc.value.status_code == 503
    assert storage.conn.execute.await_count == 1