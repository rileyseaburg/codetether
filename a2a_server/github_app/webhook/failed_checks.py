"""Failed-check remediation dispatch.

Wraps the predicate and helper that convert ``check_run`` / ``check_suite`` /
``workflow_run`` events with a failed conclusion into a CodeTether fix task.

The dispatcher accepts the callables it needs (token mint, fix request, task
dedupe) so the router can pass its module-bound names. This keeps existing
tests that patch ``router.installation_token`` working without reaching into
the helper module.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from ..check_failures import context_from_failed_check, should_remediate_failed_check
from . import responses

TokenMint = Callable[[int], Awaitable[tuple[str, Optional[str]]]]
DedupeCheck = Callable[[str, int], Awaitable[bool]]
FixHandler = Callable[[Any, str], Awaitable[dict[str, Any]]]


async def handle_failed_check(
    event_name: str,
    payload: dict[str, Any],
    *,
    installation_token: TokenMint,
    has_active_github_app_task: DedupeCheck,
    handle_fix_request: FixHandler,
) -> dict[str, Any] | None:
    """Return a response dict for failed-check events, or None if not applicable."""
    if not should_remediate_failed_check(event_name, payload):
        return None
    context = context_from_failed_check(event_name, payload)
    token, _ = await installation_token(context.installation_id)
    if await has_active_github_app_task(
        context.repo_full_name, context.issue_number
    ):
        return responses.rejected('active-task-exists', trigger='failed_check')
    result = await handle_fix_request(context, token)
    return {'trigger': 'failed_check', **result}
