"""Ordered policy identity resolution across supported token issuers."""

from fastapi import Request

from a2a_server.policy_bearer import token
from a2a_server.policy_oidc_resolver import resolve as resolve_oidc
from a2a_server.policy_spiffe_resolver import resolve as resolve_spiffe


async def resolve(request: Request) -> dict[str, object] | None:
    """Prefer workload identity, then preserve existing OIDC behavior."""
    credential = token(request)
    if not credential:
        return None
    workload = await resolve_spiffe(credential)
    return workload or await resolve_oidc(request, credential)
