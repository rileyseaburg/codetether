"""Availability validation for explicitly routed workers."""

import logging

from collections.abc import MutableMapping

from a2a_server import database as db
from a2a_server.worker_heartbeat import is_recent
from a2a_server.worker_target_failure import reject


logger = logging.getLogger(__name__)


async def validate_target_worker(
    metadata: MutableMapping[str, object], *, strict: bool = False
) -> None:
    """Require a live worker in strict mode or remove an advisory route."""
    target = str(metadata.get('target_worker_id') or '').strip()
    if not target:
        return
    worker = await _load(target)
    if not worker:
        reject(metadata, target, strict)
        return
    heartbeat = worker.get('last_seen') or worker.get('last_heartbeat')
    value = str(heartbeat) if heartbeat else None
    if not is_recent(value):
        reject(metadata, target, strict, value or 'missing')


async def _load(target: str) -> dict[str, object] | None:
    try:
        return await db.db_get_worker(target)
    except Exception as error:
        logger.debug(
            'Failed to load target worker %s from DB: %s', target, error
        )
        return None
