"""Regression coverage for GitHub Action server-mode dispatch tasks."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from a2a_server.automation_api import DispatchTaskRequest, dispatch_task


class FakeConnection:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self):
        self.conn = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.conn)


@pytest.mark.asyncio
async def test_dispatch_task_stores_github_action_review_as_null_workspace(monkeypatch):
    """Server-mode GitHub Action dispatches must not FK to a fake 'global' workspace."""
    pool = FakePool()
    monkeypatch.setattr('a2a_server.automation_api.get_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr('a2a_server.automation_api.KNATIVE_ENABLED', False)
    enqueue = AsyncMock(return_value=SimpleNamespace(id='run-1'))
    monkeypatch.setattr('a2a_server.automation_api.enqueue_task', enqueue)

    response = await dispatch_task(
        DispatchTaskRequest(
            title='PR Review: #12 Example',
            description='Review this diff from GitHub Actions.',
            agent_type='code-review',
            metadata={'source': 'github-actions', 'repo': 'acme/widget', 'pr_number': 12},
        ),
        http_request=SimpleNamespace(),
        user=SimpleNamespace(tenant_id='tenant-1', user_id='user-1'),
    )

    insert_calls = [
        call for call in pool.conn.execute_calls if 'INSERT INTO tasks' in call[0]
    ]
    assert insert_calls, 'dispatch_task should insert a task row'
    insert_args = insert_calls[0][1]

    # Parameter $5 maps to workspace_id in the INSERT statement. It must be SQL
    # NULL/None; using the string 'global' violates the workspaces FK in prod.
    assert insert_args[4] is None
    assert json.loads(insert_args[5])['source'] == 'github-actions'
    enqueue.assert_awaited_once()
    assert response.task_id.startswith('task-')
    assert response.status == 'pending'


@pytest.mark.asyncio
async def test_dispatch_task_falls_back_to_queue_when_knative_publish_raises(monkeypatch):
    """Knative broker errors must not surface as server-mode dispatch HTTP 500s."""
    import httpx

    pool = FakePool()
    monkeypatch.setattr('a2a_server.automation_api.get_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr('a2a_server.automation_api.KNATIVE_ENABLED', True)
    monkeypatch.setattr(
        'a2a_server.automation_api.dispatch_task_to_knative',
        AsyncMock(side_effect=httpx.ConnectError('broker unavailable')),
    )
    enqueue = AsyncMock(return_value=SimpleNamespace(id='run-1'))
    monkeypatch.setattr('a2a_server.automation_api.enqueue_task', enqueue)

    response = await dispatch_task(
        DispatchTaskRequest(
            title='PR Review: #12 Example',
            description='Review this diff from GitHub Actions.',
            agent_type='code-review',
            model='openai-codex/gpt-5.5',
            metadata={'source': 'github-actions', 'repo': 'acme/widget', 'pr_number': 12},
        ),
        http_request=SimpleNamespace(),
        user=SimpleNamespace(tenant_id='tenant-1', user_id='user-1'),
    )

    enqueue.assert_awaited_once()
    assert enqueue.await_args.kwargs['model_ref'] == 'openai-codex/gpt-5.5'
    assert response.task_id.startswith('task-')
    assert response.status == 'pending'
    assert response.event_id is None
    assert response.dispatched_via_knative is False
