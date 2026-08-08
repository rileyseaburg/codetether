import pytest

from jwt import encode

import a2a_server.policy_spiffe_resolver as resolver

from a2a_server.agent_identity_binding import AgentIdentityBinding
from a2a_server.spiffe_auth import SpiffeIdentity


@pytest.mark.asyncio
async def test_spiffe_binding_overrides_default_role(monkeypatch):
    identity = SpiffeIdentity('spiffe://td/ns/a/sa/b', 'td', '/ns/a/sa/b', {})
    binding = AgentIdentityBinding(
        'hire-1',
        'engineering-manager',
        identity.spiffe_id,
        'subject-1',
        'spotless',
        ['line-manager'],
        ['engineering'],
        'binding-1',
        'sha256:1',
        'ctprov_1234567890123456',
        'tenant-1',
    )
    monkeypatch.setattr(resolver.spiffe_auth, 'spiffe_enabled', lambda: True)
    monkeypatch.setattr(
        resolver.spiffe_auth, 'validate_jwt_svid', lambda _: identity
    )

    async def get_binding(_):
        return binding

    monkeypatch.setattr(resolver, 'get_binding', get_binding)
    token = encode({'sub': identity.spiffe_id}, 'candidate', algorithm='HS256')
    user = await resolver.resolve(token)
    assert user['roles'] == ['line-manager']
    assert user['keycloak_sub'] == 'subject-1'
    assert user['tenant_id'] == 'tenant-1'


@pytest.mark.asyncio
async def test_oidc_token_does_not_trigger_spire_jwks(monkeypatch):
    monkeypatch.setattr(resolver.spiffe_auth, 'spiffe_enabled', lambda: True)

    def unexpected(_):
        raise AssertionError('ordinary OIDC tokens must bypass SPIRE')

    monkeypatch.setattr(resolver.spiffe_auth, 'validate_jwt_svid', unexpected)
    token = encode({'sub': 'keycloak-user'}, 'candidate', algorithm='HS256')
    assert await resolver.resolve(token) is None
