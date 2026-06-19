"""Persistent Worker Pool — 7-Day Task Execution Infrastructure.

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

import json
import logging
import os

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any


logger = logging.getLogger(__name__)

PERSISTENT_WORKER_ENABLED = (
    os.environ.get('PERSISTENT_WORKER_ENABLED', 'false').lower() == 'true'
)
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
GITHUB_APP_TENANT_EMAIL = os.environ.get(
    'GITHUB_APP_TENANT_EMAIL', 'github-actions@codetether.run'
)


def _github_work_key(metadata: dict[str, Any]) -> str | None:
    """Return a stable idempotency key for active GitHub App work.

    The key is intentionally scoped to one workflow stage and head SHA so a PR can
    move from prepare -> code, and a new commit can trigger fresh work, while
    concurrent webhook/active-work scans cannot create duplicate workers for the
    same PR commit/stage.
    """
    if metadata.get('source') != 'github-app':
        return None

    repo = str(metadata.get('repo') or '').strip()
    number = metadata.get('pr_number') or metadata.get('issue_number')
    stage = str(
        metadata.get('workflow_stage') or metadata.get('agent_type') or ''
    ).strip()
    head_sha = str(
        metadata.get('pr_head_sha')
        or metadata.get('github_check_head_sha')
        or metadata.get('head_sha')
        or ''
    ).strip()

    if not (repo and number and stage):
        return None
    return f'github-app:{repo}:{number}:{stage}:{head_sha}'


def _is_github_app_task(metadata: dict[str, Any]) -> bool:
    return bool(
        metadata.get('source') == 'github-app'
        or metadata.get('github_installation_id')
        or metadata.get('github_issue_url')
    )


async def _resolve_github_app_tenant_id(
    metadata: dict[str, Any], workspace_id: str | None
) -> str:
    tenant_id = str(metadata.get('tenant_id') or '').strip()
    if tenant_id:
        return tenant_id

    env_tenant_id = str(
        os.environ.get('GITHUB_APP_TENANT_ID')
        or os.environ.get('A2A_GITHUB_APP_TENANT_ID')
        or ''
    ).strip()
    if env_tenant_id:
        return env_tenant_id

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise RuntimeError(
            'Database not available for GitHub App tenant resolution'
        )
    async with pool.acquire() as conn:
        if workspace_id:
            tenant_id = await conn.fetchval(
                'SELECT tenant_id FROM workspaces WHERE id = $1', workspace_id
            )
            if tenant_id:
                return str(tenant_id)
        tenant_id = await conn.fetchval(
            'SELECT tenant_id FROM users WHERE lower(email) = lower($1) LIMIT 1',
            GITHUB_APP_TENANT_EMAIL,
        )
        if tenant_id:
            return str(tenant_id)
    raise RuntimeError('GitHub App task tenant_id is required')


async def _bind_workspace_tenant(
    workspace_id: str | None, tenant_id: str
) -> None:
    if not workspace_id or not tenant_id:
        return
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE workspaces SET tenant_id = $2, updated_at = NOW() '
            'WHERE id = $1 AND tenant_id IS NULL',
            workspace_id,
            tenant_id,
        )


@asynccontextmanager
async def _github_work_dedupe_lock(metadata: dict[str, Any]):
    """Serialize GitHub App task creation for one work key across API pods."""
    work_key = _github_work_key(metadata)
    if not work_key:
        yield None
        return

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        yield work_key
        return

    conn = await pool.acquire()
    try:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1, 0))', work_key
        )
        yield work_key
    finally:
        try:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1, 0))', work_key
            )
        finally:
            await pool.release(conn)


async def _active_github_work_task_id(work_key: str | None) -> str | None:
    """Return the oldest active task for a GitHub App idempotency key."""
    if not work_key:
        return None

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM tasks
            WHERE status IN ('pending', 'queued', 'running', 'working')
              AND COALESCE(metadata, '{}'::jsonb)->>'source' = 'github-app'
              AND COALESCE(metadata, '{}'::jsonb)->>'github_work_key' = $1
            ORDER BY created_at ASC
            LIMIT 1
            """,
            work_key,
        )
    return str(row['id']) if row else None


async def create_and_dispatch_task(
    workspace_id: str,
    title: str,
    prompt: str,
    agent_type: str = 'build',
    priority: int = 0,
    model_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    task_timeout_seconds: int = DEFAULT_TASK_TIMEOUT,
    github_issue_url: str | None = None,
    with_created: bool = False,
):
    """Create a task AND dispatch it as fire-and-forget in one call.

    Primary entry point for the webhook flow:
      POST /v1/webhooks/github → handle_fix_request() → this function

    Does three things:
      1. Creates the task via the bridge (standard task row)
      2. Creates a fire-and-forget run with the given timeout
      3. Notifies SSE workers that a new task is available

    Returns the task ID. When ``with_created`` is True, returns
    ``(task_id, created)`` instead, where ``created`` is False if an active
    task for the same GitHub work key was reused instead of created. Callers
    use this to avoid posting duplicate acceptance comments on redelivered or
    fanned-out webhook events.
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
    effective_metadata.setdefault('agent_type', agent_type)
    if model_ref:
        effective_metadata['model_ref'] = model_ref

    if _is_github_app_task(effective_metadata):
        tenant_id = await _resolve_github_app_tenant_id(
            effective_metadata, workspace_id
        )
        effective_metadata['tenant_id'] = tenant_id
        await _bind_workspace_tenant(workspace_id, tenant_id)
    else:
        tenant_id = (
            str(effective_metadata.get('tenant_id') or '').strip() or None
        )

    work_key = _github_work_key(effective_metadata)
    if work_key:
        effective_metadata['github_work_key'] = work_key

    created = True
    async with _github_work_dedupe_lock(effective_metadata) as locked_work_key:
        existing_task_id = await _active_github_work_task_id(locked_work_key)
        if existing_task_id:
            logger.info(
                'Reusing active GitHub App task %s for work key %s',
                existing_task_id,
                locked_work_key,
            )
            return (
                (existing_task_id, False) if with_created else existing_task_id
            )

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
            tenant_id=tenant_id,
        )

    logger.info(
        f'Created and dispatched FF task {task_id} '
        f'(timeout={task_timeout_seconds}s, github={bool(github_issue_url)})'
    )
    return (task_id, created) if with_created else task_id


async def dispatch_fire_and_forget(
    task_id: str,
    title: str,
    description: str,
    agent_type: str = 'build',
    model: str | None = None,
    priority: int = 0,
    task_timeout_seconds: int = 604800,
    github_issue_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Fire-and-forget dispatch: create task + run, return immediately."""
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    async with pool.acquire() as conn:
        run_id = await conn.fetchval(
            'SELECT create_fire_and_forget_run($1, $2, $3, $4, $5, $6)',
            task_id,
            user_id,
            tenant_id,
            priority,
            min(task_timeout_seconds, PERSISTENT_WORKER_MAX_TIMEOUT),
            github_issue_url,
        )

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tasks SET dispatch_mode = 'fire_and_forget', updated_at = NOW() "
            'WHERE id = $1',
            task_id,
        )

    # Notify SSE workers
    try:
        from .worker_sse import notify_workers_of_new_task

        task_data = {
            'id': task_id,
            'title': title,
            'prompt': description,
            'agent_type': agent_type,
            'model': model,
            'priority': priority,
            'metadata': metadata or {},
            'dispatch_mode': 'fire_and_forget',
            'task_timeout_seconds': task_timeout_seconds,
        }
        routed_metadata = metadata or {}
        for key in (
            'target_agent_name',
            'target_worker_id',
            'required_capabilities',
        ):
            if routed_metadata.get(key):
                task_data[key] = routed_metadata[key]
        notified = await notify_workers_of_new_task(task_data)
        logger.info(
            f'FF task {task_id} dispatched (run={run_id}), '
            f'notified {len(notified)} SSE workers'
        )
    except Exception as e:
        logger.warning(f'SSE notify failed for {task_id}: {e}')

    return {
        'task_id': task_id,
        'run_id': run_id,
        'status': 'queued',
        'dispatch_mode': 'fire_and_forget',
        'task_timeout_seconds': task_timeout_seconds,
        'message': 'Task dispatched. Monitor via heartbeat API or GitHub comments.',
    }


async def claim_extended_task(
    worker_id: str,
    agent_name: str | None = None,
    capabilities: list[str] | None = None,
    models_supported: list[str] | None = None,
) -> dict[str, Any] | None:
    """Claim next task including fire_and_forget with checkpoint resume."""
    from . import database as db

    worker_capabilities = [
        str(cap).strip() for cap in (capabilities or []) if str(cap).strip()
    ]

    # Extended polling is load-balanced independently of the SSE connection.
    # If the poll request did not include capabilities, fall back to durable
    # worker registration so claim-time filtering still prevents Knative-only
    # workers from claiming persistent build/review/forage jobs.
    if not worker_capabilities:
        try:
            worker = await db.db_get_worker(worker_id)
            if worker:
                stored_capabilities = worker.get('capabilities') or []
                worker_capabilities = [
                    str(cap).strip()
                    for cap in stored_capabilities
                    if str(cap).strip()
                ]
        except Exception as e:
            logger.debug(
                f'Failed to load registered capabilities for worker {worker_id}: {e}'
            )

    if (
        'knative' in worker_capabilities
        and 'persistent' not in worker_capabilities
    ):
        logger.debug(
            f'Worker {worker_id} is knative-only; skipping extended persistent claim'
        )
        return None

    pool = await db.get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM claim_next_task_run_extended($1, $2, $3, $4, $5, $6)',
            worker_id,
            PERSISTENT_WORKER_LEASE_SECONDS,
            agent_name,
            json.dumps(worker_capabilities),
            models_supported or None,
            PERSISTENT_WORKER_MAX_TIMEOUT,
        )

    if not row or not row.get('run_id'):
        return None

    result = dict(row)
    logger.info(
        f'Worker {worker_id} claimed run {result["run_id"]} '
        f'(task={result["task_id"]}, mode={result.get("dispatch_mode")}, '
        f'target_agent={result.get("target_agent_name")}, '
        f'resume={result.get("resume_attempt", 0)})'
    )
    return result


async def post_extended_heartbeat(
    task_id: str,
    worker_id: str,
    progress_pct: float | None = None,
    status_message: str | None = None,
    checkpoint: dict[str, Any] | None = None,
    checkpoint_seq: int | None = None,
    log_tail: str | None = None,
    lease_extension_seconds: int | None = None,
) -> dict[str, Any]:
    """Extended heartbeat for 7-day tasks with checkpoint and lease renewal."""
    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    progress_json = None
    if progress_pct is not None or status_message is not None:
        progress_json = json.dumps(
            {
                'progress_pct': progress_pct,
                'status_message': status_message,
                'worker_id': worker_id,
                'heartbeat_at': datetime.now(UTC).isoformat(),
            }
        )

    checkpoint_json = json.dumps(checkpoint) if checkpoint else None
    lease_seconds = lease_extension_seconds or PERSISTENT_WORKER_LEASE_SECONDS

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM extended_heartbeat($1, $2, $3, $4, $5, $6, $7)',
            task_id,
            worker_id,
            progress_json,
            checkpoint_json,
            checkpoint_seq,
            lease_seconds,
            log_tail,
        )

    if not row or not row['success']:
        return {
            'success': False,
            'message': 'Heartbeat rejected: no active run or wrong worker',
        }

    return {
        'success': True,
        'lease_expires_at': row['lease_expires_at'].isoformat()
        if row['lease_expires_at']
        else None,
        'within_timeout': row['within_timeout'],
        'elapsed_seconds': row['elapsed_seconds'],
        'resume_attempt': row['resume_attempt'],
    }
