# ruff: noqa: SLF001
import os

from types import SimpleNamespace

import pytest


os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')

from a2a_server import agent_bridge
from a2a_server.agent_bridge import AgentBridge


@pytest.mark.asyncio
async def test_save_task_propagates_database_false(monkeypatch):
    records = []

    async def failed_upsert(task):
        records.append(task)
        return False

    monkeypatch.setattr(agent_bridge.db, 'db_upsert_task', failed_upsert)
    task = SimpleNamespace(
        metadata={'tenant_id': 'tenant-a'},
        model=None,
        model_ref=None,
        target_agent_name=None,
        model_used=None,
        id='task',
        codebase_id='global',
        title='title',
        prompt='prompt',
        agent_type='build',
        status=SimpleNamespace(value='pending'),
        priority=0,
        result=None,
        error=None,
        created_at=SimpleNamespace(isoformat=lambda: 'created'),
        started_at=None,
        completed_at=None,
    )
    assert await AgentBridge.__new__(AgentBridge)._save_task(task) is False
    assert records[0]['tenant_id'] == 'tenant-a'
