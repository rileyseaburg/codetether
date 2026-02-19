"""
Task Reaper - Automatic recovery for stuck tasks.

This module provides automatic detection and recovery of tasks that become stuck
due to worker failures, network issues, or other problems.

Features:
- Detects tasks stuck in 'running' status without progress
- Requeues stuck tasks for retry (up to max_attempts)
- Marks tasks as failed after max retries
- Provides health metrics for monitoring
- Supports configurable timeouts and intervals

Usage:
    # Start the reaper (typically called from server startup)
    reaper = TaskReaper()
    await reaper.start()

    # Stop the reaper (on shutdown)
    await reaper.stop()

    # Manual recovery
    stats = await reaper.recover_stuck_tasks()

Configuration (environment variables):
    TASK_STUCK_TIMEOUT_SECONDS: Time before a task is considered stuck (default: 300)
    TASK_REAPER_INTERVAL_SECONDS: How often to check for stuck tasks (default: 60)
    TASK_MAX_ATTEMPTS: Maximum retry attempts before failing (default: 3)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration from environment
STUCK_TIMEOUT_SECONDS = int(
    os.environ.get('TASK_STUCK_TIMEOUT_SECONDS', '300')
)  # 5 minutes
REAPER_INTERVAL_SECONDS = int(
    os.environ.get('TASK_REAPER_INTERVAL_SECONDS', '60')
)  # 1 minute
MAX_ATTEMPTS = int(os.environ.get('TASK_MAX_ATTEMPTS', '3'))


@dataclass
class ReaperStats:
    """Statistics from a reaper run."""

    checked_at: datetime = field(default_factory=datetime.utcnow)
    tasks_checked: int = 0
    tasks_requeued: int = 0
    tasks_failed: int = 0
    tasks_notified: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checked_at': self.checked_at.isoformat(),
            'tasks_checked': self.tasks_checked,
            'tasks_requeued': self.tasks_requeued,
            'tasks_failed': self.tasks_failed,
            'tasks_notified': self.tasks_notified,
            'errors': self.errors,
        }


class TaskReaper:
    """
    Background service that detects and recovers stuck tasks.

    A task is considered "stuck" if:
    1. Status is 'running'
    2. started_at is older than STUCK_TIMEOUT_SECONDS
    3. No output has been received recently (if output tracking enabled)

    Recovery strategy:
    1. If attempts < MAX_ATTEMPTS: requeue task (status -> 'pending')
    2. If attempts >= MAX_ATTEMPTS: fail task (status -> 'failed')
    3. Notify user if email configured
    """

    def __init__(
        self,
        stuck_timeout: int = STUCK_TIMEOUT_SECONDS,
        interval: int = REAPER_INTERVAL_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self.stuck_timeout = stuck_timeout
        self.interval = interval
        self.max_attempts = max_attempts
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_stats: Optional[ReaperStats] = None

    async def start(self) -> None:
        """Start the background reaper loop."""
        if self._running:
            logger.warning('Task reaper already running')
            return

        self._running = True
        self._task = asyncio.create_task(self._reaper_loop())
        logger.info(
            f'Task reaper started (timeout={self.stuck_timeout}s, '
            f'interval={self.interval}s, max_attempts={self.max_attempts})'
        )

    async def stop(self) -> None:
        """Stop the background reaper loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('Task reaper stopped')

    async def _reaper_loop(self) -> None:
        """Main loop that periodically checks for stuck tasks."""
        # Wait a bit before first run to let server fully start
        await asyncio.sleep(10)

        while self._running:
            try:
                stats = await self.recover_stuck_tasks()
                self._last_stats = stats

                if stats.tasks_requeued > 0 or stats.tasks_failed > 0:
                    logger.info(
                        f'Task reaper: requeued={stats.tasks_requeued}, '
                        f'failed={stats.tasks_failed}'
                    )

            except Exception as e:
                logger.error(f'Task reaper error: {e}', exc_info=True)

            await asyncio.sleep(self.interval)

    async def recover_stuck_tasks(self) -> ReaperStats:
        """
        Check for and recover stuck tasks.

        Returns statistics about the recovery operation.
        """
        stats = ReaperStats()

        try:
            # Import here to avoid circular imports
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                stats.errors.append('Database pool not available')
                return stats

            async with pool.acquire() as conn:
                # Find stuck tasks
                cutoff = datetime.utcnow() - timedelta(
                    seconds=self.stuck_timeout
                )

                try:
                    # Treat a task as "stuck" only when it's been running longer than the
                    # timeout *and* the assigned worker is no longer heartbeating.
                    # This avoids requeuing legitimate long-running jobs.
                    stuck_tasks = await conn.fetch(
                        """
                        SELECT t.id, t.workspace_id, t.title, t.prompt, t.agent_type,
                               t.status, t.priority, t.worker_id, t.started_at,
                               COALESCE((t.metadata->>'attempts')::int, 0) as attempts,
                               t.metadata
                        FROM tasks t
                        LEFT JOIN workers w ON t.worker_id = w.worker_id
                        WHERE t.status = 'running'
                          AND t.started_at < $1
                          AND (
                            t.worker_id IS NULL
                            OR w.worker_id IS NULL
                            OR w.last_seen < $1
                          )
                        ORDER BY t.started_at ASC
                        """,
                        cutoff,
                    )
                except Exception as e:
                    # Backward compatibility: older schemas may still use codebase_id.
                    if (
                        'workspace_id' in str(e).lower()
                        and 'column' in str(e).lower()
                    ):
                        stuck_tasks = await conn.fetch(
                            """
                            SELECT t.id, t.codebase_id AS workspace_id, t.title, t.prompt, t.agent_type,
                                   t.status, t.priority, t.worker_id, t.started_at,
                                   COALESCE((t.metadata->>'attempts')::int, 0) as attempts,
                                   t.metadata
                            FROM tasks t
                            LEFT JOIN workers w ON t.worker_id = w.worker_id
                            WHERE t.status = 'running'
                              AND t.started_at < $1
                              AND (
                                t.worker_id IS NULL
                                OR w.worker_id IS NULL
                                OR w.last_seen < $1
                              )
                            ORDER BY t.started_at ASC
                            """,
                            cutoff,
                        )
                    else:
                        raise

                stats.tasks_checked = len(stuck_tasks)

                for task in stuck_tasks:
                    task_id = task['id']
                    attempts = task['attempts']

                    try:
                        if attempts >= self.max_attempts:
                            # Max attempts reached - fail the task
                            await self._fail_task(conn, task)
                            stats.tasks_failed += 1
                            logger.warning(
                                f'Task {task_id} failed after {attempts} attempts '
                                f'(max={self.max_attempts})'
                            )
                        else:
                            # Requeue for retry
                            await self._requeue_task(conn, task, attempts)
                            stats.tasks_requeued += 1
                            logger.info(
                                f'Task {task_id} requeued for retry '
                                f'(attempt {attempts + 1}/{self.max_attempts})'
                            )

                    except Exception as e:
                        error_msg = f'Failed to recover task {task_id}: {e}'
                        stats.errors.append(error_msg)
                        logger.error(error_msg)

        except Exception as e:
            stats.errors.append(f'Recovery failed: {e}')
            logger.error(f'Task recovery failed: {e}', exc_info=True)

        return stats

    async def _requeue_task(self, conn, task: dict, attempts: int) -> None:
        """Requeue a stuck task for retry."""
        import json

        task_id = task['id']
        metadata = task['metadata']

        # Parse metadata if it's a string
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        elif metadata is None:
            metadata = {}

        # Update attempt count in metadata
        metadata['attempts'] = attempts + 1
        metadata['last_stuck_at'] = datetime.utcnow().isoformat()
        metadata['stuck_reason'] = 'No progress detected'

        await conn.execute(
            """
            UPDATE tasks SET
                status = 'pending',
                started_at = NULL,
                worker_id = NULL,
                error = $2,
                metadata = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            f'Requeued: stuck for >{self.stuck_timeout}s (attempt {attempts + 1})',
            json.dumps(metadata),
        )

        # Clear any stale in-memory claim so workers can re-claim
        await self._clear_claim(task_id)

        # Notify via SSE that task is available again
        await self._notify_task_available(task_id)

    async def _fail_task(self, conn, task: dict) -> None:
        """Mark a task as permanently failed."""
        import json

        task_id = task['id']
        metadata = task['metadata']

        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        elif metadata is None:
            metadata = {}

        metadata['failed_at'] = datetime.utcnow().isoformat()
        metadata['failure_reason'] = (
            f'Max attempts ({self.max_attempts}) exceeded'
        )

        await conn.execute(
            """
            UPDATE tasks SET
                status = 'failed',
                completed_at = NOW(),
                error = $2,
                metadata = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            f'Failed: max attempts ({self.max_attempts}) exceeded after repeated stuck detection',
            json.dumps(metadata),
        )

        # Clear any stale in-memory claim
        await self._clear_claim(task_id)

        # Send failure notification
        await self._notify_task_failed(task, metadata)

    async def _clear_claim(self, task_id: str) -> None:
        """Remove a task from the in-memory claimed-tasks map."""
        try:
            from .worker_sse import get_worker_registry

            registry = get_worker_registry()
            if registry:
                async with registry._lock:
                    old_worker = registry._claimed_tasks.pop(task_id, None)
                    if old_worker:
                        logger.info(
                            f'Cleared stale claim on task {task_id} '
                            f'(was held by worker {old_worker})'
                        )
                        # Also reset the worker's busy flag if it's still connected
                        worker = registry._workers.get(old_worker)
                        if worker and worker.current_task_id == task_id:
                            worker.is_busy = False
                            worker.current_task_id = None
        except Exception as e:
            logger.debug(f'Failed to clear claim for task {task_id}: {e}')

    async def _notify_task_available(self, task_id: str) -> None:
        """Notify workers that a task is available for claiming."""
        try:
            from .worker_sse import get_worker_registry

            registry = get_worker_registry()
            if registry:
                await registry.broadcast_task_available(task_id)
        except Exception as e:
            logger.debug(f'Failed to notify task available: {e}')

    async def _notify_task_failed(self, task: dict, metadata: dict) -> None:
        """Send notification when a task permanently fails."""
        try:
            # Try to send email notification if configured
            notify_email = metadata.get('notify_email')
            if notify_email:
                from .email_notifications import send_task_failed_email

                await send_task_failed_email(
                    to_email=notify_email,
                    task_id=task['id'],
                    task_title=task.get('title', 'Untitled Task'),
                    error_message=f'Task failed after {self.max_attempts} attempts',
                    attempts=metadata.get('attempts', self.max_attempts),
                )
        except Exception as e:
            logger.debug(f'Failed to send failure notification: {e}')

    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get the last reaper run statistics."""
        if self._last_stats:
            return self._last_stats.to_dict()
        return None

    def get_health(self) -> Dict[str, Any]:
        """Get reaper health status."""
        return {
            'running': self._running,
            'stuck_timeout_seconds': self.stuck_timeout,
            'interval_seconds': self.interval,
            'max_attempts': self.max_attempts,
            'last_run': self._last_stats.to_dict()
            if self._last_stats
            else None,
        }


# Global reaper instance
_reaper: Optional[TaskReaper] = None


def get_task_reaper() -> Optional[TaskReaper]:
    """Get the global task reaper instance."""
    return _reaper


async def start_task_reaper(
    stuck_timeout: int = STUCK_TIMEOUT_SECONDS,
    interval: int = REAPER_INTERVAL_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
) -> TaskReaper:
    """Start the global task reaper."""
    global _reaper

    if _reaper is not None:
        return _reaper

    _reaper = TaskReaper(
        stuck_timeout=stuck_timeout,
        interval=interval,
        max_attempts=max_attempts,
    )
    await _reaper.start()
    return _reaper


async def stop_task_reaper() -> None:
    """Stop the global task reaper."""
    global _reaper

    if _reaper:
        await _reaper.stop()
        _reaper = None
