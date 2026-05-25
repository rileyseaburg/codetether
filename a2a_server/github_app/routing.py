"""Worker selection for GitHub App tasks."""

from datetime import datetime, timezone
from typing import Any, Optional

from .settings import (
    PREFERRED_AGENTS,
    TARGET_AGENT,
    TARGET_CAPABILITIES,
    TARGET_WORKER_ID,
)


def _is_recent(value: Optional[str], max_age_seconds: int = 120) -> bool:
    if not value:
        return False
    last_seen = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_seen).total_seconds() <= max_age_seconds


def _best_worker(workers: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    idle = [worker for worker in workers if not worker.get('is_busy')]
    pool = idle or workers
    if not pool:
        return None
    return max(pool, key=lambda worker: str(worker.get('last_heartbeat') or ''))


def _capabilities(worker: dict[str, Any]) -> set[str]:
    raw = worker.get('capabilities') or []
    if isinstance(raw, str):
        return {raw}
    return {str(cap) for cap in raw if cap}


def _has_any_capability(worker: dict[str, Any], capabilities: tuple[str, ...]) -> bool:
    worker_caps = _capabilities(worker)
    return any(cap in worker_caps for cap in capabilities)


def clone_task_routing_metadata() -> dict[str, Any]:
    """Return mandatory capability metadata for GitHub App durable tasks.

    GitHub App work now runs as the direct replacement path on one cluster, so
    every clone/build/review/fix task must require the persistent workspace
    capability unless it is pinned to a concrete worker id. A configured target
    agent may narrow the agent name, but it no longer removes the capability
    gate.
    """
    metadata: dict[str, Any] = {}
    if TARGET_AGENT:
        metadata['target_agent_name'] = TARGET_AGENT
    if not TARGET_WORKER_ID and TARGET_CAPABILITIES:
        metadata['required_capabilities'] = list(TARGET_CAPABILITIES)
    return metadata


def _worker_routing_metadata(worker: dict[str, Any]) -> dict[str, Any]:
    """Route to a stable worker class instead of an ephemeral worker id."""
    metadata = clone_task_routing_metadata()
    name = str(worker.get('name') or '').strip()
    if name and not metadata.get('target_agent_name'):
        metadata['target_agent_name'] = name
    return metadata


async def resolve_task_target() -> dict[str, Any]:
    """Pick a durable worker route for GitHub App tasks.

    Worker IDs are generated at process start, so using a discovered worker id
    here pins queued work to a pod lifetime. Prefer stable worker name plus
    capability requirements; only honor target_worker_id when explicitly
    configured as a hard operator override.
    """
    from .. import database as db

    workers = [
        worker for worker in await db.db_list_workers(status='active')
        if _is_recent(str(worker.get('last_seen') or ''))
    ]
    if TARGET_WORKER_ID and any(
        str(worker.get('worker_id')) == TARGET_WORKER_ID for worker in workers
    ):
        return {'target_worker_id': TARGET_WORKER_ID}

    capable_match = _best_worker(
        [worker for worker in workers if _has_any_capability(worker, TARGET_CAPABILITIES)]
    )
    if capable_match:
        return _worker_routing_metadata(capable_match)

    for agent_name in PREFERRED_AGENTS:
        match = _best_worker(
            [worker for worker in workers if worker.get('name') == agent_name]
        )
        if match:
            return _worker_routing_metadata(match)
    local_match = _best_worker(
        [
            worker
            for worker in workers
            if 'k8s' not in str(worker.get('hostname') or '').lower()
            and 'knative' not in str(worker.get('name') or '').lower()
        ]
    )
    if local_match:
        return _worker_routing_metadata(local_match)
    return clone_task_routing_metadata()
