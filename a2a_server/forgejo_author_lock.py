"""Cross-replica serialization for one Forgejo author work item."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from a2a_server import database as db
from a2a_server.forgejo_author_task import task_identity


@asynccontextmanager
async def serialized(metadata: Mapping[str, object]) -> AsyncIterator[None]:
    """Hold a PostgreSQL advisory lock for one immutable review work key."""
    key, _task_id = task_identity(metadata)
    pool = await db.get_pool()
    if pool is None:
        raise RuntimeError('durable task storage is unavailable')
    conn = await pool.acquire()
    try:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1, 0))', key
        )
        yield
    finally:
        try:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1, 0))', key
            )
        finally:
            await pool.release(conn)
