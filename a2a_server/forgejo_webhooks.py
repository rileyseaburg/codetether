"""Native Forgejo webhook handling for @codetether issue and PR requests."""

# Lazy service imports avoid the server/monitor import cycle; long SQL and worker
# prompts remain readable as intact protocol strings.
# ruff: noqa: E501, PLC0415, PLR2004

from __future__ import annotations

import hashlib
import hmac
import importlib
import os

from typing import Any
from urllib.parse import quote, urlparse

import httpx

from fastapi import APIRouter, HTTPException, Request

from a2a_server.github_app.mention import is_fix_request, mentions_bot
from a2a_server.github_app.routing import resolve_task_target
from a2a_server.github_app.settings import TASK_PRIORITY
from a2a_server.github_app.workspace import workspace_id
from a2a_server.session_view import session_view_router


forgejo_webhook_router = APIRouter(tags=['forgejo'])
forgejo_webhook_router.include_router(session_view_router)


def _setting(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


def _event_name(request: Request) -> str:
    return (
        request.headers.get('X-Forgejo-Event')
        or request.headers.get('X-Gitea-Event')
        or ''
    ).lower()


def _signature(request: Request) -> str:
    return (
        request.headers.get('X-Forgejo-Signature')
        or request.headers.get('X-Gitea-Signature')
        or ''
    )


def verify_forgejo_signature(signature: str, body: bytes) -> None:
    """Verify a Forgejo/Gitea webhook HMAC-SHA256 signature."""
    secret = _setting('FORGEJO_WEBHOOK_SECRET')
    if not secret:
        raise HTTPException(503, 'Forgejo webhook secret is not configured')
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    supplied = signature.removeprefix('sha256=')
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, 'Invalid Forgejo webhook signature')


def _context(event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if event != 'issue_comment' or payload.get('action') not in {
        'created',
        'edited',
    }:
        return None
    comment = payload.get('comment') or {}
    issue = payload.get('issue') or {}
    repo = payload.get('repository') or {}
    body = str(comment.get('body') or '')
    if payload.get('action') == 'edited':
        old = ((payload.get('changes') or {}).get('body') or {}).get(
            'from'
        ) or ''
        if mentions_bot(str(old)):
            return None
    if not mentions_bot(body):
        return None
    full_name = str(repo.get('full_name') or repo.get('name') or '')
    number = int(issue.get('number') or issue.get('index') or 0)
    if not full_name or not number:
        return None
    pull = issue.get('pull_request') or {}
    return {
        'repo': full_name,
        'number': number,
        'is_pr': bool(pull),
        'body': body,
        'issue': issue,
        'repo_data': repo,
        'comment': comment,
        'comment_id': int(comment.get('id') or 0),
        'html_url': str(issue.get('html_url') or ''),
        'actor_login': str(
            (payload.get('sender') or {}).get('login')
            or (payload.get('sender') or {}).get('username')
            or (comment.get('user') or {}).get('login')
            or ''
        ),
    }


def _is_self_authored(payload: dict[str, Any]) -> bool:
    bot = _setting('FORGEJO_BOT_USERNAME', 'codetether').lower()
    actors = [
        (payload.get('comment') or {}).get('user') or {},
        payload.get('sender') or {},
    ]
    return any(
        str(actor.get('login') or actor.get('username') or '').lower() == bot
        for actor in actors
    )


def _api_base(payload: dict[str, Any]) -> str:
    configured = _setting('FORGEJO_API_URL')
    if configured:
        return configured.rstrip('/')
    repo_url = str((payload.get('repository') or {}).get('html_url') or '')
    parsed = urlparse(repo_url)
    if parsed.scheme and parsed.netloc:
        return f'{parsed.scheme}://{parsed.netloc}/api/v1'
    raise HTTPException(503, 'Forgejo API URL is not configured')


def _token() -> str:
    token = _setting('FORGEJO_TOKEN')
    if not token:
        raise HTTPException(503, 'Forgejo bot token is not configured')
    return token


async def forgejo_json(
    method: str, base: str, path: str, payload: dict | None = None
) -> object:
    """Call the configured Forgejo JSON API using the bot token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f'{base}{path}',
            headers={
                'Authorization': f'token {_token()}',
                'Accept': 'application/json',
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(
            502, f'Forgejo API {method} {path} failed: {response.text[:400]}'
        )
    return response.json() if response.content else {}


async def _comment(base: str, repo: str, number: int, body: str) -> None:
    owner, name = repo.split('/', 1)
    await forgejo_json(
        'POST',
        base,
        f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}/issues/{number}/comments',
        {'body': body},
    )


async def _active_task(repo: str, number: int) -> bool:
    db = importlib.import_module('a2a_server.database')
    pool = await db.get_pool()
    if not pool:
        return False
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id FROM tasks WHERE status IN ('pending','queued','running','in_progress')
               AND COALESCE(metadata, '{}'::jsonb)->>'source' = 'forgejo-webhook'
               AND COALESCE(metadata, '{}'::jsonb)->>'repo' = $1
               AND COALESCE(metadata, '{}'::jsonb)->>'issue_number' = $2 LIMIT 1""",
            repo,
            str(number),
        )
    return bool(row)


async def _ensure_workspace(
    ctx: dict[str, Any], clone_url: str, branch: str, token: str
) -> str:
    from a2a_server import database as db
    from a2a_server.git_service import store_git_credential_record
    from a2a_server.monitor_api import _redis_upsert_workspace_meta

    wid = workspace_id(clone_url, branch)
    workspace = {
        'id': wid,
        'name': ctx['repo'],
        'path': f'/var/lib/codetether/repos/{wid}',
        'description': f'Forgejo webhook workspace for {ctx["repo"]}',
        'git_url': clone_url,
        'git_branch': branch,
        'status': 'active',
        'agent_config': {
            'source': 'forgejo-webhook',
            'repo': {'full_name': ctx['repo']},
        },
    }
    await db.db_upsert_workspace(workspace)
    await _redis_upsert_workspace_meta(workspace)
    if not await store_git_credential_record(
        wid,
        {
            'token': token,
            'token_type': 'forgejo_pat',
            'git_url': clone_url,
        },
    ):
        raise HTTPException(503, 'Could not store Forgejo git credentials')
    return wid


async def _dispatch(ctx: dict[str, Any], base: str) -> dict[str, Any]:
    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    repo = ctx['repo']
    owner, name = repo.split('/', 1)
    repo_data = await forgejo_json(
        'GET', base, f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    )
    default_branch = str(repo_data.get('default_branch') or 'main')
    branch = default_branch
    head_sha = ''
    if ctx['is_pr']:
        pr = await forgejo_json(
            'GET',
            base,
            f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}/pulls/{ctx["number"]}',
        )
        head = pr.get('head') or {}
        branch = str(head.get('ref') or default_branch)
        head_sha = str(head.get('sha') or '')
    clone_url = str(
        repo_data.get('clone_url') or ctx['repo_data'].get('clone_url') or ''
    )
    if not clone_url:
        raise HTTPException(422, 'Forgejo repository clone URL is missing')
    wid = await _ensure_workspace(ctx, clone_url, branch, _token())
    work_branch = (
        branch if ctx['is_pr'] else f'codetether/issue-{ctx["number"]}'
    )
    kind = 'pull request' if ctx['is_pr'] else 'issue'
    prompt = f"""Handle Forgejo {kind} #{ctx['number']} in {repo}.

Request:
{ctx['body']}

Use the checked-out Forgejo repository. Work on `{work_branch}` (create it from `{default_branch}` for an issue; for a PR update its existing branch). Implement the requested changes, run focused validation, commit, and push. For an issue, open a Forgejo pull request against `{default_branch}`. Post concise progress and the final commit/PR URL back to Forgejo issue #{ctx['number']}. Do not use GitHub APIs."""
    routing = await resolve_task_target()
    from a2a_server.forgejo_agent_client import create_task as create_agent_task

    operation = 'fix' if is_fix_request(ctx['body']) else 'review'
    forgejo_agent_task = await create_agent_task(
        repo=repo,
        operation=operation,
        prompt=prompt,
        idempotency_key=(
            f'forgejo-comment:{ctx.get("comment_id") or 0}:'
            f'{head_sha or work_branch}:{operation}'
        ),
        issue_index=ctx['number'],
        pull_request_index=ctx['number'] if ctx['is_pr'] else 0,
        head_sha=head_sha,
        metadata={
            'source': 'forgejo-agent',
            'trigger_actor_login': ctx.get('actor_login'),
            'comment_id': ctx.get('comment_id'),
        },
        base_url=base,
    )
    forgejo_agent_task_id = int(forgejo_agent_task['id'])
    forgejo_agent_task_url = str(forgejo_agent_task['html_url'])

    from a2a_server.temporal.config import temporal_settings

    if temporal_settings().enabled:
        from a2a_server.forgejo_agent_client import (
            update_task as update_agent_task,
        )
        from a2a_server.temporal.client import start_forgejo_workflow
        from a2a_server.temporal.models import ForgejoAgentWorkflowInput

        workflow_id = await start_forgejo_workflow(
            ForgejoAgentWorkflowInput(
                forgejo_task_id=forgejo_agent_task_id,
                repository=repo,
                issue_number=ctx['number'],
                pull_request_number=ctx['number'] if ctx['is_pr'] else 0,
                workspace_id=wid,
                branch=work_branch,
                head_sha=head_sha,
                operation=operation,
            )
        )
        await update_agent_task(
            repo=repo,
            task_id=forgejo_agent_task_id,
            base_url=base,
            status='accepted',
        )
        return {
            'accepted': True,
            'workspace_id': wid,
            'temporal_workflow_id': workflow_id,
            'forgejo_agent_task_id': forgejo_agent_task_id,
            'forgejo_agent_task_url': forgejo_agent_task_url,
        }

    followup = {
        'workspace_id': wid,
        'source': 'forgejo-webhook',
        'workflow_stage': 'code',
        'platform': 'forgejo',
        'repo': repo,
        'issue_number': ctx['number'],
        'pr_number': ctx['number'] if ctx['is_pr'] else None,
        'branch_name': work_branch,
        'default_branch': default_branch,
        'forgejo_api_url': base,
        'forgejo_issue_url': ctx['html_url'],
        'forgejo_agent_task_id': forgejo_agent_task_id,
        'forgejo_agent_task_url': forgejo_agent_task_url,
        'trigger_actor_login': ctx.get('actor_login'),
        'pr_head_sha': head_sha,
        'forgejo_work_key': (
            f'forgejo:{repo}:{ctx["number"]}:code:{head_sha or work_branch}:'
            f'{ctx.get("comment_id") or 0}'
        ),
        **routing,
    }
    metadata = {
        'workspace_id': wid,
        'source': 'forgejo-webhook',
        'platform': 'forgejo',
        'repo': repo,
        'issue_number': ctx['number'],
        'git_url': clone_url,
        'git_branch': branch,
        'pr_number': ctx['number'] if ctx['is_pr'] else None,
        'pr_head_sha': head_sha,
        'trigger_actor_login': ctx.get('actor_login'),
        'forgejo_api_url': base,
        'forgejo_agent_task_id': forgejo_agent_task_id,
        'forgejo_agent_task_url': forgejo_agent_task_url,
        'forgejo_work_key': (
            f'forgejo:{repo}:{ctx["number"]}:clone:{head_sha or branch}:'
            f'{ctx.get("comment_id") or 0}'
        ),
        **routing,
        'post_clone_task': {
            'title': f'Work Forgejo {kind} #{ctx["number"]}',
            'prompt': prompt,
            'agent_type': 'build',
            'priority': TASK_PRIORITY,
            'model_ref': 'zai:glm-5.1',
            'metadata': followup,
        },
    }
    task_id = await create_and_dispatch_task(
        workspace_id=wid,
        title=f'Prepare Forgejo {kind} #{ctx["number"]}',
        prompt=f'Clone or refresh {repo} on branch {branch} for Forgejo automation.',
        agent_type='clone_repo',
        priority=TASK_PRIORITY,
        metadata=metadata,
        task_timeout_seconds=604800,
    )
    from a2a_server.forgejo_agent_client import update_task as update_agent_task

    await update_agent_task(
        repo=repo,
        task_id=forgejo_agent_task_id,
        base_url=base,
        status='accepted',
        external_task_id=str(task_id),
        head_sha=head_sha,
        branch=work_branch,
    )
    return {
        'accepted': True,
        'workspace_id': wid,
        'clone_task_id': task_id,
        'forgejo_agent_task_id': forgejo_agent_task_id,
        'forgejo_agent_task_url': forgejo_agent_task_url,
    }


async def _handle_status_event(
    payload: dict[str, Any], base: str
) -> dict[str, Any]:
    """Create one remediation task for a failed status on an open PR head."""
    from a2a_server.forgejo_automation import (
        create_status_remediation_task,
        is_failed_status,
        is_self_status,
    )

    repo_data = payload.get('repository') or {}
    repo = str(repo_data.get('full_name') or '')
    sha = str(payload.get('sha') or '')
    sender = payload.get('sender') or {}
    status = {
        'id': payload.get('id'),
        'status': payload.get('state') or payload.get('status'),
        'context': payload.get('context'),
        'description': payload.get('description'),
        'target_url': payload.get('target_url'),
        'creator': sender,
    }
    if not (repo and sha) or '/' not in repo:
        return {'accepted': False, 'reason': 'invalid-status-payload'}
    if not is_failed_status(status) or is_self_status(status):
        return {'accepted': False, 'reason': 'non-failed-or-self-status'}

    owner, name = repo.split('/', 1)
    repo_path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    pr = None
    for page in range(1, 21):
        pulls = await forgejo_json(
            'GET', base, f'{repo_path}/pulls?state=open&limit=50&page={page}'
        )
        if not isinstance(pulls, list):
            return {
                'accepted': False,
                'reason': 'invalid-forgejo-pulls-response',
            }
        pr = next(
            (
                candidate
                for candidate in pulls
                if str(((candidate or {}).get('head') or {}).get('sha') or '')
                == sha
            ),
            None,
        )
        if pr or len(pulls) < 50:
            break
    if not pr:
        return {'accepted': False, 'reason': 'no-open-pr-for-status-sha'}

    task_id = await create_status_remediation_task(
        base=base,
        repo=repo,
        pr=pr,
        status=status,
    )
    return {
        'accepted': bool(task_id),
        'reason': 'queued' if task_id else 'duplicate-or-ignored',
        'task_id': task_id,
    }


@forgejo_webhook_router.post('/v1/webhooks/forgejo/agent-control')
async def handle_forgejo_agent_control(request: Request) -> dict[str, Any]:
    """Verify and signal a native Forgejo cancel/retry control."""
    import json
    import time

    body = await request.body()
    verify_forgejo_signature(_signature(request), body)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, 'Invalid Forgejo control JSON') from exc
    issued_at = int(payload.get('issued_at') or 0)
    if not issued_at or abs(int(time.time()) - issued_at) > 300:
        raise HTTPException(401, 'Expired Forgejo agent control')
    action = str(payload.get('action') or '')
    if action not in {'cancel', 'retry'}:
        raise HTTPException(422, 'Unsupported Forgejo agent control')
    forgejo_task_id = int(payload.get('task_id') or 0)
    if not forgejo_task_id:
        raise HTTPException(422, 'Forgejo task ID is required')

    from a2a_server.temporal.client import signal_control
    from a2a_server.temporal.models import ForgejoControlSignal

    await signal_control(
        ForgejoControlSignal(
            action=action,
            forgejo_task_id=forgejo_task_id,
            requested_by=str(payload.get('requested_by') or ''),
            request_id=str(payload.get('request_id') or ''),
        )
    )
    return {'accepted': True, 'task_id': forgejo_task_id, 'action': action}


@forgejo_webhook_router.post('/v1/webhooks/forgejo')
async def handle_forgejo_webhook(request: Request) -> dict[str, Any]:
    """Authenticate and process a Forgejo issue-comment delivery."""
    body = await request.body()
    verify_forgejo_signature(_signature(request), body)
    payload = await request.json()
    event = _event_name(request)
    if event == 'ping':
        return {'ok': True}
    if event == 'status':
        return await _handle_status_event(payload, _api_base(payload))
    if _is_self_authored(payload):
        return {'accepted': False, 'reason': 'self-authored-event'}
    ctx = _context(event, payload)
    if not ctx:
        return {'accepted': False, 'reason': 'unsupported-or-no-mention'}
    base = _api_base(payload)
    if await _active_task(ctx['repo'], ctx['number']):
        return {'accepted': False, 'reason': 'active-task-exists'}
    if not is_fix_request(ctx['body']):
        await _comment(
            base,
            ctx['repo'],
            ctx['number'],
            '## 🤖 CodeTether\n\nI saw the mention. Ask me explicitly to fix, implement, handle, update, or otherwise change the code, for example: `@codetether handle this issue`.',
        )
        return {'accepted': False, 'reason': 'non-fix mention'}
    result = await _dispatch(ctx, base)
    await _comment(
        base,
        ctx['repo'],
        ctx['number'],
        "## 🛠️ CodeTether Fix\n\nPicked this up. I'm preparing the Forgejo workspace and will report progress here.",
    )
    return result
