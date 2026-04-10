"""
Token Billing Service for Multi-Tenant AI Usage.

Records per-request token consumption, calculates cost using the model_pricing
registry, deducts from tenant balances, and reports metered usage to Stripe.

Cost precision: micro-cents (10,000 micro-cents = 1 cent = $0.01)

Billing models supported:
- subscription: flat-rate, usage tracked but not billed per-token
- prepaid: credits deducted per request, auto-reload optional
- metered: usage reported to Stripe for variable invoicing
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import get_pool

logger = logging.getLogger(__name__)

# Micro-cent conversion helpers
MICRO_CENTS_PER_CENT = 10_000
MICRO_CENTS_PER_DOLLAR = 1_000_000


@dataclass
class TokenCounts:
    """Token counts from an LLM response."""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TokenCounts':
        """Parse token counts from various response formats."""
        if not data:
            return cls()

        def _get(keys):
            """Get first non-None value from multiple possible keys."""
            for k in keys:
                v = data.get(k)
                if v is not None:
                    return v
            return 0

        # Handle nested 'cache' object (agent format)
        cache = data.get('cache')
        if isinstance(cache, dict):
            cache_read = cache.get('read') or 0
            cache_write = cache.get('write') or 0
        else:
            cache_read = _get(['cache_read_tokens', 'cacheReadTokens'])
            cache_write = _get(['cache_write_tokens', 'cacheWriteTokens'])

        return cls(
            input_tokens=_get(['input', 'input_tokens', 'inputTokens']),
            output_tokens=_get(['output', 'output_tokens', 'outputTokens']),
            reasoning_tokens=_get(['reasoning', 'reasoning_tokens', 'reasoningTokens']),
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.reasoning_tokens


@dataclass
class UsageRecord:
    """Result of recording token usage."""
    usage_id: int
    cost_micro_cents: int
    remaining_balance_micro_cents: int
    over_limit: bool

    @property
    def cost_dollars(self) -> float:
        return self.cost_micro_cents / MICRO_CENTS_PER_DOLLAR

    @property
    def cost_cents(self) -> float:
        return self.cost_micro_cents / MICRO_CENTS_PER_CENT


@dataclass
class BudgetCheck:
    """Result of checking token budget before a request."""
    allowed: bool
    reason: str
    balance_micro_cents: int
    monthly_spend_micro_cents: int
    monthly_limit_cents: Optional[int]
    billing_model: str

    @property
    def monthly_spend_dollars(self) -> float:
        return self.monthly_spend_micro_cents / MICRO_CENTS_PER_DOLLAR


class TokenBillingService:
    """
    Core service for multi-tenant token billing.

    Handles:
    - Recording token usage per tenant/user
    - Calculating costs from model_pricing registry
    - Pre-request budget checks
    - Balance deductions (prepaid model)
    - Stripe metered usage reporting
    - Usage aggregation queries
    """

    # =========================================================================
    # Core: Record Usage
    # =========================================================================

    async def record_usage(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        tokens: TokenCounts,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Optional[UsageRecord]:
        """
        Record token usage for a tenant and deduct from balance if applicable.

        This is the main entry point called after every LLM response.

        Returns:
            UsageRecord with cost and balance info, or None on error
        """
        if tokens.total == 0 and tokens.cache_read_tokens == 0:
            return None

        pool = await get_pool()
        if not pool:
            logger.error('Database pool not available for token billing')
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT * FROM record_token_usage($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)',
                    tenant_id,
                    user_id,
                    provider,
                    model,
                    tokens.input_tokens,
                    tokens.output_tokens,
                    tokens.reasoning_tokens,
                    tokens.cache_read_tokens,
                    tokens.cache_write_tokens,
                    session_id,
                    task_id,
                    message_id,
                )

            if row:
                record = UsageRecord(
                    usage_id=row['usage_id'],
                    cost_micro_cents=row['cost_micro_cents'],
                    remaining_balance_micro_cents=row['remaining_balance_micro_cents'],
                    over_limit=row['over_limit'],
                )

                logger.info(
                    f'Token usage recorded: tenant={tenant_id} '
                    f'model={provider}/{model} '
                    f'tokens={tokens.total} '
                    f'cost=${record.cost_dollars:.6f} '
                    f'balance=${record.remaining_balance_micro_cents / MICRO_CENTS_PER_DOLLAR:.2f}'
                )

                if record.over_limit:
                    logger.warning(
                        f'Tenant {tenant_id} exceeded monthly spending limit'
                    )

                return record

            return None

        except Exception as e:
            logger.error(f'Failed to record token usage: {e}')
            return None

    # =========================================================================
    # Pre-request Budget Check
    # =========================================================================

    async def check_budget(
        self,
        tenant_id: str,
        estimated_tokens: int = 10000,
    ) -> BudgetCheck:
        """
        Check if a tenant can afford to make an LLM request.

        Call this before sending a request to the LLM to enforce limits.

        Args:
            tenant_id: Tenant to check
            estimated_tokens: Rough estimate of total tokens for the request

        Returns:
            BudgetCheck with allowed=True/False and reason
        """
        pool = await get_pool()
        if not pool:
            return BudgetCheck(
                allowed=False,
                reason='Database unavailable',
                balance_micro_cents=0,
                monthly_spend_micro_cents=0,
                monthly_limit_cents=None,
                billing_model='unknown',
            )

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT * FROM check_token_budget($1, $2)',
                    tenant_id,
                    estimated_tokens,
                )

            if row:
                return BudgetCheck(
                    allowed=row['allowed'],
                    reason=row['reason'],
                    balance_micro_cents=row['balance_micro_cents'],
                    monthly_spend_micro_cents=row['monthly_spend_micro_cents'],
                    monthly_limit_cents=row['monthly_limit_cents'],
                    billing_model=row['billing_model'],
                )

            return BudgetCheck(
                allowed=False,
                reason='Tenant not found',
                balance_micro_cents=0,
                monthly_spend_micro_cents=0,
                monthly_limit_cents=None,
                billing_model='unknown',
            )

        except Exception as e:
            logger.error(f'Failed to check token budget: {e}')
            # Fail open for subscription tenants, fail closed for prepaid
            return BudgetCheck(
                allowed=True,
                reason=f'Budget check failed: {e}',
                balance_micro_cents=0,
                monthly_spend_micro_cents=0,
                monthly_limit_cents=None,
                billing_model='unknown',
            )

    # =========================================================================
    # Credit Management
    # =========================================================================

    async def add_credits(
        self,
        tenant_id: str,
        amount_cents: int,
        reason: str = 'manual',
    ) -> Optional[int]:
        """
        Add credits to a tenant's token balance.

        Args:
            tenant_id: Tenant to credit
            amount_cents: Amount in cents (e.g., 2000 = $20.00)
            reason: Reason for credit (audit trail)

        Returns:
            New balance in micro-cents, or None on error
        """
        pool = await get_pool()
        if not pool:
            return None

        try:
            async with pool.acquire() as conn:
                new_balance = await conn.fetchval(
                    'SELECT add_tenant_credits($1, $2, $3)',
                    tenant_id,
                    amount_cents,
                    reason,
                )

            logger.info(
                f'Added ${amount_cents / 100:.2f} credits to tenant {tenant_id}, '
                f'new balance: ${(new_balance or 0) / MICRO_CENTS_PER_DOLLAR:.2f}'
            )
            return new_balance

        except Exception as e:
            logger.error(f'Failed to add credits: {e}')
            return None

    # =========================================================================
    # Usage Queries
    # =========================================================================

    async def get_tenant_usage_summary(
        self,
        tenant_id: str,
        month: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated token usage for a tenant for a given month.

        Returns summary with total tokens, cost, and per-model breakdown.
        """
        pool = await get_pool()
        if not pool:
            return {'error': 'Database unavailable'}

        if month is None:
            month = datetime.now(tz=timezone.utc)

        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        try:
            async with pool.acquire() as conn:
                # Aggregate totals
                totals = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as request_count,
                        COALESCE(SUM(input_tokens), 0) as total_input,
                        COALESCE(SUM(output_tokens), 0) as total_output,
                        COALESCE(SUM(reasoning_tokens), 0) as total_reasoning,
                        COALESCE(SUM(cache_read_tokens), 0) as total_cache_read,
                        COALESCE(SUM(cache_write_tokens), 0) as total_cache_write,
                        COALESCE(SUM(cost_micro_cents), 0) as total_cost_micro_cents,
                        COALESCE(SUM(base_cost_micro_cents), 0) as total_base_cost_micro_cents
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= $2
                      AND created_at < ($2 + INTERVAL '1 month')
                    """,
                    tenant_id,
                    month_start,
                )

                # Per-model breakdown
                models = await conn.fetch(
                    """
                    SELECT
                        provider, model,
                        COUNT(*) as request_count,
                        SUM(input_tokens + output_tokens + COALESCE(reasoning_tokens, 0)) as total_tokens,
                        SUM(cost_micro_cents) as cost_micro_cents
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= $2
                      AND created_at < ($2 + INTERVAL '1 month')
                    GROUP BY provider, model
                    ORDER BY cost_micro_cents DESC
                    """,
                    tenant_id,
                    month_start,
                )

                # Get tenant balance
                balance_row = await conn.fetchrow(
                    'SELECT token_balance_micro_cents, billing_model, monthly_spend_limit_cents FROM tenants WHERE id = $1',
                    tenant_id,
                )

            total_cost_mc = totals['total_cost_micro_cents'] if totals else 0

            return {
                'tenant_id': tenant_id,
                'month': month_start.isoformat(),
                'billing_model': balance_row['billing_model'] if balance_row else 'subscription',
                'balance_dollars': (balance_row['token_balance_micro_cents'] or 0) / MICRO_CENTS_PER_DOLLAR if balance_row else 0,
                'monthly_limit_dollars': (balance_row['monthly_spend_limit_cents'] or 0) / 100 if balance_row and balance_row['monthly_spend_limit_cents'] else None,
                'totals': {
                    'request_count': totals['request_count'] if totals else 0,
                    'input_tokens': totals['total_input'] if totals else 0,
                    'output_tokens': totals['total_output'] if totals else 0,
                    'reasoning_tokens': totals['total_reasoning'] if totals else 0,
                    'cache_read_tokens': totals['total_cache_read'] if totals else 0,
                    'cache_write_tokens': totals['total_cache_write'] if totals else 0,
                    'cost_dollars': total_cost_mc / MICRO_CENTS_PER_DOLLAR,
                    'base_cost_dollars': (totals['total_base_cost_micro_cents'] if totals else 0) / MICRO_CENTS_PER_DOLLAR,
                },
                'by_model': [
                    {
                        'provider': row['provider'],
                        'model': row['model'],
                        'request_count': row['request_count'],
                        'total_tokens': row['total_tokens'],
                        'cost_dollars': row['cost_micro_cents'] / MICRO_CENTS_PER_DOLLAR,
                    }
                    for row in models
                ],
            }

        except Exception as e:
            logger.error(f'Failed to get usage summary: {e}')
            return {'error': str(e)}

    async def get_recent_usage(
        self,
        tenant_id: str,
        limit: int = 50,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent individual usage records for a tenant."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                query = """
                    SELECT
                        id, tenant_id, user_id, provider, model,
                        input_tokens, output_tokens, reasoning_tokens,
                        cache_read_tokens, cache_write_tokens,
                        cost_micro_cents, session_id, task_id, created_at
                    FROM token_usage
                    WHERE tenant_id = $1
                """
                params: list = [tenant_id]

                if user_id:
                    query += ' AND user_id = $2'
                    params.append(user_id)

                query += ' ORDER BY created_at DESC LIMIT $' + str(len(params) + 1)
                params.append(limit)

                rows = await conn.fetch(query, *params)

            return [
                {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'provider': row['provider'],
                    'model': row['model'],
                    'input_tokens': row['input_tokens'],
                    'output_tokens': row['output_tokens'],
                    'reasoning_tokens': row['reasoning_tokens'],
                    'cache_read_tokens': row['cache_read_tokens'],
                    'cache_write_tokens': row['cache_write_tokens'],
                    'cost_dollars': row['cost_micro_cents'] / MICRO_CENTS_PER_DOLLAR,
                    'session_id': row['session_id'],
                    'task_id': row['task_id'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f'Failed to get recent usage: {e}')
            return []

    # =========================================================================
    # Model Pricing Management
    # =========================================================================

    async def get_model_pricing(
        self,
        provider: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get all active model pricing, optionally filtered by provider."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                if provider:
                    rows = await conn.fetch(
                        'SELECT * FROM model_pricing WHERE is_active = TRUE AND provider = $1 ORDER BY provider, model',
                        provider,
                    )
                else:
                    rows = await conn.fetch(
                        'SELECT * FROM model_pricing WHERE is_active = TRUE ORDER BY provider, model'
                    )

            return [
                {
                    'id': row['id'],
                    'provider': row['provider'],
                    'model': row['model'],
                    'input_cost_per_m': float(row['input_cost_per_m']),
                    'output_cost_per_m': float(row['output_cost_per_m']),
                    'cache_read_cost_per_m': float(row['cache_read_cost_per_m'] or 0),
                    'cache_write_cost_per_m': float(row['cache_write_cost_per_m'] or 0),
                    'reasoning_cost_per_m': float(row['reasoning_cost_per_m']) if row['reasoning_cost_per_m'] else None,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f'Failed to get model pricing: {e}')
            return []

    async def upsert_model_pricing(
        self,
        provider: str,
        model: str,
        input_cost_per_m: float,
        output_cost_per_m: float,
        cache_read_cost_per_m: float = 0,
        cache_write_cost_per_m: float = 0,
        reasoning_cost_per_m: Optional[float] = None,
    ) -> bool:
        """Add or update pricing for a model."""
        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO model_pricing (provider, model, input_cost_per_m, output_cost_per_m,
                        cache_read_cost_per_m, cache_write_cost_per_m, reasoning_cost_per_m)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (provider, model) DO UPDATE SET
                        input_cost_per_m = EXCLUDED.input_cost_per_m,
                        output_cost_per_m = EXCLUDED.output_cost_per_m,
                        cache_read_cost_per_m = EXCLUDED.cache_read_cost_per_m,
                        cache_write_cost_per_m = EXCLUDED.cache_write_cost_per_m,
                        reasoning_cost_per_m = EXCLUDED.reasoning_cost_per_m,
                        updated_at = NOW()
                    """,
                    provider, model, input_cost_per_m, output_cost_per_m,
                    cache_read_cost_per_m, cache_write_cost_per_m, reasoning_cost_per_m,
                )
            logger.info(f'Upserted pricing for {provider}/{model}')
            return True

        except Exception as e:
            logger.error(f'Failed to upsert model pricing: {e}')
            return False

    # =========================================================================
    # Stripe Metered Billing Sync
    # =========================================================================

    async def report_unreported_usage_to_stripe(
        self,
        tenant_id: str,
    ) -> int:
        """
        Report unreported token usage to Stripe for metered billing.

        Called periodically (e.g., hourly) for tenants on the 'metered' billing model.
        Groups unreported usage and reports total to Stripe as metered usage.

        Returns:
            Number of usage records reported
        """
        pool = await get_pool()
        if not pool:
            return 0

        try:
            async with pool.acquire() as conn:
                # Get tenant's Stripe metered item ID
                tenant = await conn.fetchrow(
                    'SELECT stripe_metered_item_id, billing_model FROM tenants WHERE id = $1',
                    tenant_id,
                )

                if not tenant or tenant['billing_model'] != 'metered':
                    return 0

                metered_item_id = tenant['stripe_metered_item_id']
                if not metered_item_id:
                    logger.warning(
                        f'Tenant {tenant_id} on metered billing but no stripe_metered_item_id'
                    )
                    return 0

                # Get unreported usage total
                unreported = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as record_count,
                        COALESCE(SUM(cost_micro_cents), 0) as total_micro_cents
                    FROM token_usage
                    WHERE tenant_id = $1 AND stripe_reported = FALSE
                    """,
                    tenant_id,
                )

                if not unreported or unreported['record_count'] == 0:
                    return 0

                # Convert micro-cents to cents (Stripe quantity)
                total_cents = unreported['total_micro_cents'] // MICRO_CENTS_PER_CENT

                if total_cents <= 0:
                    return 0

                # Report to Stripe
                from .billing_service import get_billing_service
                billing = get_billing_service()
                await billing.report_usage(
                    subscription_item_id=metered_item_id,
                    quantity=total_cents,
                )

                # Mark as reported
                await conn.execute(
                    """
                    UPDATE token_usage
                    SET stripe_reported = TRUE, stripe_reported_at = NOW()
                    WHERE tenant_id = $1 AND stripe_reported = FALSE
                    """,
                    tenant_id,
                )

                record_count = unreported['record_count']
                logger.info(
                    f'Reported {record_count} usage records (${total_cents / 100:.2f}) '
                    f'to Stripe for tenant {tenant_id}'
                )
                return record_count

        except Exception as e:
            logger.error(f'Failed to report usage to Stripe: {e}')
            return 0

    # =========================================================================
    # Tenant Configuration
    # =========================================================================

    async def set_billing_model(
        self,
        tenant_id: str,
        billing_model: str,
        monthly_limit_cents: Optional[int] = None,
        monthly_alert_cents: Optional[int] = None,
        markup_percent: float = 0,
    ) -> bool:
        """Configure billing model for a tenant."""
        if billing_model not in ('subscription', 'prepaid', 'metered'):
            logger.error(f'Invalid billing model: {billing_model}')
            return False

        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tenants SET
                        billing_model = $2,
                        monthly_spend_limit_cents = $3,
                        monthly_spend_alert_cents = $4,
                        token_markup_percent = $5
                    WHERE id = $1
                    """,
                    tenant_id,
                    billing_model,
                    monthly_limit_cents,
                    monthly_alert_cents,
                    markup_percent,
                )
            logger.info(
                f'Set billing model for tenant {tenant_id}: '
                f'model={billing_model}, limit=${(monthly_limit_cents or 0) / 100:.0f}'
            )
            return True

        except Exception as e:
            logger.error(f'Failed to set billing model: {e}')
            return False


# Singleton instance
_token_billing: Optional[TokenBillingService] = None


def get_token_billing_service() -> TokenBillingService:
    """Get the singleton token billing service instance."""
    global _token_billing
    if _token_billing is None:
        _token_billing = TokenBillingService()
    return _token_billing
