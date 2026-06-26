"""Authentication helpers shared by worker-facing routes."""

import os
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException, Request


@lru_cache(maxsize=1)
def get_auth_tokens_set() -> set:
    """Return the set of configured auth tokens."""
    raw = os.environ.get('A2A_AUTH_TOKENS')
    if not raw:
        return set()
    tokens: set = set()
    for pair in raw.split(','):
        pair = pair.strip()
        if not pair:
            continue
        if ':' in pair:
            _, token = pair.split(':', 1)
            token = token.strip()
            if token:
                tokens.add(token)
        else:
            tokens.add(pair)
    return tokens


def verify_auth(request: Request) -> Optional[str]:
    """Verify the caller's identity for worker-facing routes.

    When SPIFFE is enabled (``SPIFFE_ENABLED=true``) the Bearer credential is
    validated as a SPIFFE JWT-SVID and the caller's SPIFFE ID is returned. The
    parsed identity is stashed on ``request.state.spiffe`` so downstream OPA
    authorization can map the SPIFFE path to tenant/role.

    During migration (``SPIFFE_ALLOW_TOKEN_LEGACY=true``, the default) a token
    matching ``A2A_AUTH_TOKENS`` is still accepted when no valid SVID is
    presented. Set ``SPIFFE_ALLOW_TOKEN_LEGACY=false`` to retire shared tokens.

    Returns the SPIFFE ID or legacy token, or None when no auth is configured.
    Raises HTTPException(401/403) on invalid credentials.
    """
    from a2a_server import spiffe_auth

    tokens = get_auth_tokens_set()

    if spiffe_auth.spiffe_enabled():
        token = spiffe_auth.bearer_token(request)
        if token:
            try:
                identity = spiffe_auth.validate_jwt_svid(token)
                request.state.spiffe = identity
                return identity.spiffe_id
            except HTTPException:
                # If legacy tokens are still allowed, let a configured shared
                # token satisfy the request instead of the SVID.
                if not (spiffe_auth.allow_token_legacy() and token in tokens):
                    raise
                return token
        if spiffe_auth.allow_token_legacy() and not tokens:
            return None
        raise HTTPException(status_code=401, detail='Missing Bearer SVID')

    if not tokens:
        return None

    auth = (
        request.headers.get('authorization')
        or request.headers.get('Authorization')
        or ''
    )
    if not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing Bearer token')

    token = auth.removeprefix('Bearer ').strip()
    if not token or token not in tokens:
        raise HTTPException(status_code=403, detail='Invalid token')

    return token
