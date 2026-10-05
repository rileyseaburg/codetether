"""Authentication helpers shared by worker-facing routes."""

import os

from functools import lru_cache

from fastapi import HTTPException, Request

from a2a_server import spiffe_auth


@lru_cache(maxsize=1)
def get_auth_tokens_set() -> set:
    """Return the set of configured auth tokens."""
    raw = os.environ.get('A2A_AUTH_TOKENS')
    if not raw:
        return set()
    tokens: set = set()
    for pair in raw.split(','):
        entry = pair.strip()
        if not entry:
            continue
        if ':' in entry:
            _, token = entry.split(':', 1)
            token = token.strip()
            if token:
                tokens.add(token)
        else:
            tokens.add(entry)
    return tokens


def unauthenticated_allowed() -> bool:
    """Explicit local-dev opt-out; zero trust means never implicit.

    Before this switch existed, an unset ``A2A_AUTH_TOKENS`` (with SPIFFE
    off, or with legacy tokens allowed) silently disabled worker auth.
    """
    value = os.environ.get('A2A_ALLOW_UNAUTHENTICATED_WORKERS', '')
    return value.strip().lower() in {'1', 'true', 'yes'}


def _no_credentials_configured() -> None:
    """Fail closed when no worker credential source is configured."""
    if unauthenticated_allowed():
        return
    raise HTTPException(
        status_code=401,
        detail='Worker authentication is not configured',
    )


def verify_auth(request: Request) -> str | None:
    """Verify the caller's identity for worker-facing routes.

    When SPIFFE is enabled (``SPIFFE_ENABLED=true``) the Bearer credential is
    validated as a SPIFFE JWT-SVID and the caller's SPIFFE ID is returned. The
    parsed identity is stashed on ``request.state.spiffe`` so downstream OPA
    authorization can map the SPIFFE path to tenant/role.

    During migration (``SPIFFE_ALLOW_TOKEN_LEGACY=true``, the default) a token
    matching ``A2A_AUTH_TOKENS`` is still accepted when no valid SVID is
    presented. Set ``SPIFFE_ALLOW_TOKEN_LEGACY=false`` to retire shared tokens.

    Returns the SPIFFE ID or legacy token. Returns None only when no
    credential source is configured *and* ``A2A_ALLOW_UNAUTHENTICATED_WORKERS``
    is explicitly set; otherwise that case is rejected (fail closed).
    Raises HTTPException(401/403) on invalid credentials.
    """
    tokens = get_auth_tokens_set()

    if spiffe_auth.spiffe_enabled():
        token = spiffe_auth.bearer_token(request)
        if token:
            try:
                identity = spiffe_auth.validate_jwt_svid(token)
            except HTTPException:
                # If legacy tokens are still allowed, let a configured shared
                # token satisfy the request instead of the SVID.
                if not (spiffe_auth.allow_token_legacy() and token in tokens):
                    raise
                return token
            if not spiffe_auth.is_allowed_worker(identity.spiffe_id):
                raise HTTPException(
                    status_code=403, detail='Workload not authorized as worker'
                )
            request.state.spiffe = identity
            return identity.spiffe_id
        if spiffe_auth.allow_token_legacy() and not tokens:
            return _no_credentials_configured()
        raise HTTPException(status_code=401, detail='Missing Bearer SVID')

    if not tokens:
        return _no_credentials_configured()

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


async def verify_worker_or_user_auth(request: Request) -> str | None:
    """Accept either worker credentials or an authenticated platform user.

    Read-only worker views (``GET /v1/worker/connected``) are rendered by the
    dashboard with the signed-in user's Keycloak access token, not a worker
    SVID or shared ``A2A_AUTH_TOKENS`` entry. With SPIFFE enabled,
    :func:`verify_auth` rejected those calls with 401, and the dashboard's
    tenant client treats any 401 as an expired session and signs the user
    out, so the UI bounced to ``/login`` in a loop immediately after login.

    Worker credentials are tried first so worker callers keep the same
    identity semantics. When they fail, the request must resolve to a
    platform user through the shared policy resolver; otherwise the original
    worker-auth error is re-raised.
    """
    try:
        return verify_auth(request)
    except HTTPException as worker_error:
        from a2a_server.policy import (  # noqa: PLC0415 - deferred: avoids import cycle
            _resolve_user,
        )

        user = await _resolve_user(request)
        if user and user.get('auth_source') == 'spiffe':
            # A workload SVID is not a platform user: SPIFFE callers must
            # pass the worker allow-list in verify_auth, never this path.
            raise worker_error from None
        if user:
            request.state.user = user
            return str(user.get('user_id') or user.get('id') or '')
        raise worker_error
