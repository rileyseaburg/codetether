"""Tests for ingesting non-OpenCode sessions (e.g. VS Code chat transcripts)."""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from a2a_server.monitor_api import opencode_router
import a2a_server.monitor_api as monitor_api


@pytest_asyncio.fixture
async def client(monkeypatch):
    app = FastAPI()
    app.include_router(opencode_router)

    # Ensure no Redis is consulted during tests.
    monkeypatch.delenv('A2A_REDIS_URL', raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac


@pytest.mark.asyncio
async def test_ingest_external_session_persists_session_and_messages(monkeypatch, client):
    monkeypatch.delenv('A2A_AUTH_TOKENS', raising=False)
    monitor_api._get_auth_tokens_set.cache_clear()

    captured = {}

    async def fake_upsert_session(session):
        captured['session'] = session
        return True

    async def fake_upsert_message(message):
        captured.setdefault('messages', []).append(message)
        return True

    monkeypatch.setattr(monitor_api.db, 'db_upsert_session', fake_upsert_session)
    monkeypatch.setattr(monitor_api.db, 'db_upsert_message', fake_upsert_message)

    payload = {
        'source': 'vscode.chat',
        'worker_id': 'vscode',
        'session': {
            'title': 'Hello world',
            'directory': '/tmp/repo',
            'created_at': '2025-01-01T00:00:00Z',
            'updated_at': '2025-01-01T00:00:01Z',
            'summary': {'foo': 'bar'},
        },
        'messages': [
            {
                'id': 'msg_1',
                'role': 'user',
                'model': 'copilot/gpt',
                'parts': [{'type': 'text', 'text': 'hi'}],
                'time': {'created': '2025-01-01T00:00:02Z'},
            }
        ],
    }

    resp = await client.post('/v1/opencode/codebases/cb_1/sessions/ses_1/ingest', json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['messages_ingested'] == 1
    assert body['source'] == 'vscode.chat'

    assert captured['session']['id'] == 'ses_1'
    assert captured['session']['codebase_id'] == 'cb_1'
    assert captured['session']['title'] == 'Hello world'
    assert captured['session']['summary']['source'] == 'vscode.chat'
    assert captured['session']['summary']['worker_id'] == 'vscode'

    assert captured['messages'][0]['id'] == 'msg_1'
    assert captured['messages'][0]['session_id'] == 'ses_1'
    assert captured['messages'][0]['role'] == 'user'
    assert captured['messages'][0]['model'] == 'copilot/gpt'


@pytest.mark.asyncio
async def test_ingest_external_session_requires_token_when_configured(monkeypatch, client):
    monkeypatch.setenv('A2A_AUTH_TOKENS', 'admin:secret123')
    monitor_api._get_auth_tokens_set.cache_clear()

    async def fake_upsert_session(_session):
        return True

    async def fake_upsert_message(_message):
        return True

    monkeypatch.setattr(monitor_api.db, 'db_upsert_session', fake_upsert_session)
    monkeypatch.setattr(monitor_api.db, 'db_upsert_message', fake_upsert_message)

    payload = {'source': 'vscode.chat', 'session': {'title': 't'}, 'messages': []}

    resp = await client.post('/v1/opencode/codebases/cb_1/sessions/ses_1/ingest', json=payload)
    assert resp.status_code == 401

    resp = await client.post(
        '/v1/opencode/codebases/cb_1/sessions/ses_1/ingest',
        json=payload,
        headers={'Authorization': 'Bearer wrong'},
    )
    assert resp.status_code == 403

    resp = await client.post(
        '/v1/opencode/codebases/cb_1/sessions/ses_1/ingest',
        json=payload,
        headers={'Authorization': 'Bearer secret123'},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_sessions_merges_db_sessions_into_worker_sync(monkeypatch, client):
    codebase_id = 'cb_merge'
    monkeypatch.delenv('A2A_AUTH_TOKENS', raising=False)
    monitor_api._get_auth_tokens_set.cache_clear()

    # No bridge (so list_sessions uses the in-memory worker cache).
    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: None)

    monkeypatch.setitem(
        monitor_api._worker_sessions,
        codebase_id,
        [
            {
                'id': 's1',
                'title': 'Worker session',
                'updated_at': '2025-01-01T00:00:02Z',
            }
        ],
    )

    async def fake_db_list_sessions(codebase_id: str, limit: int = 500):
        return [
            {
                'id': 's1',
                'codebase_id': codebase_id,
                'title': 'DB session',
                'updated_at': '2025-01-01T00:00:01Z',
            },
            {
                'id': 's2',
                'codebase_id': codebase_id,
                'title': 'External session',
                'updated_at': '2025-01-01T00:00:03Z',
            },
        ]

    monkeypatch.setattr(monitor_api.db, 'db_list_sessions', fake_db_list_sessions)

    resp = await client.get(f'/v1/opencode/codebases/{codebase_id}/sessions')
    assert resp.status_code == 200
    body = resp.json()
    assert body['source'] == 'worker_sync'
    ids = {s.get('id') for s in body['sessions']}
    assert ids == {'s1', 's2'}

