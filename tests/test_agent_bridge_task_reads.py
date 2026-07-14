"""Regression coverage for PostgreSQL-primary task detail reads."""

import pytest

from a2a_server.agent_bridge import AgentBridge, AgentTask, AgentTaskStatus


@pytest.mark.asyncio
async def test_get_task_refreshes_stale_replica_cache_from_database(monkeypatch):
    bridge = AgentBridge(auto_start=False)
    cached = AgentTask(
        id='task-review',
        codebase_id='global',
        title='review',
        prompt='review prompt',
    )
    bridge._tasks[cached.id] = cached
    bridge._codebase_tasks['global'] = [cached.id]
    assert cached.status == AgentTaskStatus.PENDING

    database_row = cached.to_dict()
    database_row.update(
        {
            'workspace_id': 'global',
            'status': 'completed',
            'result': 'review complete',
        }
    )

    async def completed_task(task_id):
        assert task_id == cached.id
        return database_row

    monkeypatch.setattr(
        'a2a_server.agent_bridge.db.db_get_task', completed_task
    )

    refreshed = await bridge.get_task(cached.id)

    assert refreshed is not None
    assert refreshed.status == AgentTaskStatus.COMPLETED
    assert refreshed.result == 'review complete'
    assert bridge._tasks[cached.id] is refreshed
