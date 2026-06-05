"""Thin orchestrator for POST /v1/webhooks/github.

Each gate delegates to a single-responsibility helper under ``webhook/``
(signature verify, ping, self-authored guard, install welcome, failed
check, mention dispatch, unsupported-event filter). This module owns the
FastAPI router and the response chain.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from .auth import installation_token, verify_signature
from .handler import handle_fix_request
from .settings import APP_SLUG
from .watch import post_issue_comment
from .webhook import (
    failed_checks,
    filters,
    ingest,
    install_events,
    mention_dispatch,
    responses,
)
from . import active_work as _active_work

# Back-compat shim: the install-event branch used to auto-dispatch active
# work. The new design posts opt-in guidance instead; we keep the symbol so
# existing callers and tests don't break.
dispatch_active_work_for_installation = _active_work.dispatch_active_work_for_installation
has_active_github_app_task = _active_work.has_active_github_app_task

__all__ = [
    'APP_SLUG',
    'github_webhook_router',
    'handle_github_webhook',
    'verify_signature',
    'installation_token',
    'post_issue_comment',
    'handle_fix_request',
    'dispatch_active_work_for_installation',
    'has_active_github_app_task',
]

github_webhook_router = APIRouter(prefix='/v1/webhooks', tags=['github'])
logger = logging.getLogger(__name__)


@github_webhook_router.post('/github')
async def handle_github_webhook(request: Request):
    """Accept a GitHub App webhook and route it to the appropriate helper."""
    event = await ingest.read_event(request, verify=verify_signature)
    if ingest.is_ping_response(event):
        return event
    assert isinstance(event, ingest.IngestedEvent)
    event_name, payload = event.event_name, event.payload
    if filters.is_self_authored(event_name, payload):
        logger.info('self-authored event=%s action=%s', event_name, payload.get('action'))
        return responses.ignored(event_name, 'self-authored-event', action=payload.get('action'))
    if filters.is_installation_scope_event(event_name, payload):
        return await install_events.handle_installation_scope_event(event_name, payload, installation_token=installation_token)
    failed = await failed_checks.handle_failed_check(event_name, payload, installation_token=installation_token, has_active_github_app_task=has_active_github_app_task, handle_fix_request=handle_fix_request)
    if failed is not None:
        return failed
    if not filters.has_actionable_event(event_name, payload):
        logger.info('unsupported event=%s action=%s', event_name, payload.get('action'))
        return responses.ignored(event_name, 'unsupported-event-action', action=payload.get('action'))
    return await mention_dispatch.handle_mention_event(event_name, payload, installation_token=installation_token, has_active_github_app_task=has_active_github_app_task, handle_fix_request=handle_fix_request, post_issue_comment=post_issue_comment)
