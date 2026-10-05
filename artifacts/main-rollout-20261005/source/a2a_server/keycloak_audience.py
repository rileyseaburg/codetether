"""Zero-trust audience binding for Keycloak access tokens.

Signature and issuer checks prove a token came from the realm. They do not
prove it was minted *for this API*. Without an audience check, a token issued
to any client in the realm (another app, a test client) is accepted here.

Keycloak access tokens carry the target resource server(s) in ``aud`` when an
audience mapper is configured, and the requesting client in ``azp``. A token
is accepted when either names one of the allowed clients.

Configuration:
    KEYCLOAK_ALLOWED_AUDIENCES  comma list; defaults to KEYCLOAK_CLIENT_ID
"""

from __future__ import annotations

import os

from collections.abc import Iterable, Mapping
from typing import Any


def allowed_audiences(default_client_id: str) -> frozenset[str]:
    """Return the client IDs this API accepts tokens for."""
    raw = os.environ.get('KEYCLOAK_ALLOWED_AUDIENCES', '')
    values = {item.strip() for item in raw.split(',') if item.strip()}
    if not values and default_client_id:
        values.add(default_client_id)
    return frozenset(values)


def token_audiences(claims: Mapping[str, Any]) -> set[str]:
    """Collect ``aud`` (string or list) and ``azp`` from token claims."""
    found: set[str] = set()
    aud = claims.get('aud')
    if isinstance(aud, str):
        found.add(aud)
    elif isinstance(aud, Iterable):
        found.update(str(item) for item in aud if item)
    azp = claims.get('azp')
    if azp:
        found.add(str(azp))
    return found


def audience_allowed(
    claims: Mapping[str, Any], allowed: frozenset[str]
) -> bool:
    """True when the token was minted for (or by) an allowed client.

    An empty allow-list fails closed.
    """
    return bool(allowed) and not token_audiences(claims).isdisjoint(allowed)
