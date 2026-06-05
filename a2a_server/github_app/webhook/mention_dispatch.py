"""Mention-driven dispatch for issue, PR, and review webhook events.

The dispatcher accepts its dependencies as keyword arguments so the router
can pass its module-bound names. This keeps existing tests that patch
``router.installation_token``, ``router.post_issue_comment``, and
``router.handle_fix_request`` working.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from ..mention import is_fix_request
from ..payload import extract_context, is_changes_requested_review
from ..settings import APP_SLUG
from . import responses

logger = logging.getLogger(__name__)

TokenMint = Callable[[int], Awaitable[tuple[str, Optional[str]]]]
DedupeCheck = Callable[[str, int], Awaitable[bool]]
FixHandler = Callable[[Any, str], Awaitable[dict[str, Any]]]
CommentPoster = Callable[[str, int, str, str], Awaitable[None]]

NON_FIX_GUIDANCE_TEMPLATE = (
    "## 🤖 CodeTether\n\n"
    "I saw the mention, but I only start repository-changing work when the "
    "comment explicitly asks me to fix, apply, implement, handle, or "
    "otherwise change code.\n\n"
    "For issues, I can create a branch and open a PR; for pull requests, I "
    "can push to the PR branch. Try `@{slug} handle this issue` or "
    "`@{slug} implement this`."
)


def _is_actionable_request(event_name: str, payload: dict[str, Any], body: str) -> bool:
    """True for review-change requests or explicit @bot fix verbs."""
    return is_changes_requested_review(event_name, payload) or is_fix_request(body)


async def handle_mention_event(
    event_name: str,
    payload: dict[str, Any],
    *,
    installation_token: TokenMint,
    has_active_github_app_task: DedupeCheck,
    handle_fix_request: FixHandler,
    post_issue_comment: CommentPoster,
) -> dict[str, Any]:
    """Return a response for mention-bearing events."""
    context = extract_context(event_name, payload)
    if not context:
        logger.info(
            'webhook ignored no-mention event=%s action=%s',
            event_name,
            payload.get('action'),
        )
        return responses.ignored(event_name, 'no-mention', action=payload.get('action'))
    token, _ = await installation_token(context.installation_id)
    if not _is_actionable_request(event_name, payload, context.comment_body):
        if await has_active_github_app_task(
            context.repo_full_name, context.issue_number
        ):
            return responses.rejected('active-task-exists')
        body = NON_FIX_GUIDANCE_TEMPLATE.format(slug=APP_SLUG)
        await post_issue_comment(
            context.repo_full_name, context.issue_number, token, body
        )
        return responses.rejected('non-fix mention')
    if await has_active_github_app_task(
        context.repo_full_name, context.issue_number
    ):
        return responses.rejected('active-task-exists')
    return await handle_fix_request(context, token)
