"""Worker claim routing helpers shared by SSE and durable claim paths."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def normalize_capabilities(value: Any) -> list[str]:
    """Normalize capability payloads from headers, JSON, or DB rows."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(cap).strip() for cap in value if str(cap).strip()]


def has_persistent_workspace_capability(capabilities: list[str]) -> bool:
    return any(
        cap in {'persistent-workspace', 'persistent_workspace', 'persistent', 'harvester'}
        for cap in capabilities
    )


async def db_worker_agent_name(worker_id: str) -> Optional[str]:
    """Resolve a worker's registered agent name from durable storage."""
    try:
        from .database import db_get_worker

        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug(f'Failed to resolve worker {worker_id} from DB: {e}')
        return None

    if not worker:
        return None
    return str(worker.get('name') or '').strip() or None


async def db_worker_capabilities(worker_id: str) -> list[str]:
    """Resolve a worker's registered capabilities from durable storage."""
    try:
        from .database import db_get_worker

        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug(
            f'Failed to resolve worker capabilities for {worker_id}: {e}'
        )
        return []

    if not worker:
        return []
    return normalize_capabilities(worker.get('capabilities'))


async def db_worker_recent(worker_id: str, max_age_seconds: int = 120) -> bool:
    """Return true when a worker id still represents a live process."""
    try:
        from .database import db_get_worker

        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug(f'Failed to resolve target worker freshness for {worker_id}: {e}')
        return False

    if not worker or worker.get('status') != 'active':
        return False

    last_seen = worker.get('last_seen') or worker.get('last_heartbeat')
    if not last_seen:
        return False
    if isinstance(last_seen, str):
        try:
            last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
        except ValueError:
            return False
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_seen).total_seconds() <= max_age_seconds
