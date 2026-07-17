"""Forgejo-native review, remediation, and terminal workflow helpers."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from a2a_server.github_app.issue_review_task import reviewer_verdict
from a2a_server.github_app.settings import MODEL_REF, TASK_PRIORITY

from .forgejo_webhooks import forgejo_json

logger = logging.getLogger(__name__)

TASK_TIMEOUT_SECONDS = 604800
MAX_FIX_ATTEMPTS_PER_SHA = 5
_REVIEW_BODY_LIMIT = 60_000
_FAILED_STATES = {'error', 'failure', 'warning'}


def _repo_path(repo: str) -> str:
    owner, name = repo.split('/', 1)
    return f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'


def review_marker(task_id: str) -> str:
    return f'<!-- codetether-forgejo-review-task:{task_id} -->'


def remediation_key(repo: str, pr_number: int, sha: str, context: str) -> str:
    return f'forgejo:{repo}:{pr_number}:status-fix:{sha}:{context}'


def review_event(review_task: dict[str, Any]) -> str:
    verdict = reviewer_verdict(review_task)
    if verdict == 'APPROVED':
        return 'APPROVED'
    if verdict in {'CHANGES_REQUESTED', 'BLOCKED'}:
        return 'REQUEST_CHANGES'
    return 'COMMENT'


def review_body(review_task: dict[str, Any]) -> str:
    task_id = str(review_task.get('id') or '').strip()
    verdict = reviewer_verdict(review_task) or 'COMMENT'
    detail = str(
        review_task.get('result')
        or review_task.get('error')
        or 'CodeTether reviewer task completed without a textual summary.'
    ).strip()
    marker = review_marker(task_id)
    prefix = f'## CodeTether Review\n\n**Verdict:** `{verdict}`\n\n'
    available = max(0, _REVIEW_BODY_LIMIT - len(prefix) - len(marker) - 2)
    return f'{prefix}{detail[:available]}\n\n{marker}'


def is_failed_status(status: dict[str, Any]) -> bool:
    return (
        str(status.get('status') or status.get('state') or '').lower()
        in _FAILED_STATES
    )


def is_self_status(status: dict[str, Any]) -> bool:
    creator = status.get('creator') or {}
    login = str(creator.get('login') or creator.get('username') or '').lower()
    context = str(status.get('context') or '').lower()
    return login in {'codetether', 'codetether-bot'} or context.startswith(
        'codetether/'
    )


async def request_forgejo_review(
    *, base: str, repo: str, pr_number: int, reviewer: str | None
) -> bool:
    login = str(reviewer or '').strip()
    if (
        not login
        or login.lower() in {'codetether', 'codetether-bot'}
        or login.lower().endswith('[bot]')
    ):
        return False
    await forgejo_json(
        'POST',
        base,
        f'{_repo_path(repo)}/pulls/{pr_number}/requested_reviewers',
        {'reviewers': [login]},
    )
    return True


async def publish_forgejo_review(review_task: dict[str, Any]) -> dict[str, Any]:
    metadata = review_task.get('metadata') or {}
    task_id = str(review_task.get('id') or '').strip()
    repo = str(metadata.get('repo') or '').strip()
    base = str(metadata.get('forgejo_api_url') or '').rstrip('/')
    pr_number = int(metadata.get('pr_number') or 0)
    head_sha = str(metadata.get('pr_head_sha') or '').strip()
    if not (task_id and repo and base and pr_number):
        raise ValueError('review task is missing Forgejo publication context')

    path = f'{_repo_path(repo)}/pulls/{pr_number}/reviews'
    marker = review_marker(task_id)
    reviews = await forgejo_json('GET', base, f'{path}?limit=100')
    for review in reviews or []:
        if marker in str((review or {}).get('body') or ''):
            return {
                'published': True,
                'duplicate': True,
                'event': str((review or {}).get('state') or 'COMMENT'),
                'review_id': (review or {}).get('id'),
            }

    payload: dict[str, Any] = {
        'body': review_body(review_task),
        'event': review_event(review_task),
    }
    if head_sha:
        payload['commit_id'] = head_sha
    published = await forgejo_json('POST', base, path, payload)
    return {
        'published': True,
        'duplicate': False,
        'event': payload['event'],
        'review_id': (published or {}).get('id'),
    }


async def _task_exists(work_key: str) -> bool:
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return False
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id FROM tasks
               WHERE COALESCE(metadata, '{}'::jsonb)->>'forgejo_work_key' = $1
               LIMIT 1""",
            work_key,
        )
    return bool(row)


async def create_forgejo_review_task(code_task: dict[str, Any]) -> str | None:
    metadata = code_task.get('metadata') or {}
    if str(code_task.get('status')) != 'completed':
        return None
    repo = str(metadata.get('repo') or '')
    base = str(metadata.get('forgejo_api_url') or '').rstrip('/')
    pr_number = int(metadata.get('pr_number') or 0)
    workspace_id = str(metadata.get('workspace_id') or '')
    branch_hint = str(metadata.get('branch_name') or '')
    if not (repo and base and workspace_id):
        return None

    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    pr: dict[str, Any] | None = None
    if pr_number:
        pr = await forgejo_json(
            'GET', base, f'{_repo_path(repo)}/pulls/{pr_number}'
        )
    elif branch_hint:
        pulls = await forgejo_json(
            'GET', base, f'{_repo_path(repo)}/pulls?state=open&limit=50'
        )
        pr = next(
            (
                candidate
                for candidate in pulls or []
                if str(((candidate or {}).get('head') or {}).get('ref') or '')
                == branch_hint
            ),
            None,
        )
        pr_number = int(
            (pr or {}).get('number') or (pr or {}).get('index') or 0
        )
    if not pr or not pr_number:
        return None
    head = pr.get('head') or {}
    head_sha = str(head.get('sha') or '')
    branch = str(head.get('ref') or metadata.get('branch_name') or '')
    work_key = f'forgejo:{repo}:{pr_number}:review:{head_sha}'
    if await _task_exists(work_key):
        return None

    routing = {
        key: metadata[key]
        for key in (
            'target_agent_name',
            'target_worker_id',
            'required_capabilities',
        )
        if metadata.get(key)
    }
    review_metadata = {
        'workspace_id': workspace_id,
        'source': 'forgejo-webhook',
        'platform': 'forgejo',
        'workflow_stage': 'review',
        'repo': repo,
        'issue_number': metadata.get('issue_number') or pr_number,
        'pr_number': pr_number,
        'branch_name': branch,
        'pr_head_sha': head_sha,
        'forgejo_api_url': base,
        'forgejo_issue_url': metadata.get('forgejo_issue_url')
        or pr.get('html_url'),
        'trigger_actor_login': metadata.get('trigger_actor_login'),
        'parent_task_id': code_task.get('id'),
        'forgejo_work_key': work_key,
        **routing,
    }
    prompt = (
        f'Review Forgejo pull request #{pr_number} in {repo} at head {head_sha}.\n\n'
        'Inspect the implementation, tests, and evidence. Return exactly one '
        'terminal verdict: APPROVED, CHANGES_REQUESTED, or BLOCKED, followed by '
        'concise evidence. Never modify the branch during review.'
    )
    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Review Forgejo PR #{pr_number}',
        prompt=prompt,
        agent_type='review',
        priority=TASK_PRIORITY,
        model_ref=MODEL_REF,
        metadata=review_metadata,
        task_timeout_seconds=TASK_TIMEOUT_SECONDS,
        github_issue_url=review_metadata['forgejo_issue_url'],
    )
    await request_forgejo_review(
        base=base,
        repo=repo,
        pr_number=pr_number,
        reviewer=metadata.get('trigger_actor_login'),
    )
    return task_id


async def create_forgejo_fix_followup(
    review_task: dict[str, Any],
) -> str | None:
    verdict = reviewer_verdict(review_task)
    if verdict not in {'CHANGES_REQUESTED', 'BLOCKED'}:
        return None
    metadata = review_task.get('metadata') or {}
    repo = str(metadata.get('repo') or '')
    base = str(metadata.get('forgejo_api_url') or '').rstrip('/')
    pr_number = int(metadata.get('pr_number') or 0)
    workspace_id = str(metadata.get('workspace_id') or '')
    expected_sha = str(metadata.get('pr_head_sha') or '')
    review_task_id = str(review_task.get('id') or '')
    if not (
        repo
        and base
        and pr_number
        and workspace_id
        and expected_sha
        and review_task_id
    ):
        return None

    pr = await forgejo_json(
        'GET', base, f'{_repo_path(repo)}/pulls/{pr_number}'
    )
    if str(pr.get('state') or '').lower() != 'open':
        return None
    current_sha = str((pr.get('head') or {}).get('sha') or '')
    if current_sha != expected_sha:
        return None

    from a2a_server import database as db
    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT COUNT(*)::int AS attempts,
                      BOOL_OR(status IN ('pending','queued','running','working')) AS active,
                      BOOL_OR(
                        COALESCE(metadata, '{}'::jsonb)->>'review_task_id' = $4
                      ) AS review_already_handled
               FROM tasks
               WHERE COALESCE(metadata, '{}'::jsonb)->>'source' = 'forgejo-webhook'
                 AND COALESCE(metadata, '{}'::jsonb)->>'workflow_stage' = 'fix'
                 AND COALESCE(metadata, '{}'::jsonb)->>'repo' = $1
                 AND COALESCE(metadata, '{}'::jsonb)->>'pr_number' = $2
                 AND COALESCE(metadata, '{}'::jsonb)->>'pr_head_sha' = $3""",
            repo,
            str(pr_number),
            expected_sha,
            review_task_id,
        )
    attempts = int((row or {}).get('attempts') or 0)
    if (
        (row or {}).get('review_already_handled')
        or (row or {}).get('active')
        or attempts >= MAX_FIX_ATTEMPTS_PER_SHA
    ):
        return None

    routing = {
        key: metadata[key]
        for key in (
            'target_agent_name',
            'target_worker_id',
            'required_capabilities',
        )
        if metadata.get(key)
    }
    fix_metadata = {
        'workspace_id': workspace_id,
        'source': 'forgejo-webhook',
        'platform': 'forgejo',
        'workflow_stage': 'fix',
        'repo': repo,
        'issue_number': metadata.get('issue_number') or pr_number,
        'pr_number': pr_number,
        'branch_name': metadata.get('branch_name')
        or (pr.get('head') or {}).get('ref'),
        'pr_head_sha': expected_sha,
        'forgejo_api_url': base,
        'forgejo_issue_url': metadata.get('forgejo_issue_url')
        or pr.get('html_url'),
        'review_task_id': review_task_id,
        'review_verdict': verdict,
        'fix_followup': 'true',
        'fix_attempt': attempts + 1,
        'forgejo_work_key': f'forgejo:{repo}:{pr_number}:review-fix:{expected_sha}:{attempts + 1}',
        **routing,
    }
    prompt = (
        f'Apply the requested changes from Forgejo review task {review_task_id} '
        f'to PR #{pr_number} in {repo} at head {expected_sha}.\n\n'
        f'Review verdict and evidence:\n{review_task.get("result") or review_task.get("error") or verdict}\n\n'
        'Edit the existing branch, run focused validation, commit, and push. '
        'Do not open a duplicate pull request.'
    )
    return await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Apply Forgejo PR fix #{pr_number}',
        prompt=prompt,
        agent_type='build',
        priority=TASK_PRIORITY,
        model_ref=MODEL_REF,
        metadata=fix_metadata,
        task_timeout_seconds=TASK_TIMEOUT_SECONDS,
        github_issue_url=fix_metadata['forgejo_issue_url'],
    )


async def create_status_remediation_task(
    *, base: str, repo: str, pr: dict[str, Any], status: dict[str, Any]
) -> str | None:
    if not is_failed_status(status) or is_self_status(status):
        return None
    pr_number = int(pr.get('number') or pr.get('index') or 0)
    head = pr.get('head') or {}
    sha = str(head.get('sha') or '')
    branch = str(head.get('ref') or '')
    context = str(status.get('context') or 'unknown')
    work_key = remediation_key(repo, pr_number, sha, context)
    if not (pr_number and sha and branch) or await _task_exists(work_key):
        return None

    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    clone_url = str(((head.get('repo') or {}).get('clone_url')) or '')
    if not clone_url:
        repo_data = await forgejo_json('GET', base, _repo_path(repo))
        clone_url = str((repo_data or {}).get('clone_url') or '')
    if not clone_url:
        return None

    from a2a_server.forgejo_webhooks import _ensure_workspace, _token
    from a2a_server.github_app.routing import resolve_task_target

    workspace_id = await _ensure_workspace(
        {
            'repo': repo,
            'number': pr_number,
            'repo_data': head.get('repo') or {},
        },
        clone_url,
        branch,
        _token(),
    )
    routing = await resolve_task_target()
    detail = str(status.get('description') or '')
    target_url = str(status.get('target_url') or '')
    metadata = {
        'workspace_id': workspace_id,
        'source': 'forgejo-webhook',
        'platform': 'forgejo',
        'workflow_stage': 'fix',
        'repo': repo,
        'issue_number': pr_number,
        'pr_number': pr_number,
        'branch_name': branch,
        'pr_head_sha': sha,
        'forgejo_api_url': base,
        'forgejo_issue_url': pr.get('html_url'),
        'forgejo_status_context': context,
        'forgejo_status_target_url': target_url,
        'forgejo_work_key': work_key,
        **routing,
    }
    prompt = (
        f'Fix failed Forgejo status `{context}` on PR #{pr_number} in {repo} at {sha}.\n\n'
        f'Description: {detail}\nTarget: {target_url}\n\n'
        'Inspect the failing check evidence, edit the existing branch, run focused '
        'validation, commit, and push. Do not open a duplicate pull request.'
    )
    return await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Fix Forgejo status {context} on PR #{pr_number}',
        prompt=prompt,
        agent_type='build',
        priority=TASK_PRIORITY,
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=TASK_TIMEOUT_SECONDS,
        github_issue_url=metadata['forgejo_issue_url'],
    )


async def reconcile_forgejo_failures(limit: int = 20) -> int:
    """Poll open Forgejo PR heads because Forgejo 15 has no status webhook."""
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT metadata->>'repo' AS repo,
                              metadata->>'forgejo_api_url' AS base
               FROM tasks
               WHERE metadata->>'source' = 'forgejo-webhook'
                 AND metadata->>'repo' IS NOT NULL
                 AND metadata->>'forgejo_api_url' IS NOT NULL
               ORDER BY repo
               LIMIT $1""",
            limit,
        )
    handled = 0
    for row in rows:
        repo = str(row['repo'])
        base = str(row['base']).rstrip('/')
        pulls = await forgejo_json(
            'GET', base, f'{_repo_path(repo)}/pulls?state=open&limit=50'
        )
        for pr in pulls or []:
            sha = str(((pr.get('head') or {}).get('sha')) or '')
            if not sha:
                continue
            statuses = await forgejo_json(
                'GET',
                base,
                f'{_repo_path(repo)}/commits/{sha}/statuses?limit=50',
            )
            for status in statuses or []:
                if await create_status_remediation_task(
                    base=base, repo=repo, pr=pr, status=status
                ):
                    handled += 1
    return handled


async def reconcile_forgejo_terminal_reviews(limit: int = 20) -> int:
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id FROM tasks
               WHERE status = 'completed'
                 AND metadata->>'source' = 'forgejo-webhook'
                 AND metadata->>'workflow_stage' = 'review'
                 AND NOT (COALESCE(metadata, '{}'::jsonb) ? 'forgejo_review_reconciled_at')
               ORDER BY completed_at
               LIMIT $1""",
            limit,
        )
    handled = 0
    for row in rows:
        task = await db.db_get_task(str(row['id']))
        if not task:
            continue
        await publish_forgejo_review(task)
        await create_forgejo_fix_followup(task)
        await _mark_review_reconciled(str(row['id']))
        handled += 1
    return handled


async def _mark_review_reconciled(task_id: str) -> None:
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE tasks
               SET metadata = COALESCE(metadata, '{}'::jsonb)
                   || jsonb_build_object('forgejo_review_reconciled_at', NOW()::text),
                   updated_at = NOW()
               WHERE id = $1""",
            task_id,
        )
