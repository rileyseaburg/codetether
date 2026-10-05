"""Forgejo identity receipt response validation."""

import httpx

from a2a_server.agent_identity_errors import IdentityUpstreamError


def receipt(response: httpx.Response) -> dict[str, object]:
    """Require the durable receipt shape returned by Forgejo."""
    try:
        value = response.json()
    except ValueError as error:
        raise IdentityUpstreamError(
            'Forgejo returned an invalid identity receipt'
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get('id'), int):
        raise IdentityUpstreamError(
            'Forgejo returned an invalid identity receipt'
        )
    return value
