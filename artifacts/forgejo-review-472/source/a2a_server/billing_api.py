"""
Billing REST API for A2A Server.

Provides endpoints for subscription billing, customer management, and usage tracking:
- Setup Stripe customers for tenants
- Create checkout and billing portal sessions
- Manage subscriptions (view, cancel, change)
- Track usage metrics and invoices
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .billing_service import (
    BillingService,
    BillingServiceError,
    CustomerNotFoundError,
    PlanNotFoundError,
    SubscriptionNotFoundError,
    PLANS,
    get_billing_service,
)
from .database import (
    db_list_codebases,
    db_list_tasks,
    db_list_workers,
    get_tenant_by_id,
    update_tenant_stripe,
)
from .keycloak_auth import require_auth, UserSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/billing', tags=['billing'])


# ========================================
# Helper Functions
# ========================================


def get_plan_limits(plan: str) -> dict:
    """Get the resource limits for a given plan.

    Args:
        plan: Plan identifier ('free', 'pro', 'enterprise')

    Returns:
        Dict with 'workers', 'codebases', 'tasks_per_month' limits (-1 = unlimited)
    """
    plan_data = PLANS.get(plan, PLANS['free'])
    return plan_data['limits']


# ========================================
# Request/Response Models
# ========================================


class BillingSetupResponse(BaseModel):
    """Response model for billing setup."""

    customer_id: str = Field(..., description='Stripe customer ID')
    has_payment_method: bool = Field(
        ..., description='Whether customer has a default payment method'
    )


class CheckoutRequest(BaseModel):
    """Request model for checkout session creation."""

    plan: str = Field(..., description='Plan to subscribe to (pro, enterprise)')
    success_url: str = Field(
        ..., description='URL to redirect to on successful checkout'
    )
    cancel_url: str = Field(
        ..., description='URL to redirect to on cancelled checkout'
    )


class CheckoutResponse(BaseModel):
    """Response model for checkout session."""

    checkout_url: str = Field(..., description='Stripe Checkout session URL')


class PortalRequest(BaseModel):
    """Request model for billing portal session."""

    return_url: str = Field(
        ..., description='URL to return to after portal session'
    )


class PortalResponse(BaseModel):
    """Response model for billing portal session."""

    portal_url: str = Field(..., description='Stripe Billing Portal URL')


class SubscriptionResponse(BaseModel):
    """Response model for subscription details."""

    plan: str = Field(..., description='Current plan name')
    status: str = Field(
        ...,
        description='Subscription status (active, canceled, past_due, etc.)',
    )
    current_period_end: Optional[datetime] = Field(
        None, description='End of current billing period'
    )
    cancel_at_period_end: bool = Field(
        ..., description='Whether subscription will cancel at period end'
    )


class CancelSubscriptionRequest(BaseModel):
    """Request model for subscription cancellation."""

    at_period_end: bool = Field(
        default=True,
        description='If True, cancel at end of billing period. If False, cancel immediately.',
    )


class ChangeSubscriptionRequest(BaseModel):
    """Request model for subscription plan change."""

    new_plan: str = Field(
        ..., description='New plan to switch to (free, pro, enterprise)'
    )


class UsageResponse(BaseModel):
    """Response model for usage metrics."""

    tasks_used: int = Field(..., description='Tasks used in current period')
    tasks_limit: int = Field(
        ..., description='Task limit for plan (-1 = unlimited)'
    )
    workers_used: int = Field(..., description='Active workers')
    workers_limit: int = Field(
        ..., description='Worker limit for plan (-1 = unlimited)'
    )
    codebases_used: int = Field(..., description='Registered codebases')
    codebases_limit: int = Field(
        ..., description='Codebase limit for plan (-1 = unlimited)'
    )


class InvoiceResponse(BaseModel):
    """Response model for invoice."""

    id: str = Field(..., description='Invoice ID')
    number: Optional[str] = Field(None, description='Invoice number')
    status: str = Field(
        ..., description='Status (draft, open, paid, void, uncollectible)'
    )
    amount_due: int = Field(..., description='Amount due in cents')
    amount_paid: int = Field(..., description='Amount paid in cents')
    currency: str = Field(..., description='Currency code')
    created: datetime = Field(..., description='Invoice creation date')
    period_start: datetime = Field(..., description='Billing period start')
    period_end: datetime = Field(..., description='Billing period end')
    pdf_url: Optional[str] = Field(None, description='URL to download PDF')
    hosted_invoice_url: Optional[str] = Field(
        None, description='URL to view invoice online'
    )


class InvoiceListResponse(BaseModel):
    """Response model for invoice listing."""

    invoices: List[InvoiceResponse]


# ========================================
# Endpoints
# ========================================


@router.post('/setup', response_model=BillingSetupResponse)
async def setup_billing(
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Set up billing for the current tenant.

    Creates a Stripe customer if one doesn't exist and links it to the tenant.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    # Get tenant details
    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    # Check if customer already exists
    customer_id = tenant.get('stripe_customer_id')
    has_payment_method = False

    if customer_id:
        # Customer exists, check for payment method
        try:
            customer = await billing.get_customer(customer_id)
            has_payment_method = bool(customer.get('default_source'))
        except CustomerNotFoundError:
            # Customer was deleted in Stripe, create new one
            customer_id = None
        except BillingServiceError as e:
            logger.error(f'Failed to get customer: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    if not customer_id:
        # Create new customer
        try:
            customer_id = await billing.create_customer(
                tenant_id=tenant_id,
                email=user.email,
                name=tenant.get('display_name') or user.name,
            )
            # Update tenant with customer ID
            await update_tenant_stripe(
                tenant_id=tenant_id,
                customer_id=customer_id,
                subscription_id=tenant.get('stripe_subscription_id') or '',
            )
        except BillingServiceError as e:
            logger.error(f'Failed to create customer: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    logger.info(f'Billing setup completed for tenant {tenant_id}')

    return BillingSetupResponse(
        customer_id=customer_id,
        has_payment_method=has_payment_method,
    )


@router.post('/checkout', response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Checkout session for subscription purchase.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    customer_id = tenant.get('stripe_customer_id')
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail='Billing not set up. Call /v1/billing/setup first.',
        )

    # Get plan price ID
    try:
        plan = billing.get_plan(request.plan)
        price_id = plan.get('price_id')
        if not price_id:
            raise HTTPException(
                status_code=400,
                detail=f'Plan {request.plan} is not available for purchase',
            )
    except PlanNotFoundError:
        raise HTTPException(
            status_code=400, detail=f'Unknown plan: {request.plan}'
        )

    try:
        checkout_url = await billing.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=400, detail='Customer not found in Stripe'
        )
    except BillingServiceError as e:
        logger.error(f'Failed to create checkout session: {e}')
        raise HTTPException(status_code=500, detail=str(e))

    return CheckoutResponse(checkout_url=checkout_url)


@router.post('/portal', response_model=PortalResponse)
async def create_portal(
    request: PortalRequest,
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Create a Stripe Billing Portal session.

    Allows customers to manage payment methods, view invoices, and cancel subscriptions.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    customer_id = tenant.get('stripe_customer_id')
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail='Billing not set up. Call /v1/billing/setup first.',
        )

    try:
        portal_url = await billing.create_billing_portal_session(
            customer_id=customer_id,
            return_url=request.return_url,
        )
    except CustomerNotFoundError:
        raise HTTPException(
            status_code=400, detail='Customer not found in Stripe'
        )
    except BillingServiceError as e:
        logger.error(f'Failed to create portal session: {e}')
        raise HTTPException(status_code=500, detail=str(e))

    return PortalResponse(portal_url=portal_url)


@router.get('/subscription', response_model=SubscriptionResponse)
async def get_subscription(
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Get the current subscription details for the tenant.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    # Check for Stripe subscription
    subscription_id = tenant.get('stripe_subscription_id')
    if subscription_id:
        try:
            sub = await billing.get_subscription(subscription_id)
            # Determine plan from price ID
            plan = tenant.get('plan', 'free')
            if sub.get('items'):
                price_id = sub['items'][0].get('price_id')
                for plan_name, plan_data in PLANS.items():
                    if plan_data.get('price_id') == price_id:
                        plan = plan_name
                        break

            current_period_end = sub.get('current_period_end')
            if current_period_end and isinstance(current_period_end, int):
                current_period_end = datetime.fromtimestamp(current_period_end)

            return SubscriptionResponse(
                plan=plan,
                status=sub.get('status', 'active'),
                current_period_end=current_period_end,
                cancel_at_period_end=sub.get('cancel_at_period_end', False),
            )
        except SubscriptionNotFoundError:
            pass  # Fall through to return free plan
        except BillingServiceError as e:
            logger.error(f'Failed to get subscription: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # No active subscription - return free plan
    return SubscriptionResponse(
        plan=tenant.get('plan', 'free'),
        status='active',
        current_period_end=None,
        cancel_at_period_end=False,
    )


@router.post('/subscription/cancel', response_model=SubscriptionResponse)
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Cancel the current subscription.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    subscription_id = tenant.get('stripe_subscription_id')
    if not subscription_id:
        raise HTTPException(
            status_code=400, detail='No active subscription to cancel'
        )

    try:
        sub = await billing.cancel_subscription(
            subscription_id=subscription_id,
            at_period_end=request.at_period_end,
        )

        current_period_end = sub.get('current_period_end')
        if current_period_end and isinstance(current_period_end, int):
            current_period_end = datetime.fromtimestamp(current_period_end)

        # Determine plan from price ID
        plan = tenant.get('plan', 'free')
        if sub.get('items'):
            price_id = sub['items'][0].get('price_id')
            for plan_name, plan_data in PLANS.items():
                if plan_data.get('price_id') == price_id:
                    plan = plan_name
                    break

        logger.info(
            f'Subscription {subscription_id} cancelled for tenant {tenant_id}'
        )

        return SubscriptionResponse(
            plan=plan,
            status=sub.get('status', 'canceled'),
            current_period_end=current_period_end,
            cancel_at_period_end=sub.get('cancel_at_period_end', True),
        )
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=404, detail='Subscription not found')
    except BillingServiceError as e:
        logger.error(f'Failed to cancel subscription: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/subscription/change', response_model=SubscriptionResponse)
async def change_subscription(
    request: ChangeSubscriptionRequest,
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Change the subscription to a new plan.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    subscription_id = tenant.get('stripe_subscription_id')
    if not subscription_id:
        raise HTTPException(
            status_code=400,
            detail='No active subscription. Use /v1/billing/checkout to subscribe.',
        )

    # Get new plan price ID
    try:
        plan = billing.get_plan(request.new_plan)
        new_price_id = plan.get('price_id')
        if not new_price_id:
            raise HTTPException(
                status_code=400,
                detail=f'Plan {request.new_plan} is not available for purchase',
            )
    except PlanNotFoundError:
        raise HTTPException(
            status_code=400, detail=f'Unknown plan: {request.new_plan}'
        )

    try:
        sub = await billing.update_subscription(
            subscription_id=subscription_id,
            new_price_id=new_price_id,
        )

        current_period_end = sub.get('current_period_end')
        if current_period_end and isinstance(current_period_end, int):
            current_period_end = datetime.fromtimestamp(current_period_end)

        logger.info(
            f'Subscription {subscription_id} changed to {request.new_plan} '
            f'for tenant {tenant_id}'
        )

        return SubscriptionResponse(
            plan=request.new_plan,
            status=sub.get('status', 'active'),
            current_period_end=current_period_end,
            cancel_at_period_end=sub.get('cancel_at_period_end', False),
        )
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=404, detail='Subscription not found')
    except BillingServiceError as e:
        logger.error(f'Failed to change subscription: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/usage', response_model=UsageResponse)
async def get_usage(
    user: UserSession = Depends(require_auth),
):
    """
    Get usage metrics for the current billing period.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    # Get plan limits
    plan = tenant.get('plan', 'free')
    limits = get_plan_limits(plan)

    # Count current usage
    try:
        workers = await db_list_workers(tenant_id=tenant_id)
        codebases = await db_list_codebases(tenant_id=tenant_id)
        tasks = await db_list_tasks(tenant_id=tenant_id, limit=10000)
    except Exception as e:
        logger.error(f'Failed to get usage metrics: {e}')
        raise HTTPException(status_code=500, detail='Failed to get usage data')

    return UsageResponse(
        tasks_used=len(tasks),
        tasks_limit=limits.get('tasks_per_month', 100),
        workers_used=len(workers),
        workers_limit=limits.get('workers', 1),
        codebases_used=len(codebases),
        codebases_limit=limits.get('codebases', 3),
    )


@router.get('/invoices', response_model=InvoiceListResponse)
async def get_invoices(
    limit: int = Query(default=10, ge=1, le=100, description='Max invoices'),
    user: UserSession = Depends(require_auth),
    billing: BillingService = Depends(get_billing_service),
):
    """
    Get invoices for the tenant.
    """
    tenant_id = getattr(user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(
            status_code=400, detail='No tenant associated with this user'
        )

    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')

    customer_id = tenant.get('stripe_customer_id')
    if not customer_id:
        # No billing set up, return empty list
        return InvoiceListResponse(invoices=[])

    try:
        # Fetch invoices from Stripe
        import stripe

        await billing._ensure_initialized()
        invoices_response = stripe.Invoice.list(
            customer=customer_id,
            limit=limit,
        )

        invoices = []
        for inv in invoices_response.data:
            invoices.append(
                InvoiceResponse(
                    id=inv.id,
                    number=inv.number,
                    status=inv.status,
                    amount_due=inv.amount_due,
                    amount_paid=inv.amount_paid,
                    currency=inv.currency,
                    created=datetime.fromtimestamp(inv.created),
                    period_start=datetime.fromtimestamp(inv.period_start),
                    period_end=datetime.fromtimestamp(inv.period_end),
                    pdf_url=inv.invoice_pdf,
                    hosted_invoice_url=inv.hosted_invoice_url,
                )
            )

        return InvoiceListResponse(invoices=invoices)

    except CustomerNotFoundError:
        return InvoiceListResponse(invoices=[])
    except BillingServiceError as e:
        logger.error(f'Failed to get invoices: {e}')
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f'Failed to get invoices: {e}')
        return InvoiceListResponse(invoices=[])
