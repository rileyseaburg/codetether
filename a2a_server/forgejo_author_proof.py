"""Authenticated retrieval of Forgejo PR and commit proof."""

from collections.abc import Mapping

import httpx

from a2a_server.forgejo_verification_config import api_base
from a2a_server.forgejo_verification_response import response_json


async def fetch(
    metadata: Mapping[str, object],
    token: str,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Fetch the current PR and exact commit using a non-persisted token."""
    if not token:
        raise RuntimeError('Forgejo verification credential is required')
    host = str(metadata.get('forgejo_host') or '').lower()
    repo = str(metadata.get('repo') or '')
    number = str(metadata.get('pr_number') or '')
    head = str(metadata.get('pr_head_sha') or '').lower()
    headers = {'Authorization': f'token {token}', 'Accept': 'application/json'}
    try:
        async with httpx.AsyncClient(
            timeout=15.0, transport=transport, headers=headers
        ) as client:
            pull = await response_json(
                client, f'{api_base(host)}/repos/{repo}/pulls/{number}'
            )
            commit = await response_json(
                client, f'{api_base(host)}/repos/{repo}/git/commits/{head}'
            )
            return pull, commit
    except httpx.HTTPError as error:
        raise RuntimeError('Forgejo verification request failed') from error
