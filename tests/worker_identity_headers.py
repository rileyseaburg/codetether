"""Signed canonical-worker request headers for tests."""

import hashlib
import hmac
import time

from a2a_server.worker_identity_proof_payload import canonical


KEY_ID = 'author-key'
SECRET = 'test-provenance-secret'


def headers(
    action: str, worker_id: str, name: str, resource: str
) -> dict[str, str]:
    """Sign one fresh server-compatible worker possession proof."""
    timestamp = str(int(time.time()))
    payload = canonical(action, worker_id, name, resource, timestamp)
    signature = hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return {
        'x-codetether-key-id': KEY_ID,
        'x-codetether-proof-timestamp': timestamp,
        'x-codetether-worker-proof': signature,
    }
