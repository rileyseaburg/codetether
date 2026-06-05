"""Standardized response builders for the GitHub App webhook.

Centralizing the response shapes here keeps the router's branches thin and makes
it easy to add fields consistently (e.g., trace IDs) in one place.
"""

from __future__ import annotations

from typing import Any


def ignored(event: str, reason: str, action: Any = None) -> dict[str, Any]:
    """Build a response for an event that was deliberately not actioned."""
    response: dict[str, Any] = {
        'ignored': True,
        'reason': reason,
        'event': event,
    }
    if action is not None:
        response['action'] = action
    return response


def rejected(reason: str, **extra: Any) -> dict[str, Any]:
    """Build a response for an actionable event that was declined for a reason."""
    return {'accepted': False, 'reason': reason, **extra}


def accepted(trigger: str, **extra: Any) -> dict[str, Any]:
    """Build a response for an actionable event that produced work."""
    return {'accepted': True, 'trigger': trigger, **extra}
