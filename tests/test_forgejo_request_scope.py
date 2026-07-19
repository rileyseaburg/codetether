from types import SimpleNamespace

import pytest

from fastapi import HTTPException
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from a2a_server.forgejo_request_scope import resolve


def request(token=''):
    headers = {'authorization': f'Bearer {token}'} if token else {}
    return SimpleNamespace(state=SimpleNamespace(), headers=headers)


def test_configured_token_label_scopes_the_request(monkeypatch):
    monkeypatch.setenv('A2A_AUTH_TOKENS', 'reviewer:secret,other:different')
    scope, tenant = resolve(request('secret'))
    assert scope.startswith('token:reviewer:')
    assert 'secret' not in scope
    assert tenant is None


@pytest.mark.parametrize('token,status', [('', 401), ('wrong', 403)])
def test_missing_or_invalid_task_token_fails_closed(monkeypatch, token, status):
    monkeypatch.setenv('A2A_AUTH_TOKENS', 'reviewer:secret')
    with pytest.raises(HTTPException) as error:
        resolve(request(token))
    assert error.value.status_code == status


def test_unconfigured_task_authentication_fails_closed(monkeypatch):
    monkeypatch.delenv('A2A_AUTH_TOKENS', raising=False)
    with pytest.raises(HTTPException) as error:
        resolve(request('secret'))
    assert error.value.status_code == HTTP_503_SERVICE_UNAVAILABLE
