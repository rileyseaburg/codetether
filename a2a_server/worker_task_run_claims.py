"""Durable task_run leasing for worker claims."""

from __future__ import annotations

import json
import logging
from typing import Any

from .worker_claim_routing import db_worker_agent_name, db_worker_capabilities

logger = logging.getLogger(__name__)


async def claim_task_run_for_worker(
    task_id: str,
    worker_id: str,
) -> dict[str, Any]:
    """Best-effort lease of the task_runs row for a specific SSE task claim."""
    try:
        from . import database as db
        from .persistent_worker_pool import PERSISTENT_WORKER_LEASE_SECONDS

        pool = await db.get_pool()
        if not pool:
            return {}
        worker_agent_name = await db_worker_agent_name(worker_id)
        worker_capabilities = await db_worker_capabilities(worker_id)
        capabilities_json = json.dumps(worker_capabilities)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                WITH candidate AS (
                    SELECT tr.id
                    FROM task_runs tr
                    JOIN tasks t ON t.id = tr.task_id
                    WHERE tr.task_id = $1
                      AND tr.status IN ('queued', 'running')
                      AND (
                          tr.lease_owner IS NULL
                          OR tr.lease_owner = $2
                          OR tr.lease_expires_at < NOW()
                      )
                      AND (
                          t.metadata->>'target_worker_id' IS NULL
                          OR t.metadata->>'target_worker_id' = ''
                          OR t.metadata->>'target_worker_id' = $2
                          OR (
                            $4::jsonb @> '["persistent-workspace"]'::jsonb
                            AND NOT EXISTS (
                              SELECT 1
                              FROM workers target_worker
                              WHERE target_worker.worker_id = t.metadata->>'target_worker_id'
                                AND target_worker.status = 'active'
                                AND target_worker.last_seen > NOW() - INTERVAL '2 minutes'
                            )
                          )
                      )
                      AND (
                          COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') IS NULL
                          OR COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') = ''
                          OR COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') = $5
                      )
                      AND (
                          COALESCE(tr.required_capabilities, t.metadata->'required_capabilities') IS NULL
                          OR COALESCE(tr.required_capabilities, t.metadata->'required_capabilities') = '[]'::jsonb
                          OR $4::jsonb @> COALESCE(tr.required_capabilities, t.metadata->'required_capabilities')
                      )
                    ORDER BY
                        CASE WHEN tr.lease_owner = $2 THEN 0 ELSE 1 END,
                        tr.created_at DESC
                    LIMIT 1
                    FOR UPDATE OF tr SKIP LOCKED
                )
                UPDATE task_runs tr
                SET lease_owner = $2,
                    lease_expires_at = NOW() + ($3::int * INTERVAL '1 second'),
                    status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    last_heartbeat_at = NOW(),
                    updated_at = NOW()
                FROM candidate
                WHERE tr.id = candidate.id
                RETURNING
                    tr.id AS run_id,
                    tr.task_id,
                    tr.user_id,
                    tr.tenant_id,
                    tr.dispatch_mode,
                    tr.task_timeout_seconds,
                    tr.github_issue_url,
                    tr.checkpoint,
                    COALESCE(tr.checkpoint_seq, 0) AS checkpoint_seq,
                    COALESCE(tr.resume_attempt, 0) AS resume_attempt
                """,
                task_id,
                worker_id,
                PERSISTENT_WORKER_LEASE_SECONDS,
                capabilities_json,
                worker_agent_name,
            )

        return dict(row) if row else {}
    except Exception as e:
        logger.warning(f'No task_run lease attached to claim {task_id}: {e}')
        return {}


async def mirror_release_to_task_run(
    task_id: str,
    worker_id: str,
    status: str,
    result: str | None,
    error: str | None,
) -> None:
    """Mirror legacy worker release status into the durable task_runs row."""
    try:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE task_runs
                SET status = $3,
                    result_summary = COALESCE($4, result_summary),
                    last_error = COALESCE($5, last_error),
                    completed_at = CASE
                        WHEN $3 IN ('completed', 'failed', 'cancelled') THEN NOW()
                        ELSE completed_at
                    END,
                    lease_owner = COALESCE(lease_owner, $2),
                    last_heartbeat_at = NOW(),
                    updated_at = NOW()
                WHERE task_id = $1
                  AND (lease_owner IS NULL OR lease_owner = $2 OR status IN ('queued', 'running'))
                """,
                task_id,
                worker_id,
                status,
                result,
                error,
            )
    except Exception as exc:
        logger.debug('Could not mirror release to task_runs for %s: %s', task_id, exc)
