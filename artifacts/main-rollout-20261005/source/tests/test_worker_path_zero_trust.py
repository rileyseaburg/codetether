"""Zero-trust: worker infrastructure routes are never open by default."""

import pytest

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from a2a_server import policy, policy_middleware
from a2a_server.policy_middleware import (
    _WORKER_PATH,
    PolicyAuthorizationMiddleware,
)


HTTP_OK = 200
HTTP_UNAUTHORIZED = 401

LEAKED_PATHS = [
    '/v1/agent/workers',
    '/v1/agent/workers/',
    '/v1/agent/workers/w1',
    '/v1/agent/tasks',
    '/v1/agent/tasks/',
]


@pytest.mark.parametrize('path', LEAKED_PATHS)
def test_worker_regex_covers_listing_paths(path):
    assert _WORKER_PATH.search(path)


def _ok(_request):
    return JSONResponse({'ok': True})


def _app() -> TestClient:
    routes = [
        Route('/v1/agent/workers', _ok, methods=['GET']),
        Route('/v1/agent/workers/{wid}', _ok, methods=['GET']),
        Route('/v1/agent/workers/{wid}/heartbeat', _ok, methods=['POST']),
        Route('/v1/agent/tasks', _ok, methods=['GET', 'POST']),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(PolicyAuthorizationMiddleware)
    return TestClient(app)


@pytest.fixture
def no_worker_token(monkeypatch):
    monkeypatch.setattr(policy, 'OPA_ENABLED', True)
    monkeypatch.setattr(policy_middleware, 'WORKER_AUTH_TOKEN', None)
    monkeypatch.delenv('A2A_ALLOW_UNAUTHENTICATED_WORKERS', raising=False)

    async def _anonymous(_request):
        return None

    monkeypatch.setattr(policy, '_resolve_user', _anonymous)
    return monkeypatch


@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('GET', '/v1/agent/workers'),
        ('GET', '/v1/agent/workers/w1'),
        ('POST', '/v1/agent/workers/w1/heartbeat'),
        ('GET', '/v1/agent/tasks'),
    ],
)
def test_anonymous_worker_routes_rejected(no_worker_token, method, path):
    response = _app().request(method, path)
    assert response.status_code == HTTP_UNAUTHORIZED


def test_public_chat_task_post_still_open(no_worker_token):
    response = _app().post('/v1/agent/tasks', json={})
    assert response.status_code == HTTP_OK


def test_worker_token_accepted(no_worker_token):
    no_worker_token.setattr(policy_middleware, 'WORKER_AUTH_TOKEN', 'wtok')
    response = _app().get(
        '/v1/agent/tasks', headers={'Authorization': 'Bearer wtok'}
    )
    assert response.status_code == HTTP_OK


def test_wrong_worker_token_rejected(no_worker_token):
    no_worker_token.setattr(policy_middleware, 'WORKER_AUTH_TOKEN', 'wtok')
    response = _app().get(
        '/v1/agent/tasks', headers={'Authorization': 'Bearer nope'}
    )
    assert response.status_code == HTTP_UNAUTHORIZED


def test_signed_in_user_accepted(no_worker_token):
    async def _user(_request):
        return {'user_id': 'u1', 'roles': ['viewer']}

    no_worker_token.setattr(policy, '_resolve_user', _user)
    response = _app().get('/v1/agent/workers')
    assert response.status_code == HTTP_OK


def test_dev_opt_out_allows_anonymous(no_worker_token):
    no_worker_token.setenv('A2A_ALLOW_UNAUTHENTICATED_WORKERS', 'true')
    response = _app().get('/v1/agent/workers')
    assert response.status_code == HTTP_OK
