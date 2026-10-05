"""Validate Keycloak administration transports."""

from urllib.parse import urlparse


def is_secure_keycloak_transport(url: str) -> bool:
    """Accept TLS endpoints or plaintext Kubernetes service DNS only."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    if parsed.scheme == 'https':
        return True
    return parsed.scheme == 'http' and parsed.hostname.endswith(
        '.svc.cluster.local'
    )
