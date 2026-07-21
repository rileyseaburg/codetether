import pytest

from a2a_server.agent_identity_api_types import ProvisionAgentIdentityRequest
from a2a_server.agent_identity_service import IdentityProvisioner
from a2a_server.agent_identity_types import KeycloakIdentity


FORGEJO_IDENTITY_ID = 42


@pytest.mark.asyncio
async def test_provisioner_converges_planes_in_order(monkeypatch):
    monkeypatch.setenv('SPIFFE_TRUST_DOMAIN', 'codetether.run')
    events = []

    async def workload(identity, persona, provisioning):
        events.append(('workload', identity.spiffe_id, persona, provisioning))

    async def keycloak(realm, identity, name, roles, groups):
        events.append(('keycloak', realm, roles, groups))
        return KeycloakIdentity('subject-42')

    async def binding(receipt):
        events.append(('binding', receipt))

    async def forgejo(receipt):
        events.append(('forgejo', receipt))
        return {'id': FORGEJO_IDENTITY_ID}

    request = ProvisionAgentIdentityRequest(
        provisioning_id='hire-42',
        persona_id='engineering-manager',
        display_name='Morgan',
        realm_name='spotlessbinco',
        realm_roles=['line-manager'],
        groups=['engineering'],
    )
    provisioner = IdentityProvisioner(workload, keycloak, binding, forgejo)
    result = await provisioner.provision(request)
    assert [event[0] for event in events] == [
        'workload',
        'keycloak',
        'binding',
        'forgejo',
    ]
    assert result.forgejo_identity_id == FORGEJO_IDENTITY_ID
    assert result.keycloak_subject == 'subject-42'
    assert events[-1][1]['persona_id'] == 'engineering-manager'
