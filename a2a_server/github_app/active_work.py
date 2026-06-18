"""GitHub App installed-repository active work dispatch."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from a2a_server.github_app.auth import github_json, installation_token
from a2a_server.github_app.context import MentionContext
from a2a_server.github_app.handler import handle_fix_request
from a2a_server.github_app.mention import is_fix_request


DEFAULT_ACTIVE_WORK_MAX_AGE_DAYS = 7
GITHUB_PAGE_SIZE = 100

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


async def list_installation_repositories(
    installation_id: int,
) -> list[dict[str, object]]:
    """Return repositories visible to a GitHub App installation token."""
    token, _ = await installation_token(installation_id)
    repos: list[dict[str, object]] = []
    page = 1
    while True:
        data = await github_json(
            'GET',
            f'/installation/repositories?per_page={GITHUB_PAGE_SIZE}&page={page}',
            token,
        )
        batch = data.get('repositories') or []
        repos.extend(batch)
        if len(batch) < GITHUB_PAGE_SIZE:
            return repos
        page += 1


def _context_for_item(
    repo: str,
    installation_id: int,
    item: dict[str, object],
) -> MentionContext:
    """Build the normal mention context for a discovered active item."""
    number = int(item['number'])
    is_pr = 'pull_request' in item
    body = str(item.get('body') or '')
    return MentionContext(
        repo_full_name=repo,
        installation_id=installation_id,
        issue_number=number,
        pr_number=number if is_pr else None,
        comment_id=int(item.get('id') or number),
        comment_body=body,
    )


def _active_work_max_age() -> timedelta:
    """Return the maximum age for automatic active-work dispatch."""
    raw = os.environ.get('GITHUB_APP_ACTIVE_WORK_MAX_AGE_DAYS', '').strip()
    try:
        days = int(raw) if raw else DEFAULT_ACTIVE_WORK_MAX_AGE_DAYS
    except ValueError:
        days = DEFAULT_ACTIVE_WORK_MAX_AGE_DAYS
    return timedelta(days=max(days, 0))


def _parse_github_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _is_stale_active_item(
    item: dict[str, object],
    *,
    now: datetime | None = None,
) -> bool:
    """True when an open issue/PR is too old for automatic active scanning."""
    timestamp = _parse_github_time(
        item.get('updated_at') or item.get('created_at'),
    )
    if timestamp is None:
        # Missing timestamps usually means a test fixture or unusual GitHub
        # response; do not drop it solely because the clock evidence is absent.
        return False
    now = now or datetime.now(UTC)
    return now - timestamp > _active_work_max_age()


def _active_item_fix_request(item: dict[str, object]) -> bool:
    """Only explicit @CodeTether fix requests should be auto-queued."""
    return is_fix_request(str(item.get('body') or ''))


async def dispatch_active_work_for_repo(
    repo_full_name: str,
    installation_id: int,
    *,
    limit: int = GITHUB_PAGE_SIZE,
) -> list[ActiveWorkDispatch]:
    """Queue replacement work for open active issues and PRs in a repo."""
    token, _ = await installation_token(installation_id)
    results: list[ActiveWorkDispatch] = []
    page = 1
    while True:
        items = await github_json(
            'GET',
            f'/repos/{repo_full_name}/issues?state=open&per_page={limit}'
            f'&page={page}',
            token,
        )
        if not items:
            return results
        for item in items:
            dispatch = await _dispatch_item(
                repo_full_name,
                installation_id,
                item,
                token,
            )
            results.append(dispatch)
        if len(items) < limit:
            return results
        page += 1


async def has_active_github_app_task(repo_full_name: str, number: int) -> bool:
    """Return true when an open GitHub App task already targets this item."""
    try:
        database = importlib.import_module('a2a_server.database')
        pool = await database.get_pool()
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
    item: dict[str, object],
    token: str,
) -> ActiveWorkDispatch:
    """Queue one open issue or PR through the standard GitHub App path."""
    context = _context_for_item(repo_full_name, installation_id, item)
    kind = 'pull_request' if context.pr_number else 'issue'
    if _is_stale_active_item(item):
        return ActiveWorkDispatch(
            repo=repo_full_name,
            number=context.issue_number,
            kind=kind,
            accepted=False,
            reason='stale-active-item',
        )
    if not _active_item_fix_request(item):
        return ActiveWorkDispatch(
            repo=repo_full_name,
            number=context.issue_number,
            kind=kind,
            accepted=False,
            reason='no-explicit-fix-request',
        )
    if await has_active_github_app_task(repo_full_name, context.issue_number):
        return ActiveWorkDispatch(
            repo=repo_full_name,
            number=context.issue_number,
            kind=kind,
            accepted=False,
            reason='active-task-exists',
        )
    result = await handle_fix_request(context, token)
    return ActiveWorkDispatch(
        repo=repo_full_name,
        number=context.issue_number,
        kind=kind,
        accepted=bool(result.get('accepted')),
        reason=str(result.get('reason') or ''),
        task_id=str(result.get('clone_task_id') or ''),
    )


async def dispatch_active_work_for_installation(
    installation_id: int,
    *,
    limit_per_repo: int = GITHUB_PAGE_SIZE,
) -> list[ActiveWorkDispatch]:
    """Queue work for open active issues/PRs in every installed repository."""
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
            ),
        )
        await asyncio.sleep(0)
    return all_results
