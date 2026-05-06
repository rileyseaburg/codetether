import asyncio
import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

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
