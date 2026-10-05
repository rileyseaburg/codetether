"""Bridge durable fire-and-forget task runs into connected SSE workers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_persistent_claim_loop_task: Optional[asyncio.Task] = None
_persistent_claim_loop_stop: Optional[asyncio.Event] = None


async def _task_payload_for_worker(task_id: str) -> Optional[dict[str, Any]]:
    """Load a task row and format the SSE payload expected by Rust workers."""

    async def _from_task_dict(task: dict[str, Any]) -> dict[str, Any]:
        metadata = task.get('metadata') or {}
        return {
            'id': task.get('id'),
            'codebase_id': task.get('codebase_id') or task.get('workspace_id'),
            'title': task.get('title'),
            'prompt': task.get('prompt'),
            'agent_type': task.get('agent_type'),
            'priority': task.get('priority'),
            'metadata': metadata,
            'model': task.get('model'),
            'model_ref': task.get('model_ref') or metadata.get('model_ref'),
            'target_agent_name': task.get('target_agent_name')
            or metadata.get('target_agent_name'),
            'dispatch_mode': metadata.get('dispatch_mode') or 'fire_and_forget',
            'task_timeout_seconds': metadata.get('task_timeout_seconds'),
            'created_at': task.get('created_at'),
        }

    try:
        from .agent_bridge import get_bridge as get_agent_bridge

        bridge = get_agent_bridge()
        task = await bridge.get_task(task_id) if bridge else None
        if task:
            metadata = task.metadata or {}
            return {
                'id': task.id,
                'codebase_id': task.codebase_id,
                'title': task.title,
                'prompt': task.prompt,
                'agent_type': task.agent_type,
                'priority': task.priority,
                'metadata': metadata,
                'model': task.model,
                'model_ref': getattr(task, 'model_ref', None) or metadata.get('model_ref'),
                'target_agent_name': getattr(task, 'target_agent_name', None)
                or metadata.get('target_agent_name'),
                'dispatch_mode': metadata.get('dispatch_mode') or 'fire_and_forget',
                'task_timeout_seconds': metadata.get('task_timeout_seconds'),
                'created_at': task.created_at.isoformat() if task.created_at else None,
            }
    except Exception as exc:
        logger.warning(
            'Bridge task load failed for %s; falling back to DB row: %s',
            task_id,
            exc,
        )

    try:
        from .database import db_get_task

        raw_task = await db_get_task(task_id)
        if raw_task:
            return await _from_task_dict(raw_task)
    except Exception as exc:
        logger.warning(f'Failed to load extended task payload {task_id}: {exc}')
    return None


async def _persistent_claim_loop(
    stop_event: asyncio.Event,
    registry_factory: Callable[[], Any],
) -> None:
    from .persistent_worker_pool import claim_extended_task

    while not stop_event.is_set():
        try:
            registry = registry_factory()
            workers = await registry.list_idle_persistent_workers()
            claimed_any = False
            for worker in workers:
                result = await claim_extended_task(
                    worker_id=worker.worker_id,
                    agent_name=worker.agent_name,
                    capabilities=worker.capabilities,
                )
                if not result:
                    continue
                payload = await _task_payload_for_worker(result['task_id'])
                if not payload:
                    continue
                payload['run_id'] = result.get('run_id')
                payload['dispatch_mode'] = result.get('dispatch_mode') or 'fire_and_forget'
                payload['task_timeout_seconds'] = result.get('task_timeout_seconds')
                if result.get('checkpoint') is not None:
                    payload['checkpoint'] = result.get('checkpoint')
                    payload['checkpoint_seq'] = result.get('checkpoint_seq', 0)
                    payload['resume_attempt'] = result.get('resume_attempt', 0)
                pushed = await registry.push_task_to_worker(worker.worker_id, payload)
                if pushed:
                    await registry.claim_task(result['task_id'], worker.worker_id)
                    claimed_any = True
                    logger.info(
                        'Persistent claim loop pushed run %s task %s to worker %s',
                        result.get('run_id'), result.get('task_id'), worker.worker_id,
                    )
                else:
                    logger.warning(
                        'Persistent claim loop claimed task %s for disconnected worker %s',
                        result.get('task_id'), worker.worker_id,
                    )
            await asyncio.wait_for(stop_event.wait(), timeout=5 if claimed_any else 15)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f'Persistent claim loop error: {exc}')
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass


def start_persistent_claim_loop(registry_factory: Callable[[], Any]) -> None:
    """Start the durable task-run to SSE bridge once per process."""
    global _persistent_claim_loop_task, _persistent_claim_loop_stop
    if _persistent_claim_loop_task and not _persistent_claim_loop_task.done():
        return
    _persistent_claim_loop_stop = asyncio.Event()
    _persistent_claim_loop_task = asyncio.create_task(
        _persistent_claim_loop(_persistent_claim_loop_stop, registry_factory)
    )
    logger.info('Persistent claim loop started')


async def stop_persistent_claim_loop() -> None:
    """Stop the durable task-run to SSE bridge."""
    global _persistent_claim_loop_task, _persistent_claim_loop_stop
    if _persistent_claim_loop_stop:
        _persistent_claim_loop_stop.set()
    if _persistent_claim_loop_task:
        _persistent_claim_loop_task.cancel()
        try:
            await _persistent_claim_loop_task
        except asyncio.CancelledError:
            pass
    _persistent_claim_loop_task = None
    _persistent_claim_loop_stop = None
