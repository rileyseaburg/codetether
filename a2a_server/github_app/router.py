"""Thin orchestrator for POST /v1/webhooks/github.

Each gate delegates to a single-responsibility helper under ``webhook/``
(signature verify, ping, self-authored guard, install welcome, failed
check, mention dispatch, unsupported-event filter).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from . import active_work as _active_work
from .auth import installation_token, verify_signature
from .handler import handle_fix_request
from .settings import APP_SLUG
from .watch import post_issue_comment
from .webhook import (
    Deps,
    failed_checks,
    filters,
    ingest,
    install_events,
    mention_dispatch,
    responses,
)

# Back-compat shim: install events no longer auto-dispatch; the symbol is
# preserved for callers and tests that still import it.
dispatch_active_work_for_installation = (
    _active_work.dispatch_active_work_for_installation
)
has_active_github_app_task = _active_work.has_active_github_app_task

github_webhook_router = APIRouter(prefix='/v1/webhooks', tags=['github'])
logger = logging.getLogger(__name__)


def _deps() -> Deps:
    """Build a Deps carrier that re-reads the router's bound callables per call."""
    return Deps(
        installation_token=installation_token,
        has_active_github_app_task=has_active_github_app_task,
        handle_fix_request=handle_fix_request,
        post_issue_comment=post_issue_comment,
    )


@github_webhook_router.post('/github')
async def handle_github_webhook(request: Request):
    """Accept a GitHub App webhook and route it to the appropriate helper."""
    event = await ingest.read_event(request, verify=verify_signature)
    if ingest.is_ping_response(event):
        return event
    assert isinstance(event, ingest.IngestedEvent)
    name, payload = event.event_name, event.payload
    deps = _deps()
    if filters.is_self_authored(name, payload):
        return _log_and_ignore(name, payload, 'self-authored-event')
    if filters.is_installation_scope_event(name, payload):
        return await install_events.handle_installation_scope_event(
            name, payload, deps
        )
    failed = await failed_checks.handle_failed_check(name, payload, deps)
    if failed is not None:
        return failed
    if not filters.has_actionable_event(name, payload):
        return _log_and_ignore(name, payload, 'unsupported-event-action')
    return await mention_dispatch.handle_mention_event(name, payload, deps)


def _log_and_ignore(name: str, payload: dict, reason: str) -> dict:
    """Log a single-action ignore case and return the response."""
    logger.info('%s event=%s action=%s', reason, name, payload.get('action'))
    return responses.ignored(name, reason, action=payload.get('action'))
