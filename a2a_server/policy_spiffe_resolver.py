"""SPIFFE authentication and durable OPA authority resolution."""

from jwt import PyJWTError, decode

from a2a_server import spiffe_auth
from a2a_server.agent_identity_repository import get_binding


async def resolve(token: str) -> dict[str, object] | None:
    """Resolve a JWT-SVID and overlay any durable authority binding."""
    if not spiffe_auth.spiffe_enabled() or not _candidate(token):
        return None
    identity = spiffe_auth.validate_jwt_svid(token)
    binding = await get_binding(identity.spiffe_id)
    return binding.policy_user() if binding else identity.to_policy_user()


def _candidate(token: str) -> bool:
    """Avoid SPIRE JWKS traffic for ordinary application bearer tokens."""
    try:
        claims = decode(token, options={'verify_signature': False})
    except PyJWTError:
        return False
    return str(claims.get('sub') or '').startswith('spiffe://')
