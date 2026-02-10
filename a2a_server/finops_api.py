"""
FinOps REST API.

Provides endpoints for cost analytics, anomaly detection, forecasting,
budget policies, alerts, and optimization recommendations.
"""

import logging
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .keycloak_auth import require_auth, UserSession
from .finops import (
    FinOpsService,
    get_finops_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/finops', tags=['finops'])


# ========================================
# Response Models
# ========================================


class CostForecastResponse(BaseModel):
    tenant_id: str
    period: str
    projected_cost_dollars: float
    daily_average_dollars: float
    days_in_period: int
    days_elapsed: int
    confidence: str
    trend: str
    pct_change_vs_last_period: Optional[float] = None


class CostAnomalyResponse(BaseModel):
    anomaly_type: str
    severity: str
    model: Optional[str] = None
    provider: Optional[str] = None
    description: str
    expected_value: float
    actual_value: float
    deviation_factor: float


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    message: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    metadata: Optional[dict] = None
    acknowledged: bool
    notified: bool
    created_at: Optional[str] = None


class AlertSummaryResponse(BaseModel):
    total: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0


class BudgetPolicyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    soft_limit_cents: Optional[int] = Field(None, ge=0, description='Warning threshold in cents')
    hard_limit_cents: Optional[int] = Field(None, ge=0, description='Block threshold in cents')
    scope: str = Field(default='tenant', description='tenant, user, model, or project')
    scope_filter: Optional[str] = Field(None, description='Filter value for scope (e.g., user_id)')
    period: str = Field(default='monthly', description='daily, weekly, or monthly')
    action_on_soft: str = Field(default='alert', description='alert or alert+webhook')
    action_on_hard: str = Field(default='alert', description='alert, block, alert+block, or throttle')
    webhook_url: Optional[str] = None


class BudgetPolicyResponse(BaseModel):
    id: int
    name: str
    scope: str
    scope_filter: Optional[str] = None
    period: str
    soft_limit_cents: Optional[int] = None
    hard_limit_cents: Optional[int] = None
    action_on_soft: str
    action_on_hard: str
    webhook_url: Optional[str] = None
    is_active: bool
    last_evaluated_at: Optional[str] = None
    created_at: Optional[str] = None


class RecommendationResponse(BaseModel):
    id: int
    recommendation_type: str
    title: str
    description: str
    estimated_savings_percent: float
    estimated_savings_dollars: float
    estimated_savings_cents: int
    current_model: Optional[str] = None
    suggested_model: Optional[str] = None
    evidence: Optional[dict] = None
    status: str
    created_at: Optional[str] = None


class DismissRecommendationRequest(BaseModel):
    reason: str = ''


class CostBreakdownResponse(BaseModel):
    dimension: str
    request_count: int
    input_tokens: int
    output_tokens: int
    cost_micro_cents: int
    cost_dollars: float


class CostTrendResponse(BaseModel):
    date: str
    requests: int
    cost_micro_cents: int
    cost_dollars: float
    tokens: int


class EnforceBudgetResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None


# ========================================
# Helper
# ========================================


def _get_tenant_id(user: UserSession) -> str:
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')
    return tenant_id


# ========================================
# Forecast & Analytics
# ========================================


@router.get('/forecast', response_model=CostForecastResponse)
async def get_cost_forecast(
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get projected end-of-month cost based on usage trends."""
    tenant_id = _get_tenant_id(user)
    forecast = await finops.forecast_monthly_cost(tenant_id)
    if not forecast:
        raise HTTPException(status_code=404, detail='Not enough data for forecast')
    return forecast


@router.get('/cost-breakdown', response_model=List[CostBreakdownResponse])
async def get_cost_breakdown(
    group_by: str = Query(default='model', description='model, user, project, environment, or day'),
    days: int = Query(default=30, ge=1, le=365),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get cost breakdown grouped by dimension (model, user, project, etc.)."""
    tenant_id = _get_tenant_id(user)
    if group_by not in ('model', 'user', 'project', 'environment', 'day'):
        raise HTTPException(status_code=400, detail='Invalid group_by value')
    return await finops.get_cost_breakdown(tenant_id, group_by=group_by, days=days)


@router.get('/cost-trend', response_model=List[CostTrendResponse])
async def get_cost_trend(
    days: int = Query(default=30, ge=1, le=365),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get daily cost trend for charting."""
    tenant_id = _get_tenant_id(user)
    return await finops.get_cost_trend(tenant_id, days=days)


# ========================================
# Anomaly Detection
# ========================================


@router.get('/anomalies', response_model=List[CostAnomalyResponse])
async def detect_anomalies(
    lookback_days: int = Query(default=14, ge=3, le=90),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Detect cost anomalies by comparing today's usage against historical baseline."""
    tenant_id = _get_tenant_id(user)
    anomalies = await finops.detect_anomalies(tenant_id, lookback_days=lookback_days)
    return [
        CostAnomalyResponse(
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            model=a.model,
            provider=a.provider,
            description=a.description,
            expected_value=a.expected_value,
            actual_value=a.actual_value,
            deviation_factor=a.deviation_factor,
        )
        for a in anomalies
    ]


# ========================================
# Budget Policies
# ========================================


@router.get('/policies', response_model=List[BudgetPolicyResponse])
async def list_budget_policies(
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """List all budget policies for the tenant."""
    tenant_id = _get_tenant_id(user)
    policies = await finops.list_budget_policies(tenant_id)
    return [
        BudgetPolicyResponse(
            **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in p.items()}
        )
        for p in policies
    ]


@router.post('/policies', status_code=201)
async def create_budget_policy(
    request: BudgetPolicyRequest,
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Create or update a budget policy."""
    tenant_id = _get_tenant_id(user)

    if request.scope not in ('tenant', 'user', 'model', 'project'):
        raise HTTPException(status_code=400, detail='Invalid scope')
    if request.period not in ('daily', 'weekly', 'monthly'):
        raise HTTPException(status_code=400, detail='Invalid period')
    if not request.soft_limit_cents and not request.hard_limit_cents:
        raise HTTPException(status_code=400, detail='At least one limit is required')

    policy_id = await finops.create_budget_policy(
        tenant_id=tenant_id,
        name=request.name,
        soft_limit_cents=request.soft_limit_cents,
        hard_limit_cents=request.hard_limit_cents,
        scope=request.scope,
        scope_filter=request.scope_filter,
        period=request.period,
        action_on_soft=request.action_on_soft,
        action_on_hard=request.action_on_hard,
        webhook_url=request.webhook_url,
    )

    if policy_id is None:
        raise HTTPException(status_code=500, detail='Failed to create policy')

    return {'id': policy_id, 'status': 'created'}


@router.post('/policies/evaluate')
async def evaluate_policies(
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Evaluate all active budget policies and return any breached ones."""
    tenant_id = _get_tenant_id(user)
    results = await finops.evaluate_policies(tenant_id)
    return {
        'breached_count': len(results),
        'breaches': [
            {
                'policy_id': r.policy_id,
                'policy_name': r.policy_name,
                'level': r.breached_level,
                'current_spend_dollars': r.current_spend_cents / 100,
                'limit_dollars': r.limit_cents / 100,
                'action': r.action,
            }
            for r in results
        ],
    }


# ========================================
# Alerts
# ========================================


@router.get('/alerts', response_model=List[AlertResponse])
async def get_alerts(
    unacknowledged_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get cost alerts for the tenant."""
    tenant_id = _get_tenant_id(user)
    return await finops.get_alerts(tenant_id, unacknowledged_only=unacknowledged_only, limit=limit)


@router.get('/alerts/summary', response_model=AlertSummaryResponse)
async def get_alert_summary(
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get unacknowledged alert counts by severity."""
    tenant_id = _get_tenant_id(user)
    summary = await finops.get_alert_summary(tenant_id)
    return AlertSummaryResponse(
        total=summary.get('total', 0),
        critical=summary.get('critical', 0),
        warning=summary.get('warning', 0),
        info=summary.get('info', 0),
    )


@router.post('/alerts/{alert_id}/acknowledge')
async def acknowledge_alert(
    alert_id: int,
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Acknowledge a cost alert."""
    tenant_id = _get_tenant_id(user)
    user_id = getattr(user, 'user_id', None) or getattr(user, 'sub', None)
    success = await finops.acknowledge_alert(tenant_id, alert_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail='Alert not found')
    return {'status': 'acknowledged'}


# ========================================
# Optimization Recommendations
# ========================================


@router.get('/recommendations', response_model=List[RecommendationResponse])
async def get_recommendations(
    status: str = Query(default='open', description='open, accepted, dismissed, implemented'),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Get cost optimization recommendations."""
    tenant_id = _get_tenant_id(user)
    return await finops.get_recommendations(tenant_id, status=status)


@router.post('/recommendations/{recommendation_id}/dismiss')
async def dismiss_recommendation(
    recommendation_id: int,
    request: DismissRecommendationRequest,
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Dismiss a cost optimization recommendation."""
    tenant_id = _get_tenant_id(user)
    success = await finops.dismiss_recommendation(tenant_id, recommendation_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail='Recommendation not found')
    return {'status': 'dismissed'}


@router.post('/recommendations/generate')
async def generate_recommendations(
    lookback_days: int = Query(default=30, ge=7, le=90),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Generate fresh cost optimization recommendations based on usage patterns."""
    tenant_id = _get_tenant_id(user)
    recs = await finops.generate_recommendations(tenant_id, lookback_days=lookback_days)
    return {
        'generated_count': len(recs),
        'recommendations': [
            {
                'type': r.recommendation_type,
                'title': r.title,
                'estimated_savings_percent': r.estimated_savings_percent,
                'estimated_savings_dollars': r.estimated_savings_cents / 100,
            }
            for r in recs
        ],
    }


# ========================================
# Budget Check (Public for UI)
# ========================================


@router.get('/budget-check', response_model=EnforceBudgetResponse)
async def check_budget(
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Check if the tenant's budget allows new AI operations."""
    tenant_id = _get_tenant_id(user)
    allowed, reason = await finops.enforce_budget(tenant_id)
    return EnforceBudgetResponse(allowed=allowed, reason=reason)


# ========================================
# Admin: Snapshot Builder
# ========================================


@router.post('/snapshots/build')
async def build_snapshots(
    snapshot_date: Optional[str] = Query(None, description='Date as YYYY-MM-DD (default: yesterday)'),
    user: UserSession = Depends(require_auth),
    finops: FinOpsService = Depends(get_finops_service),
):
    """Build daily cost snapshots (admin/cron operation)."""
    tenant_id = _get_tenant_id(user)

    d = None
    if snapshot_date:
        try:
            d = date.fromisoformat(snapshot_date)
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid date format, use YYYY-MM-DD')

    count = await finops.build_daily_snapshots(tenant_id=tenant_id, snapshot_date=d)
    return {'status': 'ok', 'snapshots_created': count}
