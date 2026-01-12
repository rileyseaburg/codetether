"""
Stripe Webhook Handler for A2A Server Billing.

Handles Stripe webhook events for subscription lifecycle management:
- customer.subscription.created/updated/deleted
- invoice.paid/payment_failed
- checkout.session.completed

Configuration:
    STRIPE_WEBHOOK_SECRET: Webhook signing secret (env var or Vault)
    Vault path: kv/codetether/stripe (key: webhook_secret)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

import stripe
from fastapi import APIRouter, HTTPException, Request

from .database import get_tenant_by_id, update_tenant, list_tenants

logger = logging.getLogger(__name__)

# Router for webhook endpoints
billing_webhook_router = APIRouter(prefix='/v1/webhooks', tags=['billing'])

# Plan definitions - maps Stripe price_ids to plan names
# These should match your Stripe product/price configuration
PLANS = {
    # Free tier (no subscription required)
    'free': {
        'name': 'Free',
        'workers': 1,
        'codebases': 3,
        'tasks_per_month': 100,
    },
    # Pro tier
    'pro': {
        'name': 'Pro',
        'workers': 5,
        'codebases': 20,
        'tasks_per_month': 5000,
    },
    # Enterprise tier
    'enterprise': {
        'name': 'Enterprise',
        'workers': -1,  # unlimited
        'codebases': -1,  # unlimited
        'tasks_per_month': -1,  # unlimited
    },
}

# Map Stripe price IDs to plan names
PRICE_TO_PLAN: Dict[str, str] = {
    'price_1SoawKE8yr4fu4JjkHQA2Y2c': 'pro',  # $49/month
    'price_1SoawKE8yr4fu4Jj7iDEjsk6': 'enterprise',  # $199/month
}

# Idempotency: Track processed event IDs to avoid duplicate processing
# In production, use Redis or database for persistence across restarts
_processed_events: Set[str] = set()
_processed_events_lock = asyncio.Lock()

# Maximum events to keep in memory (prevent unbounded growth)
MAX_PROCESSED_EVENTS = 10000

# Webhook secret - loaded lazily
_webhook_secret: Optional[str] = None


async def _get_webhook_secret() -> str:
    """
    Get Stripe webhook secret from Vault or environment.

    Priority:
    1. Environment variable STRIPE_WEBHOOK_SECRET
    2. Vault at kv/codetether/stripe (key: webhook_secret)
    """
    global _webhook_secret

    if _webhook_secret:
        return _webhook_secret

    # Try environment variable first
    env_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    if env_secret:
        _webhook_secret = env_secret
        logger.info('Using Stripe webhook secret from environment')
        return _webhook_secret

    # Try Vault
    try:
        from .vault_client import get_vault_client

        client = get_vault_client()
        secret_data = await client.read_secret('codetether/stripe')
        if secret_data and 'webhook_secret' in secret_data:
            _webhook_secret = secret_data['webhook_secret']
            logger.info('Using Stripe webhook secret from Vault')
            return _webhook_secret
    except Exception as e:
        logger.warning(f'Failed to fetch webhook secret from Vault: {e}')

    raise ValueError(
        'Stripe webhook secret not configured. '
        'Set STRIPE_WEBHOOK_SECRET env var or configure in Vault at kv/codetether/stripe'
    )


def price_id_to_plan(price_id: str) -> str:
    """
    Convert a Stripe price_id to a plan name.

    Args:
        price_id: Stripe price identifier

    Returns:
        Plan name (free, pro, enterprise)
    """
    return PRICE_TO_PLAN.get(price_id, 'free')


async def get_tenant_by_customer_id(
    customer_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Look up a tenant by their Stripe customer ID.

    Args:
        customer_id: Stripe customer ID (cus_xxx)

    Returns:
        Tenant dict or None if not found
    """
    try:
        # List all tenants and find the one with matching customer_id
        # In production, you'd want an index on stripe_customer_id
        tenants = await list_tenants(limit=10000)
        for tenant in tenants:
            if tenant.get('stripe_customer_id') == customer_id:
                return tenant
        return None
    except Exception as e:
        logger.error(
            f'Error looking up tenant by customer_id {customer_id}: {e}'
        )
        return None


async def _is_event_processed(event_id: str) -> bool:
    """Check if an event has already been processed (idempotency)."""
    async with _processed_events_lock:
        return event_id in _processed_events


async def _mark_event_processed(event_id: str) -> None:
    """Mark an event as processed (idempotency)."""
    async with _processed_events_lock:
        # Prevent unbounded growth - remove oldest events if at limit
        if len(_processed_events) >= MAX_PROCESSED_EVENTS:
            # Remove first 1000 events (FIFO approximation with set)
            events_list = list(_processed_events)
            _processed_events.clear()
            _processed_events.update(events_list[1000:])

        _processed_events.add(event_id)


async def _handle_subscription_created(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.created event.

    Updates tenant with subscription_id and sets plan based on price_id.
    """
    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')

    if not customer_id or not subscription_id:
        logger.warning('Subscription created event missing customer or id')
        return

    tenant = await get_tenant_by_customer_id(customer_id)
    if not tenant:
        logger.warning(f'No tenant found for customer {customer_id}')
        return

    # Get plan from price_id
    items = subscription.get('items', {}).get('data', [])
    plan = 'free'
    if items:
        price_id = items[0].get('price', {}).get('id', '')
        plan = price_id_to_plan(price_id)

    # Update tenant
    try:
        await update_tenant(
            tenant['id'],
            plan=plan,
        )
        # Also update stripe_subscription_id
        from .database import update_tenant_stripe

        await update_tenant_stripe(
            tenant['id'],
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        logger.info(
            f'Tenant {tenant["id"]} subscription created: {subscription_id}, plan: {plan}'
        )
    except Exception as e:
        logger.error(f'Failed to update tenant {tenant["id"]}: {e}')


async def _handle_subscription_updated(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.updated event.

    Updates tenant plan if price changed, handles status changes.
    """
    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')
    status = subscription.get('status')

    if not customer_id:
        logger.warning('Subscription updated event missing customer')
        return

    tenant = await get_tenant_by_customer_id(customer_id)
    if not tenant:
        logger.warning(f'No tenant found for customer {customer_id}')
        return

    # Get plan from price_id
    items = subscription.get('items', {}).get('data', [])
    plan = tenant.get('plan', 'free')  # Keep current plan as default
    if items:
        price_id = items[0].get('price', {}).get('id', '')
        plan = price_id_to_plan(price_id)

    # Handle status changes
    if status == 'past_due':
        logger.warning(
            f'Tenant {tenant["id"]} subscription {subscription_id} is past due'
        )
        # Could trigger notification here
    elif status == 'unpaid':
        logger.warning(
            f'Tenant {tenant["id"]} subscription {subscription_id} is unpaid, '
            'downgrading to free'
        )
        plan = 'free'
    elif status == 'canceled':
        logger.info(
            f'Tenant {tenant["id"]} subscription {subscription_id} canceled'
        )
        plan = 'free'
    elif status == 'active':
        logger.info(
            f'Tenant {tenant["id"]} subscription {subscription_id} is active'
        )

    # Update tenant plan
    try:
        await update_tenant(tenant['id'], plan=plan)
        logger.info(f'Tenant {tenant["id"]} updated to plan: {plan}')
    except Exception as e:
        logger.error(f'Failed to update tenant {tenant["id"]}: {e}')


async def _handle_subscription_deleted(subscription: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.deleted event.

    Sets tenant plan back to 'free' and clears subscription_id.
    """
    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')

    if not customer_id:
        logger.warning('Subscription deleted event missing customer')
        return

    tenant = await get_tenant_by_customer_id(customer_id)
    if not tenant:
        logger.warning(f'No tenant found for customer {customer_id}')
        return

    # Downgrade to free and clear subscription
    try:
        await update_tenant(tenant['id'], plan='free')

        # Clear subscription_id by updating with empty string
        from .database import update_tenant_stripe

        await update_tenant_stripe(
            tenant['id'],
            customer_id=customer_id,
            subscription_id='',
        )

        logger.info(
            f'Tenant {tenant["id"]} subscription {subscription_id} deleted, '
            'downgraded to free'
        )
    except Exception as e:
        logger.error(f'Failed to update tenant {tenant["id"]}: {e}')


async def _handle_invoice_paid(invoice: Dict[str, Any]) -> None:
    """
    Handle invoice.paid event.

    Logs successful payment. Could trigger email notification.
    """
    customer_id = invoice.get('customer')
    amount_paid = (
        invoice.get('amount_paid', 0) / 100
    )  # Convert cents to dollars
    invoice_id = invoice.get('id')

    if not customer_id:
        logger.warning('Invoice paid event missing customer')
        return

    tenant = await get_tenant_by_customer_id(customer_id)
    tenant_id = tenant['id'] if tenant else 'unknown'

    logger.info(
        f'Invoice {invoice_id} paid: ${amount_paid:.2f} for tenant {tenant_id}'
    )

    # TODO: Trigger email notification
    # await send_payment_confirmation_email(tenant, invoice)


async def _handle_invoice_payment_failed(invoice: Dict[str, Any]) -> None:
    """
    Handle invoice.payment_failed event.

    Logs failed payment. Could trigger email/notification to tenant admin.
    """
    customer_id = invoice.get('customer')
    amount_due = invoice.get('amount_due', 0) / 100  # Convert cents to dollars
    invoice_id = invoice.get('id')
    attempt_count = invoice.get('attempt_count', 0)

    if not customer_id:
        logger.warning('Invoice payment failed event missing customer')
        return

    tenant = await get_tenant_by_customer_id(customer_id)
    tenant_id = tenant['id'] if tenant else 'unknown'

    logger.warning(
        f'Invoice {invoice_id} payment failed: ${amount_due:.2f} for tenant '
        f'{tenant_id} (attempt {attempt_count})'
    )

    # TODO: Trigger notification to tenant admin
    # await send_payment_failed_notification(tenant, invoice)


async def _handle_checkout_completed(session: Dict[str, Any]) -> None:
    """
    Handle checkout.session.completed event.

    For subscription checkouts, ensures tenant is updated with customer_id
    and subscription_id.
    """
    mode = session.get('mode')

    # Only process subscription checkouts
    if mode != 'subscription':
        logger.debug(f'Ignoring checkout session with mode: {mode}')
        return

    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    client_reference_id = session.get('client_reference_id')  # tenant_id

    if not customer_id or not subscription_id:
        logger.warning('Checkout completed missing customer or subscription')
        return

    # Try to find tenant by client_reference_id (tenant_id passed at checkout)
    tenant = None
    if client_reference_id:
        tenant = await get_tenant_by_id(client_reference_id)

    # Fallback: try to find by customer_id (if tenant already linked)
    if not tenant and customer_id:
        tenant = await get_tenant_by_customer_id(customer_id)

    if not tenant:
        logger.warning(
            f'No tenant found for checkout - customer: {customer_id}, '
            f'ref: {client_reference_id}'
        )
        return

    # Update tenant with Stripe IDs
    try:
        from .database import update_tenant_stripe

        await update_tenant_stripe(
            tenant['id'],
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        logger.info(
            f'Tenant {tenant["id"]} linked to Stripe customer {customer_id}'
        )
    except Exception as e:
        logger.error(f'Failed to update tenant {tenant["id"]}: {e}')


@billing_webhook_router.post('/stripe')
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    Verifies webhook signature and processes supported events.
    Returns 200 OK quickly; heavy processing is done async.
    """
    # Get raw body for signature verification
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not sig_header:
        raise HTTPException(
            status_code=400, detail='Missing stripe-signature header'
        )

    # Get webhook secret
    try:
        webhook_secret = await _get_webhook_secret()
    except ValueError as e:
        logger.error(f'Webhook secret not configured: {e}')
        raise HTTPException(status_code=500, detail='Webhook not configured')

    # Verify signature and construct event
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f'Invalid webhook signature: {e}')
        raise HTTPException(status_code=400, detail='Invalid signature')
    except Exception as e:
        logger.error(f'Error constructing webhook event: {e}')
        raise HTTPException(status_code=400, detail='Invalid payload')

    event_id = event.get('id')
    event_type = event.get('type')

    logger.info(f'Received Stripe webhook: {event_type} ({event_id})')

    # Idempotency check
    if await _is_event_processed(event_id):
        logger.info(f'Event {event_id} already processed, skipping')
        return {'status': 'ok', 'message': 'already processed'}

    # Mark as processed early to prevent duplicates during async processing
    await _mark_event_processed(event_id)

    # Get event data
    data = event.get('data', {}).get('object', {})

    # Process event based on type
    # Use create_task for async processing to return 200 quickly
    try:
        if event_type == 'customer.subscription.created':
            asyncio.create_task(_handle_subscription_created(data))

        elif event_type == 'customer.subscription.updated':
            asyncio.create_task(_handle_subscription_updated(data))

        elif event_type == 'customer.subscription.deleted':
            asyncio.create_task(_handle_subscription_deleted(data))

        elif event_type == 'invoice.paid':
            asyncio.create_task(_handle_invoice_paid(data))

        elif event_type == 'invoice.payment_failed':
            asyncio.create_task(_handle_invoice_payment_failed(data))

        elif event_type == 'checkout.session.completed':
            asyncio.create_task(_handle_checkout_completed(data))

        else:
            logger.debug(f'Unhandled event type: {event_type}')

    except Exception as e:
        logger.error(f'Error processing webhook event {event_type}: {e}')
        # Still return 200 to prevent Stripe retries for processing errors

    return {'status': 'ok', 'event_type': event_type}
