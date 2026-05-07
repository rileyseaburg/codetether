import os

import pytest

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import a2a_server.git_service as git_service
import a2a_server.monitor_api as monitor_api
import a2a_server.persistent_worker_pool as persistent_worker_pool


@pytest.mark.asyncio
async def test_git_workspace_registration_dispatches_persistent_clone(
    monkeypatch,
):
    dispatched = []
    upserted = []
    mirrored = []

    class FakeBridge:
        async def register_workspace(self, **kwargs):
            mirrored.append(kwargs)
            return {'id': kwargs['workspace_id']}

    async def _fake_db_upsert_workspace(workspace):
        upserted.append(workspace)

    async def _fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task_123'

    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: FakeBridge())
    monkeypatch.setattr(git_service, 'validate_git_url', lambda _: True)
    monkeypatch.setattr(
        git_service, 'store_git_credentials', lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        monitor_api.db, 'db_upsert_workspace', _fake_db_upsert_workspace
    )
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', _fake_dispatch
    )

    response = await monitor_api.register_workspace(
        monitor_api.WorkspaceRegistration(
            name='rileyseaburg/spotlessbinco',
            git_url='https://github.com/rileyseaburg/spotlessbinco.git',
            git_branch='feature/upsell-tripwire-enhancements',
        )
    )

    assert response['task_id'] == 'task_123'
    assert upserted[0]['status'] == 'cloning'
    assert mirrored[0]['workspace_id'] == response['workspace_id']
    assert dispatched == [
        {
            'workspace_id': response['workspace_id'],
            'title': 'Clone repository: rileyseaburg/spotlessbinco',
            'prompt': (
                'Clone Git repo '
                'https://github.com/rileyseaburg/spotlessbinco.git '
                '(branch: feature/upsell-tripwire-enhancements)'
            ),
            'agent_type': 'clone_repo',
            'metadata': {
                'git_url': 'https://github.com/rileyseaburg/spotlessbinco.git',
                'git_branch': 'feature/upsell-tripwire-enhancements',
                'workspace_id': response['workspace_id'],
            },
            'task_timeout_seconds': 604800,
        }
    ]
