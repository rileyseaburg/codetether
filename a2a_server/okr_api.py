"""
OKR API - Objectives and Key Results management.

Provides CRUD endpoints for OKRs, key results, and runs so the
dashboard can manage goal-driven execution workflows.

Defense-in-depth: Application-level WHERE tenant_id filtering +
PostgreSQL RLS via tenant_scope() context manager.

Endpoints:
    GET    /v1/okr           - List OKRs for tenant
    POST   /v1/okr           - Create a new OKR
    GET    /v1/okr/stats     - Aggregate stats
    GET    /v1/okr/{id}      - Get single OKR
    PUT    /v1/okr/{id}      - Update OKR (status, objective)
    DELETE /v1/okr/{id}      - Delete an OKR
    GET    /v1/okr/{id}/runs - List runs for an OKR
    POST   /v1/okr/{id}/runs - Start a new run
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .database import get_pool, tenant_scope, set_tenant_context, clear_tenant_context
from .keycloak_auth import require_auth, UserSession

logger = logging.getLogger(__name__)

okr_router = APIRouter(prefix='/v1/okr', tags=['okr'])


# ============================================================================
# Models
# ============================================================================


class KeyResultResponse(BaseModel):
    id: str
    description: str
    progress: int
    status: str


class OKRResponse(BaseModel):
    id: str
    objective: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    key_results: List[KeyResultResponse] = []
    run_id: Optional[str] = None


class OKRCreateRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=2000)


class OKRUpdateRequest(BaseModel):
    objective: Optional[str] = None
    status: Optional[str] = None


class OKRStatsResponse(BaseModel):
    total: int
    by_status: dict
    completion_rate: Optional[float] = None


class OKRRunResponse(BaseModel):
    id: str
    okr_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Helpers
# ============================================================================

VALID_OKR_STATUSES = {'draft', 'approved', 'running', 'completed', 'denied'}
VALID_KR_STATUSES = {'not-started', 'in-progress', 'completed', 'blocked'}
VALID_RUN_STATUSES = {'pending', 'running', 'completed', 'failed'}


def _ts(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _get_tenant(user: UserSession) -> str:
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')
    return tenant_id


async def _load_key_results(conn, okr_id) -> List[KeyResultResponse]:
    rows = await conn.fetch(
        'SELECT id, description, progress, status FROM okr_key_results WHERE okr_id = $1 ORDER BY created_at',
        okr_id,
    )
    return [
        KeyResultResponse(
            id=str(r['id']),
            description=r['description'],
            progress=r['progress'],
            status=r['status'],
        )
        for r in rows
    ]


async def _okr_to_response(conn, row) -> OKRResponse:
    okr_id = str(row['id'])
    key_results = await _load_key_results(conn, row['id'])

    # Get latest run id
    run_row = await conn.fetchrow(
        'SELECT id FROM okr_runs WHERE okr_id = $1 ORDER BY created_at DESC LIMIT 1',
        row['id'],
    )

    return OKRResponse(
        id=okr_id,
        objective=row['objective'],
        status=row['status'],
        created_at=_ts(row['created_at']),
        updated_at=_ts(row['updated_at']),
        key_results=key_results,
        run_id=str(run_row['id']) if run_row else None,
    )


# ============================================================================
# Endpoints
# ============================================================================


@okr_router.get('', response_model=List[OKRResponse])
async def list_okrs(
    status: Optional[str] = Query(None, description='Filter by status'),
    user: UserSession = Depends(require_auth),
):
    """List all OKRs for the current tenant."""
    tenant_id = _get_tenant(user)

    async with tenant_scope(tenant_id) as conn:
        if status:
            if status not in VALID_OKR_STATUSES:
                raise HTTPException(status_code=400, detail=f'Invalid status: {status}')
            rows = await conn.fetch(
                'SELECT * FROM okrs WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC',
                tenant_id, status,
            )
        else:
            rows = await conn.fetch(
                'SELECT * FROM okrs WHERE tenant_id = $1 ORDER BY created_at DESC',
                tenant_id,
            )

        return [await _okr_to_response(conn, r) for r in rows]


@okr_router.post('', response_model=OKRResponse, status_code=201)
async def create_okr(
    request: OKRCreateRequest,
    user: UserSession = Depends(require_auth),
):
    """Create a new OKR."""
    tenant_id = _get_tenant(user)
    user_id = getattr(user, 'user_id', None) or getattr(user, 'sub', None)

    async with tenant_scope(tenant_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO okrs (tenant_id, user_id, objective, status)
            VALUES ($1, $2, $3, 'draft')
            RETURNING *
            """,
            tenant_id, str(user_id) if user_id else None, request.objective,
        )
        return await _okr_to_response(conn, row)


@okr_router.get('/stats', response_model=OKRStatsResponse)
async def get_okr_stats(
    user: UserSession = Depends(require_auth),
):
    """Get aggregate OKR statistics for the tenant."""
    tenant_id = _get_tenant(user)

    async with tenant_scope(tenant_id) as conn:
        rows = await conn.fetch(
            'SELECT status, COUNT(*) as cnt FROM okrs WHERE tenant_id = $1 GROUP BY status',
            tenant_id,
        )
        total = sum(r['cnt'] for r in rows)
        by_status = {r['status']: r['cnt'] for r in rows}
        completed = by_status.get('completed', 0)
        completion_rate = completed / total if total > 0 else None

        return OKRStatsResponse(
            total=total,
            by_status=by_status,
            completion_rate=completion_rate,
        )


@okr_router.get('/{okr_id}', response_model=OKRResponse)
async def get_okr(
    okr_id: str,
    user: UserSession = Depends(require_auth),
):
    """Get a single OKR by ID."""
    tenant_id = _get_tenant(user)

    try:
        okr_uuid = uuid.UUID(okr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid OKR ID')

    async with tenant_scope(tenant_id) as conn:
        row = await conn.fetchrow(
            'SELECT * FROM okrs WHERE id = $1 AND tenant_id = $2',
            okr_uuid, tenant_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail='OKR not found')
        return await _okr_to_response(conn, row)


@okr_router.put('/{okr_id}', response_model=OKRResponse)
async def update_okr(
    okr_id: str,
    request: OKRUpdateRequest,
    user: UserSession = Depends(require_auth),
):
    """Update an OKR (status or objective)."""
    tenant_id = _get_tenant(user)

    try:
        okr_uuid = uuid.UUID(okr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid OKR ID')

    if request.status and request.status not in VALID_OKR_STATUSES:
        raise HTTPException(status_code=400, detail=f'Invalid status: {request.status}')

    async with tenant_scope(tenant_id) as conn:
        row = await conn.fetchrow(
            'SELECT * FROM okrs WHERE id = $1 AND tenant_id = $2',
            okr_uuid, tenant_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail='OKR not found')

        updates = []
        params = []
        idx = 1

        if request.objective is not None:
            updates.append(f'objective = ${idx}')
            params.append(request.objective)
            idx += 1
        if request.status is not None:
            updates.append(f'status = ${idx}')
            params.append(request.status)
            idx += 1

        if not updates:
            return await _okr_to_response(conn, row)

        updates.append(f'updated_at = ${idx}')
        params.append(datetime.now(timezone.utc))
        idx += 1

        params.append(okr_uuid)
        params.append(tenant_id)

        query = f"""
            UPDATE okrs SET {', '.join(updates)}
            WHERE id = ${idx} AND tenant_id = ${idx + 1}
            RETURNING *
        """
        updated = await conn.fetchrow(query, *params)
        return await _okr_to_response(conn, updated)


@okr_router.delete('/{okr_id}')
async def delete_okr(
    okr_id: str,
    user: UserSession = Depends(require_auth),
):
    """Delete an OKR and its key results and runs."""
    tenant_id = _get_tenant(user)

    try:
        okr_uuid = uuid.UUID(okr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid OKR ID')

    async with tenant_scope(tenant_id) as conn:
        result = await conn.execute(
            'DELETE FROM okrs WHERE id = $1 AND tenant_id = $2',
            okr_uuid, tenant_id,
        )
        if result == 'DELETE 0':
            raise HTTPException(status_code=404, detail='OKR not found')
        return {'status': 'deleted'}


@okr_router.get('/{okr_id}/runs', response_model=List[OKRRunResponse])
async def list_okr_runs(
    okr_id: str,
    user: UserSession = Depends(require_auth),
):
    """List runs for a specific OKR."""
    tenant_id = _get_tenant(user)

    try:
        okr_uuid = uuid.UUID(okr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid OKR ID')

    async with tenant_scope(tenant_id) as conn:
        # Verify OKR belongs to tenant (app-level check + RLS)
        exists = await conn.fetchval(
            'SELECT 1 FROM okrs WHERE id = $1 AND tenant_id = $2',
            okr_uuid, tenant_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail='OKR not found')

        rows = await conn.fetch(
            'SELECT * FROM okr_runs WHERE okr_id = $1 ORDER BY created_at DESC',
            okr_uuid,
        )
        return [
            OKRRunResponse(
                id=str(r['id']),
                okr_id=str(r['okr_id']),
                status=r['status'],
                started_at=_ts(r['started_at']),
                completed_at=_ts(r['completed_at']),
                error=r['error'],
            )
            for r in rows
        ]


@okr_router.post('/{okr_id}/runs', response_model=OKRRunResponse, status_code=201)
async def create_okr_run(
    okr_id: str,
    user: UserSession = Depends(require_auth),
):
    """Start a new run for an OKR."""
    tenant_id = _get_tenant(user)

    try:
        okr_uuid = uuid.UUID(okr_id)
    except ValueError:
        raise HTTPException(status_code=400, detail='Invalid OKR ID')

    async with tenant_scope(tenant_id) as conn:
        okr = await conn.fetchrow(
            'SELECT * FROM okrs WHERE id = $1 AND tenant_id = $2',
            okr_uuid, tenant_id,
        )
        if not okr:
            raise HTTPException(status_code=404, detail='OKR not found')

        if okr['status'] not in ('approved', 'running'):
            raise HTTPException(
                status_code=400,
                detail=f'OKR must be approved before starting a run (current: {okr["status"]})',
            )

        now = datetime.now(timezone.utc)

        # Create the run
        run_row = await conn.fetchrow(
            """
            INSERT INTO okr_runs (okr_id, status, started_at)
            VALUES ($1, 'running', $2)
            RETURNING *
            """,
            okr_uuid, now,
        )

        # Update OKR status to running
        await conn.execute(
            "UPDATE okrs SET status = 'running', updated_at = $2 WHERE id = $1",
            okr_uuid, now,
        )

        return OKRRunResponse(
            id=str(run_row['id']),
            okr_id=str(run_row['okr_id']),
            status=run_row['status'],
            started_at=_ts(run_row['started_at']),
            completed_at=_ts(run_row['completed_at']),
            error=run_row['error'],
        )
