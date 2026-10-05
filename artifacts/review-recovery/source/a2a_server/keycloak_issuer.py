"""Resolve the trusted public Keycloak issuer independently of transport."""

import os


def issuer_for_realm(realm: str, transport_url: str) -> str:
    """Return the configured public issuer for ``realm``.

    ``KEYCLOAK_URL`` may point at an in-cluster service for JWKS and admin API
    traffic. ``KEYCLOAK_ISSUER`` remains the public identity asserted in JWTs.
    """
    configured = os.environ.get('KEYCLOAK_ISSUER', '').rstrip('/')
    if not configured:
        return f'{transport_url.rstrip("/")}/realms/{realm}'

    base, marker, _ = configured.rpartition('/realms/')
    if marker:
        return f'{base}{marker}{realm}'
    return configured
