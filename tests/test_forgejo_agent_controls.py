from __future__ import annotations

import asyncio

import pytest

from a2a_server import forgejo_agent_client
from a2a_server import forgejo_agent_controls as controls
from a2a_server import persistent_worker_pool


def _task(status: str = 'running') -> dict:
    return {
        'id': 'codetether-1',
        'status': status,
        'workspace_id': 'workspace-1',
        'title': 'Fix issue 7',
        'prompt': 'Implement the fix',
        'agent_type': 'build',
        'priority': 100,
        'model_ref': 'zai:glm-5.1',
        'task_timeout_seconds': 604800,
        'metadata': {
            'source': 'forgejo-webhook',
            'repo': 'acme/widgets',
            'forgejo_api_url': 'https://forgejo.example/api/v1',
            'forgejo_agent_task_id': 42,
            'forgejo_work_key': 'forgejo:acme/widgets:7:code:abc',
        },
    }


@pytest.mark.asyncio
async def test_reconcile_cancelled_forgejo_task_cancels_codetether(
    monkeypatch,
):
    cancelled: list[str] = []

    async def fake_linked(limit):
        assert limit == 50
        return [_task('running')]

    async def fake_get(**kwargs):
        return {'id': 42, 'status': 'cancelled'}

    async def fake_cancel(task_id):
        cancelled.append(task_id)
        return True

    monkeypatch.setattr(controls, '_linked_tasks', fake_linked)
    monkeypatch.setattr(forgejo_agent_client, 'get_task', fake_get)
    monkeypatch.setattr(controls, '_cancel_codetether_task', fake_cancel)

    assert await controls.reconcile_forgejo_agent_controls() == 1
    assert cancelled == ['codetether-1']


@pytest.mark.asyncio
async def test_reconcile_pending_forgejo_task_retries_cancelled_codetether(
    monkeypatch,
):
    dispatched: list[dict] = []
    updates: list[dict] = []

    async def fake_linked(limit):
        return [_task('cancelled')]

    async def fake_get(**kwargs):
        return {'id': 42, 'status': 'pending'}

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'codetether-2'

    async def fake_update(**kwargs):
        updates.append(kwargs)
        return {'id': 42, 'status': 'accepted'}

    monkeypatch.setattr(controls, '_linked_tasks', fake_linked)
    monkeypatch.setattr(forgejo_agent_client, 'get_task', fake_get)
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', fake_dispatch
    )
    monkeypatch.setattr(forgejo_agent_client, 'update_task', fake_update)

    assert await controls.reconcile_forgejo_agent_controls() == 1
    assert len(dispatched) == 1
    assert dispatched[0]['workspace_id'] == 'workspace-1'
    assert dispatched[0]['metadata']['forgejo_retry_generation'] == 1
    assert dispatched[0]['metadata']['forgejo_retry_of'] == 'codetether-1'
    assert dispatched[0]['metadata']['forgejo_work_key'].endswith(':retry:1')
    assert updates == [
        {
            'repo': 'acme/widgets',
            'task_id': 42,
            'base_url': 'https://forgejo.example/api/v1',
            'status': 'accepted',
            'external_task_id': 'codetether-2',
        }
    ]


@pytest.mark.asyncio
async def test_reconcile_ignores_stale_codetether_stage(monkeypatch):
    cancelled: list[str] = []

    async def fake_linked(limit):
        return [_task('running')]

    async def fake_get(**kwargs):
        return {
            'id': 42,
            'status': 'cancelled',
            'external_task_id': 'newer-codetether-task',
        }

    async def fake_cancel(task_id):
        cancelled.append(task_id)
        return True

    monkeypatch.setattr(controls, '_linked_tasks', fake_linked)
    monkeypatch.setattr(forgejo_agent_client, 'get_task', fake_get)
    monkeypatch.setattr(controls, '_cancel_codetether_task', fake_cancel)

    assert await controls.reconcile_forgejo_agent_controls() == 0
    assert cancelled == []


@pytest.mark.asyncio
async def test_reconcile_fetches_tasks_with_bounded_concurrency(monkeypatch):
    active = 0
    maximum = 0
    tasks = []
    for index in range(16):
        task = _task('completed')
        task['id'] = f'codetether-{index}'
        task['metadata'] = {
            **task['metadata'],
            'forgejo_agent_task_id': index + 1,
        }
        tasks.append(task)

    async def fake_linked(limit):
        return tasks

    async def fake_get(*, task_id, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            'id': task_id,
            'status': 'completed',
            'external_task_id': f'codetether-{task_id - 1}',
        }

    monkeypatch.setattr(controls, '_linked_tasks', fake_linked)
    monkeypatch.setattr(forgejo_agent_client, 'get_task', fake_get)

    assert await controls.reconcile_forgejo_agent_controls() == 0
    assert 1 < maximum <= 8


@pytest.mark.asyncio
async def test_reconcile_matching_states_is_noop(monkeypatch):
    async def fake_linked(limit):
        return [_task('running')]

    async def fake_get(**kwargs):
        return {'id': 42, 'status': 'running'}

    monkeypatch.setattr(controls, '_linked_tasks', fake_linked)
    monkeypatch.setattr(forgejo_agent_client, 'get_task', fake_get)

    assert await controls.reconcile_forgejo_agent_controls() == 0
