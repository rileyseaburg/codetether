# ruff: noqa: PLR2004, SLF001

import hashlib
import hmac
import json
import sys
import time

from types import SimpleNamespace

import pytest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from a2a_server import forgejo_webhooks as fw
from a2a_server.git_service import validate_git_url


def _payload(
    body='@codetether handle this issue', *, sender='alice', action='created'
):
    return {
        'action': action,
        'comment': {'id': 9, 'body': body, 'user': {'login': sender}},
        'issue': {
            'number': 12,
            'title': 'Broken widget',
            'body': 'The widget fails.',
            'html_url': 'https://forge.example/owner/repo/issues/12',
        },
        'repository': {
            'full_name': 'owner/repo',
            'html_url': 'https://forge.example/owner/repo',
            'clone_url': 'https://forge.example/owner/repo.git',
        },
        'sender': {'login': sender},
    }


def _signature(body: bytes, secret='secret') -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('FORGEJO_WEBHOOK_SECRET', 'secret')
    monkeypatch.setenv('FORGEJO_TOKEN', 'token')
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.setenv('FORGEJO_BOT_USERNAME', 'codetether')
    app = FastAPI()
    app.include_router(fw.forgejo_webhook_router)
    return app


async def _post(app, payload, signature=None, event='issue_comment'):
    raw = json.dumps(payload).encode()
    headers = {
        'X-Forgejo-Event': event,
        'X-Forgejo-Signature': signature
        if signature is not None
        else _signature(raw),
        'Content-Type': 'application/json',
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        return await client.post(
            '/v1/webhooks/forgejo', content=raw, headers=headers
        )


def _status_payload(
    *, state='failure', sha='abc123', sender='forgejo-actions', context='tests'
):
    return {
        'id': 7,
        'sha': sha,
        'state': state,
        'context': context,
        'description': 'tests failed',
        'target_url': 'https://forge.example/actions/runs/1',
        'commit': {'id': sha},
        'repository': {
            'full_name': 'owner/repo',
            'html_url': 'https://forge.example/owner/repo',
        },
        'sender': {'login': sender},
    }


@pytest.mark.asyncio
async def test_failed_status_webhook_queues_matching_pr_remediation(
    app, monkeypatch
):
    calls = []

    async def fake_json(method, base, path, payload=None):
        assert method == 'GET'
        assert 'pulls?state=open' in path
        return [
            {
                'number': 5,
                'html_url': 'https://forge.example/owner/repo/pulls/5',
                'head': {'sha': 'abc123', 'ref': 'feature'},
            }
        ]

    async def fake_remediation(**kwargs):
        calls.append(kwargs)
        return 'fix-1'

    monkeypatch.setattr(fw, 'forgejo_json', fake_json)
    monkeypatch.setattr(
        'a2a_server.forgejo_automation.create_status_remediation_task',
        fake_remediation,
    )
    response = await _post(app, _status_payload(), event='status')
    assert response.status_code == 200
    assert response.json() == {
        'accepted': True,
        'reason': 'queued',
        'task_id': 'fix-1',
    }
    assert calls[0]['repo'] == 'owner/repo'
    assert calls[0]['pr']['number'] == 5
    assert calls[0]['status']['status'] == 'failure'
    assert calls[0]['status']['creator']['login'] == 'forgejo-actions'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('payload', 'reason'),
    [
        (_status_payload(state='success'), 'non-failed-or-self-status'),
        (
            _status_payload(sender='codetether-bot'),
            'non-failed-or-self-status',
        ),
    ],
)
async def test_status_webhook_ignores_success_and_self_status(
    app, monkeypatch, payload, reason
):
    async def unexpected(*args, **kwargs):
        raise AssertionError('Forgejo PR lookup should not run')

    monkeypatch.setattr(fw, 'forgejo_json', unexpected)
    response = await _post(app, payload, event='status')
    assert response.json() == {'accepted': False, 'reason': reason}


@pytest.mark.asyncio
async def test_status_webhook_paginates_open_pr_heads(app, monkeypatch):
    paths = []

    async def fake_json(method, base, path, payload=None):
        paths.append(path)
        if 'page=1' in path:
            return [
                {'number': number, 'head': {'sha': f'other-{number}'}}
                for number in range(50)
            ]
        return [
            {
                'number': 77,
                'html_url': 'https://forge.example/owner/repo/pulls/77',
                'head': {'sha': 'abc123', 'ref': 'feature'},
            }
        ]

    async def fake_remediation(**kwargs):
        return 'fix-page-2'

    monkeypatch.setattr(fw, 'forgejo_json', fake_json)
    monkeypatch.setattr(
        'a2a_server.forgejo_automation.create_status_remediation_task',
        fake_remediation,
    )
    response = await _post(app, _status_payload(), event='status')
    assert response.json()['task_id'] == 'fix-page-2'
    assert any('page=1' in path for path in paths)
    assert any('page=2' in path for path in paths)


@pytest.mark.asyncio
async def test_status_webhook_ignores_unmatched_sha(app, monkeypatch):
    async def fake_json(method, base, path, payload=None):
        return [{'number': 5, 'head': {'sha': 'different'}}]

    monkeypatch.setattr(fw, 'forgejo_json', fake_json)
    response = await _post(app, _status_payload(), event='status')
    assert response.json() == {
        'accepted': False,
        'reason': 'no-open-pr-for-status-sha',
    }


@pytest.mark.asyncio
async def test_status_webhook_rejects_non_list_pulls(app, monkeypatch):
    async def fake_json(*args, **kwargs):
        return {'user_error': 'unexpected response'}

    monkeypatch.setattr(fw, 'forgejo_json', fake_json)
    response = await _post(app, _status_payload(), event='status')

    assert response.status_code == 200
    assert response.json() == {
        'accepted': False,
        'reason': 'invalid-forgejo-pulls-response',
    }


@pytest.mark.asyncio
async def test_rejects_invalid_signature(app):
    response = await _post(app, _payload(), 'wrong')
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ignores_bot_authored_comment(app, monkeypatch):
    monkeypatch.setattr(fw, '_active_task', lambda *args: None)
    response = await _post(app, _payload(sender='codetether'))
    assert response.json() == {
        'accepted': False,
        'reason': 'self-authored-event',
    }


@pytest.mark.asyncio
async def test_non_fix_mention_is_durable_before_guidance(app, monkeypatch):
    from a2a_server import forgejo_inbox

    async def accept(event, ctx, base):
        assert ctx['body'] == '@codetether hello'
        return {'accepted': True, 'state': 'pending'}

    async def comment(*args):
        raise AssertionError('external effects must follow durable intake')

    monkeypatch.setattr(forgejo_inbox, 'accept', accept)
    monkeypatch.setattr(fw, '_comment', comment)
    response = await _post(app, _payload('@codetether hello'))
    assert response.json() == {'accepted': True, 'state': 'pending'}


@pytest.mark.asyncio
async def test_actionable_issue_is_acknowledged_only_after_receipt(
    app, monkeypatch
):
    from a2a_server import forgejo_inbox

    async def accept(event, ctx, base):
        assert ctx['repo'] == 'owner/repo'
        assert ctx['number'] == 12
        assert not ctx['is_pr']
        assert base == 'https://forge.example/api/v1'
        return {'accepted': True, 'delivery_id': 'receipt-1'}

    async def comment(*args):
        raise AssertionError('external effects must follow durable intake')

    monkeypatch.setattr(forgejo_inbox, 'accept', accept)
    monkeypatch.setattr(fw, '_comment', comment)
    response = await _post(app, _payload())
    assert response.status_code == 200
    assert response.json() == {'accepted': True, 'delivery_id': 'receipt-1'}


def test_opened_issue_body_is_normalized_as_actionable_context():
    payload = _payload(action='opened')
    payload['issue']['body'] = payload.pop('comment')['body']

    context = fw._context('issues', payload)

    assert context is not None
    assert context['repo'] == 'owner/repo'
    assert context['number'] == 12
    assert context['comment_id'] == 0
    assert context['body'] == '@codetether handle this issue'


@pytest.mark.asyncio
async def test_issue_dispatch_isolates_workspace_by_work_branch(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    ensure_calls = []
    workflows = []

    async def fake_json(method, base, path, payload=None):
        assert method == 'GET'
        assert path == '/repos/owner/repo'
        return {
            'default_branch': 'main',
            'clone_url': 'https://forge.example/owner/repo.git',
        }

    async def fake_ensure(
        ctx,
        clone_url,
        branch,
        token,
        *,
        workspace_branch=None,
    ):
        ensure_calls.append(
            {
                'ctx': ctx,
                'clone_url': clone_url,
                'branch': branch,
                'token': token,
                'workspace_branch': workspace_branch,
            }
        )
        return 'isolated-issue-workspace'

    async def fake_routing():
        return {}

    async def fake_create(**kwargs):
        return {
            'id': 83,
            'html_url': 'https://forge.example/owner/repo/agent/tasks/83',
        }

    async def fake_start(workflow):
        workflows.append(workflow)
        return 'forgejo-agent-task-83'

    async def fake_update(**kwargs):
        return {'id': kwargs['task_id']}

    monkeypatch.setenv('FORGEJO_TOKEN', 'token')
    monkeypatch.setattr(fw, 'forgejo_json', fake_json)
    monkeypatch.setattr(fw, '_ensure_workspace', fake_ensure)
    monkeypatch.setattr(fw, 'resolve_task_target', fake_routing)
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.create_task', fake_create
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', fake_update
    )
    monkeypatch.setattr(
        'a2a_server.temporal.config.temporal_settings',
        lambda: SimpleNamespace(enabled=True),
    )
    monkeypatch.setattr(
        'a2a_server.temporal.client.start_forgejo_workflow', fake_start
    )

    result = await fw._dispatch(
        {
            'repo': 'owner/repo',
            'number': 4743,
            'is_pr': False,
            'body': '@codetether handle this issue',
            'repo_data': {},
            'comment_id': 0,
            'html_url': 'https://forge.example/owner/repo/issues/4743',
            'actor_login': 'alice',
        },
        'https://forge.example/api/v1',
    )

    assert result['workspace_id'] == 'isolated-issue-workspace'
    assert ensure_calls[0]['branch'] == 'main'
    assert ensure_calls[0]['workspace_branch'] == 'codetether/issue-4743'
    assert workflows[0].workspace_id == 'isolated-issue-workspace'
    assert workflows[0].branch == 'codetether/issue-4743'


@pytest.mark.asyncio
async def test_pr_comment_is_normalized_as_pr(app, monkeypatch):
    from a2a_server import forgejo_inbox

    payload = _payload('@codetether fix the tests')
    payload['issue']['pull_request'] = {'merged': False}

    async def inactive(*args):
        return False

    async def dispatch(event, ctx, base):
        assert ctx['is_pr']
        return {'accepted': True}

    async def comment(*args):
        return None

    monkeypatch.setattr(fw, '_active_task', inactive)
    monkeypatch.setattr(forgejo_inbox, 'accept', dispatch)
    monkeypatch.setattr(fw, '_comment', comment)
    assert (await _post(app, payload)).json() == {'accepted': True}


@pytest.mark.asyncio
async def test_edited_existing_mention_does_not_retrigger(app):
    payload = _payload(action='edited')
    payload['changes'] = {'body': {'from': '@codetether handle this issue'}}
    response = await _post(app, payload)
    assert response.json() == {
        'accepted': False,
        'reason': 'unsupported-or-no-mention',
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('row', 'expected'), [({'id': 'task-1'}, True), (None, False)]
)
async def test_active_task_uses_database_pool(monkeypatch, row, expected):
    class Connection:
        async def fetchrow(self, query, repo, number):
            assert "source' = 'forgejo-webhook'" in query
            assert (repo, number) == ('owner/repo', '12')
            return row

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *args):
            return None

    class Pool:
        def acquire(self):
            return Acquire()

    async def get_pool():
        return Pool()

    database = SimpleNamespace(get_pool=get_pool)
    monkeypatch.setitem(sys.modules, 'a2a_server.database', database)
    assert await fw._active_task('owner/repo', 12) is expected  # noqa: SLF001


def test_configured_forgejo_host_is_allowed_without_credential_injection(
    monkeypatch,
):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    assert validate_git_url('https://forge.example/owner/repo.git')
    assert not validate_git_url('https://token@forge.example/owner/repo.git')
    assert not validate_git_url('http://forge.example/owner/repo.git')
    assert not validate_git_url('https://evil.example/owner/repo.git')


async def _post_control(app, payload, signature=None):
    raw = json.dumps(payload).encode()
    headers = {
        'X-Forgejo-Event': 'agent_task_control',
        'X-Forgejo-Signature': signature
        if signature is not None
        else _signature(raw),
        'Content-Type': 'application/json',
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        return await client.post(
            '/v1/webhooks/forgejo/agent-control',
            content=raw,
            headers=headers,
        )


@pytest.mark.asyncio
async def test_signed_agent_control_signals_temporal(app, monkeypatch):
    signals = []

    async def fake_signal(signal):
        signals.append(signal)

    monkeypatch.setattr(
        'a2a_server.temporal.client.signal_control', fake_signal
    )
    payload = {
        'action': 'cancel',
        'task_id': 42,
        'requested_by': 'alice',
        'request_id': 'control-1',
        'issued_at': int(time.time()),
    }
    response = await _post_control(app, payload)

    assert response.status_code == 200
    assert response.json() == {
        'accepted': True,
        'task_id': 42,
        'action': 'cancel',
    }
    assert len(signals) == 1
    assert signals[0].forgejo_task_id == 42
    assert signals[0].requested_by == 'alice'


@pytest.mark.asyncio
async def test_agent_control_rejects_bad_signature_and_expiry(app):
    payload = {
        'action': 'retry',
        'task_id': 42,
        'issued_at': int(time.time()) - 301,
    }
    bad_signature = await _post_control(app, payload, signature='bad')
    assert bad_signature.status_code == 401

    expired = await _post_control(app, payload)
    assert expired.status_code == 401
    assert expired.json()['detail'] == 'Expired Forgejo agent control'


@pytest.mark.asyncio
async def test_agent_control_rejects_unknown_action(app):
    response = await _post_control(
        app,
        {'action': 'delete', 'task_id': 42, 'issued_at': int(time.time())},
    )
    assert response.status_code == 422
