"""GitHub App webhook ingress for `@codetether` comment requests."""

import json

from fastapi import APIRouter, Request

from .auth import installation_token, verify_signature
from .mention import is_fix_request
from .payload import extract_context
from .handler import handle_fix_request
from .settings import APP_SLUG
from .watch import post_issue_comment

github_webhook_router = APIRouter(prefix='/v1/webhooks', tags=['github'])


@github_webhook_router.post('/github')
async def handle_github_webhook(request: Request):
    """Accept GitHub App events and translate `@codetether` PR fix comments into tasks."""
    body = await request.body()
    await verify_signature(request.headers.get('X-Hub-Signature-256', ''), body)
    event_name = request.headers.get('X-GitHub-Event', '')
    if event_name == 'ping':
        return {'ok': True, 'event': 'ping'}
    payload = json.loads(body or b'{}')
    if payload.get('action') != 'created':
        return {'ignored': True, 'reason': 'unsupported-action'}
    context = extract_context(event_name, payload)
    if not context:
        return {'ignored': True}
    token, _ = await installation_token(context.installation_id)
    if not is_fix_request(context.comment_body):
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            "## 🤖 CodeTether\n\n"
            "I saw the mention, but I only start repository-changing work when the "
            "comment explicitly asks me to fix, apply, implement, handle, or otherwise "
            "change code.\n\n"
            "For issues, I can create a branch and open a PR; for pull requests, I can "
            f"push to the PR branch. Try `@{APP_SLUG} handle this issue` or "
            f"`@{APP_SLUG} implement this`.",
        )
        return {'accepted': False, 'reason': 'non-fix mention'}
    return await handle_fix_request(context, token)
