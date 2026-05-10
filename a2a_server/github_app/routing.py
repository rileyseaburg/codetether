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
    """Return capability metadata for GitHub App durable workspace tasks.

    The clone/prep task is intentionally routed to persistent-workspace class
    workers instead of a hardcoded Knative worker name. Explicit
    GITHUB_APP_TARGET_WORKER_ID/GITHUB_APP_TARGET_AGENT settings still win for
    existing deployments that need pinning.
    """
    if TARGET_WORKER_ID or TARGET_AGENT:
        return {}
    if TARGET_CAPABILITIES:
        return {'required_capabilities': list(TARGET_CAPABILITIES)}
    return {}


async def resolve_task_target() -> dict[str, Any]:
    """Pick a connected persistent workspace worker or configured target."""
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
        return {'target_worker_id': str(capable_match['worker_id'])}

    for agent_name in PREFERRED_AGENTS:
        match = _best_worker(
            [worker for worker in workers if worker.get('name') == agent_name]
        )
        if match:
            return {'target_worker_id': str(match['worker_id'])}
    local_match = _best_worker(
        [
            worker
            for worker in workers
            if 'k8s' not in str(worker.get('hostname') or '').lower()
            and 'knative' not in str(worker.get('name') or '').lower()
        ]
    )
    if local_match:
        return {'target_worker_id': str(local_match['worker_id'])}
    if TARGET_AGENT:
        return {'target_agent_name': TARGET_AGENT}
    return clone_task_routing_metadata()
