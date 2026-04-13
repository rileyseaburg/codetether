from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

DEFAULT_CLOUD_EVENT_SOURCE = 'codetether:a2a-server'


def build_event(
    event_type: str,
    data: Dict[str, Any],
    *,
    event_id: Optional[str] = None,
    source: str = DEFAULT_CLOUD_EVENT_SOURCE,
    extensions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = {
        'id': event_id or str(uuid4()),
        'source': source,
        'type': event_type,
        'time': datetime.now(timezone.utc).isoformat(),
        'specversion': '1.0',
        'data': data,
    }
    if extensions:
        event.update({k: v for k, v in extensions.items() if v is not None})
    return event


def build_task_created_data(
    task_id: str,
    *,
    prompt: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    session_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    model: Optional[str] = None,
    priority: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    notify_email: Optional[str] = None,
) -> Dict[str, Any]:
    task_title = title or ((prompt or '')[:80] + ('...' if prompt and len(prompt) > 80 else ''))
    task_description = description or prompt or ''
    return {
        'task_id': task_id,
        'session_id': session_id,
        'title': task_title,
        'description': task_description,
        'prompt': task_description,
        'agent_type': agent_type,
        'agent': agent_type,
        'model': model,
        'priority': priority,
        'metadata': metadata or {},
        'tenant_id': tenant_id,
        'notify_email': notify_email,
    }
