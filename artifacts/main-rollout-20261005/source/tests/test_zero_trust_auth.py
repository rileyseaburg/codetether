"""Zero-trust tests: Keycloak audience binding and fail-closed worker auth."""

import pytest

from fastapi import HTTPException
from starlette.requests import Request

from a2a_server import spiffe_auth, worker_auth
from a2a_server.keycloak_audience import (
    allowed_audiences,
    audience_allowed,
    token_audiences,
)


ALLOWED = frozenset({'a2a-monitor'})
HTTP_UNAUTHORIZED = 401


class TestKeycloakAudience:
    def test_aud_string_match_allowed(self):
        assert audience_allowed({'aud': 'a2a-monitor'}, ALLOWED)

    def test_aud_list_match_allowed(self):
        assert audience_allowed({'aud': ['account', 'a2a-monitor']}, ALLOWED)

    def test_azp_match_allowed(self):
        claims = {'aud': 'account', 'azp': 'a2a-monitor'}
        assert audience_allowed(claims, ALLOWED)

    def test_token_for_other_client_rejected(self):
        claims = {'aud': 'account', 'azp': 'some-other-app'}
        assert not audience_allowed(claims, ALLOWED)

    def test_token_without_audience_rejected(self):
        assert not audience_allowed({}, ALLOWED)

    def test_empty_allow_list_fails_closed(self):
        assert not audience_allowed({'aud': 'a2a-monitor'}, frozenset())

    def test_env_overrides_default_client(self, monkeypatch):
        monkeypatch.setenv('KEYCLOAK_ALLOWED_AUDIENCES', 'api-a, api-b')
        assert allowed_audiences('a2a-monitor') == {'api-a', 'api-b'}

    def test_default_is_client_id(self, monkeypatch):
        monkeypatch.delenv('KEYCLOAK_ALLOWED_AUDIENCES', raising=False)
        assert allowed_audiences('a2a-monitor') == {'a2a-monitor'}

    def test_collects_aud_and_azp(self):
        assert token_audiences({'aud': ['x'], 'azp': 'y'}) == {'x', 'y'}


def _request() -> Request:
    return Request(
        {
            'type': 'http',
            'method': 'GET',
            'path': '/v1/worker/tasks',
            'headers': [],
            'query_string': b'',
        }
    )


@pytest.fixture
def no_credentials(monkeypatch):
    worker_auth.get_auth_tokens_set.cache_clear()
    monkeypatch.delenv('A2A_AUTH_TOKENS', raising=False)
    monkeypatch.delenv('A2A_ALLOW_UNAUTHENTICATED_WORKERS', raising=False)
    yield monkeypatch
    worker_auth.get_auth_tokens_set.cache_clear()


def test_no_credentials_fails_closed(no_credentials):
    no_credentials.setattr(spiffe_auth, 'spiffe_enabled', lambda: False)
    with pytest.raises(HTTPException) as exc:
        worker_auth.verify_auth(_request())
    assert exc.value.status_code == HTTP_UNAUTHORIZED


def test_spiffe_legacy_without_tokens_fails_closed(no_credentials):
    no_credentials.setattr(spiffe_auth, 'spiffe_enabled', lambda: True)
    no_credentials.setattr(spiffe_auth, 'allow_token_legacy', lambda: True)
    with pytest.raises(HTTPException) as exc:
        worker_auth.verify_auth(_request())
    assert exc.value.status_code == HTTP_UNAUTHORIZED


def test_explicit_dev_opt_out_allows(no_credentials):
    no_credentials.setattr(spiffe_auth, 'spiffe_enabled', lambda: False)
    no_credentials.setenv('A2A_ALLOW_UNAUTHENTICATED_WORKERS', 'true')
    assert worker_auth.verify_auth(_request()) is None
