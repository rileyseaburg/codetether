"""Worker claim routing helpers shared by SSE and durable claim paths."""

from __future__ import annotations

import json
import logging

from datetime import UTC, datetime
from typing import Any


logger = logging.getLogger(__name__)


def normalize_capabilities(value: Any) -> list[str]:
    """Normalize capability payloads from headers, JSON, or DB rows."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [value]
        value = parsed
    if not isinstance(value, list):
        return []
    return [str(cap).strip() for cap in value if str(cap).strip()]


_PERSISTENT_CAPABILITY_ALIASES = {
    'persistent': {
        'persistent',
        'persistent-workspace',
        'persistent_workspace',
        'harvester',
    },
    'persistent-workspace': {
        'persistent-workspace',
        'persistent_workspace',
        'persistent',
        'harvester',
    },
    'persistent_workspace': {
        'persistent-workspace',
        'persistent_workspace',
        'persistent',
        'harvester',
    },
}


def has_persistent_workspace_capability(capabilities: list[str]) -> bool:
    return any(
        cap in _PERSISTENT_CAPABILITY_ALIASES['persistent']
        for cap in capabilities
    )


def worker_satisfies_required_capabilities(
    worker_capabilities: list[str],
    required_capabilities: list[str],
) -> bool:
    """Return whether worker capabilities satisfy task requirements.

    Persistent workers historically register one of several equivalent names
    (persistent, persistent-workspace, persistent_workspace, harvester). Keep
    claim-time eligibility aligned with polling-time eligibility so a worker is
    not offered a task it cannot claim.
    """
    if not required_capabilities:
        return True
    if not worker_capabilities:
        return False
    worker_caps = set(worker_capabilities)
    for required in required_capabilities:
        accepted = _PERSISTENT_CAPABILITY_ALIASES.get(required, {required})
        if not worker_caps.intersection(accepted):
            return False
    return True


async def db_worker_agent_name(worker_id: str) -> str | None:
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
        logger.debug(
            f'Failed to resolve target worker freshness for {worker_id}: {e}'
        )
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
        last_seen = last_seen.replace(tzinfo=UTC)
    return (datetime.now(UTC) - last_seen).total_seconds() <= max_age_seconds
