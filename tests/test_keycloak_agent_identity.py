import pytest

from a2a_server.agent_identity_types import WorkloadIdentity
from a2a_server.keycloak_agent_account import ensure_account
from a2a_server.keycloak_agent_groups import ensure_groups
from a2a_server.keycloak_agent_roles import sync_roles
from a2a_server.keycloak_provisioner_config import KeycloakProvisionerConfig
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient
from tests.keycloak_agent_mock import transport


@pytest.mark.asyncio
async def test_keycloak_service_account_authority_projection():
    config = KeycloakProvisionerConfig(
        'https://keycloak.example', 'realm', 'realm', 'id', 'secret'
    )
    api = KeycloakAdminClient(config, transport())
    workload = WorkloadIdentity(
        'ns',
        'sa',
        'client',
        'user',
        'user@agents.invalid',
        'spiffe://td/ns/ns/sa/sa',
    )
    identity = await ensure_account(api, 'realm', workload, 'Morgan')
    await sync_roles(
        api, 'realm', identity.subject, ['line-manager'], ['line-manager']
    )
    await ensure_groups(api, 'realm', identity.subject, ['engineering'])
    assert identity.subject == 'subject-1'
