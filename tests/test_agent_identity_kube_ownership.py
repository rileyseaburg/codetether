"""Tests for refusing service-account identity takeover."""

from types import SimpleNamespace

import pytest

from a2a_server.agent_identity_errors import IdentityConflictError
from a2a_server.agent_identity_kube_ownership import verify


def account(annotations: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(metadata=SimpleNamespace(annotations=annotations))


def test_matching_identity_owns_service_account():
    verify(
        account(
            {
                'codetether.io/persona-id': 'manager',
                'codetether.io/provisioning-id': 'hire-1',
            }
        ),
        'manager',
        'hire-1',
    )


def test_unmarked_service_account_cannot_be_adopted():
    with pytest.raises(IdentityConflictError, match='another identity'):
        verify(account({}), 'manager', 'hire-1')
