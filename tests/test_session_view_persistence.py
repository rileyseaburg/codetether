# ruff: noqa: I001

import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from a2a_server import agent_bridge


@pytest.mark.asyncio
async def test_save_task_persists_session_id_in_metadata(monkeypatch):
    captured = {}

    async def fake_upsert(value):
        captured.update(value)
        return True

    monkeypatch.setattr(agent_bridge.db, 'db_upsert_task', fake_upsert)
    bridge = object.__new__(agent_bridge.AgentBridge)
    now = datetime.utcnow()
    task = SimpleNamespace(
        id='task-1',
        codebase_id='workspace-1',
        title='Fix the issue',
        prompt='Please fix it',
        agent_type='build',
        status=agent_bridge.AgentTaskStatus.RUNNING,
        priority=0,
        result=None,
        error=None,
        metadata={'source': 'forgejo-webhook'},
        model=None,
        model_ref=None,
        target_agent_name=None,
        model_used=None,
        session_id='session-1',
        created_at=now,
        started_at=now,
        completed_at=None,
    )

    await agent_bridge.AgentBridge._save_task(bridge, task)

    assert captured['metadata']['session_id'] == 'session-1'
    assert captured['metadata']['source'] == 'forgejo-webhook'
