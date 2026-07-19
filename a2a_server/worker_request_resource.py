"""Exact request-body resource binding for worker proofs."""

import hashlib

from fastapi import Request


async def derive(request: Request, subject: str) -> str:
    """Bind a worker operation to its subject and exact request bytes."""
    body_hash = hashlib.sha256(await request.body()).hexdigest()
    return f'{subject}:{body_hash}'
