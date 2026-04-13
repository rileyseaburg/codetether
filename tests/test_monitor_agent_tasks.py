import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/a2a_server',
)

from a2a_server import monitor_api, worker_sse


@pytest.mark.asyncio
async def test_create_agent_task_uses_durable_workspace(monkeypatch):
    bridge = SimpleNamespace(
        get_workspace=lambda _workspace_id: None,
        create_task=AsyncMock(
            return_value=SimpleNamespace(
                id='task-1',
                to_dict=lambda: {'id': 'task-1'},
            )
        ),
    )
    decision = SimpleNamespace(
        complexity='simple',
        model_tier='fast',
        model_ref='bedrock:test-model',
        target_agent_name=None,
        worker_personality=None,
    )
    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: bridge)
    monkeypatch.setattr(
        monitor_api, '_rehydrate_workspace_into_bridge', AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        monitor_api.db,
        'db_get_workspace',
        AsyncMock(return_value={'id': 'ws-1', 'name': 'Durable Workspace'}),
    )
    monkeypatch.setattr(
        monitor_api, '_redis_get_workspace_meta', AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        monitor_api,
        'orchestrate_task_route',
        lambda **_kwargs: (decision, {'model_ref': decision.model_ref}),
    )
    monkeypatch.setattr(
        monitor_api, '_validate_target_worker_is_available', AsyncMock()
    )
    monkeypatch.setattr(monitor_api.monitoring_service, 'log_message', AsyncMock())

    result = await monitor_api.create_agent_task(
        'ws-1',
        monitor_api.AgentTaskCreate(title='t', prompt='p'),
    )

    assert result['success'] is True
    bridge.create_task.assert_awaited_once()
    assert bridge.create_task.await_args.kwargs['codebase_id'] == 'ws-1'


@pytest.mark.asyncio
async def test_target_worker_kept_for_recent_heartbeat_without_sse(monkeypatch):
    class RegistryStub:
        async def list_workers(self):
            return []

    monkeypatch.setattr(
        monitor_api, '_get_registered_worker', AsyncMock(return_value={
            'worker_id': 'wrk-harvester',
            'status': 'active',
            'last_seen': '2026-03-17T15:00:00+00:00',
        })
    )
    monkeypatch.setattr(
        monitor_api, '_is_recent_heartbeat', lambda value, max_age_seconds=120: bool(value)
    )
    monkeypatch.setattr(
        worker_sse,
        'get_worker_registry',
        lambda: RegistryStub(),
    )

    metadata = {'target_worker_id': 'wrk-harvester'}

    await monitor_api._validate_target_worker_is_available(metadata)

    assert metadata['target_worker_id'] == 'wrk-harvester'
    assert '_routing_notice' in metadata
    assert '_routing_warning' not in metadata
