"""Regression tests for attaching OpenCode session IDs to running tasks.

We want workers to be able to report the active OpenCode `session_id` while a
long-running task is executing, so UIs can deep-link into the live session and
fetch messages.

Two key requirements:
1) Bridge task timestamps are idempotent: repeated RUNNING updates must not
   reset `started_at`.
2) The API `PUT /v1/opencode/tasks/{task_id}/status` must accept `session_id`
   and persist it onto the task.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from a2a_server.opencode_bridge import OpenCodeBridge, AgentTaskStatus
from a2a_server.monitor_api import opencode_router
import a2a_server.monitor_api as monitor_api


@pytest.mark.asyncio
async def test_bridge_running_updates_preserve_started_at_and_set_session_id(
    tmp_path,
):
    bridge = OpenCodeBridge(
        auto_start=False, db_path=str(tmp_path / 'opencode.db')
    )

    cb = await bridge.register_codebase(
        name='test',
        path=str(tmp_path),
        description='',
        worker_id='wrk_test',
    )
    task = await bridge.create_task(codebase_id=cb.id, title='t', prompt='p')
    assert task is not None

    t1 = await bridge.update_task_status(
        task.id, status=AgentTaskStatus.RUNNING
    )
    assert t1 is not None
    started_at_1 = t1.started_at
    assert started_at_1 is not None

    t2 = await bridge.update_task_status(
        task.id,
        status=AgentTaskStatus.RUNNING,
        session_id='ses_test_123',
    )
    assert t2 is not None
    assert t2.session_id == 'ses_test_123'
    assert t2.started_at == started_at_1


@pytest_asyncio.fixture
async def client(monkeypatch):
    app = FastAPI()
    app.include_router(opencode_router)

    # Avoid Redis in tests.
    monkeypatch.delenv('A2A_REDIS_URL', raising=False)

    # Avoid writing monitoring messages during tests.
    async def _noop_log_message(*args, **kwargs):
        return None

    monkeypatch.setattr(
        monitor_api.monitoring_service, 'log_message', _noop_log_message
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac


@pytest.mark.asyncio
async def test_api_task_status_accepts_session_id_and_does_not_reset_started_at(
    tmp_path, monkeypatch, client
):
    bridge = OpenCodeBridge(
        auto_start=False, db_path=str(tmp_path / 'opencode.db')
    )
    cb = await bridge.register_codebase(
        name='test',
        path=str(tmp_path),
        description='',
        worker_id='wrk_test',
    )
    task = await bridge.create_task(codebase_id=cb.id, title='t', prompt='p')
    assert task is not None

    # Route API calls to our in-test bridge.
    monkeypatch.setattr(monitor_api, 'get_opencode_bridge', lambda: bridge)

    # Seed the worker registry so update_task_status doesn't need Redis.
    monitor_api._registered_workers['wrk_test'] = {
        'worker_id': 'wrk_test',
        'name': 'test-worker',
        'capabilities': [],
        'hostname': 'test',
        'registered_at': 'now',
        'last_seen': 'now',
        'status': 'active',
    }

    # First RUNNING update.
    resp1 = await client.put(
        f'/v1/opencode/tasks/{task.id}/status',
        json={'status': 'running', 'worker_id': 'wrk_test'},
    )
    assert resp1.status_code == 200

    # Capture started_at after first update.
    status1 = (await client.get(f'/v1/opencode/tasks/{task.id}')).json()
    started_1 = status1.get('started_at')
    assert started_1 is not None

    # Second RUNNING update attaches session_id.
    resp2 = await client.put(
        f'/v1/opencode/tasks/{task.id}/status',
        json={
            'status': 'running',
            'worker_id': 'wrk_test',
            'session_id': 'ses_test_456',
        },
    )
    assert resp2.status_code == 200

    status2 = (await client.get(f'/v1/opencode/tasks/{task.id}')).json()
    assert status2.get('session_id') == 'ses_test_456'
    assert status2.get('started_at') == started_1
