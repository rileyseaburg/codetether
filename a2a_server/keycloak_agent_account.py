"""Idempotent Keycloak service-account creation for one agent workload."""

from a2a_server.agent_identity_errors import IdentityUpstreamError
from a2a_server.agent_identity_types import KeycloakIdentity, WorkloadIdentity
from a2a_server.keycloak_agent_client import ensure_client
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def ensure_account(
    api: KeycloakAdminClient,
    realm: str,
    workload: WorkloadIdentity,
    display_name: str,
) -> KeycloakIdentity:
    """Create or verify a confidential client and return its subject."""
    base = f'/admin/realms/{realm}'
    client_uuid = await ensure_client(api, realm, workload, display_name)
    user = (
        await api.request(
            'GET', f'{base}/clients/{client_uuid}/service-account-user', {200}
        )
    ).json()
    subject = str(user.get('id') or '')
    if not subject:
        raise IdentityUpstreamError('Keycloak service account has no subject')
    user.update(
        {
            'email': workload.email,
            'emailVerified': True,
            'firstName': display_name,
            'enabled': True,
        }
    )
    await api.request('PUT', f'{base}/users/{subject}', {204}, json=user)
    return KeycloakIdentity(subject)
