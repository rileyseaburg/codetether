"""Existing self-service and Keycloak policy identity resolution."""

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials


async def resolve(request: Request, token: str) -> dict[str, object] | None:
    """Resolve existing application and Keycloak bearer credentials."""
    credentials = HTTPAuthorizationCredentials(
        scheme='Bearer', credentials=token
    )
    user = await _self_service(request, credentials)
    return user or await _keycloak(credentials)


async def _self_service(
    request: Request, credentials: HTTPAuthorizationCredentials
) -> dict[str, object] | None:
    try:
        from a2a_server.user_auth import get_current_user  # noqa: PLC0415

        return await get_current_user(request, credentials)
    except Exception:
        return None


async def _keycloak(
    credentials: HTTPAuthorizationCredentials,
) -> dict[str, object] | None:
    try:
        from a2a_server.keycloak_auth import get_current_user  # noqa: PLC0415

        session = await get_current_user(credentials)
    except Exception:
        return None
    if not session:
        return None
    return {
        'id': session.user_id,
        'user_id': session.user_id,
        'email': session.email,
        'roles': session.roles,
        'tenant_id': session.tenant_id,
        'type': 'keycloak',
        'keycloak_sub': session.user_id,
        'realm_name': session.realm_name,
    }
