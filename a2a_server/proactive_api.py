"""
Proactive API - REST endpoints for managing proactive rules, health checks,
perpetual loops, and the unified audit trail.

Provides CRUD operations and status endpoints for the proactive agent layer.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import database as db

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/proactive', tags=['proactive'])


# ============================================================================
# Models — Rules
# ============================================================================


class RuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ''
    trigger_type: str = Field(..., pattern='^(event|cron|threshold)$')
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    action: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = Field(default=300, ge=0)


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=0)


class RuleResponse(RuleBase):
    id: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    next_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Models — Health Checks
# ============================================================================


class HealthCheckBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ''
    check_type: str = Field(..., pattern='^(http|db_query|metric|task_queue)$')
    check_config: Dict[str, Any] = Field(default_factory=dict)
    interval_seconds: int = Field(default=300, ge=10)
    enabled: bool = True


class HealthCheckCreate(HealthCheckBase):
    pass


class HealthCheckUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    check_config: Optional[Dict[str, Any]] = None
    interval_seconds: Optional[int] = Field(None, ge=10)
    enabled: Optional[bool] = None


class HealthCheckResponse(HealthCheckBase):
    id: str
    tenant_id: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    last_status: str = 'unknown'
    last_result: Dict[str, Any] = Field(default_factory=dict)
    consecutive_failures: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# Rules CRUD
# ============================================================================


@router.post('/rules', response_model=RuleResponse, status_code=201)
async def create_rule(body: RuleCreate):
    """Create a new proactive rule."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    rule_id = str(uuid.uuid4())
    next_run_at = None

    # Calculate initial next_run_at for cron rules
    if body.trigger_type == 'cron':
        cron_expr = body.trigger_config.get('cron_expression', '*/5 * * * *')
        tz = body.trigger_config.get('timezone', 'UTC')
        try:
            from croniter import croniter
            import pytz

            tz_obj = pytz.timezone(tz)
            now = datetime.now(tz_obj)
            itr = croniter(cron_expr, now)
            next_run_at = itr.get_next(datetime)
        except Exception as e:
            raise HTTPException(400, f'Invalid cron expression: {e}')

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_rules
                (id, name, description, trigger_type, trigger_config, action,
                 enabled, cooldown_seconds, next_run_at, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, NOW(), NOW())
            """,
            rule_id, body.name, body.description or '', body.trigger_type,
            json.dumps(body.trigger_config), json.dumps(body.action),
            body.enabled, body.cooldown_seconds, next_run_at,
        )

        row = await conn.fetchrow('SELECT * FROM agent_rules WHERE id = $1', rule_id)

    return _rule_row_to_response(row)


@router.get('/rules', response_model=List[RuleResponse])
async def list_rules(
    trigger_type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List proactive rules."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    conditions = []
    params = []
    idx = 1

    if trigger_type:
        conditions.append(f'trigger_type = ${idx}')
        params.append(trigger_type)
        idx += 1
    if enabled is not None:
        conditions.append(f'enabled = ${idx}')
        params.append(enabled)
        idx += 1

    where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT * FROM agent_rules {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}',
            *params,
        )

    return [_rule_row_to_response(r) for r in rows]


@router.get('/rules/{rule_id}', response_model=RuleResponse)
async def get_rule(rule_id: str):
    """Get a proactive rule by ID."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM agent_rules WHERE id = $1', rule_id)

    if not row:
        raise HTTPException(404, 'Rule not found')
    return _rule_row_to_response(row)


@router.put('/rules/{rule_id}', response_model=RuleResponse)
async def update_rule(rule_id: str, body: RuleUpdate):
    """Update a proactive rule."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    updates = []
    params = []
    idx = 1

    for field_name, column in [
        ('name', 'name'), ('description', 'description'),
        ('enabled', 'enabled'), ('cooldown_seconds', 'cooldown_seconds'),
    ]:
        val = getattr(body, field_name)
        if val is not None:
            updates.append(f'{column} = ${idx}')
            params.append(val)
            idx += 1

    if body.trigger_config is not None:
        updates.append(f'trigger_config = ${idx}::jsonb')
        params.append(json.dumps(body.trigger_config))
        idx += 1
    if body.action is not None:
        updates.append(f'action = ${idx}::jsonb')
        params.append(json.dumps(body.action))
        idx += 1

    if not updates:
        raise HTTPException(400, 'No fields to update')

    updates.append('updated_at = NOW()')
    params.append(rule_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f'UPDATE agent_rules SET {", ".join(updates)} WHERE id = ${idx}',
            *params,
        )
        if result == 'UPDATE 0':
            raise HTTPException(404, 'Rule not found')

        row = await conn.fetchrow('SELECT * FROM agent_rules WHERE id = $1', rule_id)

    return _rule_row_to_response(row)


@router.delete('/rules/{rule_id}', status_code=204)
async def delete_rule(rule_id: str):
    """Delete a proactive rule."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        result = await conn.execute('DELETE FROM agent_rules WHERE id = $1', rule_id)

    if result == 'DELETE 0':
        raise HTTPException(404, 'Rule not found')


@router.get('/rules/{rule_id}/runs')
async def list_rule_runs(
    rule_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get execution history for a proactive rule."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    conditions = ['rule_id = $1']
    params: list = [rule_id]
    idx = 2

    if status:
        conditions.append(f'status = ${idx}')
        params.append(status)
        idx += 1

    where = f'WHERE {" AND ".join(conditions)}'
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT * FROM agent_rule_runs {where} ORDER BY started_at DESC LIMIT ${idx} OFFSET ${idx+1}',
            *params,
        )

    return [dict(r) for r in rows]


# ============================================================================
# Health Checks CRUD
# ============================================================================


@router.post('/health-checks', response_model=HealthCheckResponse, status_code=201)
async def create_health_check(body: HealthCheckCreate):
    """Create a new health check."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    check_id = str(uuid.uuid4())
    next_check = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO health_checks
                (id, name, description, check_type, check_config,
                 interval_seconds, next_check_at, enabled, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, NOW(), NOW())
            """,
            check_id, body.name, body.description or '', body.check_type,
            json.dumps(body.check_config), body.interval_seconds,
            next_check, body.enabled,
        )

        row = await conn.fetchrow('SELECT * FROM health_checks WHERE id = $1', check_id)

    return _health_check_row_to_response(row)


@router.get('/health-checks', response_model=List[HealthCheckResponse])
async def list_health_checks(
    check_type: Optional[str] = Query(None),
    last_status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List health checks."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    conditions = []
    params = []
    idx = 1

    if check_type:
        conditions.append(f'check_type = ${idx}')
        params.append(check_type)
        idx += 1
    if last_status:
        conditions.append(f'last_status = ${idx}')
        params.append(last_status)
        idx += 1

    where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT * FROM health_checks {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}',
            *params,
        )

    return [_health_check_row_to_response(r) for r in rows]


@router.get('/health-checks/{check_id}', response_model=HealthCheckResponse)
async def get_health_check(check_id: str):
    """Get a health check by ID."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM health_checks WHERE id = $1', check_id)

    if not row:
        raise HTTPException(404, 'Health check not found')
    return _health_check_row_to_response(row)


@router.put('/health-checks/{check_id}', response_model=HealthCheckResponse)
async def update_health_check(check_id: str, body: HealthCheckUpdate):
    """Update a health check."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    updates = []
    params = []
    idx = 1

    for field_name, column in [
        ('name', 'name'), ('description', 'description'),
        ('interval_seconds', 'interval_seconds'), ('enabled', 'enabled'),
    ]:
        val = getattr(body, field_name)
        if val is not None:
            updates.append(f'{column} = ${idx}')
            params.append(val)
            idx += 1

    if body.check_config is not None:
        updates.append(f'check_config = ${idx}::jsonb')
        params.append(json.dumps(body.check_config))
        idx += 1

    if not updates:
        raise HTTPException(400, 'No fields to update')

    updates.append('updated_at = NOW()')
    params.append(check_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f'UPDATE health_checks SET {", ".join(updates)} WHERE id = ${idx}',
            *params,
        )
        if result == 'UPDATE 0':
            raise HTTPException(404, 'Health check not found')

        row = await conn.fetchrow('SELECT * FROM health_checks WHERE id = $1', check_id)

    return _health_check_row_to_response(row)


@router.delete('/health-checks/{check_id}', status_code=204)
async def delete_health_check(check_id: str):
    """Delete a health check."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        result = await conn.execute('DELETE FROM health_checks WHERE id = $1', check_id)

    if result == 'DELETE 0':
        raise HTTPException(404, 'Health check not found')


# ============================================================================
# Models — Perpetual Loops
# ============================================================================


class LoopCreate(BaseModel):
    persona_slug: str = Field(..., min_length=1, max_length=100)
    codebase_id: Optional[str] = None
    iteration_interval_seconds: int = Field(default=300, ge=30)
    max_iterations_per_day: int = Field(default=100, ge=1, le=10000)
    daily_cost_ceiling_cents: int = Field(default=500, ge=0)
    state: Dict[str, Any] = Field(default_factory=dict)


class LoopUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern='^(running|paused|stopped)$')
    iteration_interval_seconds: Optional[int] = Field(None, ge=30)
    max_iterations_per_day: Optional[int] = Field(None, ge=1, le=10000)
    daily_cost_ceiling_cents: Optional[int] = Field(None, ge=0)
    state: Optional[Dict[str, Any]] = None


class LoopResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    persona_slug: str
    codebase_id: Optional[str] = None
    status: str
    state: Dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = 0
    iterations_today: int = 0
    iteration_interval_seconds: int = 300
    max_iterations_per_day: int = 100
    daily_cost_ceiling_cents: int = 500
    cost_today_cents: int = 0
    cost_total_cents: int = 0
    last_iteration_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LoopIterationResponse(BaseModel):
    id: str
    loop_id: str
    iteration_number: int
    task_id: Optional[str] = None
    input_state: Dict[str, Any] = Field(default_factory=dict)
    output_state: Dict[str, Any] = Field(default_factory=dict)
    cost_cents: int = 0
    duration_seconds: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# Perpetual Loops CRUD
# ============================================================================


@router.post('/loops', response_model=LoopResponse, status_code=201)
async def create_loop(body: LoopCreate):
    """Create and start a new perpetual cognition loop."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    loop_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        # Validate persona exists
        persona = await conn.fetchrow(
            "SELECT slug FROM worker_profiles WHERE slug = $1", body.persona_slug
        )
        if not persona:
            raise HTTPException(400, f'Persona "{body.persona_slug}" not found in worker_profiles')

        await conn.execute("""
            INSERT INTO perpetual_loops
                (id, persona_slug, codebase_id, status, state,
                 iteration_interval_seconds, max_iterations_per_day,
                 daily_cost_ceiling_cents, created_at, updated_at)
            VALUES ($1, $2, $3, 'running', $4::jsonb, $5, $6, $7, NOW(), NOW())
        """,
            loop_id, body.persona_slug, body.codebase_id,
            json.dumps(body.state, default=str),
            body.iteration_interval_seconds, body.max_iterations_per_day,
            body.daily_cost_ceiling_cents,
        )

        row = await conn.fetchrow('SELECT * FROM perpetual_loops WHERE id = $1', loop_id)

    return _loop_row_to_response(row)


@router.get('/loops', response_model=List[LoopResponse])
async def list_loops(
    status: Optional[str] = Query(None),
    persona_slug: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List perpetual cognition loops."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f'status = ${idx}')
        params.append(status)
        idx += 1
    if persona_slug:
        conditions.append(f'persona_slug = ${idx}')
        params.append(persona_slug)
        idx += 1

    where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT * FROM perpetual_loops {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}',
            *params,
        )

    return [_loop_row_to_response(r) for r in rows]


@router.get('/loops/{loop_id}', response_model=LoopResponse)
async def get_loop(loop_id: str):
    """Get a perpetual loop by ID."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM perpetual_loops WHERE id = $1', loop_id)

    if not row:
        raise HTTPException(404, 'Loop not found')
    return _loop_row_to_response(row)


@router.put('/loops/{loop_id}', response_model=LoopResponse)
async def update_loop(loop_id: str, body: LoopUpdate):
    """Update a perpetual loop. Use status='paused' to pause, 'running' to resume."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    updates = []
    params: list = []
    idx = 1

    for field_name, column in [
        ('status', 'status'),
        ('iteration_interval_seconds', 'iteration_interval_seconds'),
        ('max_iterations_per_day', 'max_iterations_per_day'),
        ('daily_cost_ceiling_cents', 'daily_cost_ceiling_cents'),
    ]:
        val = getattr(body, field_name)
        if val is not None:
            updates.append(f'{column} = ${idx}')
            params.append(val)
            idx += 1

    if body.state is not None:
        updates.append(f'state = ${idx}::jsonb')
        params.append(json.dumps(body.state, default=str))
        idx += 1

    if not updates:
        raise HTTPException(400, 'No fields to update')

    updates.append('updated_at = NOW()')
    params.append(loop_id)

    async with pool.acquire() as conn:
        result = await conn.execute(
            f'UPDATE perpetual_loops SET {", ".join(updates)} WHERE id = ${idx}',
            *params,
        )
        if result == 'UPDATE 0':
            raise HTTPException(404, 'Loop not found')

        row = await conn.fetchrow('SELECT * FROM perpetual_loops WHERE id = $1', loop_id)

    return _loop_row_to_response(row)


@router.delete('/loops/{loop_id}', status_code=204)
async def delete_loop(loop_id: str):
    """Delete a perpetual loop and all its iterations."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        result = await conn.execute('DELETE FROM perpetual_loops WHERE id = $1', loop_id)

    if result == 'DELETE 0':
        raise HTTPException(404, 'Loop not found')


@router.get('/loops/{loop_id}/iterations', response_model=List[LoopIterationResponse])
async def list_loop_iterations(
    loop_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get iteration history for a perpetual loop."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM perpetual_loop_iterations
               WHERE loop_id = $1
               ORDER BY iteration_number DESC LIMIT $2 OFFSET $3""",
            loop_id, limit, offset,
        )

    return [_iteration_row_to_response(r) for r in rows]


# ============================================================================
# Autonomous Decisions Audit Trail
# ============================================================================


@router.get('/decisions')
async def list_decisions(
    source: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List autonomous decisions across all proactive systems."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    conditions = []
    params: list = []
    idx = 1

    if source:
        conditions.append(f'source = ${idx}')
        params.append(source)
        idx += 1
    if decision_type:
        conditions.append(f'decision_type = ${idx}')
        params.append(decision_type)
        idx += 1
    if outcome:
        conditions.append(f'outcome = ${idx}')
        params.append(outcome)
        idx += 1

    where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
    params.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT * FROM autonomous_decisions {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}',
            *params,
        )

    return [dict(r) for r in rows]


# ============================================================================
# Status / Dashboard
# ============================================================================


@router.get('/status')
async def get_proactive_status():
    """Get overall proactive layer status: rule engine, health monitor, perpetual loops."""
    result: Dict[str, Any] = {}

    try:
        from .rule_engine import get_rule_engine
        engine = get_rule_engine()
        result['rule_engine'] = engine.get_health() if engine else {'running': False}
    except Exception:
        result['rule_engine'] = {'running': False}

    try:
        from .health_monitor import get_health_monitor
        monitor = get_health_monitor()
        result['health_monitor'] = monitor.get_health() if monitor else {'running': False}
    except Exception:
        result['health_monitor'] = {'running': False}

    # Perpetual loops status (Phase 3)
    try:
        from .perpetual_loop import get_perpetual_manager
        manager = get_perpetual_manager()
        result['perpetual_loops'] = manager.get_health() if manager else {'running': False}
    except Exception:
        result['perpetual_loops'] = {'running': False}

    # Marketing automation status
    try:
        from .marketing_automation import get_marketing_automation
        marketing = get_marketing_automation()
        result['marketing_automation'] = marketing.get_health() if marketing else {'running': False}
    except Exception:
        result['marketing_automation'] = {'running': False}

    # Summary counts
    try:
        pool = await db.get_pool()
        if pool:
            async with pool.acquire() as conn:
                result['counts'] = {
                    'active_rules': await conn.fetchval(
                        'SELECT count(*) FROM agent_rules WHERE enabled = true'
                    ),
                    'active_health_checks': await conn.fetchval(
                        'SELECT count(*) FROM health_checks WHERE enabled = true'
                    ),
                    'rule_triggers_today': await conn.fetchval(
                        """SELECT count(*) FROM agent_rule_runs
                           WHERE started_at >= CURRENT_DATE
                             AND status = 'task_created'"""
                    ),
                    'failed_health_checks': await conn.fetchval(
                        "SELECT count(*) FROM health_checks WHERE last_status = 'failed'"
                    ),
                    'running_loops': await conn.fetchval(
                        "SELECT count(*) FROM perpetual_loops WHERE status = 'running'"
                    ),
                    'loop_iterations_today': await conn.fetchval(
                        "SELECT count(*) FROM perpetual_loop_iterations WHERE started_at >= CURRENT_DATE"
                    ),
                    'marketing_decisions_today': await conn.fetchval(
                        """SELECT count(*) FROM autonomous_decisions
                           WHERE source = 'marketing_automation'
                             AND created_at >= CURRENT_DATE"""
                    ),
                }
    except Exception:
        result['counts'] = {}

    return result


# ============================================================================
# Marketing Automation Status
# ============================================================================


@router.get('/marketing/status')
async def get_marketing_status():
    """Get marketing automation status and last performance report."""
    try:
        from .marketing_automation import get_marketing_automation
        service = get_marketing_automation()
        if not service:
            return {'running': False, 'enabled': False, 'last_report': None}

        return {
            **service.get_health(),
            'last_report': service.get_last_report(),
        }
    except Exception:
        return {'running': False, 'enabled': False, 'last_report': None}


@router.get('/marketing/decisions')
async def list_marketing_decisions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List marketing automation decisions from the audit trail."""
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(503, 'Database not available')

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM autonomous_decisions
               WHERE source = 'marketing_automation'
               ORDER BY created_at DESC LIMIT $1 OFFSET $2""",
            limit, offset,
        )

    return [dict(r) for r in rows]


# ============================================================================
# Helpers
# ============================================================================


def _rule_row_to_response(row) -> RuleResponse:
    trigger_config = row['trigger_config']
    if isinstance(trigger_config, str):
        trigger_config = json.loads(trigger_config)
    action = row['action']
    if isinstance(action, str):
        action = json.loads(action)

    return RuleResponse(
        id=row['id'],
        tenant_id=row.get('tenant_id'),
        user_id=row.get('user_id'),
        name=row['name'],
        description=row.get('description', ''),
        trigger_type=row['trigger_type'],
        trigger_config=trigger_config,
        action=action,
        enabled=row['enabled'],
        cooldown_seconds=row['cooldown_seconds'],
        last_triggered_at=row.get('last_triggered_at'),
        trigger_count=row.get('trigger_count', 0),
        next_run_at=row.get('next_run_at'),
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at'),
    )


def _health_check_row_to_response(row) -> HealthCheckResponse:
    check_config = row['check_config']
    if isinstance(check_config, str):
        check_config = json.loads(check_config)
    last_result = row.get('last_result', {})
    if isinstance(last_result, str):
        last_result = json.loads(last_result) if last_result else {}

    return HealthCheckResponse(
        id=row['id'],
        tenant_id=row.get('tenant_id'),
        name=row['name'],
        description=row.get('description', ''),
        check_type=row['check_type'],
        check_config=check_config,
        interval_seconds=row['interval_seconds'],
        last_checked_at=row.get('last_checked_at'),
        next_check_at=row.get('next_check_at'),
        last_status=row.get('last_status', 'unknown'),
        last_result=last_result if isinstance(last_result, dict) else {},
        consecutive_failures=row.get('consecutive_failures', 0),
        enabled=row['enabled'],
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at'),
    )


def _loop_row_to_response(row) -> LoopResponse:
    state = row.get('state', {})
    if isinstance(state, str):
        state = json.loads(state) if state else {}

    return LoopResponse(
        id=row['id'],
        tenant_id=row.get('tenant_id'),
        user_id=row.get('user_id'),
        persona_slug=row['persona_slug'],
        codebase_id=row.get('codebase_id'),
        status=row['status'],
        state=state if isinstance(state, dict) else {},
        iteration_count=row.get('iteration_count', 0),
        iterations_today=row.get('iterations_today', 0),
        iteration_interval_seconds=row.get('iteration_interval_seconds', 300),
        max_iterations_per_day=row.get('max_iterations_per_day', 100),
        daily_cost_ceiling_cents=row.get('daily_cost_ceiling_cents', 500),
        cost_today_cents=row.get('cost_today_cents', 0),
        cost_total_cents=row.get('cost_total_cents', 0),
        last_iteration_at=row.get('last_iteration_at'),
        last_heartbeat=row.get('last_heartbeat'),
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at'),
    )


def _iteration_row_to_response(row) -> LoopIterationResponse:
    input_state = row.get('input_state', {})
    if isinstance(input_state, str):
        input_state = json.loads(input_state) if input_state else {}
    output_state = row.get('output_state', {})
    if isinstance(output_state, str):
        output_state = json.loads(output_state) if output_state else {}

    return LoopIterationResponse(
        id=row['id'],
        loop_id=row['loop_id'],
        iteration_number=row['iteration_number'],
        task_id=row.get('task_id'),
        input_state=input_state if isinstance(input_state, dict) else {},
        output_state=output_state if isinstance(output_state, dict) else {},
        cost_cents=row.get('cost_cents', 0),
        duration_seconds=row.get('duration_seconds', 0),
        started_at=row.get('started_at'),
        completed_at=row.get('completed_at'),
    )
