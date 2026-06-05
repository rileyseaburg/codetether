"""Ingest helpers: signature verification, body parse, and ping handling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Union

from fastapi import Request

from ..auth import verify_signature as _default_verify_signature

PING_EVENT = 'ping'
SIGNATURE_HEADER = 'X-Hub-Signature-256'
EVENT_HEADER = 'X-GitHub-Event'

# The signature verifier is passed in by the router so existing tests that
# patch ``router.verify_signature`` continue to work without monkeypatching
# deep imports.
SignatureVerifier = Callable[[str, bytes], Awaitable[None]]


@dataclass(frozen=True)
class IngestedEvent:
    """Validated webhook event ready for downstream filters."""

    event_name: str
    payload: dict[str, Any]
    raw_body: bytes


async def read_event(
    request: Request,
    *,
    verify: SignatureVerifier | None = None,
) -> Union[IngestedEvent, dict[str, Any]]:
    """Verify the signature, read the body, and return parsed event data.

    Returns a ping response dict for ping events so the caller can short-circuit.
    """
    verify_fn = verify or _default_verify_signature
    raw_body = await request.body()
    await verify_fn(request.headers.get(SIGNATURE_HEADER, ''), raw_body)
    event_name = request.headers.get(EVENT_HEADER, '')
    if event_name == PING_EVENT:
        return {'ok': True, 'event': 'ping'}
    payload = json.loads(raw_body or b'{}')
    if not isinstance(payload, Mapping):
        payload = {}
    return IngestedEvent(event_name=event_name, payload=dict(payload), raw_body=raw_body)


def is_ping_response(value: IngestedEvent | dict[str, Any]) -> bool:
    """True when ``read_event`` returned a ping response dict instead of an event."""
    return isinstance(value, dict) and value.get('event') == PING_EVENT
