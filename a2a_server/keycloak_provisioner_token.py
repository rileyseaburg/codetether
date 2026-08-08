"""Keycloak provisioner client-credential authentication."""

from http import HTTPStatus

import httpx

from a2a_server.agent_identity_errors import IdentityUpstreamError
from a2a_server.keycloak_provisioner_config import KeycloakProvisionerConfig


async def issue(
    config: KeycloakProvisionerConfig,
    transport: httpx.AsyncBaseTransport | None,
) -> str:
    """Issue a short-lived token for the dedicated provisioner client."""
    path = f'/realms/{config.token_realm}/protocol/openid-connect/token'
    data = {
        'grant_type': 'client_credentials',
        'client_id': config.client_id,
        'client_secret': config.client_secret,
    }
    async with httpx.AsyncClient(transport=transport, timeout=20) as client:
        response = await client.post(f'{config.base_url}{path}', data=data)
    if response.status_code != HTTPStatus.OK:
        raise IdentityUpstreamError(
            'Keycloak provisioner authentication failed'
        )
    access_token = str(response.json().get('access_token') or '')
    if not access_token:
        raise IdentityUpstreamError('Keycloak returned no provisioner token')
    return access_token
