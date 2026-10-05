"""Failed-check remediation dispatch.

Wraps the predicate and helper that convert ``check_run`` / ``check_suite`` /
``workflow_run`` events with a failed conclusion into a CodeTether fix task.

Accepts a ``Deps`` carrier so the router can pass its module-bound callables
without threading each one through the signature.
"""

from __future__ import annotations

from ..check_failures import (
    context_from_failed_check,
    should_remediate_failed_check,
)
from . import responses
from .deps import Deps


async def handle_failed_check(
    event_name: str, payload: dict, deps: Deps
) -> dict | None:
    """Return a response for failed-check events, or None if not applicable."""
    if not should_remediate_failed_check(event_name, payload):
        return None
    context = context_from_failed_check(event_name, payload)
    token, _ = await deps.installation_token(context.installation_id)
    if await deps.has_active_github_app_task(
        context.repo_full_name, context.issue_number
    ):
        return responses.rejected('active-task-exists', trigger='failed_check')
    result = await deps.handle_fix_request(context, token)
    return {'trigger': 'failed_check', **result}
