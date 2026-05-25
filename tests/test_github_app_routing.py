import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import a2a_server
from a2a_server.github_app import routing


def _recent_worker(worker_id, name, capabilities, *, hostname='node', is_busy=False):
    return {
        'worker_id': worker_id,
        'name': name,
        'capabilities': capabilities,
        'hostname': hostname,
        'is_busy': is_busy,
        'last_seen': datetime.now(timezone.utc).isoformat(),
        'last_heartbeat': datetime.now(timezone.utc).isoformat(),
    }


def _patch_database(monkeypatch, db_list_workers):
    fake_db = SimpleNamespace(db_list_workers=db_list_workers)
    monkeypatch.setitem(
        sys.modules,
        'a2a_server.database',
        fake_db,
    )
    monkeypatch.setattr(a2a_server, 'database', fake_db, raising=False)


@pytest.mark.asyncio
async def test_resolve_task_target_prefers_persistent_workspace_capability(monkeypatch):
    async def fake_workers(status):
        assert status == 'active'
        return [
            _recent_worker('wrk-knative', 'knative-worker', []),
            _recent_worker('wrk-harvester', 'harvester-a', ['persistent-workspace']),
        ]

    _patch_database(monkeypatch, fake_workers)
    monkeypatch.setattr(routing, 'TARGET_WORKER_ID', '')
    monkeypatch.setattr(routing, 'TARGET_AGENT', '')
    monkeypatch.setattr(routing, 'TARGET_CAPABILITIES', ('persistent-workspace',))
    monkeypatch.setattr(routing, 'PREFERRED_AGENTS', ('knative-worker',))

    assert await routing.resolve_task_target() == {
        'target_agent_name': 'harvester-a',
        'required_capabilities': ['persistent-workspace'],
    }


@pytest.mark.asyncio
async def test_resolve_task_target_uses_capability_metadata_when_no_worker(monkeypatch):
    async def fake_workers(status):
        return []

    _patch_database(monkeypatch, fake_workers)
    monkeypatch.setattr(routing, 'TARGET_WORKER_ID', '')
    monkeypatch.setattr(routing, 'TARGET_AGENT', '')
    monkeypatch.setattr(routing, 'TARGET_CAPABILITIES', ('persistent-workspace',))

    assert await routing.resolve_task_target() == {
        'required_capabilities': ['persistent-workspace']
    }


@pytest.mark.asyncio
async def test_resolve_task_target_preserves_configured_target_agent_with_capability(monkeypatch):
    async def fake_workers(status):
        return []

    _patch_database(monkeypatch, fake_workers)
    monkeypatch.setattr(routing, 'TARGET_WORKER_ID', '')
    monkeypatch.setattr(routing, 'TARGET_AGENT', 'knative-worker')
    monkeypatch.setattr(routing, 'TARGET_CAPABILITIES', ('persistent-workspace',))

    assert await routing.resolve_task_target() == {
        'target_agent_name': 'knative-worker',
        'required_capabilities': ['persistent-workspace'],
    }
