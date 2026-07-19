"""PostgreSQL records for in-memory agent tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from a2a_server.agent_bridge import AgentTask


def build(task: AgentTask) -> dict[str, object]:
    """Build the canonical durable record for an agent task."""
    metadata = dict(task.metadata or {})
    optional = (
        ('model', task.model),
        ('model_ref', task.model_ref),
        ('target_agent_name', task.target_agent_name),
        ('model_used', task.model_used),
    )
    for key, value in optional:
        if value and key not in metadata:
            metadata[key] = value
    return {
        'id': task.id,
        'workspace_id': task.codebase_id,
        'codebase_id': task.codebase_id,
        'title': task.title,
        'prompt': task.prompt,
        'agent_type': task.agent_type,
        'status': task.status.value,
        'priority': task.priority,
        'worker_id': None,
        'result': task.result,
        'error': task.error,
        'metadata': metadata,
        'tenant_id': metadata.get('tenant_id'),
        'created_at': task.created_at.isoformat(),
        'updated_at': datetime.now(UTC).isoformat(),
        'started_at': task.started_at.isoformat() if task.started_at else None,
        'completed_at': task.completed_at.isoformat()
        if task.completed_at
        else None,
    }
