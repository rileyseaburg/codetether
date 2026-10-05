"""
Task Status Audit Trail — structured logging for every status transition.

Records every task_runs status change into the database so operators can
reconstruct the full lifecycle of any job.  Each row captures:

    task_run_id, old_status, new_status, actor, reason, metadata, timestamp

Usage (from any module that transitions a task run):

    from .task_status_audit import record_transition

    await record_transition(
        run_id=run_id,
        old_status='queued',
        new_status='picked_up',
        actor=worker_id,
        reason='Worker claimed task',
        metadata={'model_ref': model_ref},
    )

The module is intentionally dependency-light: it only needs the db pool.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def record_transition(
    *,
    run_id: str,
    old_status: str,
    new_status: str,
    actor: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    pool=None,
) -> None:
    """
    Persist a single status transition to the task_status_audit table.

    Silently succeeds even if the table doesn't exist yet (graceful degradation).

    Args:
        pool: Optional asyncpg pool. If not provided, falls back to the
              global pool from a2a_server.database.
    """
    try:
        if pool is None:
            from . import database as db

            pool = await db.get_pool()
        if not pool:
            logger.debug('DB pool not available for status audit')
            return

        # Let asyncpg handle JSONB serialization natively.
        meta_value = json.dumps(metadata) if metadata else None

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO task_status_audit
                    (task_run_id, old_status, new_status, actor, reason,
                     transition_metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, DEFAULT)
                """,
                run_id,
                old_status,
                new_status,
                actor,
                reason,
                meta_value,
            )
    except Exception as exc:
        # Graceful degradation: never let audit recording break the actual transition.
        logger.debug('task_status_audit write failed: %s', exc)


async def get_transition_history(
    run_id: str, limit: int = 50, *, pool=None
) -> list:
    """Return the full transition history for a task run (newest first)."""
    try:
        if pool is None:
            from . import database as db

            pool = await db.get_pool()
        if not pool:
            return []

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT task_run_id, old_status, new_status, actor, reason,
                       transition_metadata, created_at
                FROM task_status_audit
                WHERE task_run_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                run_id,
                limit,
            )
            return [
                {
                    'task_run_id': r['task_run_id'],
                    'old_status': r['old_status'],
                    'new_status': r['new_status'],
                    'actor': r['actor'],
                    'reason': r['reason'],
                    'metadata': (
                        json.loads(r['transition_metadata'])
                        if isinstance(r['transition_metadata'], str)
                        else r['transition_metadata']
                    ),
                    'created_at': r['created_at'].isoformat(),
                }
                for r in rows
            ]
    except Exception as exc:
        logger.debug('task_status_audit read failed: %s', exc)
        return []
