"""Validated Forgejo configuration for identity projection."""

import os

from dataclasses import dataclass
from urllib.parse import urlparse

from a2a_server.agent_identity_errors import IdentityConfigurationError


@dataclass(frozen=True)
class ForgejoIdentityConfig:
    """Allowlisted API root and scoped SPIFFE bridge credential."""

    base_url: str
    token: str

    @classmethod
    def from_env(cls) -> 'ForgejoIdentityConfig':
        """Load and validate the configured Forgejo API root."""
        base_url = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
        token = os.environ.get('FORGEJO_TOKEN', '').strip()
        parsed = urlparse(base_url)
        if parsed.scheme != 'https' or not parsed.netloc or not token:
            raise IdentityConfigurationError(
                'Forgejo SPIFFE bridge is not configured'
            )
        return cls(base_url, token)
