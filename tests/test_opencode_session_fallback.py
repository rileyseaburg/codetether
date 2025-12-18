"""Regression tests for OpenCode session listing fallbacks.

Historically, `/v1/opencode/codebases/{codebase_id}/sessions` required the codebase
to exist in the in-memory OpenCode bridge registry. In multi-replica deployments
or after restarts, the bridge can be empty while PostgreSQL still contains the
session records, causing the UI to show "empty" sessions.

These tests ensure the endpoint can fall back to PostgreSQL even when the bridge
is missing.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from a2a_server.monitor_api import opencode_router
import a2a_server.monitor_api as monitor_api


@pytest_asyncio.fixture
async def client(monkeypatch):
    # Build a minimal ASGI app with just the OpenCode routes.
    app = FastAPI()
    app.include_router(opencode_router)

    # Ensure no Redis is consulted during tests.
    monkeypatch.delenv('A2A_REDIS_URL', raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_sessions_returns_db_results_without_bridge(monkeypatch, client):
    codebase_id = 'ec77c942'

    # Simulate a node where the OpenCode bridge is unavailable/empty.
    monkeypatch.setattr(monitor_api, 'get_opencode_bridge', lambda: None)

    async def fake_db_list_sessions(codebase_id: str, limit: int = 500):
        return [
            {
                'id': 'ses_test_1',
                'codebase_id': codebase_id,
                'project_id': 'global',
                'directory': '/tmp/repo',
                'title': 'Test Session',
                'version': '1',
                'summary': {},
                'created_at': '2025-01-01T00:00:00Z',
                'updated_at': '2025-01-01T00:00:01Z',
            }
        ]

    monkeypatch.setattr(monitor_api.db, 'db_list_sessions', fake_db_list_sessions)

    resp = await client.get(f'/v1/opencode/codebases/{codebase_id}/sessions')
    assert resp.status_code == 200

    payload = resp.json()
    assert payload['source'] == 'database'
    assert len(payload['sessions']) == 1
    assert payload['sessions'][0]['codebase_id'] == codebase_id


@pytest.mark.asyncio
async def test_list_sessions_returns_empty_list_when_codebase_exists(monkeypatch, client):
    codebase_id = 'ec77c942'

    monkeypatch.setattr(monitor_api, 'get_opencode_bridge', lambda: None)

    async def fake_db_list_sessions(codebase_id: str, limit: int = 500):
        return []

    async def fake_db_get_codebase(codebase_id: str):
        return {
            'id': codebase_id,
            'name': 'Test Codebase',
            'path': '/tmp/repo',
            'description': '',
            'worker_id': 'wrk_test',
            'agent_config': {},
            'created_at': None,
            'updated_at': None,
            'status': 'active',
            'session_id': None,
            'opencode_port': None,
        }

    monkeypatch.setattr(monitor_api.db, 'db_list_sessions', fake_db_list_sessions)
    monkeypatch.setattr(monitor_api.db, 'db_get_codebase', fake_db_get_codebase)

    resp = await client.get(f'/v1/opencode/codebases/{codebase_id}/sessions')
    assert resp.status_code == 200

    payload = resp.json()
    assert payload['source'] == 'database'
    assert payload['sessions'] == []


@pytest.mark.asyncio
async def test_list_sessions_404_when_codebase_unknown(monkeypatch, client):
    codebase_id = 'doesnotexist'

    monkeypatch.setattr(monitor_api, 'get_opencode_bridge', lambda: None)

    async def fake_db_list_sessions(codebase_id: str, limit: int = 500):
        return []

    async def fake_db_get_codebase(codebase_id: str):
        return None

    monkeypatch.setattr(monitor_api.db, 'db_list_sessions', fake_db_list_sessions)
    monkeypatch.setattr(monitor_api.db, 'db_get_codebase', fake_db_get_codebase)

    resp = await client.get(f'/v1/opencode/codebases/{codebase_id}/sessions')
    assert resp.status_code == 404
    assert resp.json()['detail'] == 'Codebase not found'
