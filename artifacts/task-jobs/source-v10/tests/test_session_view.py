# ruff: noqa: I001

import os
import time


os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from a2a_server import session_view

DEFAULT_LIMIT = 1000
EXPECTED_REDACTIONS = 2


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('CODETETHER_SESSION_VIEW_SECRET', 'test-session-secret')
    monkeypatch.setenv('CODETETHER_PUBLIC_URL', 'https://api.codetether.run')


@pytest.mark.asyncio
async def test_signed_session_view_renders_tools_and_redacts_secrets(
    monkeypatch, configured
):
    task = {
        'id': 'task-1',
        'status': 'completed',
        'metadata': {
            'session_id': 'session-1',
            'repo': 'riley/codetether',
            'pr_number': 5,
        },
    }
    messages = [
        {
            'id': 'message-1',
            'session_id': 'session-1',
            'role': 'assistant',
            'content': 'I ran the focused test.',
            'model': 'test-model',
            'created_at': '2026-07-17T12:00:00+00:00',
            'tool_calls': [
                {
                    'name': 'bash',
                    'status': 'completed',
                    'args': {
                        'command': 'pytest tests/test_session_view.py',
                        'token': 'must-not-render',
                    },
                    'result': {'stdout': '1 passed', 'password': 'hidden'},
                }
            ],
        }
    ]

    async def fake_task(task_id):
        return task if task_id == 'task-1' else None

    async def fake_task_messages(value, limit):
        assert value == task
        assert limit == DEFAULT_LIMIT
        return 'session-1', messages

    monkeypatch.setattr(session_view.db, 'db_get_task', fake_task)
    monkeypatch.setattr(session_view, '_task_messages', fake_task_messages)

    app = FastAPI()
    app.include_router(session_view.session_view_router)
    url = session_view.build_task_session_url(
        'task-1', expires=int(time.time()) + 300
    )
    assert url is not None
    path = url.removeprefix('https://api.codetether.run')

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get(path)

    assert response.status_code == status.HTTP_200_OK
    assert 'CodeTether Agent · View session' in response.text
    assert 'I ran the focused test.' in response.text
    assert 'pytest tests/test_session_view.py' in response.text
    assert '1 passed' in response.text
    assert 'must-not-render' not in response.text
    assert 'hidden' not in response.text
    assert response.text.count('[REDACTED]') == EXPECTED_REDACTIONS
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert (
        "frame-ancestors 'none'" in response.headers['content-security-policy']
    )


@pytest.mark.asyncio
async def test_session_view_rejects_forged_and_expired_links(configured):
    app = FastAPI()
    app.include_router(session_view.session_view_router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        forged = await client.get(
            '/sessions/tasks/task-1',
            params={
                'expires': int(time.time()) + 300,
                'signature': 'not-valid',
            },
        )
        expired_at = int(time.time()) - 1
        expired_url = session_view.build_task_session_url(
            'task-1', expires=expired_at
        )
        assert expired_url is not None
        expired = await client.get(
            expired_url.removeprefix('https://api.codetether.run')
        )

    assert forged.status_code == status.HTTP_403_FORBIDDEN
    assert expired.status_code == status.HTTP_410_GONE


def test_task_session_url_is_task_scoped(monkeypatch, configured):
    expires = int(time.time()) + 300
    first = session_view.build_task_session_url('task-1', expires=expires)
    second = session_view.build_task_session_url('task-2', expires=expires)
    assert first and second and first != second
    assert '/sessions/tasks/task-1?' in first
    assert '/sessions/tasks/task-2?' in second
    first_signature = first.split('signature=', 1)[1]
    with pytest.raises(Exception) as exc:
        session_view.verify_task_session_signature(
            'task-2', expires, first_signature
        )
    assert getattr(exc.value, 'status_code', None) == status.HTTP_403_FORBIDDEN


def test_missing_configuration_does_not_publish_link(monkeypatch):
    monkeypatch.delenv('CODETETHER_SESSION_VIEW_SECRET', raising=False)
    monkeypatch.delenv('FORGEJO_WEBHOOK_SECRET', raising=False)
    monkeypatch.setenv('CODETETHER_PUBLIC_URL', 'https://api.codetether.run')
    assert session_view.build_task_session_url('task-1') is None
