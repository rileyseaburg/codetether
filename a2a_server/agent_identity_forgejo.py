"""Forgejo bridge client for durable workload-identity receipts."""

from http import HTTPStatus

import httpx

from a2a_server.agent_identity_errors import (
    IdentityConflictError,
    IdentityUpstreamError,
)
from a2a_server.agent_identity_forgejo_response import receipt as parse_receipt
from a2a_server.forgejo_identity_config import ForgejoIdentityConfig


async def project_receipt(
    receipt: dict[str, object],
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    """Create or replay an immutable SPIFFE identity receipt in Forgejo."""
    config = ForgejoIdentityConfig.from_env()
    headers = {
        'Authorization': f'token {config.token}',
        'Accept': 'application/json',
    }
    try:
        async with httpx.AsyncClient(transport=transport, timeout=20) as client:
            response = await client.post(
                f'{config.base_url}/spiffe/identities',
                json=receipt,
                headers=headers,
            )
    except httpx.HTTPError as error:
        raise IdentityUpstreamError(
            'Forgejo identity projection failed'
        ) from error
    if response.status_code == HTTPStatus.CONFLICT:
        raise IdentityConflictError(
            'Forgejo identity receipt conflicts with prior state'
        )
    if response.status_code not in {200, 201}:
        raise IdentityUpstreamError(
            f'Forgejo identity projection returned HTTP {response.status_code}'
        )
    return parse_receipt(response)
