"""
Persistent Worker Pool — 7-Day Task Execution Infrastructure.

Replaces Knative-based ephemeral model with persistent worker pool:
- StatefulSets (not Knative) — workers stay running 24/7
- PVC-backed workspaces surviving pod restarts
- Fire-and-forget dispatch — returns immediately, no polling
- Heartbeat-based monitoring with configurable lease renewal
- GitHub comment progress reporting every 5 minutes
- Task resumption from checkpoint on worker failure

Configuration:
    PERSISTENT_WORKER_ENABLED: Enable (default: false)
    PERSISTENT_WORKER_LEASE_SECONDS: Lease per heartbeat (default: 3600)
    PERSISTENT_WORKER_MAX_TIMEOUT: Max timeout in seconds (default: 604800 = 7d)
    GITHUB_PROGRESS_INTERVAL_SECONDS: GitHub comment frequency (default: 300)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PERSISTENT_WORKER_ENABLED = os.environ.get(
    'PERSISTENT_WORKER_ENABLED', 'false'
).lower() == 'true'
PERSISTENT_WORKER_LEASE_SECONDS = int(
    os.environ.get('PERSISTENT_WORKER_LEASE_SECONDS', '3600')
)
PERSISTENT_WORKER_MAX_TIMEOUT = int(
    os.environ.get('PERSISTENT_WORKER_MAX_TIMEOUT', '604800')
)
GITHUB_PROGRESS_INTERVAL_SECONDS = int(
    os.environ.get('GITHUB_PROGRESS_INTERVAL_SECONDS', '300')
)

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def create_and_dispatch_task(
    workspace_id: str,
    title: str,
    prompt: str,
    agent_type: str = 'build',
    priority: int = 0,
    model_ref: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    task_timeout_seconds: int = DEFAULT_TASK_TIMEOUT,
    github_issue_url: Optional[str] = None,
) -> str:
    """Create a task AND dispatch it as fire-and-forget in one call.

    Primary entry point for the webhook flow:
      POST /v1/webhooks/github → handle_fix_request() → this function

    Does three things:
      1. Creates the task via the bridge (standard task row)
      2. Creates a fire-and-forget run with the given timeout
      3. Notifies SSE workers that a new task is available

    Returns the task ID.
    """
    from .monitor_api import get_agent_bridge

    bridge = get_agent_bridge()
    if bridge is None:
        raise RuntimeError('Agent bridge not available')

    # Rehydrate workspace if not in local registry (e.g. after restart)
    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        try:
            from .monitor_api import _rehydrate_workspace_into_bridge
            workspace = await _rehydrate_workspace_into_bridge(workspace_id)
        except Exception:
            workspace = None

    effective_metadata = dict(metadata or {})
    if model_ref:
        effective_metadata['model_ref'] = model_ref

    # 1. Create the task via the bridge (standard task row in tasks table)
    task = await bridge.create_task(
        codebase_id=workspace_id,
        title=title,
        prompt=prompt,
        agent_type=agent_type,
        priority=priority,
        model=effective_metadata.get('model'),
        metadata=effective_metadata,
        model_ref=model_ref,
    )
    if not task:
        raise RuntimeError('Failed to create task')

    task_id = task.id if hasattr(task, 'id') else task.get('id')

    # 2. Dispatch fire-and-forget run (creates task_runs row with FF mode)
    await dispatch_fire_and_forget(
        task_id=task_id,
        title=title,
        description=prompt,
        agent_type=agent_type,
        model=model_ref,
        priority=priority,
        task_timeout_seconds=task_timeout_seconds,
        github_issue_url=github_issue_url,
        metadata=effective_metadata,
    )

    logger.info(
        f'Created and dispatched FF task {task_id} '
        f'(timeout={task_timeout_seconds}s, github={bool(github_issue_url)})'
    )
    return task_id


async def dispatch_fire_and_forget(
    task_id: str,
    title: str,
    description: str,
    agent_type: str = 'build',
    model: Optional[str] = None,
    priority: int = 0,
    task_timeout_seconds: int = 604800,
    github_issue_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fire-and-forget dispatch: create task + run, return immediately."""
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    async with pool.acquire() as conn:
        run_id = await conn.fetchval(
            'SELECT create_fire_and_forget_run($1, $2, $3, $4, $5, $6)',
            task_id, user_id, tenant_id, priority,
            min(task_timeout_seconds, PERSISTENT_WORKER_MAX_TIMEOUT),
            github_issue_url,
        )

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET dispatch_mode = 'fire_and_forget', updated_at = NOW() "
            "WHERE id = $1", task_id,
        )

    # Notify SSE workers
    try:
        from .worker_sse import notify_workers_of_new_task
        task_data = {
            'id': task_id, 'title': title, 'prompt': description,
            'agent_type': agent_type, 'model': model, 'priority': priority,
            'metadata': metadata or {}, 'dispatch_mode': 'fire_and_forget',
            'task_timeout_seconds': task_timeout_seconds,
        }
        notified = await notify_workers_of_new_task(task_data)
        logger.info(
            f'FF task {task_id} dispatched (run={run_id}), '
            f'notified {len(notified)} SSE workers'
        )
    except Exception as e:
        logger.warning(f'SSE notify failed for {task_id}: {e}')

    return {
        'task_id': task_id, 'run_id': run_id, 'status': 'queued',
        'dispatch_mode': 'fire_and_forget',
        'task_timeout_seconds': task_timeout_seconds,
        'message': 'Task dispatched. Monitor via heartbeat API or GitHub comments.',
    }


async def claim_extended_task(
    worker_id: str,
    agent_name: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
    models_supported: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Claim next task including fire_and_forget with checkpoint resume."""
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM claim_next_task_run_extended($1, $2, $3, $4, $5, $6)',
            worker_id, PERSISTENT_WORKER_LEASE_SECONDS,
            agent_name, json.dumps(capabilities or []),
            models_supported or None, PERSISTENT_WORKER_MAX_TIMEOUT,
        )

    if not row or not row.get('run_id'):
        return None

    result = dict(row)
    logger.info(
        f'Worker {worker_id} claimed run {result["run_id"]} '
        f'(task={result["task_id"]}, mode={result.get("dispatch_mode")}, '
        f'resume={result.get("resume_attempt", 0)})'
    )
    return result


async def post_extended_heartbeat(
    task_id: str,
    worker_id: str,
    progress_pct: Optional[float] = None,
    status_message: Optional[str] = None,
    checkpoint: Optional[Dict[str, Any]] = None,
    checkpoint_seq: Optional[int] = None,
    log_tail: Optional[str] = None,
    lease_extension_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Extended heartbeat for 7-day tasks with checkpoint and lease renewal."""
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    progress_json = None
    if progress_pct is not None or status_message is not None:
        progress_json = json.dumps({
            'progress_pct': progress_pct,
            'status_message': status_message,
            'worker_id': worker_id,
            'heartbeat_at': datetime.now(timezone.utc).isoformat(),
        })

    checkpoint_json = json.dumps(checkpoint) if checkpoint else None
    lease_seconds = lease_extension_seconds or PERSISTENT_WORKER_LEASE_SECONDS

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM extended_heartbeat($1, $2, $3, $4, $5, $6, $7)',
            task_id, worker_id, progress_json, checkpoint_json,
            checkpoint_seq, lease_seconds, log_tail,
        )

    if not row or not row['success']:
        return {
            'success': False,
            'message': 'Heartbeat rejected: no active run or wrong worker',
        }

    return {
        'success': True,
        'lease_expires_at': row['lease_expires_at'].isoformat()
            if row['lease_expires_at'] else None,
        'within_timeout': row['within_timeout'],
        'elapsed_seconds': row['elapsed_seconds'],
        'resume_attempt': row['resume_attempt'],
    }
