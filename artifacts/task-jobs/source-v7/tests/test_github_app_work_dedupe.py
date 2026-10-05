import sys
import types
from contextlib import asynccontextmanager

import pytest

from a2a_server import persistent_worker_pool as pool


def test_github_work_key_scopes_stage_and_head_sha():
    key = pool._github_work_key(
        {
            'source': 'github-app',
            'repo': 'owner/repo',
            'pr_number': 7,
            'workflow_stage': 'code',
            'pr_head_sha': 'abc123',
        }
    )

    assert key == 'github-app:owner/repo:7:code:abc123'


def test_github_work_key_falls_back_to_agent_type():
    key = pool._github_work_key(
        {
            'source': 'github-app',
            'repo': 'owner/repo',
            'issue_number': 8,
            'agent_type': 'clone_repo',
        }
    )

    assert key == 'github-app:owner/repo:8:clone_repo:'


@pytest.mark.asyncio
async def test_create_and_dispatch_reuses_existing_active_github_work(monkeypatch):
    class Bridge:
        def get_workspace(self, workspace_id):
            return {'id': workspace_id}

        async def create_task(self, **kwargs):
            raise AssertionError('duplicate path must not create a new task')

    @asynccontextmanager
    async def fake_lock(metadata):
        yield pool._github_work_key(metadata)

    async def fake_active_task(work_key):
        return 'existing-task'

    monkeypatch.setattr(pool, '_github_work_dedupe_lock', fake_lock)
    monkeypatch.setattr(pool, '_active_github_work_task_id', fake_active_task)

    monitor_api = types.ModuleType('a2a_server.monitor_api')
    monitor_api.get_agent_bridge = lambda: Bridge()
    monkeypatch.setitem(sys.modules, 'a2a_server.monitor_api', monitor_api)

    task_id = await pool.create_and_dispatch_task(
        workspace_id='workspace',
        title='Apply PR fix #7',
        prompt='fix it',
        agent_type='build',
        metadata={
            'source': 'github-app',
            'repo': 'owner/repo',
            'pr_number': 7,
            'workflow_stage': 'code',
            'pr_head_sha': 'abc123',
        },
    )

    assert task_id == 'existing-task'
