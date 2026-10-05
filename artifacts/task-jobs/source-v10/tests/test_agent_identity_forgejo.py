import httpx
import pytest

from a2a_server.agent_identity_errors import (
    IdentityConflictError,
    IdentityUpstreamError,
)
from a2a_server.agent_identity_forgejo import project_receipt


@pytest.mark.asyncio
async def test_forgejo_projection_accepts_idempotent_replay(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forgejo.example/api/v1')
    monkeypatch.setenv('FORGEJO_TOKEN', 'secret-token')

    def handler(request):
        assert request.url.path == '/api/v1/spiffe/identities'
        assert request.headers['authorization'] == 'token secret-token'
        return httpx.Response(200, json={'id': 7})

    result = await project_receipt(
        {'provisioning_id': 'hire-7'}, httpx.MockTransport(handler)
    )
    assert result == {'id': 7}


@pytest.mark.asyncio
async def test_forgejo_projection_surfaces_immutable_conflict(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forgejo.example/api/v1')
    monkeypatch.setenv('FORGEJO_TOKEN', 'secret-token')
    transport = httpx.MockTransport(lambda _: httpx.Response(409))
    with pytest.raises(IdentityConflictError):
        await project_receipt({}, transport)


@pytest.mark.asyncio
async def test_forgejo_projection_rejects_invalid_receipt(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forgejo.example/api/v1')
    monkeypatch.setenv('FORGEJO_TOKEN', 'secret-token')
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text='bad'))
    with pytest.raises(IdentityUpstreamError, match='invalid identity'):
        await project_receipt({}, transport)
