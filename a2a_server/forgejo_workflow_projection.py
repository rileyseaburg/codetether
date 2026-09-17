"""Reconcile a stale native badge from current workflow state, never history."""

import asyncio
import logging

from importlib import import_module

from temporalio.client import WorkflowExecutionStatus

from a2a_server import forgejo_agent_client as native


LOG = logging.getLogger(__name__)
TERMINAL = {'completed', 'failed', 'cancelled'}
CLOSED_FAILURES = {
    WorkflowExecutionStatus.FAILED: ('failed', 'workflow_failed'),
    WorkflowExecutionStatus.CANCELED: ('cancelled', 'workflow_cancelled'),
    WorkflowExecutionStatus.TERMINATED: ('cancelled', 'workflow_terminated'),
    WorkflowExecutionStatus.TIMED_OUT: ('failed', 'workflow_timed_out'),
}


async def reconcile_native(conn, repo, task, base):
    """Repair a closed workflow's native status while holding issue ownership.

    A dead workflow cannot execute its finalizer. Do not confuse its stale
    `running` projection with live work, but never infer success or terminate
    an execution. Continued-as-new, unknown and unavailable state fail closed.
    """
    if task.get('status') in TERMINAL:
        return task
    temporal = import_module('a2a_server.temporal.client')
    if not temporal.temporal_settings().enabled:
        return task
    try:
        return await _reconcile(conn, repo, task, base, temporal)
    except Exception:
        LOG.warning(
            'Native workflow projection deferred: %s/%s', repo, task.get('id')
        )
        return task


async def _reconcile(conn, repo, task, base, temporal) -> dict:
    task_id = int(task['id'])
    handle = await temporal.workflow_handle(task_id)
    description = await asyncio.wait_for(handle.describe(), timeout=10)
    outcome = CLOSED_FAILURES.get(description.status)
    if outcome is None:
        return task
    live = await conn.fetchval(
        """
        SELECT id FROM tasks
        WHERE metadata->>'repo'=$1
          AND (metadata->>'forgejo_agent_task_id'=$2
            OR metadata->>'recovery_native_request'=$2)
          AND status IN ('pending','queued','assigned','running',
                         'working','in_progress') LIMIT 1
    """,
        repo,
        str(task_id),
    )
    if live:
        return task
    current = await native.get_task(repo=repo, task_id=task_id, base_url=base)
    if current.get('status') != task.get('status'):
        return current
    latest = await asyncio.wait_for(handle.describe(), timeout=10)
    if (latest.run_id, latest.status) != (
        description.run_id,
        description.status,
    ):
        return current
    status, reason = outcome
    return await native.update_task(
        repo=repo,
        task_id=task_id,
        base_url=base,
        status=status,
        error=reason,
    )
