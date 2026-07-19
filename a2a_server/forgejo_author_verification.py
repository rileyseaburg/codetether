"""Independent validation of Forgejo author proof."""

from collections.abc import Mapping

import httpx

from a2a_server.forgejo_author_contract import validate
from a2a_server.forgejo_author_proof import fetch
from a2a_server.forgejo_commit_trailers import verify_binding
from a2a_server.forgejo_provenance_keys import ProvenanceKey
from a2a_server.forgejo_provenance_verification import (
    verify as verify_provenance,
)
from a2a_server.forgejo_verification_response import nested


async def verify(
    metadata: Mapping[str, object],
    token: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ProvenanceKey:
    """Verify Forgejo and CodeTether proofs for the author session."""
    validate(metadata)
    pull, commit = await fetch(metadata, token, transport)
    head = str(metadata.get('pr_head_sha') or '').lower()
    login = str(metadata.get('forgejo_author_login') or '').lower()
    if pull.get('state') != 'open' or nested(pull, 'head', 'sha') != head:
        raise LookupError('Forgejo PR head is no longer current')
    if str(nested(pull, 'user', 'login')).lower() != login:
        raise ValueError('Forgejo PR author does not match signed principal')
    message = nested(commit, 'commit', 'message')
    if not isinstance(message, str):
        raise ValueError('Forgejo commit message is missing')
    verify_binding(metadata, message)
    signer = nested(commit, 'commit', 'verification', 'signer', 'username')
    signer = signer or nested(
        commit, 'commit', 'verification', 'signer', 'login'
    )
    verified = nested(commit, 'commit', 'verification', 'verified')
    if (
        commit.get('sha') != head
        or verified is not True
        or str(signer).lower() != login
    ):
        raise ValueError('Forgejo did not verify the author commit signature')
    return verify_provenance(message, metadata)
