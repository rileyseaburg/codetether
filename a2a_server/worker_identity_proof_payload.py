"""Canonical payload for worker identity possession proofs."""


def canonical(
    action: str, worker_id: str, name: str, resource: str, timestamp: str
) -> bytes:
    """Encode one domain-separated worker proof payload."""
    values = (
        'codetether-worker-proof-v1',
        action,
        worker_id,
        name,
        resource,
        timestamp,
    )
    return '\n'.join(values).encode()
