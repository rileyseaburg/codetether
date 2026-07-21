"""Authenticated Keycloak Admin API transport."""

import httpx

from a2a_server.agent_identity_errors import IdentityUpstreamError
from a2a_server.keycloak_provisioner_config import KeycloakProvisionerConfig
from a2a_server.keycloak_provisioner_token import issue


class KeycloakAdminClient:
    """Small bearer-token client for approved Keycloak Admin API calls."""

    def __init__(
        self,
        config: KeycloakProvisionerConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self._access_token = ''

    async def request(
        self, method: str, path: str, expected: set[int], **kwargs: object
    ) -> httpx.Response:
        """Send one authenticated request and enforce explicit status codes."""
        token = await self._token()
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(
            transport=self.transport, timeout=20
        ) as client:
            response = await client.request(
                method,
                f'{self.config.base_url}{path}',
                headers=headers,
                **kwargs,
            )
        if response.status_code not in expected:
            raise IdentityUpstreamError(
                f'Keycloak Admin API returned HTTP {response.status_code}'
            )
        return response

    async def _token(self) -> str:
        if self._access_token:
            return self._access_token
        self._access_token = await issue(self.config, self.transport)
        return self._access_token
