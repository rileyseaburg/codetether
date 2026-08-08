"""Tests for Keycloak workload-client ownership."""

import httpx
import pytest

from a2a_server.agent_identity_errors import IdentityConflictError
from a2a_server.agent_identity_types import WorkloadIdentity
from a2a_server.keycloak_agent_client import ensure_client
from a2a_server.keycloak_provisioner_config import KeycloakProvisionerConfig
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


@pytest.mark.asyncio
async def test_unmarked_keycloak_client_cannot_be_adopted():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/token'):
            return httpx.Response(200, json={'access_token': 'token'})
        return httpx.Response(
            200,
            json=[
                {
                    'id': 'foreign',
                    'serviceAccountsEnabled': True,
                }
            ],
        )

    config = KeycloakProvisionerConfig(
        'https://kc', 'realm', 'realm', 'id', 'secret'
    )
    api = KeycloakAdminClient(config, httpx.MockTransport(handler))
    workload = WorkloadIdentity(
        'ns', 'sa', 'client', 'user', 'e@mail', 'spiffe://td/x'
    )
    with pytest.raises(IdentityConflictError, match='conflicts'):
        await ensure_client(api, 'realm', workload, 'Manager')
