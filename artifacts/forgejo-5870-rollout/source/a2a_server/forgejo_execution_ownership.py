"""Serialize Temporal handoffs with intake and reject superseded native retries."""
# ruff: noqa: PLC0415, E501

from contextlib import asynccontextmanager

from fastapi import HTTPException


@asynccontextmanager
async def execution_ownership(
    repository, issue_number, native_task_id, api_base, attempt=1
):
    """Hold issue ownership until a stage's task and run are durable.

    Only explicit native retries are superseded by newer actionable receipts.
    Ordinary stages of the current attempt finish before queued followups run.
    """
    from a2a_server.forgejo_inbox import ensure_schema, pool

    db = await pool()
    async with db.acquire() as conn:
        await ensure_schema(conn)
        lock_key = (
            f'forgejo-inbox:{api_base.rstrip("/")}:{repository}:{issue_number}'
        )
        owned = await conn.fetchval(
            'SELECT pg_try_advisory_lock(hashtextextended($1, 0))', lock_key
        )
        if not owned:
            raise HTTPException(409, 'Forgejo issue handoff in progress')
        try:
            if attempt > 1:
                own = await conn.fetchrow(
                    """
                    SELECT received_at, delivery_id FROM forgejo_webhook_inbox
                    WHERE api_base = $1 AND native_task_id = $2
                    ORDER BY received_at DESC, delivery_id DESC LIMIT 1
                """,
                    api_base.rstrip('/'),
                    native_task_id,
                )
                newer = await conn.fetchval(
                    """
                    SELECT delivery_id FROM forgejo_webhook_inbox
                    WHERE api_base = $1 AND context->>'repo' = $2
                        AND context->>'number' = $3
                        AND context->>'actionable' = 'true'
                        AND native_task_id IS DISTINCT FROM $4
                        AND ($5::timestamptz IS NULL OR
                             (received_at, delivery_id) > ($5, $6))
                    LIMIT 1
                """,
                    api_base.rstrip('/'),
                    repository,
                    str(issue_number),
                    native_task_id,
                    own['received_at'] if own else None,
                    own['delivery_id'] if own else '',
                )
                if newer:
                    raise HTTPException(
                        409, 'Forgejo retry superseded by newer request'
                    )
            yield
        finally:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1, 0))', lock_key
            )
