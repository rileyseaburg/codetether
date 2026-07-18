"""Reconcile native Forgejo agent controls into CodeTether execution state."""

from __future__ import annotations

import json
import logging

from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {'pending', 'queued', 'assigned', 'running', 'in_progress'}


async def _linked_tasks(limit: int) -> list[dict[str, Any]]:
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.*
            FROM tasks t
            WHERE t.metadata ? 'forgejo_agent_task_id'
              AND t.metadata->>'source' = 'forgejo-webhook'
              AND t.status IN (
                'pending', 'queued', 'assigned', 'running', 'in_progress',
                'cancelled'
              )
            ORDER BY t.updated_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def _cancel_codetether_task(task_id: str) -> bool:
    """Atomically cancel a task and its latest active run."""
    from a2a_server import database as db

    pool = await db.get_pool()
    if not pool:
        return False
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE tasks
            SET status = 'cancelled', updated_at = NOW(), completed_at = NOW()
            WHERE id = $1
              AND status IN ('pending', 'queued', 'assigned', 'running', 'in_progress')
            """,
            task_id,
        )
        await conn.execute(
            """
            UPDATE task_runs
            SET status = 'cancelled', completed_at = NOW(),
                lease_expires_at = NOW()
            WHERE task_id = $1 AND status IN ('queued', 'running')
            """,
            task_id,
        )
    return result.endswith('1')


def _metadata(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get('metadata') or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, dict) else {}


async def _retry_codetether_task(
    task: dict[str, Any], forgejo_task: dict[str, Any]
) -> str:
    """Create one new execution for a Forgejo task returned to pending."""
    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    metadata = _metadata(task)
    retry_generation = int(metadata.get('forgejo_retry_generation') or 0) + 1
    metadata['forgejo_retry_generation'] = retry_generation
    metadata['forgejo_retry_of'] = str(task.get('id') or '')
    metadata['forgejo_work_key'] = (
        f'{metadata.get("forgejo_work_key") or "forgejo-agent"}:'
        f'retry:{retry_generation}'
    )
    workspace_id = str(
        task.get('workspace_id')
        or task.get('codebase_id')
        or metadata.get('workspace_id')
        or ''
    )
    if not workspace_id:
        raise RuntimeError('linked CodeTether task has no workspace')
    return await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=str(task.get('title') or 'Retry Forgejo agent task'),
        prompt=str(task.get('prompt') or task.get('description') or ''),
        agent_type=str(
            task.get('agent_type') or metadata.get('agent_type') or 'build'
        ),
        priority=int(task.get('priority') or 0),
        model_ref=str(task.get('model_ref') or metadata.get('model_ref') or '')
        or None,
        metadata=metadata,
        task_timeout_seconds=int(task.get('task_timeout_seconds') or 604800),
    )


async def reconcile_forgejo_agent_controls(limit: int = 50) -> int:
    """Apply Forgejo cancel/retry state to linked CodeTether tasks."""
    from a2a_server.forgejo_agent_client import get_task, update_task

    handled = 0
    for task in await _linked_tasks(limit):
        metadata = _metadata(task)
        repo = str(metadata.get('repo') or '')
        forgejo_task_id = int(metadata.get('forgejo_agent_task_id') or 0)
        base_url = str(metadata.get('forgejo_api_url') or '')
        if not repo or not forgejo_task_id:
            continue
        forgejo_task = await get_task(
            repo=repo, task_id=forgejo_task_id, base_url=base_url
        )
        forgejo_status = str(forgejo_task.get('status') or '')
        codetether_status = str(task.get('status') or '')
        if (
            forgejo_status == 'cancelled'
            and codetether_status in _ACTIVE_STATUSES
        ):
            if await _cancel_codetether_task(str(task['id'])):
                handled += 1
                logger.info(
                    'Cancelled CodeTether task %s from Forgejo task %s',
                    task['id'],
                    forgejo_task_id,
                )
            continue
        if forgejo_status == 'pending' and codetether_status == 'cancelled':
            new_task_id = await _retry_codetether_task(task, forgejo_task)
            await update_task(
                repo=repo,
                task_id=forgejo_task_id,
                base_url=base_url,
                status='accepted',
                external_task_id=str(new_task_id),
            )
            handled += 1
            logger.info(
                'Retried Forgejo task %s as CodeTether task %s',
                forgejo_task_id,
                new_task_id,
            )
    return handled
