"""Webhook subpackage: single-responsibility helpers for the GitHub App router.

Public surface re-exported for the router and any external callers:

    Deps                          bound-callable carrier
    ingest.read_event             signature verify, body parse, ping shortcut
    ingest.is_ping_response       type discriminator for read_event output
    filters.is_installation_scope_event
    filters.is_self_authored
    filters.has_actionable_event
    install_events.handle_installation_scope_event
    failed_checks.handle_failed_check
    mention_dispatch.handle_mention_event
    responses.ignored, .rejected, .accepted
"""

from .deps import Deps
from . import (
    failed_checks,
    filters,
    ingest,
    install_events,
    mention_dispatch,
    responses,
)

__all__ = [
    'Deps',
    'failed_checks',
    'filters',
    'ingest',
    'install_events',
    'mention_dispatch',
    'responses',
]
