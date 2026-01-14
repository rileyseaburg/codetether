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


class TaskLimitExceeded(Exception):
    """Raised when user has exceeded their task or concurrency limits."""

    def __init__(
        self,
        reason: str,
        tasks_used: int = 0,
        tasks_limit: int = 0,
        running_count: int = 0,
        concurrency_limit: int = 0,
    ):
        self.reason = reason
        self.tasks_used = tasks_used
        self.tasks_limit = tasks_limit
        self.running_count = running_count
        self.concurrency_limit = concurrency_limit
        super().__init__(reason)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON response."""
        return {
            'error': 'task_limit_exceeded',
            'message': self.reason,
            'tasks_used': self.tasks_used,
            'tasks_limit': self.tasks_limit,
            'running_count': self.running_count,
            'concurrency_limit': self.concurrency_limit,
        }


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

    # Agent routing fields (Phase 2 - agent-targeted routing)
    target_agent_name: Optional[str] = None  # If set, only this agent can claim
    required_capabilities: Optional[List[str]] = None  # Worker must have ALL
    deadline_at: Optional[datetime] = None  # Fail if not claimed by this time
    routing_failed_at: Optional[datetime] = None
    routing_failure_reason: Optional[str] = None

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
        skip_limit_check: bool = False,
        # Agent routing parameters
        target_agent_name: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        deadline_at: Optional[datetime] = None,
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
            skip_limit_check: Skip limit enforcement (for internal/admin use)
            target_agent_name: If set, only this agent can claim the task
            required_capabilities: List of capabilities the worker must have
            deadline_at: If set, task fails if not claimed by this time

        Returns:
            TaskRun object representing the queued job

        Raises:
            TaskLimitExceeded: If user has exceeded their task or concurrency limits
        """
        import json as json_module

        run_id = str(uuid.uuid4())

        async with self._pool.acquire() as conn:
            # Check user limits before enqueuing (unless skipped)
            if user_id and not skip_limit_check:
                limit_check = await conn.fetchrow(
                    'SELECT * FROM check_user_task_limits($1)', user_id
                )

                if limit_check and not limit_check['allowed']:
                    raise TaskLimitExceeded(
                        reason=limit_check['reason'],
                        tasks_used=limit_check['tasks_used'],
                        tasks_limit=limit_check['tasks_limit'],
                        running_count=limit_check['running_count'],
                        concurrency_limit=limit_check['concurrency_limit'],
                    )

            # Convert capabilities list to JSON for storage
            capabilities_json = (
                json_module.dumps(required_capabilities)
                if required_capabilities
                else None
            )

            # Enqueue the task with routing fields
            await conn.execute(
                """
                INSERT INTO task_runs (
                    id, task_id, user_id, template_id, automation_id,
                    status, priority, notify_email, notify_webhook_url,
                    target_agent_name, required_capabilities, deadline_at,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $13)
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
                target_agent_name,
                capabilities_json,
                deadline_at,
                datetime.now(timezone.utc),
            )

            # Increment user's task usage counter
            if user_id:
                await conn.execute(
                    """
                    UPDATE users 
                    SET tasks_used_this_month = tasks_used_this_month + 1,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    user_id,
                )

        # Build log message with routing info
        routing_info = ''
        if target_agent_name:
            routing_info += f', target_agent={target_agent_name}'
        if deadline_at:
            routing_info += f', deadline={deadline_at.isoformat()}'

        logger.info(
            f'Enqueued task run {run_id} for task {task_id} '
            f'(user={user_id}, priority={priority}{routing_info})'
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
            target_agent_name=target_agent_name,
            required_capabilities=required_capabilities,
            deadline_at=deadline_at,
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

    async def get_full_queue_status(self) -> Dict[str, Any]:
        """
        Get comprehensive queue status for admin dashboard.

        Returns queue counts, notification statuses, and worker health.
        """
        async with self._pool.acquire() as conn:
            # Queue counts by status
            queue_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'running') as running,
                    COUNT(*) FILTER (WHERE status = 'needs_input') as needs_input,
                    COUNT(*) FILTER (WHERE status = 'completed' AND created_at > NOW() - INTERVAL '24 hours') as completed_24h,
                    COUNT(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '24 hours') as failed_24h,
                    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) 
                        FILTER (WHERE status = 'queued') as avg_queue_wait_seconds,
                    MAX(EXTRACT(EPOCH FROM (NOW() - created_at))) 
                        FILTER (WHERE status = 'queued') as max_queue_wait_seconds
                FROM task_runs
                """
            )

            # Notification stats
            notification_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE notification_status = 'failed' AND notification_next_retry_at <= NOW()) as email_failed_ready,
                    COUNT(*) FILTER (WHERE notification_status = 'pending' AND updated_at < NOW() - INTERVAL '5 minutes') as email_pending_stuck,
                    COUNT(*) FILTER (WHERE webhook_status = 'failed' AND webhook_next_retry_at <= NOW()) as webhook_failed_ready,
                    COUNT(*) FILTER (WHERE webhook_status = 'pending' AND updated_at < NOW() - INTERVAL '5 minutes') as webhook_pending_stuck,
                    COUNT(*) FILTER (WHERE notification_status = 'sent') as emails_sent_total,
                    COUNT(*) FILTER (WHERE webhook_status = 'sent') as webhooks_sent_total
                FROM task_runs
                WHERE created_at > NOW() - INTERVAL '24 hours'
                """
            )

            # Worker stats
            worker_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'active') as active_pools,
                    SUM(max_concurrent_tasks) FILTER (WHERE status = 'active') as total_capacity,
                    SUM(current_tasks) FILTER (WHERE status = 'active') as current_load,
                    MAX(last_heartbeat) as last_heartbeat
                FROM hosted_workers
                """
            )

            return {
                'queue': {
                    'queued': queue_stats['queued'] or 0,
                    'running': queue_stats['running'] or 0,
                    'needs_input': queue_stats['needs_input'] or 0,
                    'completed_24h': queue_stats['completed_24h'] or 0,
                    'failed_24h': queue_stats['failed_24h'] or 0,
                    'avg_wait_seconds': round(
                        float(queue_stats['avg_queue_wait_seconds'] or 0), 1
                    ),
                    'max_wait_seconds': int(
                        queue_stats['max_queue_wait_seconds'] or 0
                    ),
                },
                'notifications': {
                    'email_failed_ready': notification_stats[
                        'email_failed_ready'
                    ]
                    or 0,
                    'email_pending_stuck': notification_stats[
                        'email_pending_stuck'
                    ]
                    or 0,
                    'webhook_failed_ready': notification_stats[
                        'webhook_failed_ready'
                    ]
                    or 0,
                    'webhook_pending_stuck': notification_stats[
                        'webhook_pending_stuck'
                    ]
                    or 0,
                    'emails_sent_24h': notification_stats['emails_sent_total']
                    or 0,
                    'webhooks_sent_24h': notification_stats[
                        'webhooks_sent_total'
                    ]
                    or 0,
                },
                'workers': {
                    'active_pools': worker_stats['active_pools'] or 0,
                    'total_capacity': int(worker_stats['total_capacity'] or 0),
                    'current_load': int(worker_stats['current_load'] or 0),
                    'last_heartbeat': worker_stats['last_heartbeat'].isoformat()
                    if worker_stats['last_heartbeat']
                    else None,
                },
            }

    async def get_user_queue_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get queue status scoped to a specific user.

        Returns the user's queued/running counts, recent task history,
        and active runs with notification status.
        """
        async with self._pool.acquire() as conn:
            # User's queue counts
            queue_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'running') as running,
                    COUNT(*) FILTER (WHERE status = 'needs_input') as needs_input,
                    COUNT(*) FILTER (WHERE status = 'completed' AND created_at > NOW() - INTERVAL '24 hours') as completed_24h,
                    COUNT(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '24 hours') as failed_24h,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as total_this_month
                FROM task_runs
                WHERE user_id = $1
                """,
                user_id,
            )

            # User's active runs (queued or running)
            active_runs = await conn.fetch(
                """
                SELECT 
                    tr.id,
                    tr.task_id,
                    tr.status,
                    tr.priority,
                    tr.started_at,
                    tr.created_at,
                    tr.runtime_seconds,
                    tr.notification_status,
                    tr.result_summary,
                    t.title
                FROM task_runs tr
                LEFT JOIN tasks t ON tr.task_id = t.id
                WHERE tr.user_id = $1 
                  AND tr.status IN ('queued', 'running', 'needs_input')
                ORDER BY 
                    CASE tr.status WHEN 'running' THEN 0 WHEN 'needs_input' THEN 1 ELSE 2 END,
                    tr.priority DESC,
                    tr.created_at ASC
                LIMIT 20
                """,
                user_id,
            )

            # User's recent completed/failed runs
            recent_runs = await conn.fetch(
                """
                SELECT 
                    tr.id,
                    tr.task_id,
                    tr.status,
                    tr.completed_at,
                    tr.runtime_seconds,
                    tr.notification_status,
                    tr.result_summary,
                    t.title
                FROM task_runs tr
                LEFT JOIN tasks t ON tr.task_id = t.id
                WHERE tr.user_id = $1 
                  AND tr.status IN ('completed', 'failed')
                  AND tr.created_at > NOW() - INTERVAL '24 hours'
                ORDER BY tr.completed_at DESC
                LIMIT 10
                """,
                user_id,
            )

            # User's limits (from users table)
            user_limits = await conn.fetchrow(
                """
                SELECT 
                    concurrency_limit,
                    tasks_limit,
                    tasks_used_this_month,
                    max_runtime_seconds,
                    tier_id
                FROM users
                WHERE id = $1
                """,
                user_id,
            )

            return {
                'queue': {
                    'queued': queue_stats['queued'] or 0,
                    'running': queue_stats['running'] or 0,
                    'needs_input': queue_stats['needs_input'] or 0,
                    'completed_24h': queue_stats['completed_24h'] or 0,
                    'failed_24h': queue_stats['failed_24h'] or 0,
                    'total_this_month': queue_stats['total_this_month'] or 0,
                },
                'limits': {
                    'concurrency_limit': user_limits['concurrency_limit']
                    if user_limits
                    else 1,
                    'tasks_limit': user_limits['tasks_limit']
                    if user_limits
                    else 10,
                    'tasks_used': user_limits['tasks_used_this_month']
                    if user_limits
                    else 0,
                    'max_runtime_seconds': user_limits['max_runtime_seconds']
                    if user_limits
                    else 600,
                    'tier': user_limits['tier_id'] if user_limits else 'free',
                },
                'active_runs': [
                    {
                        'id': run['id'],
                        'task_id': run['task_id'],
                        'title': run['title'] or 'Untitled',
                        'status': run['status'],
                        'priority': run['priority'],
                        'started_at': run['started_at'].isoformat()
                        if run['started_at']
                        else None,
                        'created_at': run['created_at'].isoformat()
                        if run['created_at']
                        else None,
                        'runtime_seconds': run['runtime_seconds'],
                        'notification_status': run['notification_status'],
                    }
                    for run in active_runs
                ],
                'recent_runs': [
                    {
                        'id': run['id'],
                        'task_id': run['task_id'],
                        'title': run['title'] or 'Untitled',
                        'status': run['status'],
                        'completed_at': run['completed_at'].isoformat()
                        if run['completed_at']
                        else None,
                        'runtime_seconds': run['runtime_seconds'],
                        'notification_status': run['notification_status'],
                        'result_summary': run['result_summary'],
                    }
                    for run in recent_runs
                ],
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
        import json as json_module

        # Parse required_capabilities from JSON if present
        required_capabilities = None
        if row.get('required_capabilities'):
            try:
                caps = row['required_capabilities']
                if isinstance(caps, str):
                    required_capabilities = json_module.loads(caps)
                elif isinstance(caps, list):
                    required_capabilities = caps
            except (json_module.JSONDecodeError, TypeError):
                pass

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
            # Routing fields
            target_agent_name=row.get('target_agent_name'),
            required_capabilities=required_capabilities,
            deadline_at=row.get('deadline_at'),
            routing_failed_at=row.get('routing_failed_at'),
            routing_failure_reason=row.get('routing_failure_reason'),
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
    # Agent routing parameters
    target_agent_name: Optional[str] = None,
    required_capabilities: Optional[List[str]] = None,
    deadline_at: Optional[datetime] = None,
) -> Optional[TaskRun]:
    """
    Convenience function to enqueue a task.

    Returns None if task queue is not initialized.

    Args:
        task_id: ID of the task to execute
        user_id: Owner user ID (for concurrency limiting)
        template_id: Template that generated this task (optional)
        automation_id: Automation that generated this task (optional)
        priority: Higher = more urgent (default 0)
        notify_email: Email to notify on completion
        notify_webhook_url: Webhook to call on completion
        target_agent_name: If set, only this agent can claim the task
        required_capabilities: List of capabilities the worker must have
        deadline_at: If set, task fails if not claimed by this time
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
        target_agent_name=target_agent_name,
        required_capabilities=required_capabilities,
        deadline_at=deadline_at,
    )
