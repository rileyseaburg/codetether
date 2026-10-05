"""
Token Billing REST API.

Provides endpoints for token usage visibility, budget management,
and model pricing administration.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .keycloak_auth import require_auth, UserSession
from .token_billing import (
    TokenBillingService,
    get_token_billing_service,
    MICRO_CENTS_PER_DOLLAR,
)
from .database import get_tenant_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/token-billing', tags=['token-billing'])


# ========================================
# Response Models
# ========================================


class UsageSummaryResponse(BaseModel):
    tenant_id: str
    month: str
    billing_model: str
    balance_dollars: float
    monthly_limit_dollars: Optional[float]
    totals: dict
    by_model: List[dict]


class UsageRecordResponse(BaseModel):
    id: int
    user_id: Optional[str]
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: Optional[int]
    cache_read_tokens: Optional[int]
    cache_write_tokens: Optional[int]
    cost_dollars: float
    session_id: Optional[str]
    task_id: Optional[str]
    created_at: Optional[str]


class BudgetCheckResponse(BaseModel):
    allowed: bool
    reason: str
    balance_dollars: float
    monthly_spend_dollars: float
    monthly_limit_dollars: Optional[float]
    billing_model: str


class AddCreditsRequest(BaseModel):
    amount_cents: int = Field(..., ge=100, description='Amount in cents to add (min $1.00)')


class AddCreditsResponse(BaseModel):
    new_balance_dollars: float


class SetBillingModelRequest(BaseModel):
    billing_model: str = Field(..., description="One of: subscription, prepaid, metered")
    monthly_limit_cents: Optional[int] = Field(None, ge=0, description='Monthly spending limit in cents')
    monthly_alert_cents: Optional[int] = Field(None, ge=0, description='Alert threshold in cents')
    markup_percent: float = Field(default=0, ge=0, le=100, description='Markup percentage (0-100)')


class SetSpendingLimitRequest(BaseModel):
    monthly_limit_cents: Optional[int] = Field(None, ge=0, description='Monthly limit in cents (null = unlimited)')
    monthly_alert_cents: Optional[int] = Field(None, ge=0, description='Alert threshold in cents')


class ModelPricingResponse(BaseModel):
    id: int
    provider: str
    model: str
    input_cost_per_m: float
    output_cost_per_m: float
    cache_read_cost_per_m: float
    cache_write_cost_per_m: float
    reasoning_cost_per_m: Optional[float]


class UpsertModelPricingRequest(BaseModel):
    provider: str
    model: str
    input_cost_per_m: float = Field(..., ge=0)
    output_cost_per_m: float = Field(..., ge=0)
    cache_read_cost_per_m: float = Field(default=0, ge=0)
    cache_write_cost_per_m: float = Field(default=0, ge=0)
    reasoning_cost_per_m: Optional[float] = Field(None, ge=0)


# ========================================
# Usage Endpoints
# ========================================


@router.get('/usage/summary', response_model=UsageSummaryResponse)
async def get_usage_summary(
    month: Optional[str] = Query(None, description='Month as YYYY-MM (default: current)'),
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Get aggregated token usage summary for the current tenant."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    month_dt = None
    if month:
        try:
            month_dt = datetime.strptime(month, '%Y-%m').replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid month format, use YYYY-MM')

    summary = await billing.get_tenant_usage_summary(tenant_id, month_dt)
    if 'error' in summary:
        raise HTTPException(status_code=500, detail=summary['error'])

    return summary


@router.get('/usage/recent', response_model=List[UsageRecordResponse])
async def get_recent_usage(
    limit: int = Query(default=50, ge=1, le=500),
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Get recent individual token usage records."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    return await billing.get_recent_usage(tenant_id, limit=limit)


@router.get('/budget', response_model=BudgetCheckResponse)
async def check_budget(
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Check current budget status for the tenant."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    check = await billing.check_budget(tenant_id)
    return BudgetCheckResponse(
        allowed=check.allowed,
        reason=check.reason,
        balance_dollars=check.balance_micro_cents / MICRO_CENTS_PER_DOLLAR,
        monthly_spend_dollars=check.monthly_spend_dollars,
        monthly_limit_dollars=(check.monthly_limit_cents / 100) if check.monthly_limit_cents else None,
        billing_model=check.billing_model,
    )


# ========================================
# Credit & Config Endpoints
# ========================================


@router.post('/credits', response_model=AddCreditsResponse)
async def add_credits(
    request: AddCreditsRequest,
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Add prepaid credits to the tenant's token balance."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    new_balance = await billing.add_credits(tenant_id, request.amount_cents)
    if new_balance is None:
        raise HTTPException(status_code=500, detail='Failed to add credits')

    return AddCreditsResponse(new_balance_dollars=new_balance / MICRO_CENTS_PER_DOLLAR)


@router.put('/config/billing-model')
async def set_billing_model(
    request: SetBillingModelRequest,
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Configure the billing model for the tenant."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    if request.billing_model not in ('subscription', 'prepaid', 'metered'):
        raise HTTPException(status_code=400, detail='Invalid billing model')

    success = await billing.set_billing_model(
        tenant_id=tenant_id,
        billing_model=request.billing_model,
        monthly_limit_cents=request.monthly_limit_cents,
        monthly_alert_cents=request.monthly_alert_cents,
        markup_percent=request.markup_percent,
    )

    if not success:
        raise HTTPException(status_code=500, detail='Failed to update billing model')

    return {'status': 'ok', 'billing_model': request.billing_model}


@router.put('/config/spending-limit')
async def set_spending_limit(
    request: SetSpendingLimitRequest,
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Set monthly spending limit for the tenant."""
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail='No tenant associated')

    from .database import get_pool
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=500, detail='Database unavailable')

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tenants SET
                monthly_spend_limit_cents = $2,
                monthly_spend_alert_cents = $3
            WHERE id = $1
            """,
            tenant_id,
            request.monthly_limit_cents,
            request.monthly_alert_cents,
        )

    return {
        'status': 'ok',
        'monthly_limit_dollars': request.monthly_limit_cents / 100 if request.monthly_limit_cents else None,
    }


# ========================================
# Model Pricing Endpoints (admin)
# ========================================


@router.get('/pricing', response_model=List[ModelPricingResponse])
async def list_model_pricing(
    provider: Optional[str] = Query(None, description='Filter by provider'),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """List all active model pricing. Public endpoint for transparency."""
    return await billing.get_model_pricing(provider)


@router.put('/pricing')
async def upsert_model_pricing(
    request: UpsertModelPricingRequest,
    user: UserSession = Depends(require_auth),
    billing: TokenBillingService = Depends(get_token_billing_service),
):
    """Add or update model pricing (admin only)."""
    success = await billing.upsert_model_pricing(
        provider=request.provider,
        model=request.model,
        input_cost_per_m=request.input_cost_per_m,
        output_cost_per_m=request.output_cost_per_m,
        cache_read_cost_per_m=request.cache_read_cost_per_m,
        cache_write_cost_per_m=request.cache_write_cost_per_m,
        reasoning_cost_per_m=request.reasoning_cost_per_m,
    )

    if not success:
        raise HTTPException(status_code=500, detail='Failed to update pricing')

    return {'status': 'ok', 'provider': request.provider, 'model': request.model}
