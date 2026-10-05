"""Serialize repository-changing tasks by PR, not by CI status label or SHA."""
# ruff: noqa: PLC0415, E501

from contextlib import asynccontextmanager

from fastapi import HTTPException

from a2a_server.forgejo_automation_policy import pr_is_paused


@asynccontextmanager
async def single_writer(metadata):
    """Keep one active writer across status contexts and advancing PR heads.

    The advisory lock closes the check/create race across API replicas. Active
    task rows retain ownership after the short creation lock is released.
    Duplicate delivery keys may reuse their existing task without new work.
    """
    if metadata.get('source') != 'forgejo-webhook':
        yield
        return
    repo = str(metadata.get('repo') or '')
    number = int(metadata.get('pr_number') or metadata.get('issue_number') or 0)
    if pr_is_paused(repo, number):
        raise HTTPException(
            409, 'Forgejo automation is paused for this request'
        )
    if not repo or not number or metadata.get('agent_type') == 'review':
        yield
        return
    from a2a_server import database

    pool = await database.get_pool()
    if pool is None:
        raise HTTPException(503, 'PR writer ownership storage unavailable')
    key = f'forgejo-pr-writer:{repo}:{number}'
    work_key = metadata.get('forgejo_work_key')
    async with pool.acquire() as conn:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1,0))', key
        )
        try:
            active = await conn.fetchrow(
                """
                SELECT id, metadata->>'forgejo_work_key' AS work_key
                FROM tasks
                WHERE metadata->>'source' = 'forgejo-webhook'
                    AND metadata->>'repo' = $1
                    AND (metadata->>'pr_number' = $2 OR metadata->>'issue_number' = $2)
                    AND status IN ('pending','queued','assigned','running','in_progress','working')
                    AND COALESCE(agent_type, '') != 'review'
                    AND ($3::text IS NULL OR metadata->>'forgejo_work_key' IS DISTINCT FROM $3)
                ORDER BY created_at LIMIT 1
            """,
                repo,
                str(number),
                work_key,
            )
            if active:
                raise HTTPException(
                    409, 'Another writer already owns this Forgejo request'
                )
            yield
        finally:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1,0))', key
            )
