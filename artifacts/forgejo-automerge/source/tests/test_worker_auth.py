"""Tests for a2a_server/worker_auth.py.

Covers the dashboard regression where ``GET /v1/worker/connected`` rejected a
signed-in Keycloak user with 401 under SPIFFE and the tenant client signed the
user out in a loop.
"""

import pytest

from fastapi import HTTPException
from starlette.requests import Request

from a2a_server import policy, spiffe_auth, worker_auth


HTTP_UNAUTHORIZED = 401


def _request(token: str | None) -> Request:
    headers = []
    if token is not None:
        headers.append((b'authorization', f'Bearer {token}'.encode()))
    return Request(
        {
            'type': 'http',
            'method': 'GET',
            'path': '/v1/worker/connected',
            'headers': headers,
            'query_string': b'',
        }
    )


@pytest.fixture
def spiffe_on(monkeypatch):
    monkeypatch.setattr(spiffe_auth, 'spiffe_enabled', lambda: True)
    monkeypatch.setattr(spiffe_auth, 'allow_token_legacy', lambda: True)
    worker_auth.get_auth_tokens_set.cache_clear()
    monkeypatch.setenv('A2A_AUTH_TOKENS', 'worker-shared-token')

    def _reject(_token):
        raise HTTPException(status_code=HTTP_UNAUTHORIZED, detail='bad svid')

    monkeypatch.setattr(spiffe_auth, 'validate_jwt_svid', _reject)
    yield
    worker_auth.get_auth_tokens_set.cache_clear()


@pytest.mark.asyncio
async def test_worker_token_still_accepted(spiffe_on):
    ident = await worker_auth.verify_worker_or_user_auth(
        _request('worker-shared-token')
    )
    assert ident == 'worker-shared-token'


@pytest.mark.asyncio
async def test_keycloak_user_token_accepted(spiffe_on, monkeypatch):
    async def fake_resolve(request):
        assert request.headers['authorization'] == 'Bearer kc-user-jwt'
        return {'user_id': 'kc-123', 'email': 'user@example.test', 'roles': []}

    monkeypatch.setattr(policy, '_resolve_user', fake_resolve)
    req = _request('kc-user-jwt')
    ident = await worker_auth.verify_worker_or_user_auth(req)
    assert ident == 'kc-123'
    assert req.state.user['email'] == 'user@example.test'


@pytest.mark.asyncio
async def test_unknown_token_re_raises_worker_error(spiffe_on, monkeypatch):
    async def fake_resolve(_request):
        return None

    monkeypatch.setattr(policy, '_resolve_user', fake_resolve)
    with pytest.raises(HTTPException) as exc:
        await worker_auth.verify_worker_or_user_auth(_request('garbage'))
    assert exc.value.status_code == HTTP_UNAUTHORIZED


@pytest.mark.asyncio
async def test_missing_token_re_raises_worker_error(spiffe_on, monkeypatch):
    async def fake_resolve(_request):
        return None

    monkeypatch.setattr(policy, '_resolve_user', fake_resolve)
    with pytest.raises(HTTPException) as exc:
        await worker_auth.verify_worker_or_user_auth(_request(None))
    assert exc.value.status_code == HTTP_UNAUTHORIZED
