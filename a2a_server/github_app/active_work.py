"""GitHub App installed-repository active work dispatch."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from .auth import github_json, installation_token
from .context import MentionContext
from .handler import handle_fix_request
from .mention import is_fix_request
from .settings import APP_SLUG


logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ActiveWorkDispatch:
    """Summary of one active issue or PR considered for dispatch."""

    repo: str
    number: int
    kind: str
    accepted: bool
    reason: str = ''
    task_id: str = ''


async def list_installation_repositories(installation_id: int) -> list[dict[str, Any]]:
    """Return repositories visible to a GitHub App installation token."""
    token, _ = await installation_token(installation_id)
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        data = await github_json(
            'GET',
            f'/installation/repositories?per_page=100&page={page}',
            token,
        )
        batch = data.get('repositories') or []
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def _context_for_item(repo: str, installation_id: int, item: dict[str, Any]) -> MentionContext:
    """Build the normal mention context for a discovered active item."""
    number = int(item['number'])
    is_pr = 'pull_request' in item
    body = str(item.get('body') or '')
    prompt = body if is_fix_request(body) else f'@{APP_SLUG} handle this active work item.\n\n{body}'
    return MentionContext(
        repo_full_name=repo,
        installation_id=installation_id,
        issue_number=number,
        pr_number=number if is_pr else None,
        comment_id=int(item.get('id') or number),
        comment_body=prompt,
    )


async def dispatch_active_work_for_repo(
    repo_full_name: str,
    installation_id: int,
    *,
    limit: int = 100,
) -> list[ActiveWorkDispatch]:
    """Queue direct replacement work for all open active issues and PRs in a repo."""
    token, _ = await installation_token(installation_id)
    results: list[ActiveWorkDispatch] = []
    page = 1
    while True:
        items = await github_json(
            'GET',
            f'/repos/{repo_full_name}/issues?state=open&per_page={limit}&page={page}',
            token,
        )
        if not items:
            return results
        for item in items:
            results.append(await _dispatch_item(repo_full_name, installation_id, item, token))
        if len(items) < limit:
            return results
        page += 1


async def has_active_github_app_task(repo_full_name: str, number: int) -> bool:
    """Return true when an open GitHub App task already targets this item."""
    try:
        from .. import database as db

        pool = await db.get_pool()
        if not pool:
            return False

        number_text = str(number)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id
                FROM tasks
                WHERE status IN ('pending', 'queued', 'running', 'working')
                  AND COALESCE(metadata, '{}'::jsonb)->>'source' = 'github-app'
                  AND COALESCE(metadata, '{}'::jsonb)->>'repo' = $1
                  AND (
                    COALESCE(metadata, '{}'::jsonb)->>'issue_number' = $2
                    OR COALESCE(metadata, '{}'::jsonb)->>'pr_number' = $2
                  )
                ORDER BY created_at ASC
                LIMIT 1
                """,
                repo_full_name,
                number_text,
            )
            return row is not None
    except Exception as exc:
        logger.warning(
            'Could not check active GitHub App task for %s#%s: %s',
            repo_full_name,
            number,
            exc,
        )
        return False


async def _dispatch_item(
    repo_full_name: str,
    installation_id: int,
    item: dict[str, Any],
    token: str,
) -> ActiveWorkDispatch:
    """Queue one open issue or PR through the standard GitHub App path."""
    context = _context_for_item(repo_full_name, installation_id, item)
    if await has_active_github_app_task(repo_full_name, context.issue_number):
        return ActiveWorkDispatch(
            repo=repo_full_name,
            number=context.issue_number,
            kind='pull_request' if context.pr_number else 'issue',
            accepted=False,
            reason='active-task-exists',
        )
    result = await handle_fix_request(context, token)
    return ActiveWorkDispatch(
        repo=repo_full_name,
        number=context.issue_number,
        kind='pull_request' if context.pr_number else 'issue',
        accepted=bool(result.get('accepted')),
        reason=str(result.get('reason') or ''),
        task_id=str(result.get('clone_task_id') or ''),
    )


async def dispatch_active_work_for_installation(
    installation_id: int,
    *,
    limit_per_repo: int = 100,
) -> list[ActiveWorkDispatch]:
    """Queue work for open active issues and PRs in every installed repository."""
    repos = await list_installation_repositories(installation_id)
    all_results: list[ActiveWorkDispatch] = []
    for repo in repos:
        full_name = str(repo.get('full_name') or '').strip()
        if not full_name:
            continue
        all_results.extend(
            await dispatch_active_work_for_repo(
                full_name,
                installation_id,
                limit=limit_per_repo,
            )
        )
        await asyncio.sleep(0)
    return all_results