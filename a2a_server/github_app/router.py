"""GitHub App webhook ingress for `@codetether` comment requests."""

import json
import logging

from fastapi import APIRouter, Request

from .active_work import (
    dispatch_active_work_for_installation,
    has_active_github_app_task,
)
from .auth import installation_token, verify_signature
from .check_failures import (
    context_from_failed_check,
    should_remediate_failed_check,
)
from .mention import is_fix_request
from .payload import (
    extract_context,
    is_changes_requested_review,
    is_self_authored_event,
    is_supported_event_action,
)
from .handler import handle_fix_request
from .remediation import (
    RemediationContext,
    _is_codetether_authored,
    is_duplicate,
    mark_seen,
    normalize_check_event,
    remediation_prompt,
)
from .routing import resolve_task_target
from .settings import APP_SLUG, MODEL_REF
from .watch import post_issue_comment

github_webhook_router = APIRouter(prefix='/v1/webhooks', tags=['github'])
logger = logging.getLogger(__name__)

_REMEDIATION_EVENTS = frozenset({'check_run', 'check_suite', 'workflow_run'})


async def _handle_remediation_event(event_name: str, payload: dict) -> dict:
    """Process a check failure event into a remediation task (or skip)."""
    ctx = normalize_check_event(event_name, payload)
    if ctx is None:
        logger.info(
            'Remediation: event did not produce a context (event=%s action=%s)',
            event_name,
            payload.get('action'),
        )
        return {'ignored': True, 'reason': 'ineligible-check-event'}

    if _is_codetether_authored(ctx):
        logger.info(
            'Remediation: skipping self-authored check %r on %s@%s',
            ctx.check_name, ctx.repo_full_name, ctx.head_sha[:12],
        )
        return {'ignored': True, 'reason': 'self-authored-check'}

    if not ctx.pr_number:
        logger.info(
            'Remediation: no open PR associated with check %r on %s@%s',
            ctx.check_name, ctx.repo_full_name, ctx.head_sha[:12],
        )
        return {'ignored': True, 'reason': 'no-associated-pr'}

    if is_duplicate(ctx):
        logger.info(
            'Remediation: duplicate delivery suppressed for %r on %s@%s',
            ctx.check_name, ctx.repo_full_name, ctx.head_sha[:12],
        )
        return {'ignored': True, 'reason': 'duplicate-suppressed'}

    # Queue the remediation task
    task_id = await _queue_remediation_task(ctx)
    mark_seen(ctx)

    logger.info(
        'Remediation: queued task %s for failed check %r on %s PR #%s',
        task_id, ctx.check_name, ctx.repo_full_name, ctx.pr_number,
    )
    return {
        'accepted': True,
        'remediation_task_id': task_id,
        'check_name': ctx.check_name,
        'head_sha': ctx.head_sha,
        'pr_number': ctx.pr_number,
    }


async def _queue_remediation_task(ctx: RemediationContext) -> str:
    """Create and dispatch a fire-and-forget remediation task."""
    from ..persistent_worker_pool import create_and_dispatch_task

    routing = await resolve_task_target()
    metadata = {
        'source': 'github-app',
        'workflow_stage': 'remediation',
        'repo': ctx.repo_full_name,
        'pr_number': ctx.pr_number,
        'pr_head': ctx.branch,
        'head_sha': ctx.head_sha,
        'github_installation_id': ctx.installation_id,
        'github_issue_url': f'https://github.com/{ctx.repo_full_name}/pull/{ctx.pr_number}',
        'failed_check_name': ctx.check_name,
        'failed_check_conclusion': ctx.conclusion,
        'failed_check_details_url': ctx.details_url,
        'failed_check_event_type': ctx.event_type,
        **routing,
    }
    return await create_and_dispatch_task(
        title=f'Remediate failed check: {ctx.check_name} (PR #{ctx.pr_number})',
        prompt=remediation_prompt(ctx),
        agent_type='remediation',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=604800,
        github_issue_url=f'https://github.com/{ctx.repo_full_name}/pull/{ctx.pr_number}',
    )


@github_webhook_router.post('/github')
async def handle_github_webhook(request: Request):
    """Accept GitHub App events and translate `@codetether` mentions into tasks."""
    body = await request.body()
    await verify_signature(request.headers.get('X-Hub-Signature-256', ''), body)
    event_name = request.headers.get('X-GitHub-Event', '')
    if event_name == 'ping':
        return {'ok': True, 'event': 'ping'}
    payload = json.loads(body or b'{}')

    # --- Failed-check remediation loop (issue #88) ---
    if event_name in _REMEDIATION_EVENTS:
        return await _handle_remediation_event(event_name, payload)

    # --- Existing mention-driven flow ---
    if is_self_authored_event(event_name, payload):
        logger.info(
            'GitHub App webhook ignored self-authored event: event=%s action=%s',
            event_name,
            payload.get('action'),
        )
        return {
            'ignored': True,
            'reason': 'self-authored-event',
            'event': event_name,
            'action': payload.get('action'),
        }
    if _should_dispatch_installed_repo_active_work(event_name, payload):
        installation_id = int(payload.get('installation', {}).get('id') or 0)
        results = await dispatch_active_work_for_installation(installation_id)
        return {
            'accepted': True,
            'trigger': event_name,
            'dispatched': len(results),
        }
    if should_remediate_failed_check(event_name, payload):
        context = context_from_failed_check(event_name, payload)
        token, _ = await installation_token(context.installation_id)
        if await has_active_github_app_task(
            context.repo_full_name, context.issue_number
        ):
            return {
                'trigger': 'failed_check',
                'accepted': False,
                'reason': 'active-task-exists',
            }
        result = await handle_fix_request(context, token)
        return {'trigger': 'failed_check', **result}
    if not is_supported_event_action(event_name, payload):
        logger.info(
            'GitHub App webhook ignored unsupported event/action: event=%s action=%s',
            event_name,
            payload.get('action'),
        )
        return {
            'ignored': True,
            'reason': 'unsupported-event-action',
            'event': event_name,
            'action': payload.get('action'),
        }
    context = extract_context(event_name, payload)
    if not context:
        logger.info(
            'GitHub App webhook ignored event without @%s mention context: event=%s action=%s',
            APP_SLUG,
            event_name,
            payload.get('action'),
        )
        return {'ignored': True}
    token, _ = await installation_token(context.installation_id)
    is_review_change_request = is_changes_requested_review(event_name, payload)
    is_explicit_fix_request = is_fix_request(context.comment_body)
    if not is_review_change_request and not is_explicit_fix_request:
        if await has_active_github_app_task(
            context.repo_full_name, context.issue_number
        ):
            return {'accepted': False, 'reason': 'active-task-exists'}
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            '## 🤖 CodeTether\n\n'
            'I saw the mention, but I only start repository-changing work when the '
            'comment explicitly asks me to fix, apply, implement, handle, or otherwise '
            'change code.\n\n'
            'For issues, I can create a branch and open a PR; for pull requests, I can '
            f'push to the PR branch. Try `@{APP_SLUG} handle this issue` or '
            f'`@{APP_SLUG} implement this`.',
        )
        return {'accepted': False, 'reason': 'non-fix mention'}
    if await has_active_github_app_task(
        context.repo_full_name, context.issue_number
    ):
        return {'accepted': False, 'reason': 'active-task-exists'}
    return await handle_fix_request(context, token)


def _should_dispatch_installed_repo_active_work(
    event_name: str, payload: dict
) -> bool:
    """Return true when GitHub App repo scope changes need active-work backfill."""
    action = payload.get('action')
    return (event_name == 'installation' and action == 'created') or (
        event_name == 'installation_repositories'
        and action in {'added', 'created'}
    )
