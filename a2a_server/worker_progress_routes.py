"""Worker progress, heartbeat, resume, and durable-claim routes."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from .worker_auth import verify_auth
from .worker_extended_claim import resolve as resolve_extended_claim_name
from .worker_task_mutation import authorize as authorize_worker_mutation

logger = logging.getLogger(__name__)

worker_progress_router = APIRouter()


class TaskHeartbeatRequest(BaseModel):
    """Heartbeat + progress checkpoint from a CI runner or ephemeral worker."""

    task_id: str
    worker_id: str
    progress_pct: Optional[float] = None
    status_message: Optional[str] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_seq: int = 1
    log_tail: Optional[str] = None
    runner_metadata: Optional[Dict[str, Any]] = None


class TaskProgressResponse(BaseModel):
    """Response for progress retrieval."""

    task_id: str
    run_id: Optional[str] = None
    status: Optional[str] = None
    progress_pct: Optional[float] = None
    status_message: Optional[str] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_seq: int = 0
    last_heartbeat_at: Optional[str] = None
    worker_id: Optional[str] = None
    runner_metadata: Optional[Dict[str, Any]] = None


class ExtendedHeartbeatRequest(BaseModel):
    """Extended heartbeat for 7-day persistent worker tasks."""

    task_id: str
    worker_id: str
    progress_pct: Optional[float] = None
    status_message: Optional[str] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_seq: Optional[int] = None
    log_tail: Optional[str] = None
    lease_extension_seconds: Optional[int] = None


class ExtendedHeartbeatResponse(BaseModel):
    """Response from extended heartbeat."""

    success: bool
    lease_expires_at: Optional[str] = None
    within_timeout: bool = True
    elapsed_seconds: int = 0
    resume_attempt: int = 0
    message: str = 'Heartbeat accepted'


class TaskResumeRequest(BaseModel):
    """Request to resume a task from checkpoint."""

    task_id: str
    worker_id: str


class TaskResumeResponse(BaseModel):
    """Response with checkpoint data for resumption."""

    success: bool
    run_id: Optional[str] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_seq: int = 0
    resume_attempt: int = 0
    task_timeout_seconds: int = 604800
    github_issue_url: Optional[str] = None
    elapsed_seconds: int = 0
    message: str = 'Task resumed from checkpoint'


class ExtendedClaimRequest(BaseModel):
    """Request model for extended task claim."""

    worker_id: str
    agent_name: Optional[str] = None
    capabilities: Optional[List[str]] = None
    models_supported: Optional[List[str]] = None


class ExtendedClaimResponse(BaseModel):
    """Response model for extended task claim."""

    run_id: Optional[str] = None
    task_id: Optional[str] = None
    priority: Optional[int] = None
    target_agent_name: Optional[str] = None
    model_ref: Optional[str] = None
    dispatch_mode: Optional[str] = None
    task_timeout_seconds: Optional[int] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_seq: Optional[int] = None
    resume_attempt: Optional[int] = None
    github_issue_url: Optional[str] = None


@worker_progress_router.post('/tasks/heartbeat')
async def post_task_heartbeat(
    request: Request,
    heartbeat: TaskHeartbeatRequest,
):
    """Persist CI runner progress and renew its short lease."""
    verify_auth(request)
    await authorize_worker_mutation(
        request, 'heartbeat-progress', heartbeat.task_id, heartbeat.worker_id
    )

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    progress_data: Dict[str, Any] = {}
    if heartbeat.progress_pct is not None:
        progress_data['progress_pct'] = heartbeat.progress_pct
    if heartbeat.status_message is not None:
        progress_data['status_message'] = heartbeat.status_message
    if heartbeat.checkpoint is not None:
        progress_data['checkpoint'] = heartbeat.checkpoint
    if heartbeat.runner_metadata is not None:
        progress_data['runner_metadata'] = heartbeat.runner_metadata
    progress_data['worker_id'] = heartbeat.worker_id
    progress_data['heartbeat_at'] = datetime.now(timezone.utc).isoformat()
    progress_json = json.dumps(progress_data)

    updated = False
    try:
        async with pool.acquire() as conn:
            updated = await conn.fetchval(
                'SELECT upsert_task_progress($1, $2, $3::jsonb, $4, $5, $6)',
                heartbeat.task_id,
                heartbeat.worker_id,
                progress_json,
                heartbeat.checkpoint_seq,
                None,
                heartbeat.log_tail,
            )
    except Exception:
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE task_runs SET
                        task_progress = $3::jsonb,
                        checkpoint_seq = $4,
                        last_heartbeat_at = NOW(),
                        updated_at = NOW(),
                        last_error = COALESCE($5, last_error)
                    WHERE task_id = $1
                      AND lease_owner = $2
                      AND status NOT IN ('completed', 'failed', 'cancelled')
                    """,
                    heartbeat.task_id,
                    heartbeat.worker_id,
                    progress_json,
                    heartbeat.checkpoint_seq,
                    heartbeat.log_tail,
                )
                updated = 'UPDATE 1' in result
        except Exception as e:
            logger.warning(
                f'Heartbeat update failed for task {heartbeat.task_id}: {e}'
            )

    if not updated:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Heartbeat rejected for task {heartbeat.task_id}. '
                'Causes: stale checkpoint_seq, wrong worker_id, or task completed.'
            ),
        )

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE task_runs SET
                    lease_expires_at = NOW() + INTERVAL '10 minutes'
                WHERE task_id = $1 AND lease_owner = $2
                  AND status NOT IN ('completed', 'failed', 'cancelled')
                """,
                heartbeat.task_id,
                heartbeat.worker_id,
            )
    except Exception as e:
        logger.debug(f'Lease renewal failed in heartbeat: {e}')

    logger.info(
        f'Heartbeat from {heartbeat.worker_id} for task {heartbeat.task_id} '
        f'(seq={heartbeat.checkpoint_seq}, pct={heartbeat.progress_pct})'
    )

    return {
        'success': True,
        'task_id': heartbeat.task_id,
        'checkpoint_seq': heartbeat.checkpoint_seq,
        'message': 'Heartbeat accepted',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@worker_progress_router.get('/tasks/{task_id}/progress')
async def get_task_progress(
    request: Request,
    task_id: str,
):
    """Get the latest progress checkpoint for a task."""
    verify_auth(request)

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, status, task_progress, checkpoint_seq,
                       last_heartbeat_at, lease_owner
                FROM task_runs
                WHERE task_id = $1
                ORDER BY created_at DESC LIMIT 1
                """,
                task_id,
            )
    except Exception as e:
        logger.debug(f'Progress query failed: {e}')
        row = None

    if not row:
        raise HTTPException(
            status_code=404, detail=f'No task run found for task {task_id}'
        )

    progress = row['task_progress']
    if isinstance(progress, str):
        try:
            progress = json.loads(progress)
        except (json.JSONDecodeError, TypeError):
            progress = {}
    if not progress:
        progress = {}

    return TaskProgressResponse(
        task_id=task_id,
        run_id=row['id'],
        status=row['status'],
        progress_pct=progress.get('progress_pct'),
        status_message=progress.get('status_message'),
        checkpoint=progress.get('checkpoint'),
        checkpoint_seq=row['checkpoint_seq'] or 0,
        last_heartbeat_at=row['last_heartbeat_at'].isoformat()
        if row['last_heartbeat_at']
        else None,
        worker_id=row['lease_owner'] or progress.get('worker_id'),
        runner_metadata=progress.get('runner_metadata'),
    )


@worker_progress_router.get('/tasks/silent')
async def list_silent_runs(
    request: Request,
    silence_seconds: int = Query(
        300, description='Seconds since last heartbeat to consider silent'
    ),
):
    """List running task runs whose heartbeat is older than the threshold."""
    verify_auth(request)

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM find_silent_task_runs($1)',
                silence_seconds,
            )
    except Exception as e:
        logger.debug(f'Silent runs query failed: {e}')
        raise HTTPException(
            status_code=500, detail='Failed to query silent runs'
        )

    return {
        'silent_runs': [
            {
                'run_id': r['run_id'],
                'task_id': r['task_id'],
                'last_heartbeat_at': r['last_heartbeat_at'].isoformat()
                if r['last_heartbeat_at']
                else None,
                'progress': r['task_progress'],
                'worker_id': r['lease_owner'],
            }
            for r in rows
        ],
        'count': len(rows),
        'silence_threshold_seconds': silence_seconds,
    }


@worker_progress_router.post('/tasks/heartbeat/extended')
async def post_extended_heartbeat(
    request: Request,
    heartbeat: ExtendedHeartbeatRequest,
):
    """Extended heartbeat for 7-day persistent worker tasks."""
    verify_auth(request)
    await authorize_worker_mutation(
        request, 'heartbeat-extended', heartbeat.task_id, heartbeat.worker_id
    )

    from .persistent_worker_pool import post_extended_heartbeat as _do_heartbeat

    try:
        result = await _do_heartbeat(
            task_id=heartbeat.task_id,
            worker_id=heartbeat.worker_id,
            progress_pct=heartbeat.progress_pct,
            status_message=heartbeat.status_message,
            checkpoint=heartbeat.checkpoint,
            checkpoint_seq=heartbeat.checkpoint_seq,
            log_tail=heartbeat.log_tail,
            lease_extension_seconds=heartbeat.lease_extension_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not result['success']:
        raise HTTPException(
            status_code=409,
            detail=result.get('message', 'Heartbeat rejected'),
        )

    logger.info(
        f'Extended heartbeat from {heartbeat.worker_id} for {heartbeat.task_id} '
        f'(pct={heartbeat.progress_pct}, within_timeout={result["within_timeout"]}, '
        f'elapsed={result["elapsed_seconds"]}s)'
    )

    return ExtendedHeartbeatResponse(**result)


@worker_progress_router.post('/tasks/claim/extended')
async def claim_extended_task_endpoint(
    request: Request,
    worker_id: Optional[str] = Query(None),
    x_worker_id: Optional[str] = Header(None, alias='X-Worker-ID'),
    x_agent_name: Optional[str] = Header(None, alias='X-Agent-Name'),
):
    """Claim the next available task including long-running task runs."""
    verify_auth(request)

    resolved_worker_id = worker_id or x_worker_id
    if not resolved_worker_id:
        raise HTTPException(
            status_code=400,
            detail='worker_id is required (query param or X-Worker-ID header)',
        )

    from .persistent_worker_pool import claim_extended_task as _do_claim

    agent_name = await resolve_extended_claim_name(
        resolved_worker_id, x_agent_name
    )
    result = await _do_claim(
        worker_id=resolved_worker_id,
        agent_name=agent_name,
    )

    if not result:
        return {'success': False, 'message': 'No tasks available'}

    try:
        from .worker_sse import get_worker_registry

        registry = get_worker_registry()
        await registry.claim_task(result['task_id'], resolved_worker_id)
    except Exception:
        pass

    return {
        'success': True,
        'run_id': result['run_id'],
        'task_id': result['task_id'],
        'priority': result.get('priority'),
        'dispatch_mode': result.get('dispatch_mode', 'polling'),
        'task_timeout_seconds': result.get('task_timeout_seconds', 600),
        'checkpoint': result.get('checkpoint'),
        'checkpoint_seq': result.get('checkpoint_seq', 0),
        'resume_attempt': result.get('resume_attempt', 0),
        'github_issue_url': result.get('github_issue_url'),
        'model_ref': result.get('model_ref'),
    }


@worker_progress_router.post('/tasks/resume')
async def resume_task_from_checkpoint(
    request: Request,
    resume: TaskResumeRequest,
):
    """Resume a task from its last checkpoint."""
    verify_auth(request)
    await authorize_worker_mutation(
        request, 'resume', resume.task_id, resume.worker_id
    )

    from . import database as db

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM resume_task_from_checkpoint($1, $2, $3)',
                resume.task_id,
                resume.worker_id,
                3600,
            )

        if not row:
            return TaskResumeResponse(
                success=False,
                message='No resumable task found',
            )

        checkpoint = row['checkpoint']
        if isinstance(checkpoint, str):
            checkpoint = json.loads(checkpoint)

        return TaskResumeResponse(
            success=True,
            run_id=row['run_id'],
            checkpoint=checkpoint,
            checkpoint_seq=row['checkpoint_seq'] or 0,
            resume_attempt=row['resume_attempt'] or 0,
            task_timeout_seconds=row['task_timeout_seconds'] or 604800,
            github_issue_url=row['github_issue_url'],
            elapsed_seconds=row['elapsed_seconds'] or 0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to resume task: {e}',
        )


@worker_progress_router.post('/tasks/claim-extended')
async def claim_extended_task_legacy_endpoint(
    request: Request,
    claim: ExtendedClaimRequest,
):
    """Claim the next available task for a persistent worker."""
    verify_auth(request)

    from .persistent_worker_pool import claim_extended_task

    agent_name = await resolve_extended_claim_name(
        claim.worker_id, claim.agent_name
    )
    result = await claim_extended_task(
        worker_id=claim.worker_id,
        agent_name=agent_name,
        capabilities=claim.capabilities,
        models_supported=claim.models_supported,
    )
    if not result:
        return ExtendedClaimResponse()
    return ExtendedClaimResponse(**result)


@worker_progress_router.post('/tasks/heartbeat-extended')
async def heartbeat_extended_endpoint(
    request: Request,
    heartbeat: ExtendedHeartbeatRequest,
):
    """Legacy extended heartbeat endpoint for persistent workers."""
    verify_auth(request)
    await authorize_worker_mutation(
        request, 'heartbeat-extended', heartbeat.task_id, heartbeat.worker_id
    )

    from .persistent_worker_pool import post_extended_heartbeat

    try:
        return await post_extended_heartbeat(
            task_id=heartbeat.task_id,
            worker_id=heartbeat.worker_id,
            progress_pct=heartbeat.progress_pct,
            status_message=heartbeat.status_message,
            checkpoint=heartbeat.checkpoint,
            checkpoint_seq=heartbeat.checkpoint_seq,
            log_tail=heartbeat.log_tail,
            lease_extension_seconds=heartbeat.lease_extension_seconds,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Extended heartbeat failed: {e}',
        )
