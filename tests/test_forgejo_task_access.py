from types import SimpleNamespace

import pytest

from fastapi import HTTPException

from a2a_server.forgejo_task_access import authorize
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry


def request(token: str) -> SimpleNamespace:
    return SimpleNamespace(
        headers={'authorization': f'Bearer {token}'},
        state=SimpleNamespace(),
    )


def task() -> dict[str, object]:
    value = metadata()
    value.update(
        author_identity_key_id='author-key',
        tenant_id='tenant',
    )
    return {'id': 'cttask_1', 'metadata': value}


def test_task_access_requires_the_bound_bearer_label(monkeypatch):
    value = metadata()
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setenv(
        'A2A_AUTH_TOKENS', 'reviewer:task-token,other:other-token'
    )
    authorize(request('task-token'), task())
    with pytest.raises(HTTPException) as raised:
        authorize(request('other-token'), task())
    assert raised.value.status_code == 403  # noqa: PLR2004


def test_reserved_task_without_a_binding_fails_closed():
    with pytest.raises(HTTPException) as raised:
        authorize(request('task-token'), {'id': 'cttask_1', 'metadata': {}})
    assert raised.value.status_code == 503  # noqa: PLR2004
