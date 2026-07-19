"""Server-controlled scope for configured task bearer tokens."""

import hashlib
import hmac
import os

from fastapi import HTTPException, Request


def legacy_scope(request: Request) -> str:
    """Verify a configured bearer and return its non-secret label."""
    raw = os.environ.get('A2A_AUTH_TOKENS', '')
    if not raw:
        raise HTTPException(
            status_code=503, detail='Task authentication is not configured'
        )
    supplied = _bearer(request)
    for pair in raw.split(','):
        label, separator, expected = pair.strip().partition(':')
        expected = expected.strip()
        if (
            separator
            and label
            and expected
            and hmac.compare_digest(supplied, expected)
        ):
            fingerprint = hashlib.sha256(supplied.encode()).hexdigest()[:32]
            return f'token:{label}:{fingerprint}'
    raise HTTPException(
        status_code=403, detail='Task authentication is invalid'
    )


def _bearer(request: Request) -> str:
    authorization = request.headers.get('authorization', '')
    if not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401, detail='Task authentication is required'
        )
    supplied = authorization.removeprefix('Bearer ').strip()
    if not supplied:
        raise HTTPException(
            status_code=401, detail='Task authentication is required'
        )
    return supplied
