"""GitHub issue comment utilities for the GitHub App webhook flow.

The synchronous monitor_pr_fix() / wait_for_task() polling path has been
replaced by the event-driven task lifecycle:

  1. Webhook → handler.py creates a clone task and returns immediately.
  2. Clone task completes → pr_prepare_completion / issue_prepare_completion
     creates the follow-up build task.
  3. Build task completes → pr_final_comment / issue_final_comment posts the
     result on the GitHub issue/PR.
  4. For long-running tasks, github_progress_service posts periodic progress
     comments on the issue (every 5 minutes) using the github_issue_url stored
     in task metadata.
  5. If a worker dies, task_reaper detects the missed heartbeat and requeues
     the task (up to max_attempts). On permanent failure, it posts a comment.

All orchestration is event-driven via task_status_hook.py, which is called from
worker_sse.py / hosted_worker.py / monitor_api.py when tasks go terminal.
"""

import logging
from typing import Any

from .auth import github_json

logger = logging.getLogger(__name__)


async def post_issue_comment(
    repo_full_name: str, issue_number: int, token: str, body: str
) -> None:
    """Post a status update back onto the PR issue timeline."""
    await github_json(
        'POST',
        f'/repos/{repo_full_name}/issues/{issue_number}/comments',
        token,
        {'body': body[:65000]},
    )


ACCEPTED_COMMENT_FINGERPRINTS = {
    'Picked up this request for PR #',
    'Picked up issue #',
    'Picked up this issue (#',
}


def _looks_like_acceptance_comment(body: str) -> bool:
    """Return True when ``body`` is one of our standard acceptance messages."""
    if not body:
        return False
    return any(marker in body for marker in ACCEPTED_COMMENT_FINGERPRINTS)


async def recent_app_acceptance_comment_exists(
    repo_full_name: str,
    issue_number: int,
    token: str,
    *,
    app_slug: str,
    within_seconds: int = 600,
) -> bool:
    """Return True when the App recently posted a duplicate acceptance comment.

    The webhook ingress can be re-entered for the same PR/issue when
    ``installation``/``installation_repositories`` backfill events fire or when
    the same user comment triggers a retry. Posting a second acceptance
    message confuses users, so this helper short-circuits the duplicate post
    by scanning the recent comment timeline authored by the App.
    """
    try:
        comments = await github_json(
            'GET',
            f'/repos/{repo_full_name}/issues/{issue_number}/comments?per_page=20',
            token,
        )
    except Exception as exc:  # pragma: no cover - network/API failure path
        logger.warning(
            'Could not read recent comments for %s#%s: %s',
            repo_full_name,
            issue_number,
            exc,
        )
        return False
    if not isinstance(comments, list):
        return False
    bot_login = f'{app_slug.lower()}[bot]'
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        author = (entry.get('user') or {}).get('login') or ''
        if str(author).lower() != bot_login:
            continue
        if not _looks_like_acceptance_comment(str(entry.get('body') or '')):
            continue
        created_at = str(entry.get('created_at') or '')
        if _within_window(created_at, within_seconds):
            return True
    return False


def _within_window(iso_timestamp: str, within_seconds: int) -> bool:
    """Return True when ``iso_timestamp`` is within the last ``within_seconds`` seconds."""
    if not iso_timestamp:
        return False
    try:
        from datetime import datetime, timedelta, timezone

        parsed = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now - parsed <= timedelta(seconds=within_seconds)