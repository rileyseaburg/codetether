"""Configuration for the least-privilege Keycloak provisioner client."""

import os

from dataclasses import dataclass
from urllib.parse import urlparse

from a2a_server.agent_identity_errors import IdentityConfigurationError


@dataclass(frozen=True)
class KeycloakProvisionerConfig:
    """Credentials used only for Keycloak identity-plane administration."""

    base_url: str
    managed_realm: str
    token_realm: str
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> 'KeycloakProvisionerConfig':
        """Load a dedicated client without falling back to a human password."""
        base_url = os.environ.get('KEYCLOAK_URL', '').rstrip('/')
        managed_realm = os.environ.get('KEYCLOAK_AGENT_REALM', '').strip()
        token_realm = os.environ.get(
            'KEYCLOAK_PROVISIONER_REALM', managed_realm
        )
        client_id = os.environ.get('KEYCLOAK_PROVISIONER_CLIENT_ID', '')
        secret = os.environ.get('KEYCLOAK_PROVISIONER_CLIENT_SECRET', '')
        parsed = urlparse(base_url)
        if not all(
            (
                parsed.scheme == 'https',
                parsed.netloc,
                managed_realm,
                token_realm,
                client_id,
                secret,
            )
        ):
            raise IdentityConfigurationError(
                'Keycloak provisioner client is not configured'
            )
        return cls(base_url, managed_realm, token_realm, client_id, secret)
