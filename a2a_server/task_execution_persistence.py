"""Persist worker and session projection fields for existing agent tasks."""

from __future__ import annotations

import json
import logging
from typing import Any

from . import database as db

logger = logging.getLogger(__name__)


async def persist_task_execution(
    task_id: str,
    *,
    worker_id: str | None,
    metadata: dict[str, Any],
) -> bool:
    """Refresh execution fields omitted by the legacy task upsert conflict path."""
    pool = await db.get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tasks
                SET worker_id = COALESCE($2, worker_id),
                    metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb,
                    updated_at = NOW()
                WHERE id = $1
                """,
                task_id,
                worker_id,
                json.dumps(metadata),
            )
        return 'UPDATE 1' in result
    except Exception as exc:
        logger.error('Failed to persist task execution projection: %s', exc)
        return False
