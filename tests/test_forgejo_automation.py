from types import SimpleNamespace

import pytest

from a2a_server import forgejo_automation as automation
from a2a_server import forgejo_task_completion
from a2a_server import forgejo_webhooks
from a2a_server.github_app.settings import TASK_PRIORITY


PR = {
    'number': 5,
    'state': 'open',
    'html_url': 'https://forge.example/owner/repo/pulls/5',
    'head': {
        'sha': 'abc123',
        'ref': 'feature',
        'repo': {
            'full_name': 'owner/repo',
            'clone_url': 'https://forge.example/owner/repo.git',
        },
    },
}


def review_task(verdict='CHANGES_REQUESTED: tests fail'):
    return {
        'id': 'review-1',
        'status': 'completed',
        'result': verdict,
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'review',
            'workspace_id': 'ws1',
            'repo': 'owner/repo',
            'issue_number': 5,
            'pr_number': 5,
            'branch_name': 'feature',
            'pr_head_sha': 'abc123',
            'forgejo_api_url': 'https://forge.example/api/v1',
            'forgejo_issue_url': PR['html_url'],
            'target_agent_name': 'harvester',
            'required_capabilities': ['persistent-workspace'],
        },
    }


class Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        return None


class Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return Acquire(self.connection)


def install_database(monkeypatch, connection, *, task=None):
    async def get_pool():
        return Pool(connection)

    async def db_get_task(task_id):
        assert task_id == 'review-1'
        return task

    monkeypatch.setattr('a2a_server.database.get_pool', get_pool, raising=False)
    monkeypatch.setattr(
        'a2a_server.database.db_get_task', db_get_task, raising=False
    )


@pytest.mark.asyncio
async def test_publish_review_is_semantic_and_idempotent(monkeypatch):
    calls = []

    async def fake_json(method, base, path, payload=None):
        calls.append((method, base, path, payload))
        if method == 'GET':
            return []
        return {'id': 44}

    monkeypatch.setattr(automation, 'forgejo_json', fake_json)
    result = await automation.publish_forgejo_review(review_task())
    assert result == {
        'published': True,
        'duplicate': False,
        'event': 'REQUEST_CHANGES',
        'review_id': 44,
    }
    assert calls[1][3]['event'] == 'REQUEST_CHANGES'
    assert calls[1][3]['commit_id'] == 'abc123'
    assert automation.review_marker('review-1') in calls[1][3]['body']

    calls.clear()

    async def existing(method, base, path, payload=None):
        calls.append(method)
        return [
            {
                'id': 44,
                'state': 'REQUEST_CHANGES',
                'body': automation.review_marker('review-1'),
            }
        ]

    monkeypatch.setattr(automation, 'forgejo_json', existing)
    duplicate = await automation.publish_forgejo_review(review_task())
    assert duplicate['duplicate'] is True
    assert calls == ['GET']


@pytest.mark.asyncio
async def test_review_request_rejects_bots_and_requests_human(monkeypatch):
    calls = []

    async def fake_json(*args):
        calls.append(args)
        return []

    monkeypatch.setattr(automation, 'forgejo_json', fake_json)
    assert not await automation.request_forgejo_review(
        base='https://forge.example/api/v1',
        repo='owner/repo',
        pr_number=5,
        reviewer='codetether-bot',
    )
    assert await automation.request_forgejo_review(
        base='https://forge.example/api/v1',
        repo='owner/repo',
        pr_number=5,
        reviewer='alice',
    )
    assert calls[0][3] == {'reviewers': ['alice']}


@pytest.mark.asyncio
async def test_changes_requested_creates_exactly_one_fix(monkeypatch):
    dispatched = []

    class Connection:
        async def fetchrow(self, query, *params):
            assert "workflow_stage' = 'fix'" in query
            return {
                'attempts': 0,
                'active': False,
                'review_already_handled': False,
            }

    install_database(monkeypatch, Connection())

    async def fake_json(method, base, path, payload=None):
        assert method == 'GET'
        return PR

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'fix-1'

    monkeypatch.setattr(automation, 'forgejo_json', fake_json)
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    task_id = await automation.create_forgejo_fix_followup(review_task())
    assert task_id == 'fix-1'
    assert dispatched[0]['priority'] == TASK_PRIORITY
    assert dispatched[0]['metadata']['fix_followup'] == 'true'
    assert dispatched[0]['metadata']['review_task_id'] == 'review-1'

    class ActiveConnection:
        async def fetchrow(self, query, *params):
            return {
                'attempts': 1,
                'active': True,
                'review_already_handled': False,
            }

    install_database(monkeypatch, ActiveConnection())
    assert await automation.create_forgejo_fix_followup(review_task()) is None
    assert len(dispatched) == 1

    class CompletedSameReviewConnection:
        async def fetchrow(self, query, *params):
            assert params[-1] == 'review-1'
            return {
                'attempts': 1,
                'active': False,
                'review_already_handled': True,
            }

    install_database(monkeypatch, CompletedSameReviewConnection())
    assert await automation.create_forgejo_fix_followup(review_task()) is None
    assert len(dispatched) == 1


@pytest.mark.asyncio
async def test_failed_third_party_status_creates_deduped_fix(monkeypatch):
    dispatched = []

    class Connection:
        async def fetchrow(self, query, *params):
            assert "forgejo_work_key'" in query
            return None

    install_database(monkeypatch, Connection())

    async def fake_ensure(ctx, clone_url, branch, token):
        assert (ctx['repo'], branch, token) == (
            'owner/repo',
            'feature',
            'token',
        )
        return 'ws-status'

    async def fake_target():
        return {
            'target_agent_name': 'harvester',
            'required_capabilities': ['persistent-workspace'],
        }

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'status-fix-1'

    monkeypatch.setattr(forgejo_webhooks, '_ensure_workspace', fake_ensure)
    monkeypatch.setattr(forgejo_webhooks, '_token', lambda: 'token')
    monkeypatch.setattr(
        'a2a_server.github_app.routing.resolve_task_target', fake_target
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    status = {
        'status': 'failure',
        'context': 'tests',
        'description': 'unit tests failed',
        'target_url': 'https://forge.example/actions/1',
        'creator': {'login': 'forgejo-actions'},
    }
    task_id = await automation.create_status_remediation_task(
        base='https://forge.example/api/v1',
        repo='owner/repo',
        pr=PR,
        status=status,
    )
    assert task_id == 'status-fix-1'
    assert dispatched[0]['workspace_id'] == 'ws-status'
    assert dispatched[0]['priority'] == TASK_PRIORITY
    assert dispatched[0]['metadata']['forgejo_status_context'] == 'tests'

    self_status = {**status, 'creator': {'login': 'codetether-bot'}}
    assert (
        await automation.create_status_remediation_task(
            base='https://forge.example/api/v1',
            repo='owner/repo',
            pr=PR,
            status=self_status,
        )
        is None
    )
    assert len(dispatched) == 1


@pytest.mark.asyncio
async def test_code_completion_creates_review_and_terminal_comment(monkeypatch):
    calls = []

    async def fake_review(task):
        assert task['id'] == 'code-1'
        return 'review-1'

    async def fake_json(method, base, path, payload=None):
        calls.append((method, path, payload))
        return [] if method == 'GET' else {'id': 1}

    monkeypatch.setattr(
        forgejo_task_completion, 'create_forgejo_review_task', fake_review
    )
    monkeypatch.setattr(forgejo_task_completion, 'forgejo_json', fake_json)
    task = {
        'id': 'code-1',
        'status': 'completed',
        'result': 'Pushed abc123.',
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'code',
            'workspace_id': 'ws1',
            'repo': 'owner/repo',
            'issue_number': 5,
            'pr_number': 5,
            'forgejo_api_url': 'https://forge.example/api/v1',
        },
    }
    await forgejo_task_completion.notify_forgejo_task_completion(task)
    assert [call[0] for call in calls] == ['GET', 'POST']
    assert 'Queued review task `review-1`' in calls[1][2]['body']


@pytest.mark.asyncio
async def test_review_completion_publishes_and_queues_fix_once(monkeypatch):
    calls = []
    reconciled = []

    async def fake_publish(task):
        return {'event': 'REQUEST_CHANGES', 'review_id': 44}

    async def fake_fix(task):
        return 'fix-1'

    async def fake_mark(task_id):
        reconciled.append(task_id)

    async def fake_json(method, base, path, payload=None):
        calls.append((method, path, payload))
        return [] if method == 'GET' else {'id': 1}

    monkeypatch.setattr(
        forgejo_task_completion, 'publish_forgejo_review', fake_publish
    )
    monkeypatch.setattr(
        forgejo_task_completion, 'create_forgejo_fix_followup', fake_fix
    )
    monkeypatch.setattr(
        forgejo_task_completion, '_mark_review_reconciled', fake_mark
    )
    monkeypatch.setattr(forgejo_task_completion, 'forgejo_json', fake_json)
    await forgejo_task_completion.notify_forgejo_task_completion(review_task())
    assert reconciled == ['review-1']
    assert (
        'Published Forgejo review event `REQUEST_CHANGES`'
        in calls[1][2]['body']
    )
    assert 'Queued fix follow-up task `fix-1`' in calls[1][2]['body']


@pytest.mark.asyncio
async def test_issue_code_completion_discovers_created_pr_by_branch(
    monkeypatch,
):
    dispatched = []

    class Connection:
        async def fetchrow(self, query, *params):
            return None

    install_database(monkeypatch, Connection())

    async def fake_json(method, base, path, payload=None):
        assert method == 'GET'
        assert 'state=open' in path
        return [PR]

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'review-issue-pr'

    async def fake_request(**kwargs):
        return True

    monkeypatch.setattr(automation, 'forgejo_json', fake_json)
    monkeypatch.setattr(automation, 'request_forgejo_review', fake_request)
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    code_task = {
        'id': 'code-issue-1',
        'status': 'completed',
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'code',
            'workspace_id': 'ws1',
            'repo': 'owner/repo',
            'issue_number': 12,
            'pr_number': None,
            'branch_name': 'feature',
            'forgejo_api_url': 'https://forge.example/api/v1',
            'trigger_actor_login': 'alice',
        },
    }
    task_id = await automation.create_forgejo_review_task(code_task)
    assert task_id == 'review-issue-pr'
    assert dispatched[0]['metadata']['pr_number'] == 5
    assert dispatched[0]['metadata']['pr_head_sha'] == 'abc123'
    assert dispatched[0]['priority'] == TASK_PRIORITY

    created = []

    async def fake_create_review(task):
        created.append(task['id'])
        return 'review-issue-pr'

    async def fake_comment_json(method, base, path, payload=None):
        return [] if method == 'GET' else {'id': 1}

    monkeypatch.setattr(
        forgejo_task_completion,
        'create_forgejo_review_task',
        fake_create_review,
    )
    monkeypatch.setattr(
        forgejo_task_completion, 'forgejo_json', fake_comment_json
    )
    await forgejo_task_completion.notify_forgejo_task_completion(code_task)
    assert created == ['code-issue-1']


@pytest.mark.asyncio
async def test_forgejo_post_clone_uses_durable_dispatch(monkeypatch):
    from a2a_server import post_clone_followup

    dispatched = []
    bridge = SimpleNamespace()
    task = SimpleNamespace(
        agent_type='clone_repo',
        codebase_id='ws1',
        metadata={
            'source': 'forgejo-webhook',
            'post_clone_task': {
                'title': 'Work Forgejo PR #5',
                'prompt': 'fix it',
                'agent_type': 'build',
                'priority': TASK_PRIORITY,
                'model_ref': 'zai:glm-5.1',
                'metadata': {
                    'source': 'forgejo-webhook',
                    'forgejo_issue_url': PR['html_url'],
                    'forgejo_work_key': 'forgejo:owner/repo:5:code:abc123:9',
                },
            },
        },
    )

    async def get_task(task_id):
        assert task_id == 'clone-1'
        return task

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'code-1'

    bridge.get_task = get_task
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    queued = await post_clone_followup.enqueue_post_clone_followup(
        bridge, 'clone-1'
    )
    assert queued == 'code-1'
    assert dispatched[0]['priority'] == TASK_PRIORITY
    assert dispatched[0]['metadata']['forgejo_work_key'].endswith(':9')


def test_forgejo_work_key_is_first_class():
    from a2a_server.persistent_worker_pool import _github_work_key

    metadata = {
        'source': 'forgejo-webhook',
        'forgejo_work_key': 'forgejo:owner/repo:5:review:abc123',
    }
    assert _github_work_key(metadata) == metadata['forgejo_work_key']
