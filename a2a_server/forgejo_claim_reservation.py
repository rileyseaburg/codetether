"""Durable cross-replica reservation for verified worker claims."""

from a2a_server import database as db


ACQUIRED = 'acquired'
OWNED = 'owned'
UNAVAILABLE = 'unavailable'


async def reserve(task_id: str, worker_id: str) -> str:
    """Atomically reserve a pending task or recognize an idempotent retry."""
    try:
        pool = await db.get_pool()
        if not pool:
            raise RuntimeError('Task claim storage is unavailable')
        async with pool.acquire() as connection:
            result = await connection.execute(
                "UPDATE tasks SET status = 'running', worker_id = $2, "
                'started_at = COALESCE(started_at, NOW()), updated_at = NOW() '
                "WHERE id = $1 AND status = 'pending' AND worker_id IS NULL",
                task_id,
                worker_id,
            )
            if 'UPDATE 1' in result:
                return ACQUIRED
            row = await connection.fetchrow(
                'SELECT status, worker_id FROM tasks WHERE id = $1', task_id
            )
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError('Task claim storage is unavailable') from error
    if row and row['status'] == 'running' and row['worker_id'] == worker_id:
        return OWNED
    return UNAVAILABLE
