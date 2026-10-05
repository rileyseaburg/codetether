"""
GitHub Progress Reporter — Posts task progress as comments on GitHub issues.

The server posts progress comments on behalf of workers every 5 minutes
for fire-and-forget tasks with a github_issue_url.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GITHUB_PROGRESS_ENABLED = os.environ.get(
    'GITHUB_PROGRESS_ENABLED', 'true'
).lower() == 'true'
GITHUB_PROGRESS_INTERVAL_SECONDS = int(
    os.environ.get('GITHUB_PROGRESS_INTERVAL_SECONDS', '300')
)


def _parse_issue_url(url: str) -> Optional[Dict[str, str]]:
    """Parse a GitHub issue/PR URL into owner, repo, and number."""
    if not url:
        return None
    m = re.match(
        r'https://github\.com/([^/]+)/([^/]+)/(?:issues|pull)/(\d+)', url
    )
    if not m:
        return None
    return {'owner': m.group(1), 'repo': m.group(2), 'number': int(m.group(3))}


def _format_progress_comment(
    task_id: str,
    progress_pct: float,
    status_message: str,
    elapsed_seconds: int,
    resume_attempt: int,
    checkpoint: Optional[Dict[str, Any]] = None,
) -> str:
    """Format a progress comment for GitHub."""
    elapsed_h = elapsed_seconds // 3600
    elapsed_m = (elapsed_seconds % 3600) // 60
    elapsed_s = elapsed_seconds % 60

    if elapsed_h > 0:
        elapsed_str = f"{elapsed_h}h {elapsed_m}m"
    elif elapsed_m > 0:
        elapsed_str = f"{elapsed_m}m {elapsed_s}s"
    else:
        elapsed_str = f"{elapsed_s}s"

    filled = int(progress_pct / 100 * 20)
    bar = '█' * filled + '░' * (20 - filled)

    lines = [
        f"### 🔄 Task Progress — `{task_id[:16]}…`",
        "",
        f"`{bar}` **{progress_pct:.0f}%** complete ({elapsed_str} elapsed)",
        f"> {status_message}",
    ]

    if resume_attempt > 0:
        lines.append(
            f"\n> ℹ️ Resumed from checkpoint "
            f"({resume_attempt} time{'s' if resume_attempt > 1 else ''})"
        )

    if checkpoint:
        completed_steps = checkpoint.get('completed_steps', [])
        if completed_steps:
            lines.append("")
            lines.append("<details><summary>Completed Steps</summary>")
            lines.append("")
            for step in completed_steps[-5:]:
                icon = '✅' if step.get('status') == 'done' else '🔄'
                lines.append(f"- {icon} {step.get('name', 'Unknown step')}")
            total = len(completed_steps)
            if total > 5:
                lines.append(f"- … and {total - 5} more")
            lines.append("")
            lines.append("</details>")

    lines.append("")
    lines.append("_Updated automatically by CodeTether_")
    return "\n".join(lines)


async def post_github_progress_comment(
    issue_url: str,
    task_id: str,
    progress_pct: float,
    status_message: str,
    elapsed_seconds: int,
    resume_attempt: int = 0,
    checkpoint: Optional[Dict[str, Any]] = None,
) -> bool:
    """Post a progress comment on a GitHub issue/PR."""
    parsed = _parse_issue_url(issue_url)
    if not parsed:
        logger.warning(f'Cannot parse issue URL: {issue_url}')
        return False

    try:
        from .github_app_auth import github_installation_request
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return False

        # Get installation_id from task metadata
        installation_id = None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM tasks WHERE id = $1", task_id
            )
            if row and row['metadata']:
                metadata = row['metadata']
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                installation_id = metadata.get('github_installation_id')

        if not installation_id:
            logger.debug(f'No installation_id for task {task_id}')
            return False

        comment_body = _format_progress_comment(
            task_id=task_id,
            progress_pct=progress_pct,
            status_message=status_message,
            elapsed_seconds=elapsed_seconds,
            resume_attempt=resume_attempt,
            checkpoint=checkpoint,
        )

        api_url = (
            f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}"
            f"/issues/{parsed['number']}/comments"
        )

        response = await github_installation_request(
            installation_id=str(installation_id),
            owner=parsed['owner'],
            repo=parsed['repo'],
            method='POST',
            url=api_url,
            json={'body': comment_body},
        )

        if response.status_code in (200, 201):
            logger.info(f'Posted progress on {issue_url} for task {task_id}')
            async with pool.acquire() as conn:
                await conn.execute(
                    'SELECT record_github_comment($1)', task_id
                )
            return True
        else:
            logger.warning(
                f'GitHub comment failed: {response.status_code}'
            )
            return False

    except Exception as e:
        logger.error(f'Error posting GitHub progress: {e}')
        return False
