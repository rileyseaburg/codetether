"""
Queue Status API for operational visibility.

Provides endpoints for:
- Admin: Full queue status, notification health, worker status
- Users: Their own queue status, active/recent runs

This enables debugging production issues and powering dashboards
without needing direct database access.
"""

import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .user_auth import get_current_user, require_user
from .task_queue import get_task_queue

logger = logging.getLogger(__name__)

# Admin API key from environment (simple auth for /v1/queue/status)
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')

router = APIRouter(prefix='/v1/queue', tags=['Queue Status'])


# ========================================
# Response Models
# ========================================


class QueueCounts(BaseModel):
    """Queue counts by status."""

    queued: int
    running: int
    needs_input: int
    completed_24h: int
    failed_24h: int
    avg_wait_seconds: Optional[float] = None
    max_wait_seconds: Optional[int] = None


class NotificationCounts(BaseModel):
    """Notification status counts."""

    email_failed_ready: int
    email_pending_stuck: int
    webhook_failed_ready: int
    webhook_pending_stuck: int
    emails_sent_24h: int
    webhooks_sent_24h: int


class WorkerStatus(BaseModel):
    """Worker pool status."""

    active_pools: int
    total_capacity: int
    current_load: int
    last_heartbeat: Optional[str] = None


class FullQueueStatusResponse(BaseModel):
    """Full queue status for admin dashboard."""

    queue: QueueCounts
    notifications: NotificationCounts
    workers: WorkerStatus


class UserLimits(BaseModel):
    """User's tier limits."""

    concurrency_limit: int
    tasks_limit: int
    tasks_used: int
    max_runtime_seconds: int
    tier: str


class ActiveRun(BaseModel):
    """An active (queued/running) task run."""

    id: str
    task_id: str
    title: str
    status: str
    priority: int
    started_at: Optional[str] = None
    created_at: Optional[str] = None
    runtime_seconds: Optional[int] = None
    notification_status: Optional[str] = None


class RecentRun(BaseModel):
    """A recently completed/failed task run."""

    id: str
    task_id: str
    title: str
    status: str
    completed_at: Optional[str] = None
    runtime_seconds: Optional[int] = None
    notification_status: Optional[str] = None
    result_summary: Optional[str] = None


class UserQueueCounts(BaseModel):
    """Queue counts for a specific user."""

    queued: int
    running: int
    needs_input: int
    completed_24h: int
    failed_24h: int
    total_this_month: int


class UserQueueStatusResponse(BaseModel):
    """User-scoped queue status."""

    queue: UserQueueCounts
    limits: UserLimits
    active_runs: List[ActiveRun]
    recent_runs: List[RecentRun]


# ========================================
# Admin Auth Helper
# ========================================


async def check_admin_access(user: Optional[Dict[str, Any]]) -> bool:
    """
    Check if the request has admin access.

    Admin access is granted if:
    1. User has is_admin flag set, OR
    2. Request includes valid ADMIN_API_KEY header, OR
    3. No ADMIN_API_KEY is configured (dev mode - allow all authenticated users)
    """
    # If user has admin flag
    if user and user.get('is_admin'):
        return True

    # If no ADMIN_API_KEY configured, allow authenticated users (dev mode)
    if not ADMIN_API_KEY:
        return user is not None

    return False


# ========================================
# API Endpoints
# ========================================


@router.get('/status', response_model=FullQueueStatusResponse)
async def get_queue_status(
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get full queue status (admin/internal).

    Returns:
    - Queue counts by status (queued, running, needs_input, completed, failed)
    - Notification health (failed retries, stuck pending)
    - Worker pool status (active pools, capacity, last heartbeat)

    Auth: Requires admin access (is_admin flag or ADMIN_API_KEY env var).
    In dev mode (no ADMIN_API_KEY), any authenticated user can access.
    """
    # Check admin access
    if not await check_admin_access(user):
        raise HTTPException(
            status_code=403,
            detail='Admin access required. Set is_admin flag or configure ADMIN_API_KEY.',
        )

    queue = get_task_queue()
    if not queue:
        raise HTTPException(status_code=503, detail='Task queue not available')

    try:
        status = await queue.get_full_queue_status()
        return FullQueueStatusResponse(**status)
    except Exception as e:
        logger.error(f'Error getting queue status: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get queue status: {str(e)}'
        )


@router.get('/my', response_model=UserQueueStatusResponse)
async def get_my_queue_status(
    user: Dict[str, Any] = Depends(require_user),
):
    """
    Get queue status for the current user.

    Returns:
    - Queue counts (queued, running, completed, failed) for user's tasks
    - User's tier limits (concurrency, task limit, usage)
    - Active runs (queued/running) with status
    - Recent completed/failed runs (last 24h)

    Auth: Requires authenticated user (JWT or API key).
    """
    queue = get_task_queue()
    if not queue:
        raise HTTPException(status_code=503, detail='Task queue not available')

    try:
        status = await queue.get_user_queue_status(user['id'])
        return UserQueueStatusResponse(**status)
    except Exception as e:
        logger.error(f'Error getting user queue status for {user["id"]}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get queue status: {str(e)}'
        )


@router.get('/runs')
async def list_my_runs(
    status: Optional[str] = None,
    limit: int = 50,
    user: Dict[str, Any] = Depends(require_user),
):
    """
    List task runs for the current user.

    Query params:
    - status: Filter by status (queued, running, needs_input, completed, failed)
    - limit: Max results (default 50, max 100)

    Returns list of task runs with status, timing, and notification info.
    """
    queue = get_task_queue()
    if not queue:
        raise HTTPException(status_code=503, detail='Task queue not available')

    # Validate and cap limit
    limit = min(max(1, limit), 100)

    # Validate status if provided
    valid_statuses = {
        'queued',
        'running',
        'needs_input',
        'completed',
        'failed',
        'cancelled',
    }
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid status. Must be one of: {", ".join(valid_statuses)}',
        )

    try:
        from .task_queue import TaskRunStatus

        status_enum = TaskRunStatus(status) if status else None
        runs = await queue.list_runs(
            user_id=user['id'],
            status=status_enum,
            limit=limit,
        )

        return {
            'runs': [
                {
                    'id': run.id,
                    'task_id': run.task_id,
                    'status': run.status.value,
                    'priority': run.priority,
                    'attempts': run.attempts,
                    'started_at': run.started_at.isoformat()
                    if run.started_at
                    else None,
                    'completed_at': run.completed_at.isoformat()
                    if run.completed_at
                    else None,
                    'runtime_seconds': run.runtime_seconds,
                    'result_summary': run.result_summary,
                    'notify_email': run.notify_email,
                    'created_at': run.created_at.isoformat(),
                }
                for run in runs
            ],
            'count': len(runs),
        }
    except Exception as e:
        logger.error(f'Error listing runs for {user["id"]}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list runs: {str(e)}'
        )


@router.get('/runs/{run_id}')
async def get_run(
    run_id: str,
    user: Dict[str, Any] = Depends(require_user),
):
    """
    Get a specific task run by ID.

    Returns full run details including result and notification status.
    Users can only access their own runs.
    """
    queue = get_task_queue()
    if not queue:
        raise HTTPException(status_code=503, detail='Task queue not available')

    try:
        run = await queue.get_run(run_id)

        if not run:
            raise HTTPException(status_code=404, detail='Run not found')

        # Check ownership (unless admin)
        if run.user_id != user['id'] and not user.get('is_admin'):
            raise HTTPException(status_code=403, detail='Access denied')

        return {
            'id': run.id,
            'task_id': run.task_id,
            'user_id': run.user_id,
            'template_id': run.template_id,
            'automation_id': run.automation_id,
            'status': run.status.value,
            'priority': run.priority,
            'attempts': run.attempts,
            'max_attempts': run.max_attempts,
            'last_error': run.last_error,
            'started_at': run.started_at.isoformat()
            if run.started_at
            else None,
            'completed_at': run.completed_at.isoformat()
            if run.completed_at
            else None,
            'runtime_seconds': run.runtime_seconds,
            'result_summary': run.result_summary,
            'result_full': run.result_full,
            'notify_email': run.notify_email,
            'notify_webhook_url': run.notify_webhook_url,
            'created_at': run.created_at.isoformat(),
            'updated_at': run.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting run {run_id}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to get run: {str(e)}'
        )
