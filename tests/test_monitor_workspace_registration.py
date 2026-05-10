import os
from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_worker_confirmed_git_workspace_does_not_dispatch_clone(
    monkeypatch,
):
    dispatched = []
    upserted = []
    redis_upserted = []
    log_messages = []

    class FakeWorkspace:
        id = 'ws_ready'

        def to_dict(self):
            return {
                'id': self.id,
                'name': 'rileyseaburg/spotlessbinco',
                'path': '/var/lib/codetether/repos/ws_ready',
                'description': '',
                'worker_id': 'wrk_ready',
                'agent_config': {},
            }

    class FakeBridge:
        async def register_workspace(self, **kwargs):
            assert kwargs['worker_id'] == 'wrk_ready'
            assert kwargs['workspace_id'] == 'ws_ready'
            return FakeWorkspace()

    async def _fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        raise AssertionError('worker-confirmed workspace must not queue clone')

    async def _fake_db_get_workspace(workspace_id):
        return None

    async def _fake_db_upsert_workspace(workspace):
        upserted.append(workspace)

    async def _fake_redis_upsert(workspace):
        redis_upserted.append(workspace)

    async def _fake_log_message(**kwargs):
        log_messages.append(kwargs)

    def _fail_git_validation(_):
        raise AssertionError('git validation should not run')

    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: FakeBridge())
    monkeypatch.setattr(git_service, 'validate_git_url', _fail_git_validation)
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', _fake_dispatch
    )
    monkeypatch.setattr(monitor_api.db, 'db_get_workspace', _fake_db_get_workspace)
    monkeypatch.setattr(
        monitor_api.db, 'db_upsert_workspace', _fake_db_upsert_workspace
    )
    monkeypatch.setattr(monitor_api, '_redis_upsert_workspace_meta', _fake_redis_upsert)
    monkeypatch.setattr(
        monitor_api.monitoring_service, 'log_message', _fake_log_message
    )

    response = await monitor_api.register_workspace(
        monitor_api.WorkspaceRegistration(
            name='rileyseaburg/spotlessbinco',
            workspace_id='ws_ready',
            path='/var/lib/codetether/repos/ws_ready',
            worker_id='wrk_ready',
            git_url='https://github.com/rileyseaburg/spotlessbinco.git',
            git_branch='main',
        )
    )

    assert response['success'] is True
    assert dispatched == []
    assert upserted[-1]['status'] == 'active'
    assert upserted[-1]['worker_id'] == 'wrk_ready'
    assert upserted[-1]['git_url'] == 'https://github.com/rileyseaburg/spotlessbinco.git'
    assert upserted[-1]['git_branch'] == 'main'
    assert redis_upserted[-1]['id'] == 'ws_ready'
    assert log_messages[-1]['metadata']['worker_id'] == 'wrk_ready'


@pytest.mark.asyncio
async def test_workspace_clone_task_endpoint_dispatches_persistent_clone(
    monkeypatch,
):
    dispatched = []
    log_messages = []

    class FakeBridge:
        def get_workspace(self, workspace_id):
            return SimpleNamespace(id=workspace_id, name='spotlessbinco')

        async def create_task(self, **kwargs):
            raise AssertionError('clone_repo endpoint must not create polling task')

    async def _fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task_456'

    async def _fake_db_get_task(task_id):
        return {'id': task_id, 'agent_type': 'clone_repo'}

    async def _fake_log_message(**kwargs):
        log_messages.append(kwargs)

    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: FakeBridge())
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', _fake_dispatch
    )
    monkeypatch.setattr(monitor_api.db, 'db_get_task', _fake_db_get_task)
    monkeypatch.setattr(
        monitor_api.monitoring_service, 'log_message', _fake_log_message
    )

    response = await monitor_api.create_agent_task(
        'ws_123',
        monitor_api.AgentTaskCreate(
            title='Clone repository: rileyseaburg/spotlessbinco',
            prompt=(
                'Clone Git repo '
                'https://github.com/rileyseaburg/spotlessbinco.git '
                '(branch: feature/upsell-tripwire-enhancements)'
            ),
            agent_type='clone_repo',
            metadata={
                'git_url': 'https://github.com/rileyseaburg/spotlessbinco.git',
                'git_branch': 'feature/upsell-tripwire-enhancements',
                'workspace_id': 'ws_123',
            },
        ),
    )

    assert response == {
        'success': True,
        'task': {'id': 'task_456', 'agent_type': 'clone_repo'},
    }
    assert len(dispatched) == 1
    dispatch = dispatched[0]
    assert dispatch['workspace_id'] == 'ws_123'
    assert dispatch['title'] == 'Clone repository: rileyseaburg/spotlessbinco'
    assert dispatch['prompt'] == (
        'Clone Git repo '
        'https://github.com/rileyseaburg/spotlessbinco.git '
        '(branch: feature/upsell-tripwire-enhancements)'
    )
    assert dispatch['agent_type'] == 'clone_repo'
    assert dispatch['priority'] == 0
    assert dispatch['model_ref'] is None
    assert dispatch['task_timeout_seconds'] == 604800
    assert dispatch['metadata']['git_url'] == (
        'https://github.com/rileyseaburg/spotlessbinco.git'
    )
    assert (
        dispatch['metadata']['git_branch']
        == 'feature/upsell-tripwire-enhancements'
    )
    assert dispatch['metadata']['workspace_id'] == 'ws_123'
    assert dispatch['metadata']['routing']['policy'] == 'a2a.task_orchestration.v1'
    assert [message['message_type'] for message in log_messages] == [
        'human',
        'system',
    ]


@pytest.mark.asyncio
async def test_github_app_worker_followup_endpoint_is_idempotent(
    monkeypatch,
):
    class FakeWorkspace:
        name = 'rileyseaburg/spotlessbinco'

    class FakeBridge:
        def get_workspace(self, workspace_id):
            assert workspace_id == 'ws_123'
            return FakeWorkspace()

        async def create_task(self, **kwargs):
            raise AssertionError(
                'GitHub App worker follow-up must not create polling task'
            )

    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: FakeBridge())

    response = await monitor_api.create_agent_task(
        'ws_123',
        monitor_api.AgentTaskCreate(
            title='Apply PR fix #515',
            prompt='Fix the PR comment',
            agent_type='build',
            metadata={
                'source': 'github-app',
                'github_issue_url': (
                    'https://github.com/rileyseaburg/spotlessbinco/pull/515'
                ),
                'target_worker_id': 'wrk_123',
                'workspace_id': 'ws_123',
            },
        ),
    )

    assert response == {
        'success': True,
        'skipped': True,
        'reason': 'github_app_terminal_hook_dispatches_followup',
    }


@pytest.mark.asyncio
async def test_global_clone_task_endpoint_dispatches_persistent_clone(
    monkeypatch,
):
    dispatched = []

    class FakeBridge:
        async def create_task(self, **kwargs):
            raise AssertionError('clone_repo endpoint must not create polling task')

    async def _fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task_789'

    async def _fake_db_get_task(task_id):
        return {'id': task_id, 'agent_type': 'clone_repo'}

    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: FakeBridge())
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', _fake_dispatch
    )
    monkeypatch.setattr(monitor_api.db, 'db_get_task', _fake_db_get_task)

    response = await monitor_api.create_global_task(
        monitor_api.AgentTaskCreate(
            title='Clone repository: rileyseaburg/spotlessbinco',
            prompt='Clone Git repo https://github.com/rileyseaburg/spotlessbinco.git',
            agent_type='clone_repo',
            workspace_id='ws_global',
            metadata={
                'git_url': 'https://github.com/rileyseaburg/spotlessbinco.git',
                'workspace_id': 'ws_global',
            },
        ),
    )

    assert response == {'id': 'task_789', 'agent_type': 'clone_repo'}
    assert len(dispatched) == 1
    dispatch = dispatched[0]
    assert dispatch['workspace_id'] == 'ws_global'
    assert dispatch['title'] == 'Clone repository: rileyseaburg/spotlessbinco'
    assert dispatch['prompt'] == (
        'Clone Git repo https://github.com/rileyseaburg/spotlessbinco.git'
    )
    assert dispatch['agent_type'] == 'clone_repo'
    assert dispatch['priority'] == 0
    assert dispatch['model_ref'] is None
    assert dispatch['task_timeout_seconds'] == 604800
    assert dispatch['metadata']['git_url'] == (
        'https://github.com/rileyseaburg/spotlessbinco.git'
    )
    assert dispatch['metadata']['workspace_id'] == 'ws_global'
    assert dispatch['metadata']['routing']['policy'] == 'a2a.task_orchestration.v1'


def test_harvester_worker_registration_gets_persistent_workspace_capability():
    capabilities = monitor_api._normalized_worker_capabilities(
        'harvester-a2a-server-harvester-0',
        ['ralph', 'a2a', 'ralph'],
    )

    assert capabilities[:2] == ['ralph', 'a2a']
    assert 'harvester' in capabilities
    assert 'persistent-workspace' in capabilities
    assert 'git-clone' in capabilities
    assert capabilities.count('ralph') == 1


def test_non_harvester_worker_capabilities_are_not_reclassified():
    capabilities = monitor_api._normalized_worker_capabilities(
        'knative-worker',
        ['ralph', 'knative'],
    )

    assert capabilities == ['ralph', 'knative']