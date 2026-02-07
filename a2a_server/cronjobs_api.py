"""
Cronjobs API - REST endpoints for managing scheduled cronjobs.

Provides CRUD operations for cronjobs and execution history.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import database as db
from .user_auth import require_user
from .cron_dispatch import dispatch_cron_task
from .knative_cron import (
    KnativeCronError,
    delete_cronjob_resource,
    get_cron_driver,
    is_knative_cron_available,
    is_knative_cron_requested,
    reconcile_cronjob_resource,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/cronjobs', tags=['cronjobs'])


# ============================================================================
# Models
# ============================================================================


class CronjobBase(BaseModel):
    """Base cronjob model."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: str = Field(..., min_length=1, max_length=100)
    task_template: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = Field(default='UTC', max_length=50)
    enabled: bool = True

    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        """Validate cron expression format."""
        try:
            from croniter import croniter

            croniter(v)
        except Exception as e:
            raise ValueError(f'Invalid cron expression: {e}')
        return v


class CronjobCreate(CronjobBase):
    """Model for creating a cronjob."""

    pass


class CronjobUpdate(BaseModel):
    """Model for updating a cronjob."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = Field(None, min_length=1, max_length=100)
    task_template: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = Field(None, max_length=50)
    enabled: Optional[bool] = None

    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: Optional[str]) -> Optional[str]:
        """Validate cron expression format."""
        if v is None:
            return v
        try:
            from croniter import croniter

            croniter(v)
        except Exception as e:
            raise ValueError(f'Invalid cron expression: {e}')
        return v


class CronjobResponse(CronjobBase):
    """Model for cronjob response."""

    id: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    execution_backend: str = 'app'
    scheduler_namespace: Optional[str] = None
    scheduler_resource_name: Optional[str] = None
    scheduler_last_synced_at: Optional[datetime] = None
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    run_count: int
    error_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CronjobRunResponse(BaseModel):
    """Model for cronjob run response."""

    id: str
    cronjob_id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    output: Optional[str]
    error_message: Optional[str]
    task_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CronjobListResponse(BaseModel):
    """Model for list response."""

    items: List[CronjobResponse]
    total: int
    page: int
    page_size: int


class CronjobRunListResponse(BaseModel):
    """Model for run list response."""

    items: List[CronjobRunResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# Helper Functions
# ============================================================================


async def calculate_next_run(
    cron_expression: str, timezone: str = 'UTC'
) -> Optional[datetime]:
    """Calculate next run time for a cron expression."""
    try:
        from croniter import croniter
        import pytz

        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        itr = croniter(cron_expression, now)
        return itr.get_next(datetime)
    except Exception as e:
        logger.error(f'Failed to calculate next run: {e}')
        return None


def _active_cron_driver(*, strict: bool) -> str:
    """Resolve active cron execution backend."""
    driver = get_cron_driver()
    if driver == 'disabled' and strict:
        raise HTTPException(
            status_code=503, detail='Cron scheduler is disabled'
        )
    if driver == 'knative' and strict:
        if not is_knative_cron_requested() or not is_knative_cron_available():
            raise HTTPException(
                status_code=503,
                detail='Knative cron driver requested but unavailable',
            )
    if driver in ('disabled', 'knative'):
        return driver
    return 'app'


def _with_runtime_metadata(
    row: Dict[str, Any],
    *,
    driver: str,
    scheduler_namespace: Optional[str] = None,
    scheduler_resource_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach runtime scheduler metadata to a cronjob row dict."""
    payload = dict(row)
    payload['execution_backend'] = driver
    if scheduler_namespace:
        payload['scheduler_namespace'] = scheduler_namespace
    if scheduler_resource_name:
        payload['scheduler_resource_name'] = scheduler_resource_name
    if scheduler_namespace or scheduler_resource_name:
        payload['scheduler_last_synced_at'] = datetime.utcnow()
    return payload


async def _execute_cronjob_run(
    conn,
    job: Dict[str, Any],
    *,
    trigger_mode: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a cronjob once and persist run metadata.

    Shared by manual and internal scheduler-triggered execution paths.
    """
    run_id = str(uuid.uuid4())
    resolved_tenant_id = tenant_id if tenant_id is not None else job.get('tenant_id')
    resolved_user_id = user_id if user_id is not None else job.get('user_id')

    await conn.execute(
        """
        INSERT INTO cronjob_runs (id, cronjob_id, tenant_id, status, started_at)
        VALUES ($1, $2, $3, 'running', NOW())
        """,
        run_id,
        job['id'],
        resolved_tenant_id,
    )

    try:
        task_id, routing = await dispatch_cron_task(
            job_id=job['id'],
            run_id=run_id,
            job_name=job['name'],
            task_template=job.get('task_template') or {},
            tenant_id=resolved_tenant_id,
            user_id=resolved_user_id,
            trigger_mode=trigger_mode,
        )

        next_run = await calculate_next_run(
            job.get('cron_expression') or '* * * * *',
            job.get('timezone') or 'UTC',
        )

        await conn.execute(
            """
            UPDATE cronjobs
            SET last_run_at = NOW(),
                next_run_at = $2,
                run_count = run_count + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            job['id'],
            next_run,
        )

        await conn.execute(
            """
            UPDATE cronjob_runs
            SET status = 'completed',
                completed_at = NOW(),
                duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000,
                task_id = $2
            WHERE id = $1
            """,
            run_id,
            task_id,
        )

        return {
            'run_id': run_id,
            'task_id': task_id,
            'routing': routing,
            'next_run_at': next_run.isoformat() if next_run else None,
        }

    except Exception as e:
        await conn.execute(
            """
            UPDATE cronjob_runs
            SET status = 'failed',
                completed_at = NOW(),
                duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000,
                error_message = $2
            WHERE id = $1
            """,
            run_id,
            str(e),
        )
        await conn.execute(
            """
            UPDATE cronjobs
            SET error_count = error_count + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            job['id'],
        )
        raise


# ============================================================================
# API Endpoints
# ============================================================================


@router.post('', response_model=CronjobResponse)
async def create_cronjob(
    job: CronjobCreate,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Create a new cronjob."""
    driver = _active_cron_driver(strict=True)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    # Calculate next run time
    next_run = await calculate_next_run(job.cron_expression, job.timezone)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cronjobs (
                tenant_id, user_id, name, description, cron_expression,
                task_template, timezone, enabled, next_run_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            current_user.get('tenant_id'),
            current_user.get('id'),
            job.name,
            job.description,
            job.cron_expression,
            job.task_template,
            job.timezone,
            job.enabled,
            next_run,
        )

        if not row:
            raise HTTPException(
                status_code=500, detail='Failed to create cronjob'
            )
        row_dict = dict(row)
        sync_namespace: Optional[str] = None
        sync_name: Optional[str] = None

        if driver == 'knative':
            try:
                reconcile_result = await reconcile_cronjob_resource(
                    job_id=row_dict['id'],
                    tenant_id=row_dict.get('tenant_id'),
                    cron_expression=row_dict['cron_expression'],
                    timezone=row_dict.get('timezone'),
                    enabled=bool(row_dict.get('enabled', True)),
                )
                sync_namespace = reconcile_result.namespace
                sync_name = reconcile_result.resource_name
            except KnativeCronError as e:
                await conn.execute('DELETE FROM cronjobs WHERE id = $1', row_dict['id'])
                raise HTTPException(
                    status_code=500,
                    detail=f'Failed to provision Knative CronJob: {e}',
                ) from e

        return CronjobResponse(
            **_with_runtime_metadata(
                row_dict,
                driver=driver,
                scheduler_namespace=sync_namespace,
                scheduler_resource_name=sync_name,
            )
        )


@router.get('', response_model=CronjobListResponse)
async def list_cronjobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    enabled_only: bool = Query(False),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """List cronjobs with pagination."""
    driver = _active_cron_driver(strict=False)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        # Build query with filters
        where_clause = 'WHERE tenant_id = $1'
        params = [current_user.get('tenant_id')]

        if enabled_only:
            where_clause += ' AND enabled = true'

        # Get total count
        count_row = await conn.fetchrow(
            f'SELECT COUNT(*) FROM cronjobs {where_clause}',
            *params,
        )
        total = count_row['count'] if count_row else 0

        # Get items
        rows = await conn.fetch(
            f"""
            SELECT * FROM cronjobs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params,
            page_size,
            offset,
        )

        items = [
            CronjobResponse(**_with_runtime_metadata(dict(row), driver=driver))
            for row in rows
        ]

        return CronjobListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get('/{job_id}', response_model=CronjobResponse)
async def get_cronjob(
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Get a single cronjob by ID."""
    driver = _active_cron_driver(strict=False)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM cronjobs WHERE id = $1 AND tenant_id = $2',
            job_id,
            current_user.get('tenant_id'),
        )

        if not row:
            raise HTTPException(status_code=404, detail='Cronjob not found')

        return CronjobResponse(
            **_with_runtime_metadata(dict(row), driver=driver)
        )


@router.put('/{job_id}', response_model=CronjobResponse)
async def update_cronjob(
    job_id: str,
    job_update: CronjobUpdate,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Update a cronjob."""
    driver = _active_cron_driver(strict=True)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    # Build update query dynamically
    updates = []
    params = []
    param_idx = 1

    if job_update.name is not None:
        updates.append(f'name = ${param_idx}')
        params.append(job_update.name)
        param_idx += 1

    if job_update.description is not None:
        updates.append(f'description = ${param_idx}')
        params.append(job_update.description)
        param_idx += 1

    if job_update.cron_expression is not None:
        updates.append(f'cron_expression = ${param_idx}')
        params.append(job_update.cron_expression)
        param_idx += 1

    if job_update.task_template is not None:
        updates.append(f'task_template = ${param_idx}')
        params.append(job_update.task_template)
        param_idx += 1

    if job_update.timezone is not None:
        updates.append(f'timezone = ${param_idx}')
        params.append(job_update.timezone)
        param_idx += 1

    if job_update.enabled is not None:
        updates.append(f'enabled = ${param_idx}')
        params.append(job_update.enabled)
        param_idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail='No fields to update')

    # Add tenant_id check
    params.append(job_id)
    params.append(current_user.get('tenant_id'))

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Recalculate next_run if cron expression changed
            if job_update.cron_expression:
                row = await conn.fetchrow(
                    'SELECT timezone FROM cronjobs WHERE id = $1',
                    job_id,
                )
                if row:
                    next_run = await calculate_next_run(
                        job_update.cron_expression,
                        job_update.timezone or row['timezone'],
                    )
                    updates.append(f'next_run_at = ${param_idx}')
                    params.insert(
                        -2, next_run
                    )  # Insert before job_id and tenant_id
                    param_idx += 1

            row = await conn.fetchrow(
                f"""
                UPDATE cronjobs
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE id = ${param_idx} AND tenant_id = ${param_idx + 1}
                RETURNING *
                """,
                *params,
            )

            if not row:
                raise HTTPException(status_code=404, detail='Cronjob not found')

            row_dict = dict(row)
            sync_namespace: Optional[str] = None
            sync_name: Optional[str] = None
            if driver == 'knative':
                reconcile_result = await reconcile_cronjob_resource(
                    job_id=row_dict['id'],
                    tenant_id=row_dict.get('tenant_id'),
                    cron_expression=row_dict['cron_expression'],
                    timezone=row_dict.get('timezone'),
                    enabled=bool(row_dict.get('enabled', True)),
                )
                sync_namespace = reconcile_result.namespace
                sync_name = reconcile_result.resource_name

            return CronjobResponse(
                **_with_runtime_metadata(
                    row_dict,
                    driver=driver,
                    scheduler_namespace=sync_namespace,
                    scheduler_resource_name=sync_name,
                )
            )


@router.delete('/{job_id}')
async def delete_cronjob(
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Delete a cronjob."""
    driver = _active_cron_driver(strict=True)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                'SELECT * FROM cronjobs WHERE id = $1 AND tenant_id = $2',
                job_id,
                current_user.get('tenant_id'),
            )
            if not row:
                raise HTTPException(status_code=404, detail='Cronjob not found')

            row_dict = dict(row)
            if driver == 'knative':
                await delete_cronjob_resource(
                    job_id=row_dict['id'],
                    tenant_id=row_dict.get('tenant_id'),
                )

            await conn.execute(
                'DELETE FROM cronjobs WHERE id = $1 AND tenant_id = $2',
                job_id,
                current_user.get('tenant_id'),
            )

            return {'success': True, 'message': 'Cronjob deleted'}


@router.post('/{job_id}/toggle', response_model=CronjobResponse)
async def toggle_cronjob(
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Toggle enabled status of a cronjob."""
    driver = _active_cron_driver(strict=True)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE cronjobs
                SET enabled = NOT enabled, updated_at = NOW()
                WHERE id = $1 AND tenant_id = $2
                RETURNING *
                """,
                job_id,
                current_user.get('tenant_id'),
            )

            if not row:
                raise HTTPException(status_code=404, detail='Cronjob not found')

            row_dict = dict(row)
            sync_namespace: Optional[str] = None
            sync_name: Optional[str] = None
            if driver == 'knative':
                reconcile_result = await reconcile_cronjob_resource(
                    job_id=row_dict['id'],
                    tenant_id=row_dict.get('tenant_id'),
                    cron_expression=row_dict['cron_expression'],
                    timezone=row_dict.get('timezone'),
                    enabled=bool(row_dict.get('enabled', True)),
                )
                sync_namespace = reconcile_result.namespace
                sync_name = reconcile_result.resource_name

            return CronjobResponse(
                **_with_runtime_metadata(
                    row_dict,
                    driver=driver,
                    scheduler_namespace=sync_namespace,
                    scheduler_resource_name=sync_name,
                )
            )


@router.post('/{job_id}/trigger')
async def trigger_cronjob(
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Manually trigger a cronjob to run immediately."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    async with pool.acquire() as conn:
        # Get job details
        job = await conn.fetchrow(
            'SELECT * FROM cronjobs WHERE id = $1 AND tenant_id = $2',
            job_id,
            current_user.get('tenant_id'),
        )

        if not job:
            raise HTTPException(status_code=404, detail='Cronjob not found')

        try:
            result = await _execute_cronjob_run(
                conn,
                dict(job),
                trigger_mode='manual',
                tenant_id=current_user.get('tenant_id'),
                user_id=current_user.get('id'),
            )

            return {
                'success': True,
                'message': 'Cronjob triggered successfully',
                'task_id': result['task_id'],
                'run_id': result['run_id'],
                'routing': result['routing'],
                'next_run_at': result['next_run_at'],
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f'Failed to trigger cronjob: {e}'
            )


@router.post('/internal/{job_id}/trigger')
async def trigger_cronjob_internal(
    job_id: str,
    signature: Optional[str] = Header(None, alias='X-Cron-Signature'),
):
    """
    Internal scheduler endpoint for Kubernetes CronJobs.

    Secured by a shared token via `CRON_INTERNAL_TOKEN`.
    """
    expected_signature = os.environ.get('CRON_INTERNAL_TOKEN', '').strip()
    if not expected_signature:
        raise HTTPException(
            status_code=503,
            detail='CRON_INTERNAL_TOKEN is not configured',
        )
    if signature != expected_signature:
        raise HTTPException(status_code=401, detail='Invalid scheduler token')

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            'SELECT * FROM cronjobs WHERE id = $1',
            job_id,
        )
        if not job:
            raise HTTPException(status_code=404, detail='Cronjob not found')
        job_dict = dict(job)
        if not job_dict.get('enabled', True):
            raise HTTPException(status_code=409, detail='Cronjob is disabled')

        try:
            result = await _execute_cronjob_run(
                conn,
                job_dict,
                trigger_mode='scheduled',
                tenant_id=job_dict.get('tenant_id'),
                user_id=job_dict.get('user_id'),
            )
            return {
                'success': True,
                'job_id': job_id,
                'run_id': result['run_id'],
                'task_id': result['task_id'],
                'next_run_at': result['next_run_at'],
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f'Failed to run scheduled cronjob: {e}',
            ) from e


@router.get('/{job_id}/runs', response_model=CronjobRunListResponse)
async def get_cronjob_runs(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Get execution history for a cronjob."""
    _active_cron_driver(strict=False)
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database not available')

    offset = (page - 1) * page_size

    async with pool.acquire() as conn:
        # Verify job exists and belongs to tenant
        job = await conn.fetchrow(
            'SELECT id FROM cronjobs WHERE id = $1 AND tenant_id = $2',
            job_id,
            current_user.get('tenant_id'),
        )

        if not job:
            raise HTTPException(status_code=404, detail='Cronjob not found')

        # Get total count
        count_row = await conn.fetchrow(
            'SELECT COUNT(*) FROM cronjob_runs WHERE cronjob_id = $1',
            job_id,
        )
        total = count_row['count'] if count_row else 0

        # Get runs
        rows = await conn.fetch(
            """
            SELECT * FROM cronjob_runs
            WHERE cronjob_id = $1
            ORDER BY started_at DESC NULLS LAST
            LIMIT $2 OFFSET $3
            """,
            job_id,
            page_size,
            offset,
        )

        items = [CronjobRunResponse(**dict(row)) for row in rows]

        return CronjobRunListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.post('/validate-cron')
async def validate_cron_expression(
    expression: str,
    timezone: str = 'UTC',
):
    """Validate a cron expression and return next 5 execution times."""
    try:
        from croniter import croniter
        import pytz

        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        itr = croniter(expression, now)
        next_runs = [itr.get_next(datetime) for _ in range(5)]

        return {
            'valid': True,
            'next_runs': [run.isoformat() for run in next_runs],
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
        }
