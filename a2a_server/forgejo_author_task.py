"""Durable task identity and worker binding for Forgejo conversations."""

import hashlib

from collections.abc import Mapping, MutableMapping

from a2a_server import database as db
from a2a_server.forgejo_author_contract import validate
from a2a_server.forgejo_worker_binding import require as require_worker_binding


def task_identity(metadata: Mapping[str, object]) -> tuple[str, str]:
    """Return the server-derived work key and deterministic task ID."""
    validate(metadata)
    parts = (
        'forgejo-pr-review:v1',
        str(metadata.get('idempotency_scope') or 'internal:global'),
        str(metadata['forgejo_host']).lower(),
        str(metadata['repo']).lower(),
        str(metadata['pr_number']),
        'forgejo-author-review',
        str(metadata['pr_head_sha']).lower(),
        str(metadata['target_agent_name']),
    )
    key = ':'.join(parts)
    task_id = f'cttask_{hashlib.sha256(key.encode()).hexdigest()[:40]}'
    return key, task_id


async def prepare(
    metadata: MutableMapping[str, object],
) -> tuple[str, dict[str, object] | None]:
    """Require durable storage, bind the worker, and find any prior task."""
    _key, task_id = task_identity(metadata)
    if await db.get_pool() is None:
        raise RuntimeError('durable task storage is unavailable')
    existing = await db.db_get_task(task_id)
    if existing:
        return task_id, existing
    tenant_id = str(metadata.get('tenant_id') or '') or None
    worker = await db.db_get_active_worker_by_name(
        str(metadata['target_agent_name']), tenant_id=tenant_id
    )
    if not worker:
        raise LookupError('canonical author worker is not active')
    require_worker_binding(worker, metadata)
    metadata['target_worker_id'] = str(worker['worker_id'])
    metadata['idempotency_key'] = task_id
    metadata['github_work_key'] = task_id
    return task_id, None
