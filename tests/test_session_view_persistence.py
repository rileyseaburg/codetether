# ruff: noqa: I001, SLF001

import json
import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from a2a_server import agent_bridge, task_execution_persistence


@pytest.mark.asyncio
async def test_save_task_persists_session_id_in_metadata(monkeypatch):
    captured = {}
    projected = {}

    async def fake_upsert(value):
        captured.update(value)
        return True

    async def fake_persist(task_id, **kwargs):
        projected.update(task_id=task_id, **kwargs)
        return True

    monkeypatch.setattr(agent_bridge.db, 'db_upsert_task', fake_upsert)
    monkeypatch.setattr(agent_bridge, 'persist_task_execution', fake_persist)
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
        worker_id='worker-1',
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

    assert captured['worker_id'] == 'worker-1'
    assert captured['metadata']['session_id'] == 'session-1'
    assert captured['metadata']['source'] == 'forgejo-webhook'
    assert projected['task_id'] == 'task-1'
    assert projected['worker_id'] == 'worker-1'
    assert projected['metadata']['session_id'] == 'session-1'


@pytest.mark.asyncio
async def test_persist_task_execution_merges_worker_and_session_metadata(
    monkeypatch,
):
    captured = {}

    class Connection:
        async def execute(self, query, *params):
            captured['query'] = query
            captured['params'] = params
            return 'UPDATE 1'

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class Pool:
        def acquire(self):
            return Acquire()

    async def fake_pool():
        return Pool()

    monkeypatch.setattr(task_execution_persistence.db, 'get_pool', fake_pool)

    saved = await task_execution_persistence.persist_task_execution(
        'task-1',
        worker_id='worker-1',
        metadata={'source': 'forgejo-webhook', 'session_id': 'session-1'},
    )

    assert saved is True
    normalized_query = ' '.join(captured['query'].split())
    assert 'worker_id = COALESCE($2, worker_id)' in normalized_query
    assert (
        "metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb"
        in normalized_query
    )
    assert captured['params'][1] == 'worker-1'
    assert json.loads(captured['params'][2])['session_id'] == 'session-1'
