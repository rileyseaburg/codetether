"""
Cron task dispatch helpers.

Shared logic for creating/routing tasks from cronjobs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from .agent_bridge import get_agent_bridge
from .task_orchestration import orchestrate_task_route

logger = logging.getLogger(__name__)


def _coerce_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return default
    return default


def _coerce_str(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


async def dispatch_cron_task(
    *,
    job_id: str,
    run_id: str,
    job_name: str,
    task_template: Dict[str, Any],
    tenant_id: Optional[str],
    user_id: Optional[str],
    trigger_mode: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Create and route a cron-triggered task through the shared agent bridge.

    Returns:
        (task_id, routing_info)
    """
    bridge = get_agent_bridge()
    if bridge is None:
        raise RuntimeError('Agent bridge not available')

    template = _coerce_dict(task_template)
    metadata = _coerce_dict(template.get('metadata'))
    agent_type = _coerce_str(template.get('agent_type')) or 'build'
    codebase_id = _coerce_str(template.get('codebase_id'))
    priority = _coerce_int(template.get('priority'), default=0)

    prompt = _coerce_str(template.get('prompt')) or _coerce_str(
        template.get('description')
    )
    if not prompt:
        prompt = f'Run cronjob "{job_name}".'

    default_title_prefix = 'Manual' if trigger_mode == 'manual' else 'Cronjob'
    title = _coerce_str(template.get('title')) or f'{default_title_prefix}: {job_name}'

    # Stamp scheduler metadata so runs can be traced and resumed reliably.
    metadata.setdefault('cronjob_id', job_id)
    metadata.setdefault('cronjob_run_id', run_id)
    metadata.setdefault('trigger_mode', trigger_mode)
    if tenant_id:
        metadata.setdefault('tenant_id', tenant_id)
    if user_id:
        metadata.setdefault('user_id', str(user_id))

    worker_personality = _coerce_str(template.get('worker_personality')) or _coerce_str(
        metadata.get('worker_personality')
    )
    model = _coerce_str(template.get('model')) or _coerce_str(
        metadata.get('model')
    )
    model_ref = _coerce_str(template.get('model_ref')) or _coerce_str(
        metadata.get('model_ref')
    )

    routing_decision, routed_metadata = orchestrate_task_route(
        prompt=prompt,
        agent_type=agent_type,
        metadata=metadata,
        model=model,
        model_ref=model_ref,
        worker_personality=worker_personality,
    )

    task = await bridge.create_task(
        codebase_id=codebase_id,
        title=title,
        prompt=prompt,
        agent_type=agent_type,
        priority=priority,
        model=routed_metadata.get('model'),
        metadata=routed_metadata,
        model_ref=routing_decision.model_ref,
    )
    if not task:
        raise RuntimeError('Failed to create task for cronjob')

    # Notify connected SSE workers immediately (best-effort).
    task_data = {
        'id': task.id,
        'codebase_id': task.codebase_id,
        'title': task.title,
        'prompt': task.prompt,
        'agent_type': task.agent_type,
        'priority': task.priority,
        'metadata': task.metadata,
        'model': task.model,
        'model_ref': task.model_ref,
        'target_agent_name': task.target_agent_name,
        'created_at': task.created_at.isoformat()
        if task.created_at
        else None,
    }
    required_capabilities = routed_metadata.get('required_capabilities')
    if isinstance(required_capabilities, list):
        task_data['required_capabilities'] = required_capabilities

    try:
        from .worker_sse import notify_workers_of_new_task

        await notify_workers_of_new_task(task_data)
    except Exception as e:
        logger.debug(
            'Failed to push cron task %s to SSE workers immediately: %s',
            task.id,
            e,
        )

    routing_info = {
        'complexity': routing_decision.complexity,
        'model_tier': routing_decision.model_tier,
        'model_ref': routing_decision.model_ref,
        'target_agent_name': routing_decision.target_agent_name,
        'worker_personality': routing_decision.worker_personality,
    }

    return task.id, routing_info

