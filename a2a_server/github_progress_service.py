"""Background service that posts progress comments on GitHub issues."""

import asyncio
import json
import logging
from typing import Optional

from .github_progress_reporter import (
    GITHUB_PROGRESS_ENABLED,
    GITHUB_PROGRESS_INTERVAL_SECONDS,
    post_github_progress_comment,
)

logger = logging.getLogger(__name__)


class GitHubProgressReporter:
    """Background service that posts progress comments on GitHub issues."""

    def __init__(
        self,
        interval_seconds: int = GITHUB_PROGRESS_INTERVAL_SECONDS,
    ):
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not GITHUB_PROGRESS_ENABLED:
            logger.info('GitHub progress reporter disabled')
            return
        self._running = True
        self._task = asyncio.create_task(self._report_loop())
        logger.info(
            f'GitHub progress reporter started (interval={self._interval}s)'
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _report_loop(self) -> None:
        await asyncio.sleep(15)
        while self._running:
            try:
                await self._report_all_pending()
            except Exception as e:
                logger.error(f'GitHub progress reporter error: {e}')
            await asyncio.sleep(self._interval)

    async def _report_all_pending(self) -> int:
        """Find all fire-and-forget runs needing comments and post them."""
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return 0

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    'SELECT * FROM find_runs_needing_github_comment($1)',
                    self._interval,
                )
        except Exception as e:
            logger.debug(f'Failed to query runs needing comments: {e}')
            return 0

        posted = 0
        for row in rows:
            try:
                checkpoint = row['checkpoint']
                if isinstance(checkpoint, str):
                    checkpoint = json.loads(checkpoint)

                success = await post_github_progress_comment(
                    issue_url=row['github_issue_url'],
                    task_id=row['task_id'],
                    progress_pct=row['progress_pct'] or 0,
                    status_message=row['status_message'] or 'Working...',
                    elapsed_seconds=row['elapsed_seconds'] or 0,
                    resume_attempt=row['resume_attempt'] or 0,
                    checkpoint=checkpoint,
                )
                if success:
                    posted += 1
            except Exception as e:
                logger.warning(
                    f'Failed to post comment for task {row["task_id"]}: {e}'
                )

        if posted > 0:
            logger.info(f'Posted {posted} progress comments to GitHub')
        return posted


# Global instance
_reporter: Optional[GitHubProgressReporter] = None


async def start_github_progress_reporter() -> Optional[GitHubProgressReporter]:
    global _reporter
    if _reporter is not None:
        return _reporter
    _reporter = GitHubProgressReporter()
    await _reporter.start()
    return _reporter


async def stop_github_progress_reporter() -> None:
    global _reporter
    if _reporter:
        await _reporter.stop()
        _reporter = None
