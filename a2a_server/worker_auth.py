"""Authentication helpers shared by worker-facing routes."""

import os
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException, Request


@lru_cache(maxsize=1)
def get_auth_tokens_set() -> set:
    """Return the set of configured auth tokens."""
    raw = os.environ.get('A2A_AUTH_TOKENS')
    if not raw:
        return set()
    tokens: set = set()
    for pair in raw.split(','):
        pair = pair.strip()
        if not pair:
            continue
        if ':' in pair:
            _, token = pair.split(':', 1)
            token = token.strip()
            if token:
                tokens.add(token)
        else:
            tokens.add(pair)
    return tokens


def verify_auth(request: Request) -> Optional[str]:
    """Verify Bearer token if worker authentication is configured."""
    tokens = get_auth_tokens_set()
    if not tokens:
        return None

    auth = (
        request.headers.get('authorization')
        or request.headers.get('Authorization')
        or ''
    )
    if not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing Bearer token')

    token = auth.removeprefix('Bearer ').strip()
    if not token or token not in tokens:
        raise HTTPException(status_code=403, detail='Invalid token')

    return token
