"""
Stripe Billing Service for A2A Server.

Provides subscription billing, customer management, and usage tracking
via Stripe. API key is fetched from Vault or environment variable.

Configuration (environment variables):
    STRIPE_API_KEY: Stripe API key (optional if using Vault)

Vault Configuration:
    Path: kv/codetether/stripe
    Key: api_key
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import stripe

from .vault_client import get_vault_client

logger = logging.getLogger(__name__)

# Thread pool for running sync Stripe operations
_executor = ThreadPoolExecutor(max_workers=4)

# Plan definitions
PLANS: Dict[str, Dict[str, Any]] = {
    'free': {
        'name': 'Free',
        'price_id': None,
        'limits': {
            'workers': 1,
            'codebases': 3,
            'tasks_per_month': 100,
        },
    },
    'pro': {
        'name': 'Pro',
        'price_id': 'price_1SoawKE8yr4fu4JjkHQA2Y2c',  # $49/month
        'limits': {
            'workers': 5,
            'codebases': 20,
            'tasks_per_month': 5000,
        },
    },
    'enterprise': {
        'name': 'Enterprise',
        'price_id': 'price_1SoawKE8yr4fu4Jj7iDEjsk6',  # $199/month
        'limits': {
            'workers': -1,  # Unlimited
            'codebases': -1,  # Unlimited
            'tasks_per_month': -1,  # Unlimited
        },
    },
}


class BillingServiceError(Exception):
    """Base exception for billing service errors."""

    pass


class CustomerNotFoundError(BillingServiceError):
    """Raised when a customer is not found."""

    pass


class SubscriptionNotFoundError(BillingServiceError):
    """Raised when a subscription is not found."""

    pass


class PlanNotFoundError(BillingServiceError):
    """Raised when a plan is not found."""

    pass


class BillingService:
    """
    Stripe billing service for subscription management.

    Supports both async operations (using thread pool executor for sync Stripe SDK)
    and provides customer, subscription, and usage management.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the billing service.

        Args:
            api_key: Optional Stripe API key. If not provided, will be
                    fetched from STRIPE_API_KEY env var or Vault.
        """
        self._api_key = api_key
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self) -> None:
        """Ensure the Stripe API key is loaded and configured."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            api_key = self._api_key

            # Try environment variable first
            if not api_key:
                api_key = os.environ.get('STRIPE_API_KEY')
                if api_key:
                    logger.info(
                        'Using Stripe API key from environment variable'
                    )

            # Fall back to Vault
            if not api_key:
                try:
                    vault_client = get_vault_client()
                    secret = await vault_client.read_secret(
                        'kv/codetether/stripe'
                    )
                    if secret and 'api_key' in secret:
                        api_key = secret['api_key']
                        logger.info('Using Stripe API key from Vault')
                    else:
                        logger.warning(
                            'Stripe API key not found in Vault at kv/codetether/stripe'
                        )
                except Exception as e:
                    logger.error(
                        f'Failed to fetch Stripe API key from Vault: {e}'
                    )

            if not api_key:
                raise BillingServiceError(
                    'Stripe API key not configured. Set STRIPE_API_KEY env var '
                    'or store in Vault at kv/codetether/stripe'
                )

            stripe.api_key = api_key
            self._api_key = api_key
            self._initialized = True
            logger.info('Stripe billing service initialized')

    async def _run_sync(self, func, *args, **kwargs) -> Any:
        """Run a synchronous function in the thread pool executor."""
        await self._ensure_initialized()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, lambda: func(*args, **kwargs)
        )

    # =========================================================================
    # Customer Management
    # =========================================================================

    async def create_customer(
        self, tenant_id: str, email: str, name: str
    ) -> str:
        """
        Create a new Stripe customer.

        Args:
            tenant_id: Internal tenant/user ID for reference
            email: Customer email address
            name: Customer display name

        Returns:
            Stripe customer ID
        """
        try:
            customer = await self._run_sync(
                stripe.Customer.create,
                email=email,
                name=name,
                metadata={'tenant_id': tenant_id},
            )
            logger.info(
                f'Created Stripe customer {customer.id} for tenant {tenant_id}'
            )
            return customer.id
        except stripe.StripeError as e:
            logger.error(f'Failed to create Stripe customer: {e}')
            raise BillingServiceError(f'Failed to create customer: {e}')

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer data dictionary
        """
        try:
            customer = await self._run_sync(
                stripe.Customer.retrieve, customer_id
            )
            if customer.deleted:
                raise CustomerNotFoundError(
                    f'Customer {customer_id} has been deleted'
                )
            return {
                'id': customer.id,
                'email': customer.email,
                'name': customer.name,
                'metadata': dict(customer.metadata)
                if customer.metadata
                else {},
                'created': customer.created,
                'default_source': customer.default_source,
            }
        except stripe.InvalidRequestError as e:
            if 'No such customer' in str(e):
                raise CustomerNotFoundError(f'Customer {customer_id} not found')
            raise BillingServiceError(f'Failed to get customer: {e}')
        except stripe.StripeError as e:
            logger.error(f'Failed to get customer {customer_id}: {e}')
            raise BillingServiceError(f'Failed to get customer: {e}')

    async def update_customer(
        self,
        customer_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update customer details.

        Args:
            customer_id: Stripe customer ID
            email: New email address (optional)
            name: New display name (optional)

        Returns:
            Updated customer data dictionary
        """
        try:
            update_params = {}
            if email is not None:
                update_params['email'] = email
            if name is not None:
                update_params['name'] = name

            if not update_params:
                return await self.get_customer(customer_id)

            customer = await self._run_sync(
                stripe.Customer.modify, customer_id, **update_params
            )
            logger.info(f'Updated Stripe customer {customer_id}')
            return {
                'id': customer.id,
                'email': customer.email,
                'name': customer.name,
                'metadata': dict(customer.metadata)
                if customer.metadata
                else {},
                'created': customer.created,
            }
        except stripe.InvalidRequestError as e:
            if 'No such customer' in str(e):
                raise CustomerNotFoundError(f'Customer {customer_id} not found')
            raise BillingServiceError(f'Failed to update customer: {e}')
        except stripe.StripeError as e:
            logger.error(f'Failed to update customer {customer_id}: {e}')
            raise BillingServiceError(f'Failed to update customer: {e}')

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: int = 14,
    ) -> Dict[str, Any]:
        """
        Create a new subscription for a customer.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the plan
            trial_days: Number of trial days (default 14)

        Returns:
            Subscription data dictionary
        """
        try:
            subscription_params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
            }

            if trial_days > 0:
                subscription_params['trial_period_days'] = trial_days

            subscription = await self._run_sync(
                stripe.Subscription.create, **subscription_params
            )
            logger.info(
                f'Created subscription {subscription.id} for customer {customer_id}'
            )
            return self._format_subscription(subscription)
        except stripe.InvalidRequestError as e:
            if 'No such customer' in str(e):
                raise CustomerNotFoundError(f'Customer {customer_id} not found')
            raise BillingServiceError(f'Failed to create subscription: {e}')
        except stripe.StripeError as e:
            logger.error(f'Failed to create subscription: {e}')
            raise BillingServiceError(f'Failed to create subscription: {e}')

    async def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of billing period.
                          If False, cancel immediately.

        Returns:
            Updated subscription data dictionary
        """
        try:
            if at_period_end:
                subscription = await self._run_sync(
                    stripe.Subscription.modify,
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                subscription = await self._run_sync(
                    stripe.Subscription.cancel, subscription_id
                )
            logger.info(
                f'Cancelled subscription {subscription_id} '
                f'(at_period_end={at_period_end})'
            )
            return self._format_subscription(subscription)
        except stripe.InvalidRequestError as e:
            if 'No such subscription' in str(e):
                raise SubscriptionNotFoundError(
                    f'Subscription {subscription_id} not found'
                )
            raise BillingServiceError(f'Failed to cancel subscription: {e}')
        except stripe.StripeError as e:
            logger.error(
                f'Failed to cancel subscription {subscription_id}: {e}'
            )
            raise BillingServiceError(f'Failed to cancel subscription: {e}')

    async def update_subscription(
        self, subscription_id: str, new_price_id: str
    ) -> Dict[str, Any]:
        """
        Update a subscription to a new plan/price.

        Args:
            subscription_id: Stripe subscription ID
            new_price_id: New Stripe price ID

        Returns:
            Updated subscription data dictionary
        """
        try:
            # Get current subscription to find the item ID
            subscription = await self._run_sync(
                stripe.Subscription.retrieve, subscription_id
            )

            if not subscription.items.data:
                raise BillingServiceError('Subscription has no items')

            item_id = subscription.items.data[0].id

            # Update the subscription item with new price
            updated_subscription = await self._run_sync(
                stripe.Subscription.modify,
                subscription_id,
                items=[{'id': item_id, 'price': new_price_id}],
                proration_behavior='create_prorations',
            )
            logger.info(
                f'Updated subscription {subscription_id} to price {new_price_id}'
            )
            return self._format_subscription(updated_subscription)
        except stripe.InvalidRequestError as e:
            if 'No such subscription' in str(e):
                raise SubscriptionNotFoundError(
                    f'Subscription {subscription_id} not found'
                )
            raise BillingServiceError(f'Failed to update subscription: {e}')
        except stripe.StripeError as e:
            logger.error(
                f'Failed to update subscription {subscription_id}: {e}'
            )
            raise BillingServiceError(f'Failed to update subscription: {e}')

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription data dictionary
        """
        try:
            subscription = await self._run_sync(
                stripe.Subscription.retrieve, subscription_id
            )
            return self._format_subscription(subscription)
        except stripe.InvalidRequestError as e:
            if 'No such subscription' in str(e):
                raise SubscriptionNotFoundError(
                    f'Subscription {subscription_id} not found'
                )
            raise BillingServiceError(f'Failed to get subscription: {e}')
        except stripe.StripeError as e:
            logger.error(f'Failed to get subscription {subscription_id}: {e}')
            raise BillingServiceError(f'Failed to get subscription: {e}')

    def _format_subscription(
        self, subscription: stripe.Subscription
    ) -> Dict[str, Any]:
        """Format a Stripe subscription object to a dictionary."""
        items = []
        for item in subscription.items.data:
            items.append(
                {
                    'id': item.id,
                    'price_id': item.price.id,
                    'product_id': item.price.product,
                    'quantity': item.quantity,
                }
            )

        return {
            'id': subscription.id,
            'customer_id': subscription.customer,
            'status': subscription.status,
            'current_period_start': subscription.current_period_start,
            'current_period_end': subscription.current_period_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'canceled_at': subscription.canceled_at,
            'trial_start': subscription.trial_start,
            'trial_end': subscription.trial_end,
            'items': items,
            'metadata': dict(subscription.metadata)
            if subscription.metadata
            else {},
        }

    # =========================================================================
    # Billing Portal
    # =========================================================================

    async def create_billing_portal_session(
        self, customer_id: str, return_url: str
    ) -> str:
        """
        Create a Stripe Billing Portal session.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after the session

        Returns:
            Portal session URL
        """
        try:
            session = await self._run_sync(
                stripe.billing_portal.Session.create,
                customer=customer_id,
                return_url=return_url,
            )
            logger.info(
                f'Created billing portal session for customer {customer_id}'
            )
            return session.url
        except stripe.InvalidRequestError as e:
            if 'No such customer' in str(e):
                raise CustomerNotFoundError(f'Customer {customer_id} not found')
            raise BillingServiceError(
                f'Failed to create billing portal session: {e}'
            )
        except stripe.StripeError as e:
            logger.error(
                f'Failed to create billing portal session for {customer_id}: {e}'
            )
            raise BillingServiceError(
                f'Failed to create billing portal session: {e}'
            )

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Create a Stripe Checkout session for subscription purchase.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the plan
            success_url: URL to redirect on successful checkout
            cancel_url: URL to redirect on cancelled checkout

        Returns:
            Checkout session URL
        """
        try:
            session = await self._run_sync(
                stripe.checkout.Session.create,
                customer=customer_id,
                mode='subscription',
                line_items=[{'price': price_id, 'quantity': 1}],
                success_url=success_url,
                cancel_url=cancel_url,
            )
            logger.info(
                f'Created checkout session for customer {customer_id}, '
                f'price {price_id}'
            )
            return session.url
        except stripe.InvalidRequestError as e:
            if 'No such customer' in str(e):
                raise CustomerNotFoundError(f'Customer {customer_id} not found')
            raise BillingServiceError(f'Failed to create checkout session: {e}')
        except stripe.StripeError as e:
            logger.error(
                f'Failed to create checkout session for {customer_id}: {e}'
            )
            raise BillingServiceError(f'Failed to create checkout session: {e}')

    # =========================================================================
    # Plan Configuration
    # =========================================================================

    def get_plan(self, plan_name: str) -> Dict[str, Any]:
        """
        Get plan configuration by name.

        Args:
            plan_name: Plan name (free, pro, enterprise)

        Returns:
            Plan configuration dictionary
        """
        plan = PLANS.get(plan_name.lower())
        if not plan:
            raise PlanNotFoundError(f'Plan {plan_name} not found')
        return plan.copy()

    def get_plan_limits(self, plan_name: str) -> Dict[str, int]:
        """
        Get plan limits by name.

        Args:
            plan_name: Plan name (free, pro, enterprise)

        Returns:
            Plan limits dictionary
        """
        plan = self.get_plan(plan_name)
        return plan['limits'].copy()

    def list_plans(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available plans.

        Returns:
            Dictionary of all plans
        """
        return {name: plan.copy() for name, plan in PLANS.items()}

    # =========================================================================
    # Usage Tracking
    # =========================================================================

    async def report_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Report metered usage for a subscription item.

        Args:
            subscription_item_id: Stripe subscription item ID
            quantity: Usage quantity to report
            timestamp: Unix timestamp for the usage (default: current time)

        Returns:
            Usage record data dictionary
        """
        try:
            usage_params = {
                'quantity': quantity,
                'action': 'increment',
            }
            if timestamp:
                usage_params['timestamp'] = timestamp
            else:
                usage_params['timestamp'] = int(time.time())

            usage_record = await self._run_sync(
                stripe.SubscriptionItem.create_usage_record,
                subscription_item_id,
                **usage_params,
            )
            logger.info(
                f'Reported usage for subscription item {subscription_item_id}: '
                f'{quantity} units'
            )
            return {
                'id': usage_record.id,
                'quantity': usage_record.quantity,
                'timestamp': usage_record.timestamp,
                'subscription_item': usage_record.subscription_item,
            }
        except stripe.InvalidRequestError as e:
            raise BillingServiceError(f'Failed to report usage: {e}')
        except stripe.StripeError as e:
            logger.error(
                f'Failed to report usage for {subscription_item_id}: {e}'
            )
            raise BillingServiceError(f'Failed to report usage: {e}')

    async def get_usage(
        self,
        subscription_item_id: str,
        start_date: int,
        end_date: int,
    ) -> Dict[str, Any]:
        """
        Get usage records for a subscription item.

        Args:
            subscription_item_id: Stripe subscription item ID
            start_date: Unix timestamp for start of period
            end_date: Unix timestamp for end of period

        Returns:
            Usage summary dictionary
        """
        try:
            # Use usage record summaries for the period
            summaries = await self._run_sync(
                stripe.SubscriptionItem.list_usage_record_summaries,
                subscription_item_id,
            )

            total_usage = 0
            records = []
            for summary in summaries.data:
                # Filter by date range
                if start_date <= summary.period.start <= end_date:
                    total_usage += summary.total_usage
                    records.append(
                        {
                            'id': summary.id,
                            'total_usage': summary.total_usage,
                            'period_start': summary.period.start,
                            'period_end': summary.period.end,
                        }
                    )

            return {
                'subscription_item_id': subscription_item_id,
                'start_date': start_date,
                'end_date': end_date,
                'total_usage': total_usage,
                'records': records,
            }
        except stripe.InvalidRequestError as e:
            raise BillingServiceError(f'Failed to get usage: {e}')
        except stripe.StripeError as e:
            logger.error(f'Failed to get usage for {subscription_item_id}: {e}')
            raise BillingServiceError(f'Failed to get usage: {e}')


# Singleton instance
_billing_service: Optional[BillingService] = None


def get_billing_service() -> BillingService:
    """Get the singleton billing service instance."""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service
