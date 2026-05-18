import os

import pytest

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

from a2a_server import git_service
from a2a_server.github_app import issue_prepare_completion
from a2a_server.github_app import pr_prepare_completion
from a2a_server.github_app import task_completion


@pytest.mark.asyncio
async def test_pr_prepare_task_creates_pr_followup(monkeypatch):
    calls = []

    async def fake_handle(task, worker_id=None):
        calls.append((task, worker_id))

    monkeypatch.setattr(task_completion, 'handle_pr_prepare_completion', fake_handle)

    task = {
        'title': 'Prepare PR workspace #40',
        'metadata': {'source': 'github-app', 'pr_number': 40},
    }
    await task_completion.notify_issue_task_completion(task, 'wrk_123')

    assert calls == [(task, 'wrk_123')]


@pytest.mark.asyncio
async def test_pr_build_task_posts_pr_final_comment(monkeypatch):
    calls = []

    async def fake_notify(task):
        calls.append(task)

    monkeypatch.setattr(task_completion, 'notify_pr_final_comment', fake_notify)

    task = {
        'title': 'Apply PR fix #40',
        'metadata': {'source': 'github-app', 'pr_number': 40},
    }
    await task_completion.notify_issue_task_completion(task)

    assert calls == [task]


@pytest.mark.asyncio
async def test_pr_prepare_completion_skips_duplicate_followup(monkeypatch):
    created = []

    async def fake_context(task):
        return ('rileyseaburg/codetether', 40, None, 'token')

    async def fake_claim(task_id):
        assert task_id == 'prepare-1'
        return False

    async def fake_create(**kwargs):
        created.append(kwargs)
        return 'apply-1'

    monkeypatch.setattr(
        pr_prepare_completion, 'github_app_task_context', fake_context
    )
    monkeypatch.setattr(
        pr_prepare_completion, '_claim_pr_followup_creation', fake_claim
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task', fake_create
    )

    task = {
        'id': 'prepare-1',
        'title': 'Prepare PR workspace #40',
        'status': 'completed',
        'metadata': {
            'source': 'github-app',
            'workspace_id': 'workspace-1',
            'post_clone_task': {
                'title': 'Apply PR fix #40',
                'prompt': 'fix it',
                'metadata': {'repo': 'rileyseaburg/codetether', 'pr_number': 40},
            },
        },
    }
    await pr_prepare_completion.handle_pr_prepare_completion(task, 'wrk_123')

    assert created == []


@pytest.mark.asyncio
async def test_pr_prepare_completion_records_followup_task(monkeypatch):
    created = []
    recorded = []

    async def fake_context(task):
        return ('rileyseaburg/codetether', 40, None, 'token')

    async def fake_claim(task_id):
        assert task_id == 'prepare-1'
        return True

    async def fake_record(task_id, followup_task_id):
        recorded.append((task_id, followup_task_id))

    async def fake_create(**kwargs):
        created.append(kwargs)
        return 'apply-1'

    monkeypatch.setattr(
        pr_prepare_completion, 'github_app_task_context', fake_context
    )
    monkeypatch.setattr(
        pr_prepare_completion, '_claim_pr_followup_creation', fake_claim
    )
    monkeypatch.setattr(
        pr_prepare_completion, '_record_pr_followup_task', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task', fake_create
    )

    task = {
        'id': 'prepare-1',
        'title': 'Prepare PR workspace #40',
        'status': 'completed',
        'metadata': {
            'source': 'github-app',
            'workspace_id': 'workspace-1',
            'github_issue_url': (
                'https://github.com/rileyseaburg/codetether/pull/40'
            ),
            'post_clone_task': {
                'title': 'Apply PR fix #40',
                'prompt': 'fix it',
                'metadata': {'repo': 'rileyseaburg/codetether', 'pr_number': 40},
            },
        },
    }
    await pr_prepare_completion.handle_pr_prepare_completion(task, 'wrk_123')

    assert created[0]['title'] == 'Apply PR fix #40'
    assert created[0]['metadata']['target_worker_id'] == 'wrk_123'
    assert recorded == [('prepare-1', 'apply-1')]


@pytest.mark.asyncio
async def test_issue_prepare_completion_records_followup_task(monkeypatch):
    created = []
    recorded = []

    async def fake_context(task):
        return ('rileyseaburg/codetether', 39, 'codetether/issue-39', 'token')

    async def fake_claim(task_id):
        assert task_id == 'prepare-issue-1'
        return True

    async def fake_record(task_id, followup_task_id):
        recorded.append((task_id, followup_task_id))

    async def fake_create(**kwargs):
        created.append(kwargs)
        return 'work-issue-1'

    monkeypatch.setattr(issue_prepare_completion, 'issue_task_context', fake_context)
    monkeypatch.setattr(issue_prepare_completion, '_claim_pr_followup_creation', fake_claim)
    monkeypatch.setattr(issue_prepare_completion, '_record_pr_followup_task', fake_record)
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task', fake_create
    )

    task = {
        'id': 'prepare-issue-1',
        'title': 'Prepare issue workspace #39',
        'status': 'completed',
        'metadata': {
            'source': 'github-app',
            'workspace_id': 'workspace-issue-1',
            'github_issue_url': 'https://github.com/rileyseaburg/codetether/issues/39',
            'post_clone_task': {
                'title': 'Work issue #39',
                'prompt': 'fix it',
                'metadata': {'repo': 'rileyseaburg/codetether', 'issue_number': 39},
            },
        },
    }
    await issue_prepare_completion.handle_issue_prepare_completion(task, 'wrk_456')

    assert created[0]['title'] == 'Work issue #39'
    assert created[0]['metadata']['target_worker_id'] == 'wrk_456'
    assert recorded == [('prepare-issue-1', 'work-issue-1')]


@pytest.mark.asyncio
async def test_issue_prepare_completion_skips_duplicate_followup(monkeypatch):
    created = []

    async def fake_context(task):
        return ('rileyseaburg/codetether', 39, 'codetether/issue-39', 'token')

    async def fake_claim(task_id):
        assert task_id == 'prepare-issue-1'
        return False

    async def fake_create(**kwargs):
        created.append(kwargs)
        return 'work-issue-1'

    monkeypatch.setattr(issue_prepare_completion, 'issue_task_context', fake_context)
    monkeypatch.setattr(issue_prepare_completion, '_claim_pr_followup_creation', fake_claim)
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task', fake_create
    )

    task = {
        'id': 'prepare-issue-1',
        'title': 'Prepare issue workspace #39',
        'status': 'completed',
        'metadata': {
            'source': 'github-app',
            'workspace_id': 'workspace-issue-1',
            'post_clone_task': {
                'title': 'Work issue #39',
                'prompt': 'fix it',
                'metadata': {'repo': 'rileyseaburg/codetether', 'issue_number': 39},
            },
        },
    }
    await issue_prepare_completion.handle_issue_prepare_completion(task, 'wrk_456')

    assert created == []


@pytest.mark.asyncio
async def test_issue_prepare_task_still_uses_issue_followup(monkeypatch):
    calls = []

    async def fake_handle(task, worker_id=None):
        calls.append((task, worker_id))

    monkeypatch.setattr(task_completion, 'handle_issue_prepare_completion', fake_handle)

    task = {
        'title': 'Prepare issue workspace #39',
        'metadata': {'source': 'github-app', 'issue_number': 39},
    }
    await task_completion.notify_issue_task_completion(task, 'wrk_456')

    assert calls == [(task, 'wrk_456')]


@pytest.mark.asyncio
async def test_git_credentials_fall_back_to_workspace_github_app(monkeypatch):
    async def fake_get_git_credentials(workspace_id):
        assert workspace_id == 'ws_private'
        return None

    async def fake_db_get_workspace(workspace_id):
        assert workspace_id == 'ws_private'
        return {
            'git_url': 'https://github.com/rileyseaburg/spotlessbinco.git',
            'agent_config': {},
            'git_auth': {
                'github_app': {
                    'installation_id': '12345',
                }
            },
        }

    async def fake_installation_token(installation_id):
        assert installation_id == 12345
        return 'ghs_test_token', '2026-04-24T22:00:00Z'

    from a2a_server import database as db
    from a2a_server.github_app import auth

    monkeypatch.setattr(git_service, 'get_git_credentials', fake_get_git_credentials)
    monkeypatch.setattr(db, 'db_get_workspace', fake_db_get_workspace)
    monkeypatch.setattr(auth, 'installation_token', fake_installation_token)

    credentials = await git_service.issue_git_credentials(
        'ws_private',
        requested_host='github.com',
        requested_path='rileyseaburg/spotlessbinco.git',
    )

    assert credentials == {
        'username': 'x-access-token',
        'password': 'ghs_test_token',
        'expires_at': '2026-04-24T22:00:00Z',
        'token_type': 'github_app',
        'host': 'github.com',
        'path': 'rileyseaburg/spotlessbinco.git',
    }
