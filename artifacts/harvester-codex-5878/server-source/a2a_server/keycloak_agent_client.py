"""Idempotent confidential-client creation for an agent workload."""

from a2a_server.agent_identity_errors import IdentityConflictError
from a2a_server.agent_identity_types import WorkloadIdentity
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def ensure_client(
    api: KeycloakAdminClient,
    realm: str,
    workload: WorkloadIdentity,
    display_name: str,
) -> str:
    """Create or verify a service-account-enabled client."""
    path = f'/admin/realms/{realm}/clients'
    params = {'clientId': workload.client_id}
    clients = (await api.request('GET', path, {200}, params=params)).json()
    if not clients:
        body = {
            'clientId': workload.client_id,
            'name': display_name,
            'enabled': True,
            'publicClient': False,
            'standardFlowEnabled': False,
            'directAccessGrantsEnabled': False,
            'serviceAccountsEnabled': True,
            'protocol': 'openid-connect',
            'attributes': {'codetether.spiffe_id': workload.spiffe_id},
        }
        await api.request('POST', path, {201, 409}, json=body)
        clients = (await api.request('GET', path, {200}, params=params)).json()
    attributes = clients[0].get('attributes') if len(clients) == 1 else {}
    if (
        len(clients) != 1
        or not clients[0].get('serviceAccountsEnabled')
        or (attributes or {}).get('codetether.spiffe_id') != workload.spiffe_id
    ):
        raise IdentityConflictError('Keycloak client conflicts with workload')
    return str(clients[0].get('id') or '')
