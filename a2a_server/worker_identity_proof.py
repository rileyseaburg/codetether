"""Verification of per-request canonical worker identity proofs."""

import hashlib
import hmac
import time

from collections.abc import Mapping

from a2a_server.forgejo_provenance_keys import ProvenanceKey, resolve
from a2a_server.worker_identity_proof_payload import canonical


MAX_CLOCK_SKEW_SECONDS = 120
SIGNATURE_LENGTH = 64


def verify(
    headers: Mapping[str, str],
    action: str,
    worker_id: str,
    name: str,
    resource: str,
) -> ProvenanceKey:
    """Verify a fresh HMAC proof bound to the request and canonical identity."""
    key_id = headers.get('x-codetether-key-id', '')
    timestamp = headers.get('x-codetether-proof-timestamp', '')
    signature = headers.get('x-codetether-worker-proof', '')
    try:
        age = abs(int(time.time()) - int(timestamp))
    except ValueError as error:
        raise ValueError(
            'worker identity proof timestamp is invalid'
        ) from error
    if age > MAX_CLOCK_SKEW_SECONDS:
        raise ValueError('worker identity proof is stale')
    key = resolve(key_id)
    if key.agent_identity != name:
        raise ValueError('worker proof key is not bound to the agent identity')
    expected = hmac.new(
        key.secret.encode(),
        canonical(action, worker_id, name, resource, timestamp),
        hashlib.sha256,
    ).hexdigest()
    if len(signature) != SIGNATURE_LENGTH or not hmac.compare_digest(
        signature, expected
    ):
        raise ValueError('worker identity proof is invalid')
    return key
