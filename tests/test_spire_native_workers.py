"""SPIRE-native worker identity on worker routes and SVID validation."""

import time

import jwt
import pytest

from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from a2a_server import policy, policy_middleware, spiffe_auth, worker_auth
from a2a_server.policy_middleware import (
    PolicyAuthorizationMiddleware,
    worker_identity_allowed,
)


HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_UNAVAILABLE = 503

TD = 'codetether.io'
WORKER_ID = f'spiffe://{TD}/ns/a2a-system/sa/a2a-server-harvester'
OTHER_ID = f'spiffe://{TD}/ns/default/sa/default'
ISSUER = 'https://oidc-discovery.codetether.io'

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJwkClient:
    @staticmethod
    def get_signing_key_from_jwt(_token):
        return type('K', (), {'key': _KEY.public_key()})()


def _svid(sub, *, aud='a2a-server', iss=ISSUER):
    claims = {'sub': sub, 'aud': aud, 'exp': int(time.time()) + 300}
    if iss:
        claims['iss'] = iss
    return jwt.encode(claims, _KEY, algorithm='RS256')


@pytest.fixture
def spire(monkeypatch):
    monkeypatch.setenv('SPIFFE_ENABLED', 'true')
    monkeypatch.setenv('SPIFFE_TRUST_DOMAIN', TD)
    monkeypatch.setenv('SPIFFE_AUDIENCE', 'a2a-server')
    monkeypatch.setenv('SPIFFE_ISSUER', ISSUER)
    monkeypatch.setenv('SPIFFE_JWKS_URL', 'https://spire.example/keys')
    monkeypatch.setattr(spiffe_auth, '_get_jwk_client', _FakeJwkClient)
    return monkeypatch


# ── SVID validation hardening ────────────────────────────────────


def test_valid_worker_svid(spire):
    ident = spiffe_auth.validate_jwt_svid(_svid(WORKER_ID))
    assert ident.spiffe_id == WORKER_ID


def test_wrong_issuer_rejected(spire):
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(_svid(WORKER_ID, iss='https://evil'))
    assert exc.value.status_code == HTTP_FORBIDDEN


def test_missing_audience_config_fails_closed(spire):
    spire.delenv('SPIFFE_AUDIENCE')
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(_svid(WORKER_ID))
    assert exc.value.status_code == HTTP_UNAVAILABLE


def test_missing_trust_domain_config_fails_closed(spire):
    spire.delenv('SPIFFE_TRUST_DOMAIN')
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(_svid(WORKER_ID))
    assert exc.value.status_code == HTTP_UNAVAILABLE


def test_legacy_trust_domain_rejected(spire):
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(
            _svid('spiffe://codetether.run/ns/a2a-system/sa/x')
        )
    assert exc.value.status_code == HTTP_FORBIDDEN


# ── Worker allow-list ────────────────────────────────────────────


def _spiffe_user(spiffe_id):
    return {'auth_source': 'spiffe', 'spiffe_id': spiffe_id}


def test_allow_list_exact(monkeypatch):
    monkeypatch.setenv('SPIFFE_WORKER_IDS', WORKER_ID)
    assert worker_identity_allowed(_spiffe_user(WORKER_ID))
    assert not worker_identity_allowed(_spiffe_user(OTHER_ID))


def test_allow_list_prefix(monkeypatch):
    monkeypatch.setenv('SPIFFE_WORKER_IDS', f'spiffe://{TD}/ns/a2a-system/*')
    assert worker_identity_allowed(_spiffe_user(WORKER_ID))
    assert not worker_identity_allowed(_spiffe_user(OTHER_ID))


def test_empty_allow_list_denies_spiffe(monkeypatch):
    monkeypatch.delenv('SPIFFE_WORKER_IDS', raising=False)
    assert not worker_identity_allowed(_spiffe_user(WORKER_ID))


def test_keycloak_user_unaffected(monkeypatch):
    monkeypatch.delenv('SPIFFE_WORKER_IDS', raising=False)
    assert worker_identity_allowed({'auth_source': 'keycloak'})


# ── Middleware end to end ────────────────────────────────────────


def _client() -> TestClient:
    async def ok(_request):
        return JSONResponse({'ok': True})

    app = Starlette(routes=[Route('/v1/agent/workers', ok)])
    app.add_middleware(PolicyAuthorizationMiddleware)
    return TestClient(app)


@pytest.fixture
def gate(spire):
    spire.setattr(policy, 'OPA_ENABLED', True)
    spire.setattr(policy_middleware, 'WORKER_AUTH_TOKEN', 'shared')
    spire.delenv('A2A_ALLOW_UNAUTHENTICATED_WORKERS', raising=False)
    spire.setenv('SPIFFE_WORKER_IDS', WORKER_ID)

    async def resolve(request):
        token = spiffe_auth.bearer_token(request)
        ident = spiffe_auth.validate_jwt_svid(token)
        return ident.to_policy_user()

    spire.setattr(policy, '_resolve_user', resolve)
    return spire


def _get(token):
    return _client().get(
        '/v1/agent/workers', headers={'Authorization': f'Bearer {token}'}
    )


def test_allow_listed_worker_svid_accepted(gate):
    assert _get(_svid(WORKER_ID)).status_code == HTTP_OK


def test_other_workload_svid_forbidden(gate):
    assert _get(_svid(OTHER_ID)).status_code == HTTP_FORBIDDEN


def test_shared_token_rejected_in_spire_native_mode(gate):
    gate.setenv('SPIFFE_ALLOW_TOKEN_LEGACY', 'false')

    async def anonymous(_request):
        return None

    gate.setattr(policy, '_resolve_user', anonymous)
    assert _get('shared').status_code == HTTP_UNAUTHORIZED


def test_shared_token_accepted_during_migration(gate):
    gate.setenv('SPIFFE_ALLOW_TOKEN_LEGACY', 'true')
    assert _get('shared').status_code == HTTP_OK


# ── /v1/worker/* (worker_auth.verify_auth) ───────────────────────


def _worker_request(token):
    return StarletteRequest(
        {
            'type': 'http',
            'method': 'GET',
            'path': '/v1/worker/tasks/stream',
            'headers': [(b'authorization', f'Bearer {token}'.encode())],
            'query_string': b'',
        }
    )


@pytest.fixture
def worker_sse(spire):
    worker_auth.get_auth_tokens_set.cache_clear()
    spire.delenv('A2A_AUTH_TOKENS', raising=False)
    spire.setenv('SPIFFE_WORKER_IDS', WORKER_ID)
    yield worker_auth
    worker_auth.get_auth_tokens_set.cache_clear()


def test_worker_sse_allow_listed_svid(worker_sse):
    token = _svid(WORKER_ID)
    assert worker_sse.verify_auth(_worker_request(token)) == WORKER_ID


def test_worker_sse_other_workload_forbidden(worker_sse):
    with pytest.raises(Exception) as exc:
        worker_sse.verify_auth(_worker_request(_svid(OTHER_ID)))
    assert exc.value.status_code == HTTP_FORBIDDEN


@pytest.mark.asyncio
async def test_worker_or_user_path_rejects_spiffe(worker_sse, spire):
    async def as_spiffe_user(request):
        token = spiffe_auth.bearer_token(request)
        return spiffe_auth.validate_jwt_svid(token).to_policy_user()

    spire.setattr(policy, '_resolve_user', as_spiffe_user)
    with pytest.raises(Exception) as exc:
        await worker_sse.verify_worker_or_user_auth(
            _worker_request(_svid(OTHER_ID))
        )
    assert exc.value.status_code == HTTP_FORBIDDEN
