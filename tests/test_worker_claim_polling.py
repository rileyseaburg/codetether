import asyncio
import os
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import a2a_server.agent_bridge as agent_bridge
import a2a_server.database as database
import a2a_server.monitor_api as monitor_api
import a2a_server.worker_sse as worker_sse
from a2a_server.worker_sse import WorkerRegistry, worker_sse_router


@pytest.fixture
def registry(monkeypatch):
    registry = WorkerRegistry()
    monkeypatch.setattr(worker_sse, '_worker_registry', registry)
    return registry


@pytest.mark.asyncio
async def test_pending_task_polling_hides_claimed_tasks(monkeypatch, registry):
    async def _fake_list_tasks(**kwargs):
        assert kwargs['status'] == 'pending'
        return [
            {'id': 'task_claimed', 'status': 'pending'},
            {'id': 'task_available', 'status': 'pending'},
        ]

    monkeypatch.setattr(monitor_api.db, 'db_list_tasks', _fake_list_tasks)

    await registry.register_worker(
        worker_id='worker_1',
        agent_name='agent-alpha',
        queue=asyncio.Queue(),
    )
    assert await registry.claim_task('task_claimed', 'worker_1')

    tasks = await monitor_api.list_all_tasks(status='pending')

    assert tasks == [{'id': 'task_available', 'status': 'pending'}]


@pytest.mark.asyncio
async def test_pending_task_polling_hides_targeted_tasks_from_unidentified_workers(
    monkeypatch,
):
    async def _fake_list_tasks(**kwargs):
        assert kwargs['status'] == 'pending'
        return [
            {
                'id': 'task_targeted_elsewhere',
                'status': 'pending',
                'metadata': {'target_worker_id': 'worker_2'},
            },
            {'id': 'task_available', 'status': 'pending', 'metadata': {}},
        ]

    monkeypatch.setattr(monitor_api.db, 'db_list_tasks', _fake_list_tasks)

    tasks = await monitor_api.list_all_tasks(status='pending')

    assert tasks == [
        {'id': 'task_available', 'status': 'pending', 'metadata': {}}
    ]


@pytest.mark.asyncio
async def test_pending_task_polling_includes_tasks_targeted_to_requesting_worker(
    monkeypatch,
):
    async def _fake_list_tasks(**kwargs):
        assert kwargs['status'] == 'pending'
        assert kwargs['worker_id'] == 'worker_2'
        return [
            {
                'id': 'task_targeted_here',
                'status': 'pending',
                'metadata': {'target_worker_id': 'worker_2'},
            },
            {
                'id': 'task_targeted_elsewhere',
                'status': 'pending',
                'metadata': {'target_worker_id': 'worker_3'},
            },
        ]

    monkeypatch.setattr(monitor_api.db, 'db_list_tasks', _fake_list_tasks)

    tasks = await monitor_api.list_all_tasks(
        status='pending', worker_id='worker_2'
    )

    assert tasks == [
        {
            'id': 'task_targeted_here',
            'status': 'pending',
            'metadata': {'target_worker_id': 'worker_2'},
        }
    ]


@pytest.mark.asyncio
async def test_claim_task_falls_back_to_db_when_bridge_update_misses(
    monkeypatch, registry
):
    class BridgeMiss:
        async def get_task(self, task_id):
            return None

        async def update_task_status(self, **kwargs):
            return None

    calls = []

    async def _fake_update_task_status(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(agent_bridge, 'get_bridge', lambda: BridgeMiss())
    monkeypatch.setattr(
        database, 'db_update_task_status', _fake_update_task_status
    )
    monkeypatch.setattr(
        worker_sse, '_claim_task_run_for_worker', AsyncMock(return_value={})
    )

    await registry.register_worker(
        worker_id='worker_1',
        agent_name='agent-alpha',
        queue=asyncio.Queue(),
    )

    app = FastAPI()
    app.include_router(worker_sse_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url='http://test'
    ) as client:
        response = await client.post(
            '/v1/worker/tasks/claim',
            headers={'X-Worker-ID': 'worker_1'},
            json={'task_id': 'task_claimed'},
        )

    assert response.status_code == 200
    assert calls == [
        {
            'task_id': 'task_claimed',
            'status': 'running',
            'worker_id': 'worker_1',
        }
    ]


@pytest.mark.asyncio
async def test_claim_task_returns_attached_task_run_metadata(
    monkeypatch, registry
):
    class BridgeMiss:
        async def get_task(self, task_id):
            return None

        async def update_task_status(self, **kwargs):
            return None

    async def _fake_update_task_status(**kwargs):
        return True

    async def _fake_claim_task_run(task_id, worker_id):
        assert task_id == 'task_claimed'
        assert worker_id == 'worker_1'
        return {
            'run_id': 'run_1',
            'task_timeout_seconds': 604800,
        }

    monkeypatch.setattr(agent_bridge, 'get_bridge', lambda: BridgeMiss())
    monkeypatch.setattr(
        database, 'db_update_task_status', _fake_update_task_status
    )
    monkeypatch.setattr(
        worker_sse, '_claim_task_run_for_worker', _fake_claim_task_run
    )

    await registry.register_worker(
        worker_id='worker_1',
        agent_name='agent-alpha',
        queue=asyncio.Queue(),
    )

    app = FastAPI()
    app.include_router(worker_sse_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url='http://test'
    ) as client:
        response = await client.post(
            '/v1/worker/tasks/claim',
            headers={'X-Worker-ID': 'worker_1'},
            json={'task_id': 'task_claimed'},
        )

    assert response.status_code == 200
    assert response.json()['run_id'] == 'run_1'
    assert response.json()['task_timeout_seconds'] == 604800


@pytest.mark.asyncio
async def test_claim_task_uses_db_worker_name_when_registry_misses(
    monkeypatch, registry
):
    class TargetedTask:
        codebase_id = 'global'
        target_agent_name = None
        metadata = {'target_agent_name': 'agent-alpha'}

    class Bridge:
        async def get_task(self, task_id):
            assert task_id == 'task_targeted'
            return TargetedTask()

    async def _fake_db_get_worker(worker_id):
        assert worker_id == 'worker_1'
        return {'name': 'agent-alpha'}

    monkeypatch.setattr(agent_bridge, 'get_bridge', lambda: Bridge())
    monkeypatch.setattr(database, 'db_get_worker', _fake_db_get_worker)

    assert await registry.claim_task('task_targeted', 'worker_1') is True
    assert registry._claimed_tasks['task_targeted'] == 'worker_1'


@pytest.mark.asyncio
async def test_claim_task_rejects_worker_missing_required_capability(
    monkeypatch, registry
):
    class PersistentTask:
        codebase_id = 'global'
        target_agent_name = None
        metadata = {'required_capabilities': ['persistent']}

    class Bridge:
        async def get_task(self, task_id):
            assert task_id == 'task_persistent'
            return PersistentTask()

    monkeypatch.setattr(agent_bridge, 'get_bridge', lambda: Bridge())

    await registry.register_worker(
        worker_id='worker_knative',
        agent_name='knative-worker',
        queue=asyncio.Queue(),
        capabilities=['knative'],
    )

    assert (
        await registry.claim_task('task_persistent', 'worker_knative')
        is False
    )
    assert 'task_persistent' not in registry._claimed_tasks


@pytest.mark.asyncio
async def test_notify_uses_metadata_required_capabilities(registry):
    await registry.register_worker(
        worker_id='worker_knative',
        agent_name='knative-worker',
        queue=asyncio.Queue(),
        capabilities=['knative'],
    )
    persistent_queue = asyncio.Queue()
    await registry.register_worker(
        worker_id='worker_persistent',
        agent_name='persistent-worker',
        queue=persistent_queue,
        capabilities=['persistent'],
    )

    notified = await worker_sse.notify_workers_of_new_task(
        {
            'id': 'task_persistent',
            'codebase_id': 'global',
            'metadata': {'required_capabilities': ['persistent']},
        }
    )

    assert notified == ['worker_persistent']


@pytest.mark.asyncio
async def test_release_task_accepts_db_claim_when_local_registry_misses(
    monkeypatch, registry
):
    class Bridge:
        async def update_task_status(self, **kwargs):
            updates.append(kwargs)
            return object()

    updates = []

    monkeypatch.setattr(agent_bridge, 'get_bridge', lambda: Bridge())
    monkeypatch.setattr(
        worker_sse,
        '_db_claim_allows_release',
        AsyncMock(return_value=True),
    )

    app = FastAPI()
    app.include_router(worker_sse_router)
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url='http://test'
    ) as client:
        response = await client.post(
            '/v1/worker/tasks/release',
            headers={'X-Worker-ID': 'worker_1'},
            json={'task_id': 'task_claimed', 'status': 'running'},
        )

    assert response.status_code == 200
    assert response.json()['success'] is True
    assert updates == [
        {
            'task_id': 'task_claimed',
            'status': agent_bridge.AgentTaskStatus.RUNNING,
            'result': None,
            'error': None,
            'worker_id': 'worker_1',
        }
    ]


@pytest.mark.asyncio
async def test_claim_task_run_helper_matches_deployed_schema(monkeypatch):
    seen = {}

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    class FakeConnection:
        async def fetchrow(self, sql, *params):
            seen['sql'] = sql
            seen['params'] = params
            return {
                'run_id': 'run_1',
                'task_id': 'task_claimed',
                'user_id': 'user_1',
                'tenant_id': 'tenant_1',
                'dispatch_mode': 'fire_and_forget',
                'task_timeout_seconds': 604800,
                'github_issue_url': None,
                'checkpoint': None,
                'checkpoint_seq': 0,
                'resume_attempt': 0,
            }

    async def _fake_get_pool():
        return FakePool()

    monkeypatch.setattr(database, 'get_pool', _fake_get_pool)

    result = await worker_sse._claim_task_run_for_worker(
        'task_claimed',
        'worker_1',
    )

    assert result['run_id'] == 'run_1'
    assert result['task_timeout_seconds'] == 604800
    assert seen['params'][:2] == ('task_claimed', 'worker_1')
    assert "t.metadata->>'target_worker_id'" in seen['sql']
    assert 'provider_keys' not in seen['sql']
    assert 'provider_key_source' not in seen['sql']


@pytest.mark.asyncio
async def test_pending_task_query_keeps_fire_and_forget_tasks_visible(
    monkeypatch,
):
    seen = {}

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    class FakeConnection:
        async def fetch(self, sql, *params):
            seen['sql'] = sql
            seen['params'] = params
            return []

    async def _fake_get_pool():
        return FakePool()

    monkeypatch.setattr(database, 'get_pool', _fake_get_pool)

    tasks = await database.db_list_tasks(
        status='pending',
        agent_name='agent-alpha',
        limit=25,
    )

    assert tasks == []
    assert seen['params'] == (
        'pending',
        'agent-alpha',
        'agent-alpha',
        'agent-alpha',
        25,
    )
    assert "metadata->>'target_agent_name' = $3" in seen['sql']
    assert "dispatch_mode != 'fire_and_forget'" in seen['sql']
    assert 'task_runs tr' in seen['sql']


@pytest.mark.asyncio
async def test_worker_stream_headers_disable_proxy_transforms(registry):
    request = Request(
        {
            'type': 'http',
            'method': 'GET',
            'path': '/v1/worker/tasks/stream',
            'headers': [],
            'query_string': b'',
            'client': ('testclient', 50000),
            'server': ('testserver', 80),
            'scheme': 'http',
        }
    )

    response = await worker_sse.worker_task_stream(
        request,
        agent_name='agent-alpha',
        worker_id='worker_1',
        x_agent_name=None,
        x_worker_id=None,
        x_capabilities=None,
        x_codebases=None,
    )

    assert response.headers['cache-control'] == 'no-cache, no-transform'
    assert response.headers['x-accel-buffering'] == 'no'
