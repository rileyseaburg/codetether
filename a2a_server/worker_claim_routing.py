"""Worker claim routing helpers shared by SSE and durable claim paths."""

from __future__ import annotations

import logging

from datetime import UTC, datetime

from a2a_server.database import db_get_worker


type CapabilityPayload = str | list[object] | tuple[object, ...] | None

logger = logging.getLogger(__name__)

PERSISTENT_ALIASES = {
    'persistent-workspace',
    'persistent_workspace',
    'persistent',
    'harvester',
}


def normalize_capabilities(value: CapabilityPayload) -> list[str]:
    """Normalize capability payloads from headers, JSON, or DB rows.

    Treat persistent workspace capability aliases as satisfying the legacy
    ``persistent`` requirement emitted by task routing. Existing harvesters
    commonly register ``persistent-workspace``/``persistent_workspace`` rather
    than literal ``persistent``.
    """
    if isinstance(value, str):
        raw_capabilities: list[object] = [value]
    elif isinstance(value, tuple):
        raw_capabilities = list(value)
    elif isinstance(value, list):
        raw_capabilities = value
    else:
        return []

    capabilities: list[str] = []
    for raw_cap in raw_capabilities:
        cap = str(raw_cap).strip()
        if not cap:
            continue
        capabilities.append(cap)
        if cap in PERSISTENT_ALIASES:
            capabilities.append('persistent')
    return list(dict.fromkeys(capabilities))


def has_persistent_workspace_capability(capabilities: list[str]) -> bool:
    """Return true if capabilities include a persistent worker alias."""
    return any(cap in PERSISTENT_ALIASES for cap in capabilities)


async def db_worker_agent_name(worker_id: str) -> str | None:
    """Resolve a worker's registered agent name from durable storage."""
    try:
        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug('Failed to resolve worker %s from DB: %s', worker_id, e)
        return None

    if not worker:
        return None
    return str(worker.get('name') or '').strip() or None


async def db_worker_capabilities(worker_id: str) -> list[str]:
    """Resolve a worker's registered capabilities from durable storage."""
    try:
        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug(
            'Failed to resolve worker capabilities for %s: %s',
            worker_id,
            e,
        )
        return []

    if not worker:
        return []
    return normalize_capabilities(worker.get('capabilities'))


async def db_worker_recent(worker_id: str, max_age_seconds: int = 120) -> bool:
    """Return true when a worker id still represents a live process."""
    try:
        worker = await db_get_worker(worker_id)
    except Exception as e:
        logger.debug(
            'Failed to resolve target worker freshness for %s: %s',
            worker_id,
            e,
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
    age_seconds = (datetime.now(UTC) - last_seen).total_seconds()
    return age_seconds <= max_age_seconds
