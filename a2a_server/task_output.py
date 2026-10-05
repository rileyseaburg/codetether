"""Durable task output shared by polling and SSE.

Ownership comes from the task, not connected-worker presence or routing headers.
Legacy infrastructure credentials retain fleet authority during migration;
SPIFFE workers require a provisioned durable identity binding.
"""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from . import database, policy


@asynccontextmanager
async def connection():
    """Fail closed on storage/schema outages, preserving authorization errors."""
    try:
        pool = await database.get_pool()
        if pool is None:
            raise RuntimeError('Database pool unavailable')
        async with pool.acquire() as conn:
            yield conn
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail='Task output storage unavailable'
        ) from exc


async def _task(conn, task_id, *, lock=False):
    row = await conn.fetchrow(
        'SELECT id, tenant_id, worker_id, status FROM tasks WHERE id = $1'
        + (' FOR UPDATE' if lock else ''),
        task_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='Task not found')
    return dict(row)


async def _authorize_read(request, task):
    # Called only after verify_worker_or_user_auth. Never trust routing state.
    user = getattr(request.state, 'user', None)
    if user is None and getattr(request.state, 'spiffe', None) is not None:
        user = await policy._resolve_user(request)  # noqa: SLF001
        if not user or user.get('auth_source') != 'spiffe':
            raise HTTPException(status_code=403, detail='Identity unavailable')
    if user is None:
        return  # Authenticated legacy infrastructure / explicitly enabled dev.
    tenant_id = user.get('tenant_id')
    if tenant_id:
        if tenant_id != task['tenant_id']:
            raise HTTPException(status_code=404, detail='Task not found')
    elif 'admin' not in user.get('roles', []):
        raise HTTPException(status_code=403, detail='Task tenant authority required')
    await policy.enforce_policy(user=user, action='task:read', resource=task)


async def append_output(request: Request, task_id: str, chunk) -> dict:
    """Append under the task lock; never resurrect terminal tasks.

    Called only after verify_worker_auth. Platform user credentials cannot write.
    """
    async with connection() as conn:
        async with conn.transaction():
            task = await _task(conn, task_id, lock=True)
            if task['worker_id'] != chunk.worker_id:
                raise HTTPException(status_code=403, detail='Worker does not own task')
            identity = getattr(request.state, 'spiffe', None)
            if identity is not None:
                worker_identity = await conn.fetchval(
                    'SELECT spiffe_id FROM workers WHERE worker_id = $1',
                    chunk.worker_id,
                )
                if not worker_identity or worker_identity != identity.spiffe_id:
                    raise HTTPException(status_code=403, detail='Worker identity mismatch')
            if task['status'] not in ('running', 'working'):
                raise HTTPException(status_code=409, detail='Task is not running')
            cursor = await conn.fetchval(
                'SELECT COALESCE(MAX(cursor), 0) + 1 FROM task_output_chunks '
                'WHERE task_id = $1', task_id,
            )
            timestamp = chunk.timestamp or datetime.now(timezone.utc).isoformat()
            await conn.execute(
                'INSERT INTO task_output_chunks '
                '(task_id, cursor, worker_id, output, timestamp, event) '
                'VALUES ($1, $2, $3, $4, $5, $6::jsonb)',
                task_id, cursor, chunk.worker_id, chunk.output, timestamp,
                json.dumps(chunk.event) if chunk.event is not None else None,
            )
            await conn.execute(
                'UPDATE tasks SET updated_at = NOW() WHERE id = $1', task_id,
            )
    return {'cursor': cursor, 'timestamp': timestamp}


async def read_output(request: Request, task_id: str, since: int = 0) -> dict:
    """Return bounded replay with an exclusive cursor, not a buffer index."""
    if since < 0:
        raise HTTPException(status_code=422, detail='Cursor must be nonnegative')
    async with connection() as conn:
        async with conn.transaction(isolation='repeatable_read'):
            task = await _task(conn, task_id)
            await _authorize_read(request, task)
            rows = await conn.fetch(
                'SELECT cursor, output, timestamp, worker_id, event '
                'FROM task_output_chunks WHERE task_id = $1 AND cursor > $2 '
                'ORDER BY cursor LIMIT 1001', task_id, since,
            )
    outputs = []
    for row in rows[:1000]:
        output = dict(row)
        if isinstance(output['event'], str):
            output['event'] = json.loads(output['event'])
        outputs.append(output)
    cursor = outputs[-1]['cursor'] if outputs else since
    return {
        'task_id': task_id, 'outputs': outputs, 'total': cursor,
        'next_cursor': cursor, 'has_more': len(rows) > 1000,
        'status': task['status'],
    }