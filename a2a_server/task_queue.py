"""
Task Queue for Hosted Workers

This module provides the queue interface for the hosted worker system.
Tasks are enqueued when created and workers claim/execute them asynchronously.

Key concepts:
- task_runs table is the job queue (separate from tasks table)
- Jobs have leases that expire if workers die
- Per-user concurrency limits enforced at claim time
- Workers renew leases via heartbeat
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskRunStatus(str, Enum):
    """Status of a task run in the queue."""

    QUEUED = 'queued'
    RUNNING = 'running'
    NEEDS_INPUT = 'needs_input'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


@dataclass
class TaskRun:
    """A task execution in the queue."""

    id: str
    task_id: str
    user_id: Optional[str] = None
    template_id: Optional[str] = None
    automation_id: Optional[str] = None

    status: TaskRunStatus = TaskRunStatus.QUEUED
    priority: int = 0

    lease_owner: Optional[str] = None
    lease_expires_at: Optional[datetime] = None

    attempts: int = 0
    max_attempts: int = 2
    last_error: Optional[str] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    runtime_seconds: Optional[int] = None

    result_summary: Optional[str] = None
    result_full: Optional[Dict[str, Any]] = None

    notify_email: Optional[str] = None
    notify_webhook_url: Optional[str] = None
    notification_sent: bool = False

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TaskQueue:
    """
    Interface to the task_runs queue.

    This is the main API for enqueuing tasks and checking queue status.
    Workers use the claim_* and complete_* functions directly via SQL.
    """

    def __init__(self, db_pool):
        """
        Initialize the task queue.

        Args:
            db_pool: asyncpg connection pool
        """
        self._pool = db_pool

    async def enqueue(
        self,
        task_id: str,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        automation_id: Optional[str] = None,
        priority: int = 0,
        notify_email: Optional[str] = None,
        notify_webhook_url: Optional[str] = None,
    ) -> TaskRun:
        """
        Enqueue a task for execution by hosted workers.

        Args:
            task_id: ID of the task to execute
            user_id: Owner user ID (for concurrency limiting)
            template_id: Template that generated this task (optional)
            automation_id: Automation that generated this task (optional)
            priority: Higher = more urgent (default 0)
            notify_email: Email to notify on completion
            notify_webhook_url: Webhook to call on completion

        Returns:
            TaskRun object representing the queued job
        """
        run_id = str(uuid.uuid4())

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO task_runs (
                    id, task_id, user_id, template_id, automation_id,
                    status, priority, notify_email, notify_webhook_url,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10)
                """,
                run_id,
                task_id,
                user_id,
                template_id,
                automation_id,
                TaskRunStatus.QUEUED.value,
                priority,
                notify_email,
                notify_webhook_url,
                datetime.now(timezone.utc),
            )

        logger.info(
            f'Enqueued task run {run_id} for task {task_id} (user={user_id}, priority={priority})'
        )

        return TaskRun(
            id=run_id,
            task_id=task_id,
            user_id=user_id,
            template_id=template_id,
            automation_id=automation_id,
            priority=priority,
            notify_email=notify_email,
            notify_webhook_url=notify_webhook_url,
        )

    async def get_run(self, run_id: str) -> Optional[TaskRun]:
        """Get a task run by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM task_runs WHERE id = $1', run_id
            )
            if row:
                return self._row_to_task_run(row)
            return None

    async def get_run_by_task(self, task_id: str) -> Optional[TaskRun]:
        """Get the most recent task run for a task."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM task_runs 
                WHERE task_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                task_id,
            )
            if row:
                return self._row_to_task_run(row)
            return None

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        status: Optional[TaskRunStatus] = None,
        limit: int = 100,
    ) -> List[TaskRun]:
        """List task runs with optional filtering."""
        conditions = []
        params = []
        param_idx = 1

        if user_id:
            conditions.append(f'user_id = ${param_idx}')
            params.append(user_id)
            param_idx += 1

        if status:
            conditions.append(f'status = ${param_idx}')
            params.append(status.value)
            param_idx += 1

        where_clause = ' AND '.join(conditions) if conditions else 'TRUE'

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM task_runs 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx}
                """,
                *params,
                limit,
            )
            return [self._row_to_task_run(row) for row in rows]

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        async with self._pool.acquire() as conn:
            # Overall stats
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'running') as running,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_24h,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_24h,
                    AVG(runtime_seconds) FILTER (WHERE status = 'completed') as avg_runtime,
                    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) 
                        FILTER (WHERE status = 'queued') as avg_wait_seconds
                FROM task_runs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                """
            )

            # Per-user running counts
            user_running = await conn.fetch(
                """
                SELECT user_id, COUNT(*) as running_count
                FROM task_runs
                WHERE status = 'running'
                GROUP BY user_id
                """
            )

            return {
                'queued': stats['queued'] or 0,
                'running': stats['running'] or 0,
                'completed_24h': stats['completed_24h'] or 0,
                'failed_24h': stats['failed_24h'] or 0,
                'avg_runtime_seconds': float(stats['avg_runtime'] or 0),
                'avg_wait_seconds': float(stats['avg_wait_seconds'] or 0),
                'users_with_running_tasks': len(user_running),
            }

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a queued task run."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE task_runs SET
                    status = 'cancelled',
                    updated_at = NOW()
                WHERE id = $1 AND status = 'queued'
                """,
                run_id,
            )
            return result == 'UPDATE 1'

    async def reclaim_expired_leases(self) -> int:
        """
        Reclaim jobs with expired leases.

        Should be called periodically (e.g., every 30 seconds).
        Returns number of jobs reclaimed.
        """
        async with self._pool.acquire() as conn:
            result = await conn.fetchval('SELECT reclaim_expired_task_runs()')
            if result and result > 0:
                logger.info(f'Reclaimed {result} expired task run leases')
            return result or 0

    def _row_to_task_run(self, row) -> TaskRun:
        """Convert database row to TaskRun object."""
        return TaskRun(
            id=row['id'],
            task_id=row['task_id'],
            user_id=row['user_id'],
            template_id=row['template_id'],
            automation_id=row['automation_id'],
            status=TaskRunStatus(row['status']),
            priority=row['priority'],
            lease_owner=row['lease_owner'],
            lease_expires_at=row['lease_expires_at'],
            attempts=row['attempts'],
            max_attempts=row['max_attempts'],
            last_error=row['last_error'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            runtime_seconds=row['runtime_seconds'],
            result_summary=row['result_summary'],
            result_full=row['result_full'],
            notify_email=row['notify_email'],
            notify_webhook_url=row['notify_webhook_url'],
            notification_sent=row['notification_sent'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )


# Global task queue instance (initialized when DB pool is ready)
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> Optional[TaskQueue]:
    """Get the global task queue instance."""
    return _task_queue


def set_task_queue(queue: TaskQueue) -> None:
    """Set the global task queue instance."""
    global _task_queue
    _task_queue = queue


async def enqueue_task(
    task_id: str,
    user_id: Optional[str] = None,
    template_id: Optional[str] = None,
    automation_id: Optional[str] = None,
    priority: int = 0,
    notify_email: Optional[str] = None,
    notify_webhook_url: Optional[str] = None,
) -> Optional[TaskRun]:
    """
    Convenience function to enqueue a task.

    Returns None if task queue is not initialized.
    """
    queue = get_task_queue()
    if queue is None:
        logger.warning(
            f'Task queue not initialized, cannot enqueue task {task_id}'
        )
        return None

    return await queue.enqueue(
        task_id=task_id,
        user_id=user_id,
        template_id=template_id,
        automation_id=automation_id,
        priority=priority,
        notify_email=notify_email,
        notify_webhook_url=notify_webhook_url,
    )
