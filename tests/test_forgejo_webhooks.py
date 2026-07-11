# ruff: noqa: PLR2004

import hashlib
import hmac
import json

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


async def _post(app, payload, signature=None):
    raw = json.dumps(payload).encode()
    headers = {
        'X-Forgejo-Event': 'issue_comment',
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
async def test_non_fix_mention_posts_guidance(app, monkeypatch):
    comments = []

    async def inactive(*args):
        return False

    async def comment(*args):
        comments.append(args)

    monkeypatch.setattr(fw, '_active_task', inactive)
    monkeypatch.setattr(fw, '_comment', comment)
    response = await _post(app, _payload('@codetether hello'))
    assert response.json() == {'accepted': False, 'reason': 'non-fix mention'}
    assert 'Ask me explicitly' in comments[0][3]


@pytest.mark.asyncio
async def test_actionable_issue_dispatches_and_acknowledges(app, monkeypatch):
    comments = []

    async def inactive(*args):
        return False

    async def dispatch(ctx, base):
        assert ctx['repo'] == 'owner/repo'
        assert ctx['number'] == 12
        assert not ctx['is_pr']
        assert base == 'https://forge.example/api/v1'
        return {'accepted': True, 'clone_task_id': 'task-1'}

    async def comment(*args):
        comments.append(args)

    monkeypatch.setattr(fw, '_active_task', inactive)
    monkeypatch.setattr(fw, '_dispatch', dispatch)
    monkeypatch.setattr(fw, '_comment', comment)
    response = await _post(app, _payload())
    assert response.status_code == 200
    assert response.json() == {'accepted': True, 'clone_task_id': 'task-1'}
    assert 'Picked this up' in comments[0][3]


@pytest.mark.asyncio
async def test_pr_comment_is_normalized_as_pr(app, monkeypatch):
    payload = _payload('@codetether fix the tests')
    payload['issue']['pull_request'] = {'merged': False}

    async def inactive(*args):
        return False

    async def dispatch(ctx, base):
        assert ctx['is_pr']
        return {'accepted': True}

    async def comment(*args):
        return None

    monkeypatch.setattr(fw, '_active_task', inactive)
    monkeypatch.setattr(fw, '_dispatch', dispatch)
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


def test_configured_forgejo_host_is_allowed_without_credential_injection(
    monkeypatch,
):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    assert validate_git_url('https://forge.example/owner/repo.git')
    assert not validate_git_url('https://token@forge.example/owner/repo.git')
    assert not validate_git_url('http://forge.example/owner/repo.git')
    assert not validate_git_url('https://evil.example/owner/repo.git')
