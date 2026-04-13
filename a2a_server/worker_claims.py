from dataclasses import dataclass
from typing import Optional

from . import database as db


@dataclass
class TaskRunClaimContext:
    run_id: str
    attempt_number: int
    attempt_id: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_identity_id: Optional[str] = None


def build_agent_identity_id(
    user_id: Optional[str], tenant_id: Optional[str]
) -> Optional[str]:
    if user_id:
        return f'user:{user_id}'
    if tenant_id:
        return f'tenant:{tenant_id}'
    return None


async def mark_task_run_running(
    task_id: str, worker_id: str
) -> Optional[TaskRunClaimContext]:
    pool = await db.get_pool()
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE task_runs
            SET status = 'running',
                lease_owner = $2,
                started_at = COALESCE(started_at, NOW()),
                updated_at = NOW(),
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM task_runs
                WHERE task_id = $1 AND status = 'queued'
                ORDER BY created_at DESC
                LIMIT 1
            )
            RETURNING id, user_id, tenant_id, attempts
            """,
            task_id,
            worker_id,
        )
    if not row:
        return None
    attempt_number = int(row['attempts'] or 1)
    return TaskRunClaimContext(
        run_id=row['id'],
        attempt_number=attempt_number,
        attempt_id=f"{row['id']}:attempt:{attempt_number}",
        user_id=row['user_id'],
        tenant_id=row['tenant_id'],
        agent_identity_id=build_agent_identity_id(
            row['user_id'], row['tenant_id']
        ),
    )
