"""Event/action filter predicates used to reject bot loops and stray traffic."""

from __future__ import annotations

from typing import Any

from ..payload import is_self_authored_event, is_supported_event_action

INSTALLATION_EVENT = 'installation'
INSTALLATION_REPOS_EVENT = 'installation_repositories'
INSTALL_CREATED_ACTIONS = {'created'}
REPO_SCOPE_ACTIONS = {'added', 'created'}


def is_installation_scope_event(event_name: str, payload: dict[str, Any]) -> bool:
    """True for installation/installation_repositories scope changes."""
    action = payload.get('action')
    if event_name == INSTALLATION_EVENT and action in INSTALL_CREATED_ACTIONS:
        return True
    if event_name == INSTALLATION_REPOS_EVENT and action in REPO_SCOPE_ACTIONS:
        return True
    return False


def is_self_authored(event_name: str, payload: dict[str, Any]) -> bool:
    """Re-export of payload.is_self_authored_event for router-local cohesion."""
    return is_self_authored_event(event_name, payload)


def has_actionable_event(event_name: str, payload: dict[str, Any]) -> bool:
    """Re-export of payload.is_supported_event_action for router-local cohesion."""
    return is_supported_event_action(event_name, payload)
