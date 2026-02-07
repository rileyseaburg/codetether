"""Tests for Keycloak token normalization in user auth."""

from types import SimpleNamespace

import pytest

import a2a_server.user_auth as user_auth


def test_normalize_keycloak_identity_derives_subject_from_username():
    payload = {
        'preferred_username': 'builder@example.com',
        'iss': 'https://auth.quantum-forge.io/realms/quantum-forge',
    }

    identity = user_auth._normalize_keycloak_identity(payload)

    assert identity['sub'] is not None
    assert identity['sub'].startswith('keycloak:')
    assert identity['email'] == 'builder@example.com'
    assert identity['realm_name'] == 'quantum-forge'


def test_normalize_keycloak_identity_derives_email_from_subject():
    payload = {'sub': 'kc-user-123'}

    identity = user_auth._normalize_keycloak_identity(payload)

    assert identity['sub'] == 'kc-user-123'
    assert identity['email'] == 'kc-user-123@keycloak.local'


@pytest.mark.asyncio
async def test_get_or_create_keycloak_user_virtual_includes_tenant(monkeypatch):
    async def fake_get_pool():
        return None

    monkeypatch.setattr(user_auth, 'get_pool', fake_get_pool)

    request = SimpleNamespace(
        state=SimpleNamespace(tenant_id='tenant-abc'),
        headers={},
    )

    result = await user_auth._get_or_create_keycloak_user(
        {
            'sub': 'sub-123',
            'email': 'dev@example.com',
            'name': 'Dev User',
            'roles': ['member'],
            'realm_name': 'quantum-forge',
        },
        request=request,
    )

    assert result['id'] == 'sub-123'
    assert result['tenant_id'] == 'tenant-abc'
    assert result['realm_name'] == 'quantum-forge'
    assert result['roles'] == ['member']
