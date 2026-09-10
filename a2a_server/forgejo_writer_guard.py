"""Serialize repository-changing tasks by PR, not by CI status label or SHA."""

# ruff: noqa: PLC0415, E501
import os

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
    readonly_chunk = (
        metadata.get('agent_type') == 'plan'
        and metadata.get('workflow_stage') == 'review_chunk'
        and 'review-readonly' in (metadata.get('required_capabilities') or [])
        and (
            (
                bool(os.getenv('FORGEJO_REVIEW_SAFE_WORKER', ''))
                and metadata.get('target_agent_name')
                == os.getenv('FORGEJO_REVIEW_SAFE_WORKER', '')
            )
            or (
                metadata.get('job_execution') is True
                and metadata.get('job_readonly') is True
            )
        )
    )
    if (
        not repo
        or not number
        or metadata.get('agent_type') == 'review'
        or readonly_chunk
    ):
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
                    AND NOT COALESCE((agent_type='plan' AND metadata->>'workflow_stage'='review_chunk'
                      AND metadata->'required_capabilities' @> '["review-readonly"]'::jsonb
                      AND (($4<>'' AND metadata->>'target_agent_name'=$4)
                        OR (metadata->>'job_execution'='true' AND metadata->>'job_readonly'='true'))),false)
                    AND ($3::text IS NULL OR metadata->>'forgejo_work_key' IS DISTINCT FROM $3)
                ORDER BY created_at LIMIT 1
            """,
                repo,
                str(number),
                work_key,
                os.getenv('FORGEJO_REVIEW_SAFE_WORKER', ''),
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
