"""
User Billing - Stripe tier wiring for mid-market/consumer users.

Handles Stripe webhook events to sync user tiers and enforce limits.
This is separate from tenant_billing which handles B2B/enterprise.

Key features:
- Durable price-to-tier mapping (no code deploy for new prices)
- Webhook idempotency (persistent across restarts)
- Billing period usage resets
- Limit enforcement (tasks, concurrency, runtime)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .database import get_pool

logger = logging.getLogger(__name__)


# ========================================
# Database Operations
# ========================================


async def is_event_processed(event_id: str) -> bool:
    """Check if a Stripe event was already processed (idempotency)."""
    pool = await get_pool()
    if not pool:
        return False

    async with pool.acquire() as conn:
        result = await conn.fetchval(
            'SELECT is_stripe_event_processed($1)', event_id
        )
        return result or False


async def mark_event_processed(
    event_id: str,
    event_type: str,
    customer_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Mark a Stripe event as processed."""
    pool = await get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            'SELECT mark_stripe_event_processed($1, $2, $3, $4, $5)',
            event_id,
            event_type,
            customer_id,
            subscription_id,
            user_id,
        )


async def get_user_by_stripe_customer_id(
    customer_id: str,
) -> Optional[Dict[str, Any]]:
    """Look up a user by their Stripe customer ID."""
    pool = await get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM users WHERE stripe_customer_id = $1', customer_id
        )
        return dict(row) if row else None


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up a user by email (fallback for first-time Stripe link)."""
    pool = await get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM users WHERE email = $1', email.lower()
        )
        return dict(row) if row else None


async def sync_user_tier_from_stripe(
    user_id: str,
    stripe_customer_id: Optional[str],
    stripe_subscription_id: Optional[str],
    stripe_price_id: Optional[str],
    subscription_status: str,
    current_period_start: Optional[datetime],
    current_period_end: Optional[datetime],
) -> bool:
    """
    Sync user tier and limits from Stripe subscription data.

    This is the main function for updating user state from Stripe webhooks.
    It handles:
    - Mapping price_id to tier_id
    - Updating user's tier and limits
    - Resetting usage counters on billing period change

    Args:
        user_id: Internal user ID
        stripe_customer_id: Stripe customer ID (cus_xxx)
        stripe_subscription_id: Stripe subscription ID (sub_xxx)
        stripe_price_id: Stripe price ID (price_xxx)
        subscription_status: Stripe subscription status
        current_period_start: Billing period start
        current_period_end: Billing period end

    Returns:
        True if successful, False otherwise
    """
    pool = await get_pool()
    if not pool:
        logger.error('Database pool not available')
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                'SELECT sync_user_tier_from_stripe($1, $2, $3, $4, $5, $6, $7)',
                user_id,
                stripe_customer_id,
                stripe_subscription_id,
                stripe_price_id,
                subscription_status,
                current_period_start,
                current_period_end,
            )

        logger.info(
            f'Synced user {user_id} tier from Stripe: '
            f'price={stripe_price_id}, status={subscription_status}'
        )
        return True
    except Exception as e:
        logger.error(f'Failed to sync user tier from Stripe: {e}')
        return False


async def check_user_task_limits(user_id: str) -> Dict[str, Any]:
    """
    Check if user can create a new task.

    Returns:
        {
            'allowed': bool,
            'reason': str,
            'tasks_used': int,
            'tasks_limit': int,
            'running_count': int,
            'concurrency_limit': int
        }
    """
    pool = await get_pool()
    if not pool:
        return {
            'allowed': False,
            'reason': 'Database unavailable',
            'tasks_used': 0,
            'tasks_limit': 0,
            'running_count': 0,
            'concurrency_limit': 0,
        }

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM check_user_task_limits($1)', user_id
        )

        if row:
            return {
                'allowed': row['allowed'],
                'reason': row['reason'],
                'tasks_used': row['tasks_used'],
                'tasks_limit': row['tasks_limit'],
                'running_count': row['running_count'],
                'concurrency_limit': row['concurrency_limit'],
            }

        return {
            'allowed': False,
            'reason': 'User not found',
            'tasks_used': 0,
            'tasks_limit': 0,
            'running_count': 0,
            'concurrency_limit': 0,
        }


async def increment_user_task_usage(user_id: str) -> bool:
    """
    Increment user's task usage counter.

    Called after successfully enqueuing a task.

    Returns:
        True if within limits, False if limit exceeded
    """
    pool = await get_pool()
    if not pool:
        return False

    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            UPDATE users
            SET tasks_used_this_month = tasks_used_this_month + 1,
                updated_at = NOW()
            WHERE id = $1
            RETURNING tasks_used_this_month, tasks_limit
            """,
            user_id,
        )

        if result:
            return result['tasks_used_this_month'] <= result['tasks_limit']
        return False


# ========================================
# Stripe Webhook Handlers (for users)
# ========================================


async def handle_user_subscription_event(
    event_id: str,
    event_type: str,
    subscription: Dict[str, Any],
) -> bool:
    """
    Handle Stripe subscription events for users.

    Events handled:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted

    Returns:
        True if handled successfully, False otherwise
    """
    # Idempotency check
    if await is_event_processed(event_id):
        logger.info(f'Event {event_id} already processed, skipping')
        return True

    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')
    status = subscription.get('status', 'active')

    if not customer_id:
        logger.warning(f'Subscription event {event_id} missing customer ID')
        return False

    # Find user by Stripe customer ID
    user = await get_user_by_stripe_customer_id(customer_id)

    if not user:
        logger.warning(f'No user found for customer {customer_id}')
        # Mark as processed anyway to avoid retries
        await mark_event_processed(
            event_id, event_type, customer_id, subscription_id
        )
        return False

    # Extract price_id from subscription items
    price_id = None
    items = subscription.get('items', {}).get('data', [])
    if items:
        price_id = items[0].get('price', {}).get('id')

    # Extract billing period
    current_period_start = subscription.get('current_period_start')
    current_period_end = subscription.get('current_period_end')

    # Convert Unix timestamps to datetime
    if current_period_start and isinstance(current_period_start, int):
        current_period_start = datetime.fromtimestamp(
            current_period_start, tz=timezone.utc
        )
    if current_period_end and isinstance(current_period_end, int):
        current_period_end = datetime.fromtimestamp(
            current_period_end, tz=timezone.utc
        )

    # Handle deletion - clear subscription data
    if event_type == 'customer.subscription.deleted':
        status = 'canceled'
        subscription_id = None
        price_id = None

    # Sync user tier
    success = await sync_user_tier_from_stripe(
        user_id=user['id'],
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        stripe_price_id=price_id,
        subscription_status=status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
    )

    # Mark event as processed
    await mark_event_processed(
        event_id, event_type, customer_id, subscription_id, user['id']
    )

    logger.info(
        f'Handled {event_type} for user {user["id"]}: '
        f'tier synced, status={status}'
    )

    # Track conversion for marketing feedback loop
    if success and event_type in (
        'customer.subscription.created',
        'customer.subscription.updated',
    ):
        try:
            from .conversion_tracker import track_conversion

            conv_type = 'subscription'
            if event_type == 'customer.subscription.created':
                conv_type = 'subscription'
            await track_conversion(
                event_type=conv_type,
                email=user.get('email'),
                user_id=user['id'],
                order_id=subscription_id,
            )
        except Exception:
            pass  # Never break billing for conversion tracking

    return success


async def handle_checkout_completed_for_user(
    event_id: str,
    session: Dict[str, Any],
) -> bool:
    """
    Handle checkout.session.completed for user subscriptions.

    Links the Stripe customer to the user if needed, then syncs tier.
    """
    # Idempotency check
    if await is_event_processed(event_id):
        logger.info(f'Event {event_id} already processed, skipping')
        return True

    mode = session.get('mode')
    if mode != 'subscription':
        logger.debug(f'Ignoring checkout session with mode: {mode}')
        return True

    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    customer_email = session.get('customer_email')
    # client_reference_id could be user_id
    client_reference_id = session.get('client_reference_id')

    if not customer_id:
        logger.warning(f'Checkout session {event_id} missing customer ID')
        return False

    # Find user by: 1) client_reference_id (user_id), 2) customer_id, 3) email
    user = None

    if client_reference_id:
        from .user_auth import get_user_by_id

        user = await get_user_by_id(client_reference_id)

    if not user and customer_id:
        user = await get_user_by_stripe_customer_id(customer_id)

    if not user and customer_email:
        user = await get_user_by_email(customer_email)

    if not user:
        logger.warning(
            f'No user found for checkout - customer: {customer_id}, '
            f'email: {customer_email}, ref: {client_reference_id}'
        )
        await mark_event_processed(
            event_id, 'checkout.session.completed', customer_id, subscription_id
        )
        return False

    # Link customer_id to user if not already set
    pool = await get_pool()
    if pool and not user.get('stripe_customer_id'):
        async with pool.acquire() as conn:
            await conn.execute(
                'UPDATE users SET stripe_customer_id = $1, updated_at = NOW() WHERE id = $2',
                customer_id,
                user['id'],
            )
        logger.info(
            f'Linked Stripe customer {customer_id} to user {user["id"]}'
        )

    # Now fetch the subscription to get full details
    try:
        import stripe
        from .billing_service import get_billing_service

        billing = await get_billing_service()
        await billing._ensure_initialized()

        sub = stripe.Subscription.retrieve(subscription_id)

        # Extract details
        price_id = None
        items = sub.get('items', {}).get('data', [])
        if items:
            price_id = items[0].get('price', {}).get('id')

        current_period_start = sub.get('current_period_start')
        current_period_end = sub.get('current_period_end')

        if current_period_start and isinstance(current_period_start, int):
            current_period_start = datetime.fromtimestamp(
                current_period_start, tz=timezone.utc
            )
        if current_period_end and isinstance(current_period_end, int):
            current_period_end = datetime.fromtimestamp(
                current_period_end, tz=timezone.utc
            )

        success = await sync_user_tier_from_stripe(
            user_id=user['id'],
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            subscription_status=sub.get('status', 'active'),
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
    except Exception as e:
        logger.error(f'Failed to fetch subscription {subscription_id}: {e}')
        success = False

    await mark_event_processed(
        event_id,
        'checkout.session.completed',
        customer_id,
        subscription_id,
        user['id'],
    )

    # Track conversion for marketing feedback loop
    if success:
        try:
            from .conversion_tracker import track_conversion
            await track_conversion(
                event_type='subscription',
                email=user.get('email') or customer_email,
                user_id=user['id'],
                order_id=subscription_id,
            )
        except Exception:
            pass  # Never break billing for conversion tracking

    return success


# ========================================
# Convenience functions for checkout creation
# ========================================


async def create_user_checkout_session(
    user_id: str,
    tier_id: str,
    success_url: str,
    cancel_url: str,
) -> Optional[str]:
    """
    Create a Stripe Checkout session for a user to upgrade their tier.

    Args:
        user_id: User ID to upgrade
        tier_id: Target tier (pro, agency)
        success_url: URL to redirect on success
        cancel_url: URL to redirect on cancel

    Returns:
        Checkout session URL, or None on error
    """
    from .user_auth import get_user_by_id

    user = await get_user_by_id(user_id)
    if not user:
        logger.error(f'User {user_id} not found')
        return None

    pool = await get_pool()
    if not pool:
        return None

    # Get price_id for tier
    async with pool.acquire() as conn:
        price_row = await conn.fetchrow(
            """
            SELECT price_id FROM stripe_price_map
            WHERE tier_id = $1 AND is_active = TRUE
            LIMIT 1
            """,
            tier_id,
        )

    if not price_row:
        logger.error(f'No active price found for tier {tier_id}')
        return None

    price_id = price_row['price_id']

    try:
        import stripe
        from .billing_service import get_billing_service

        billing = await get_billing_service()
        await billing._ensure_initialized()

        # Create or get customer
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            customer = stripe.Customer.create(
                email=user['email'],
                name=f'{user.get("first_name", "")} {user.get("last_name", "")}'.strip()
                or None,
                metadata={'user_id': user_id},
            )
            customer_id = customer.id

            # Save customer_id to user
            async with pool.acquire() as conn:
                await conn.execute(
                    'UPDATE users SET stripe_customer_id = $1, updated_at = NOW() WHERE id = $2',
                    customer_id,
                    user_id,
                )

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            client_reference_id=user_id,
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                'metadata': {'user_id': user_id},
            },
        )

        logger.info(
            f'Created checkout session for user {user_id} to upgrade to {tier_id}'
        )
        return session.url

    except Exception as e:
        logger.error(f'Failed to create checkout session: {e}')
        return None


async def create_user_billing_portal_session(
    user_id: str,
    return_url: str,
) -> Optional[str]:
    """
    Create a Stripe Billing Portal session for user to manage subscription.

    Returns:
        Portal session URL, or None on error
    """
    from .user_auth import get_user_by_id

    user = await get_user_by_id(user_id)
    if not user:
        logger.error(f'User {user_id} not found')
        return None

    customer_id = user.get('stripe_customer_id')
    if not customer_id:
        logger.error(f'User {user_id} has no Stripe customer ID')
        return None

    try:
        import stripe
        from .billing_service import get_billing_service

        billing = await get_billing_service()
        await billing._ensure_initialized()

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return session.url

    except Exception as e:
        logger.error(f'Failed to create billing portal session: {e}')
        return None
