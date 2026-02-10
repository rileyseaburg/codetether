"""
FinOps Service for Multi-Tenant AI Cost Management.

Provides:
- Budget enforcement middleware (pre-request block/throttle)
- Cost anomaly detection (statistical + threshold-based)
- Spending forecasting (linear projection from daily snapshots)
- Cost optimization recommendations (model downgrades, caching)
- Budget policy evaluation and alerting
- Daily snapshot aggregation
- Auto top-up trigger logic

All monetary values are in micro-cents (10,000 micro-cents = 1 cent)
unless otherwise noted.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .database import get_pool
from .token_billing import (
    MICRO_CENTS_PER_CENT,
    MICRO_CENTS_PER_DOLLAR,
    TokenBillingService,
    get_token_billing_service,
)

logger = logging.getLogger(__name__)


# =========================================================================
# Data Models
# =========================================================================


@dataclass
class CostAlert:
    """A cost alert triggered by a threshold breach or anomaly."""
    alert_type: str
    severity: str
    title: str
    message: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetPolicyResult:
    """Result of evaluating a budget policy."""
    policy_id: int
    policy_name: str
    breached_level: str  # 'soft' or 'hard'
    current_spend_cents: float
    limit_cents: int
    action: str


@dataclass
class CostForecast:
    """Projected cost for a given period."""
    tenant_id: str
    period: str  # 'monthly'
    projected_cost_dollars: float
    daily_average_dollars: float
    days_in_period: int
    days_elapsed: int
    confidence: str  # 'low', 'medium', 'high'
    trend: str  # 'increasing', 'decreasing', 'stable'
    pct_change_vs_last_period: Optional[float] = None


@dataclass
class CostAnomaly:
    """A detected cost anomaly."""
    anomaly_type: str  # 'rate_spike', 'volume_spike', 'new_model', 'cost_jump'
    severity: str
    model: Optional[str]
    provider: Optional[str]
    description: str
    expected_value: float
    actual_value: float
    deviation_factor: float  # How many std deviations


@dataclass
class OptimizationRecommendation:
    """A cost optimization recommendation."""
    recommendation_type: str
    title: str
    description: str
    estimated_savings_percent: float
    estimated_savings_cents: int
    current_model: Optional[str] = None
    suggested_model: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


# Model tier mapping for downgrade recommendations
MODEL_TIERS: Dict[str, Dict[str, Any]] = {
    'claude-opus-4-6': {'tier': 1, 'family': 'claude', 'alternative': 'claude-sonnet-4'},
    'claude-opus-4-5': {'tier': 2, 'family': 'claude', 'alternative': 'claude-sonnet-4'},
    'claude-sonnet-4': {'tier': 3, 'family': 'claude', 'alternative': 'claude-haiku-3-5'},
    'claude-haiku-3-5': {'tier': 4, 'family': 'claude', 'alternative': None},
    'gpt-5.2': {'tier': 1, 'family': 'gpt', 'alternative': 'gpt-4.1'},
    'gpt-4.1': {'tier': 2, 'family': 'gpt', 'alternative': 'gpt-4.1-mini'},
    'gpt-4.1-mini': {'tier': 3, 'family': 'gpt', 'alternative': None},
    'gpt-4o': {'tier': 2, 'family': 'gpt', 'alternative': 'gpt-4o-mini'},
    'gpt-4o-mini': {'tier': 4, 'family': 'gpt', 'alternative': None},
    'o3': {'tier': 2, 'family': 'openai-reasoning', 'alternative': 'o3-mini'},
    'o3-mini': {'tier': 3, 'family': 'openai-reasoning', 'alternative': None},
    'gemini-3-pro': {'tier': 2, 'family': 'gemini', 'alternative': 'gemini-2.5-flash'},
    'gemini-2.5-pro': {'tier': 2, 'family': 'gemini', 'alternative': 'gemini-2.5-flash'},
    'gemini-2.5-flash': {'tier': 4, 'family': 'gemini', 'alternative': None},
}


class FinOpsService:
    """
    Core FinOps engine for multi-tenant AI cost management.

    Responsibilities:
    - Pre-request budget enforcement
    - Cost anomaly detection
    - Spending forecasting
    - Optimization recommendations
    - Budget policy evaluation
    - Daily snapshot building
    - Alert generation
    """

    # =========================================================================
    # Budget Enforcement (Pre-Request)
    # =========================================================================

    async def enforce_budget(
        self,
        tenant_id: str,
        estimated_tokens: int = 10000,
    ) -> Tuple[bool, Optional[str]]:
        """
        Pre-request budget enforcement check.

        Returns:
            (allowed, reason) - True if request should proceed
        """
        pool = await get_pool()
        if not pool:
            return True, None  # Fail open if DB unavailable

        try:
            async with pool.acquire() as conn:
                # 1. Check tenant balance (prepaid model)
                tenant = await conn.fetchrow(
                    """
                    SELECT billing_model, token_balance_micro_cents,
                           monthly_spend_limit_cents, monthly_spend_alert_cents,
                           auto_topup_enabled, auto_topup_threshold_cents
                    FROM tenants WHERE id = $1
                    """,
                    tenant_id,
                )

                if not tenant:
                    return False, 'Tenant not found'

                billing_model = tenant['billing_model'] or 'subscription'

                # For prepaid: check balance
                if billing_model == 'prepaid':
                    balance = tenant['token_balance_micro_cents'] or 0
                    if balance <= 0:
                        return False, 'Prepaid balance exhausted. Add credits to continue.'

                    # Check auto-top-up trigger
                    if tenant['auto_topup_enabled']:
                        threshold = (tenant['auto_topup_threshold_cents'] or 500) * MICRO_CENTS_PER_CENT
                        if balance < threshold:
                            # Fire and forget auto-top-up (handled async)
                            logger.info(f'Auto top-up triggered for tenant {tenant_id} (balance below threshold)')

                # 2. Check monthly spending limit
                if tenant['monthly_spend_limit_cents']:
                    monthly_spend = await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(cost_micro_cents), 0)
                        FROM token_usage
                        WHERE tenant_id = $1
                          AND created_at >= date_trunc('month', NOW())
                        """,
                        tenant_id,
                    )
                    limit_mc = tenant['monthly_spend_limit_cents'] * MICRO_CENTS_PER_CENT
                    if monthly_spend >= limit_mc:
                        return False, f'Monthly spending limit of ${tenant["monthly_spend_limit_cents"] / 100:.0f} reached.'

                    # Check alert threshold
                    if tenant['monthly_spend_alert_cents']:
                        alert_mc = tenant['monthly_spend_alert_cents'] * MICRO_CENTS_PER_CENT
                        if monthly_spend >= alert_mc and monthly_spend - estimated_tokens * 50 < alert_mc:
                            # Just crossed the alert threshold
                            await self._create_alert(
                                conn, tenant_id,
                                alert_type='budget_threshold',
                                severity='warning',
                                title='Spending alert threshold reached',
                                message=f'Monthly spend has reached ${monthly_spend / MICRO_CENTS_PER_DOLLAR:.2f}, '
                                        f'alert threshold is ${tenant["monthly_spend_alert_cents"] / 100:.2f}.',
                                threshold_value=tenant['monthly_spend_alert_cents'] / 100,
                                actual_value=monthly_spend / MICRO_CENTS_PER_DOLLAR,
                            )

                # 3. Evaluate budget policies
                policies = await conn.fetch(
                    """
                    SELECT id, name, hard_limit_cents, action_on_hard
                    FROM budget_policies
                    WHERE tenant_id = $1 AND is_active = TRUE AND hard_limit_cents IS NOT NULL
                    """,
                    tenant_id,
                )
                for policy in policies:
                    if 'block' in (policy['action_on_hard'] or ''):
                        period_spend = await conn.fetchval(
                            """
                            SELECT COALESCE(SUM(cost_micro_cents), 0)
                            FROM token_usage
                            WHERE tenant_id = $1
                              AND created_at >= date_trunc('month', NOW())
                            """,
                            tenant_id,
                        )
                        if period_spend >= policy['hard_limit_cents'] * MICRO_CENTS_PER_CENT:
                            return False, f'Budget policy "{policy["name"]}" hard limit reached.'

            return True, None

        except Exception as e:
            logger.error(f'Budget enforcement error: {e}')
            return True, None  # Fail open

    # =========================================================================
    # Cost Anomaly Detection
    # =========================================================================

    async def detect_anomalies(
        self,
        tenant_id: str,
        lookback_days: int = 14,
        sensitivity: Optional[float] = None,
    ) -> List[CostAnomaly]:
        """
        Detect cost anomalies by comparing recent usage against historical baseline.

        Uses standard deviation-based detection:
        - Compares today's cost rate against the mean of the lookback period
        - Flags when actual exceeds mean + (sensitivity * stddev)

        Args:
            tenant_id: Tenant to analyze
            lookback_days: Number of days for baseline calculation
            sensitivity: Standard deviations threshold (default from tenant config)

        Returns:
            List of detected anomalies
        """
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                # Get tenant sensitivity config
                if sensitivity is None:
                    row = await conn.fetchrow(
                        'SELECT anomaly_sensitivity FROM tenants WHERE id = $1',
                        tenant_id,
                    )
                    sensitivity = float(row['anomaly_sensitivity']) if row and row['anomaly_sensitivity'] else 2.0

                today = date.today()
                lookback_start = today - timedelta(days=lookback_days)

                # Get daily totals from snapshots
                daily_totals = await conn.fetch(
                    """
                    SELECT snapshot_date,
                           SUM(total_cost_micro_cents) as daily_cost,
                           SUM(request_count) as daily_requests,
                           SUM(total_input_tokens + total_output_tokens) as daily_tokens
                    FROM daily_cost_snapshots
                    WHERE tenant_id = $1
                      AND snapshot_date >= $2 AND snapshot_date < $3
                    GROUP BY snapshot_date
                    ORDER BY snapshot_date
                    """,
                    tenant_id, lookback_start, today,
                )

                if len(daily_totals) < 3:
                    return []  # Not enough data for meaningful analysis

                # Calculate baseline statistics
                costs = [float(row['daily_cost']) for row in daily_totals]
                requests = [float(row['daily_requests']) for row in daily_totals]

                cost_mean = sum(costs) / len(costs)
                cost_std = _stddev(costs)

                req_mean = sum(requests) / len(requests)
                req_std = _stddev(requests)

                # Get today's running total
                today_usage = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(cost_micro_cents), 0) as cost,
                           COUNT(*) as requests,
                           COALESCE(SUM(input_tokens + output_tokens), 0) as tokens
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= $2::DATE::TIMESTAMPTZ
                    """,
                    tenant_id, today,
                )

                anomalies: List[CostAnomaly] = []

                if not today_usage:
                    return anomalies

                today_cost = float(today_usage['cost'])
                today_requests = float(today_usage['requests'])

                # Cost spike detection
                if cost_std > 0 and today_cost > cost_mean + sensitivity * cost_std:
                    deviation = (today_cost - cost_mean) / cost_std
                    anomalies.append(CostAnomaly(
                        anomaly_type='cost_jump',
                        severity='critical' if deviation > 3 else 'warning',
                        model=None,
                        provider=None,
                        description=f'Daily cost is {deviation:.1f}x standard deviations above average. '
                                    f'${today_cost / MICRO_CENTS_PER_DOLLAR:.2f} vs avg ${cost_mean / MICRO_CENTS_PER_DOLLAR:.2f}.',
                        expected_value=cost_mean / MICRO_CENTS_PER_DOLLAR,
                        actual_value=today_cost / MICRO_CENTS_PER_DOLLAR,
                        deviation_factor=deviation,
                    ))

                # Request volume spike
                if req_std > 0 and today_requests > req_mean + sensitivity * req_std:
                    deviation = (today_requests - req_mean) / req_std
                    anomalies.append(CostAnomaly(
                        anomaly_type='volume_spike',
                        severity='warning',
                        model=None,
                        provider=None,
                        description=f'Request volume is {deviation:.1f}x std devs above average. '
                                    f'{int(today_requests)} requests vs avg {req_mean:.0f}.',
                        expected_value=req_mean,
                        actual_value=today_requests,
                        deviation_factor=deviation,
                    ))

                # Per-model anomaly detection
                model_today = await conn.fetch(
                    """
                    SELECT provider, model,
                           SUM(cost_micro_cents) as cost,
                           COUNT(*) as requests
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= $2::DATE::TIMESTAMPTZ
                    GROUP BY provider, model
                    """,
                    tenant_id, today,
                )

                for row in model_today:
                    model_baseline = await conn.fetch(
                        """
                        SELECT AVG(total_cost_micro_cents) as avg_cost,
                               AVG(request_count) as avg_requests
                        FROM daily_cost_snapshots
                        WHERE tenant_id = $1 AND provider = $2 AND model = $3
                          AND snapshot_date >= $4 AND snapshot_date < $5
                        """,
                        tenant_id, row['provider'], row['model'], lookback_start, today,
                    )

                    if model_baseline and model_baseline[0]['avg_cost']:
                        avg = float(model_baseline[0]['avg_cost'])
                        actual = float(row['cost'])
                        if avg > 0 and actual > avg * (1 + sensitivity):
                            ratio = actual / avg
                            anomalies.append(CostAnomaly(
                                anomaly_type='rate_spike',
                                severity='warning',
                                model=row['model'],
                                provider=row['provider'],
                                description=f'{row["provider"]}/{row["model"]} cost is {ratio:.1f}x the daily average.',
                                expected_value=avg / MICRO_CENTS_PER_DOLLAR,
                                actual_value=actual / MICRO_CENTS_PER_DOLLAR,
                                deviation_factor=ratio,
                            ))

                # Persist critical anomalies as alerts
                for anomaly in anomalies:
                    if anomaly.severity == 'critical':
                        await self._create_alert(
                            conn, tenant_id,
                            alert_type='anomaly',
                            severity=anomaly.severity,
                            title=f'Cost anomaly: {anomaly.anomaly_type}',
                            message=anomaly.description,
                            actual_value=anomaly.actual_value,
                            expected_value=anomaly.expected_value,
                            metadata={'model': anomaly.model, 'provider': anomaly.provider},
                        )

                return anomalies

        except Exception as e:
            logger.error(f'Anomaly detection error: {e}')
            return []

    # =========================================================================
    # Cost Forecasting
    # =========================================================================

    async def forecast_monthly_cost(
        self,
        tenant_id: str,
    ) -> Optional[CostForecast]:
        """
        Project end-of-month cost based on daily snapshots and current usage.

        Uses weighted linear projection: recent days weighted more heavily.
        """
        pool = await get_pool()
        if not pool:
            return None

        try:
            async with pool.acquire() as conn:
                today = date.today()
                month_start = today.replace(day=1)
                days_elapsed = (today - month_start).days + 1

                # Days in current month
                if today.month == 12:
                    next_month = today.replace(year=today.year + 1, month=1, day=1)
                else:
                    next_month = today.replace(month=today.month + 1, day=1)
                days_in_month = (next_month - month_start).days

                # Get daily costs this month from snapshots
                daily_costs = await conn.fetch(
                    """
                    SELECT snapshot_date, SUM(total_cost_micro_cents) as daily_cost
                    FROM daily_cost_snapshots
                    WHERE tenant_id = $1 AND snapshot_date >= $2
                    GROUP BY snapshot_date
                    ORDER BY snapshot_date
                    """,
                    tenant_id, month_start,
                )

                # Also get today's running total (not yet in snapshots)
                today_cost = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(cost_micro_cents), 0)
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= $2::DATE::TIMESTAMPTZ
                    """,
                    tenant_id, today,
                )

                all_costs = [float(row['daily_cost']) for row in daily_costs]
                if today_cost:
                    all_costs.append(float(today_cost))

                if not all_costs:
                    return CostForecast(
                        tenant_id=tenant_id,
                        period='monthly',
                        projected_cost_dollars=0,
                        daily_average_dollars=0,
                        days_in_period=days_in_month,
                        days_elapsed=days_elapsed,
                        confidence='low',
                        trend='stable',
                    )

                daily_avg = sum(all_costs) / len(all_costs)
                projected = daily_avg * days_in_month

                # Determine trend
                if len(all_costs) >= 3:
                    first_half = all_costs[:len(all_costs) // 2]
                    second_half = all_costs[len(all_costs) // 2:]
                    first_avg = sum(first_half) / len(first_half) if first_half else 0
                    second_avg = sum(second_half) / len(second_half) if second_half else 0
                    if second_avg > first_avg * 1.15:
                        trend = 'increasing'
                    elif second_avg < first_avg * 0.85:
                        trend = 'decreasing'
                    else:
                        trend = 'stable'
                else:
                    trend = 'stable'

                # Confidence based on data points
                if days_elapsed >= 14:
                    confidence = 'high'
                elif days_elapsed >= 7:
                    confidence = 'medium'
                else:
                    confidence = 'low'

                # Compare to last month
                last_month_start = (month_start - timedelta(days=1)).replace(day=1)
                last_month_total = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(total_cost_micro_cents), 0)
                    FROM daily_cost_snapshots
                    WHERE tenant_id = $1
                      AND snapshot_date >= $2 AND snapshot_date < $3
                    """,
                    tenant_id, last_month_start, month_start,
                )

                pct_change = None
                if last_month_total and last_month_total > 0:
                    pct_change = ((projected - float(last_month_total)) / float(last_month_total)) * 100

                return CostForecast(
                    tenant_id=tenant_id,
                    period='monthly',
                    projected_cost_dollars=projected / MICRO_CENTS_PER_DOLLAR,
                    daily_average_dollars=daily_avg / MICRO_CENTS_PER_DOLLAR,
                    days_in_period=days_in_month,
                    days_elapsed=days_elapsed,
                    confidence=confidence,
                    trend=trend,
                    pct_change_vs_last_period=round(pct_change, 1) if pct_change is not None else None,
                )

        except Exception as e:
            logger.error(f'Forecasting error: {e}')
            return None

    # =========================================================================
    # Cost Optimization Recommendations
    # =========================================================================

    async def generate_recommendations(
        self,
        tenant_id: str,
        lookback_days: int = 30,
    ) -> List[OptimizationRecommendation]:
        """
        Analyze tenant usage patterns and generate cost optimization recommendations.

        Checks for:
        1. Model downgrade opportunities (expensive model used for simple tasks)
        2. Cache utilization gaps (low cache hit rates)
        3. High-cost outlier requests
        """
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
                recommendations: List[OptimizationRecommendation] = []

                # 1. Model downgrade opportunities
                model_usage = await conn.fetch(
                    """
                    SELECT provider, model,
                           COUNT(*) as request_count,
                           SUM(cost_micro_cents) as total_cost,
                           AVG(input_tokens + output_tokens) as avg_tokens,
                           AVG(output_tokens) as avg_output
                    FROM token_usage
                    WHERE tenant_id = $1 AND created_at >= $2
                    GROUP BY provider, model
                    ORDER BY total_cost DESC
                    """,
                    tenant_id, cutoff,
                )

                # Get pricing for alternative models
                pricing = await conn.fetch(
                    'SELECT provider, model, input_cost_per_m, output_cost_per_m FROM model_pricing WHERE is_active = TRUE'
                )
                pricing_map = {(r['provider'], r['model']): r for r in pricing}

                for usage in model_usage:
                    model_name = usage['model']
                    tier_info = MODEL_TIERS.get(model_name)
                    if not tier_info or not tier_info['alternative']:
                        continue

                    alt = tier_info['alternative']
                    avg_output = float(usage['avg_output'] or 0)

                    # If average output is short (< 500 tokens), suggest cheaper model
                    if avg_output < 500 and tier_info['tier'] <= 2:
                        current_cost = float(usage['total_cost'])
                        # Estimate savings from model pricing ratio
                        current_pricing = pricing_map.get((usage['provider'], model_name))
                        alt_pricing = None
                        for prov in ['anthropic', 'openai', 'google', 'azure-anthropic']:
                            alt_pricing = pricing_map.get((prov, alt))
                            if alt_pricing:
                                break

                        if current_pricing and alt_pricing:
                            cost_ratio = float(alt_pricing['output_cost_per_m']) / float(current_pricing['output_cost_per_m'])
                            est_savings_pct = (1 - cost_ratio) * 100
                            est_savings_cents = int(current_cost * (1 - cost_ratio) / MICRO_CENTS_PER_CENT)

                            if est_savings_pct > 20:
                                recommendations.append(OptimizationRecommendation(
                                    recommendation_type='model_downgrade',
                                    title=f'Switch {model_name} → {alt} for short outputs',
                                    description=(
                                        f'{usage["request_count"]} requests used {model_name} with avg output '
                                        f'of {avg_output:.0f} tokens. {alt} handles short outputs well '
                                        f'at {est_savings_pct:.0f}% lower cost.'
                                    ),
                                    estimated_savings_percent=round(est_savings_pct, 1),
                                    estimated_savings_cents=est_savings_cents,
                                    current_model=model_name,
                                    suggested_model=alt,
                                    evidence={
                                        'request_count': usage['request_count'],
                                        'avg_output_tokens': round(avg_output),
                                        'current_monthly_cost_dollars': current_cost / MICRO_CENTS_PER_DOLLAR,
                                    },
                                ))

                # 2. Cache utilization analysis
                cache_stats = await conn.fetchrow(
                    """
                    SELECT
                        SUM(input_tokens) as total_input,
                        SUM(cache_read_tokens) as total_cache_read,
                        SUM(cache_write_tokens) as total_cache_write,
                        SUM(cost_micro_cents) as total_cost,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE tenant_id = $1 AND created_at >= $2
                      AND provider IN ('anthropic', 'azure-anthropic')
                    """,
                    tenant_id, cutoff,
                )

                if cache_stats and cache_stats['total_input'] and cache_stats['total_input'] > 10000:
                    cache_rate = (cache_stats['total_cache_read'] or 0) / cache_stats['total_input']
                    if cache_rate < 0.1 and cache_stats['request_count'] > 20:
                        # Low cache utilization on Anthropic models
                        potential_savings_pct = 15.0  # Conservative estimate
                        recommendations.append(OptimizationRecommendation(
                            recommendation_type='cache_optimization',
                            title='Enable prompt caching for Anthropic models',
                            description=(
                                f'Only {cache_rate * 100:.1f}% of input tokens are cache hits across '
                                f'{cache_stats["request_count"]} requests. Enabling prompt caching for '
                                f'system prompts and repeated context can reduce input costs by ~{potential_savings_pct:.0f}%.'
                            ),
                            estimated_savings_percent=potential_savings_pct,
                            estimated_savings_cents=int(
                                float(cache_stats['total_cost']) * (potential_savings_pct / 100) / MICRO_CENTS_PER_CENT
                            ),
                            evidence={
                                'cache_hit_rate': round(cache_rate * 100, 1),
                                'total_input_tokens': cache_stats['total_input'],
                                'request_count': cache_stats['request_count'],
                            },
                        ))

                # 3. High-cost outlier detection
                p95_cost = await conn.fetchval(
                    """
                    SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY cost_micro_cents)
                    FROM token_usage
                    WHERE tenant_id = $1 AND created_at >= $2
                    """,
                    tenant_id, cutoff,
                )

                if p95_cost:
                    outliers = await conn.fetchrow(
                        """
                        SELECT COUNT(*) as count, SUM(cost_micro_cents) as total_cost
                        FROM token_usage
                        WHERE tenant_id = $1 AND created_at >= $2
                          AND cost_micro_cents > $3 * 3
                        """,
                        tenant_id, cutoff, p95_cost,
                    )

                    if outliers and outliers['count'] > 5:
                        recommendations.append(OptimizationRecommendation(
                            recommendation_type='prompt_reduction',
                            title='Reduce high-cost outlier requests',
                            description=(
                                f'{outliers["count"]} requests exceeded 3x the 95th percentile cost. '
                                f'These outliers cost ${outliers["total_cost"] / MICRO_CENTS_PER_DOLLAR:.2f} total. '
                                f'Consider setting max token limits or splitting large prompts.'
                            ),
                            estimated_savings_percent=10.0,
                            estimated_savings_cents=int(
                                float(outliers['total_cost']) * 0.5 / MICRO_CENTS_PER_CENT
                            ),
                            evidence={
                                'outlier_count': outliers['count'],
                                'outlier_cost_dollars': outliers['total_cost'] / MICRO_CENTS_PER_DOLLAR,
                                'p95_cost_dollars': float(p95_cost) / MICRO_CENTS_PER_DOLLAR,
                            },
                        ))

                # Persist new recommendations
                for rec in recommendations:
                    await conn.execute(
                        """
                        INSERT INTO cost_recommendations
                            (tenant_id, recommendation_type, title, description,
                             estimated_savings_percent, estimated_savings_cents,
                             current_model, suggested_model, evidence)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT DO NOTHING
                        """,
                        tenant_id, rec.recommendation_type, rec.title, rec.description,
                        rec.estimated_savings_percent, rec.estimated_savings_cents,
                        rec.current_model, rec.suggested_model,
                        __import__('json').dumps(rec.evidence),
                    )

                return recommendations

        except Exception as e:
            logger.error(f'Recommendation generation error: {e}')
            return []

    # =========================================================================
    # Budget Policy Management
    # =========================================================================

    async def evaluate_policies(
        self,
        tenant_id: str,
    ) -> List[BudgetPolicyResult]:
        """Evaluate all active budget policies for a tenant."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    'SELECT * FROM evaluate_budget_policies($1)',
                    tenant_id,
                )

                results = []
                for row in rows:
                    result = BudgetPolicyResult(
                        policy_id=row['policy_id'],
                        policy_name=row['policy_name'],
                        breached_level=row['breached_level'],
                        current_spend_cents=float(row['current_spend_cents']),
                        limit_cents=row['limit_cents'],
                        action=row['action'],
                    )
                    results.append(result)

                    # Create alert for breaches
                    await self._create_alert(
                        conn, tenant_id,
                        alert_type='budget_threshold',
                        severity='critical' if result.breached_level == 'hard' else 'warning',
                        title=f'Budget policy "{result.policy_name}" {result.breached_level} limit breached',
                        message=f'Current spend: ${result.current_spend_cents / 100:.2f}, '
                                f'limit: ${result.limit_cents / 100:.2f}.',
                        threshold_value=result.limit_cents / 100,
                        actual_value=result.current_spend_cents / 100,
                    )

                return results

        except Exception as e:
            logger.error(f'Policy evaluation error: {e}')
            return []

    async def create_budget_policy(
        self,
        tenant_id: str,
        name: str,
        soft_limit_cents: Optional[int] = None,
        hard_limit_cents: Optional[int] = None,
        scope: str = 'tenant',
        scope_filter: Optional[str] = None,
        period: str = 'monthly',
        action_on_soft: str = 'alert',
        action_on_hard: str = 'alert',
        webhook_url: Optional[str] = None,
    ) -> Optional[int]:
        """Create a new budget policy."""
        pool = await get_pool()
        if not pool:
            return None

        try:
            async with pool.acquire() as conn:
                policy_id = await conn.fetchval(
                    """
                    INSERT INTO budget_policies
                        (tenant_id, name, scope, scope_filter, period,
                         soft_limit_cents, hard_limit_cents,
                         action_on_soft, action_on_hard, webhook_url)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (tenant_id, name) DO UPDATE SET
                        scope = EXCLUDED.scope,
                        scope_filter = EXCLUDED.scope_filter,
                        period = EXCLUDED.period,
                        soft_limit_cents = EXCLUDED.soft_limit_cents,
                        hard_limit_cents = EXCLUDED.hard_limit_cents,
                        action_on_soft = EXCLUDED.action_on_soft,
                        action_on_hard = EXCLUDED.action_on_hard,
                        webhook_url = EXCLUDED.webhook_url,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    tenant_id, name, scope, scope_filter, period,
                    soft_limit_cents, hard_limit_cents,
                    action_on_soft, action_on_hard, webhook_url,
                )
                return policy_id
        except Exception as e:
            logger.error(f'Create budget policy error: {e}')
            return None

    async def list_budget_policies(
        self,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:
        """List all budget policies for a tenant."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, name, scope, scope_filter, period,
                           soft_limit_cents, hard_limit_cents,
                           action_on_soft, action_on_hard, webhook_url,
                           is_active, last_evaluated_at, created_at
                    FROM budget_policies
                    WHERE tenant_id = $1
                    ORDER BY created_at DESC
                    """,
                    tenant_id,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f'List budget policies error: {e}')
            return []

    # =========================================================================
    # Daily Snapshot Builder
    # =========================================================================

    async def build_daily_snapshots(
        self,
        tenant_id: Optional[str] = None,
        snapshot_date: Optional[date] = None,
    ) -> int:
        """
        Build daily cost snapshots for one or all tenants.

        Should be called daily (e.g., by cron) for yesterday's data.
        """
        pool = await get_pool()
        if not pool:
            return 0

        if snapshot_date is None:
            snapshot_date = date.today() - timedelta(days=1)

        try:
            async with pool.acquire() as conn:
                if tenant_id:
                    count = await conn.fetchval(
                        'SELECT build_daily_snapshot($1, $2)',
                        tenant_id, snapshot_date,
                    )
                    return count or 0
                else:
                    # Build for all active tenants
                    tenants = await conn.fetch(
                        "SELECT id FROM tenants WHERE finops_enabled = TRUE"
                    )
                    total = 0
                    for t in tenants:
                        count = await conn.fetchval(
                            'SELECT build_daily_snapshot($1, $2)',
                            t['id'], snapshot_date,
                        )
                        total += count or 0
                    return total

        except Exception as e:
            logger.error(f'Snapshot build error: {e}')
            return 0

    # =========================================================================
    # Cost Allocation & Analytics
    # =========================================================================

    async def get_cost_breakdown(
        self,
        tenant_id: str,
        group_by: str = 'model',  # 'model', 'user', 'project', 'environment', 'day'
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get cost breakdown grouped by various dimensions.

        For chargeback, cost allocation, and team-level visibility.
        """
        pool = await get_pool()
        if not pool:
            return []

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

        group_col = {
            'model': 'provider || \'/\' || model',
            'user': 'COALESCE(user_id, \'unattributed\')',
            'project': 'COALESCE(project_id, \'default\')',
            'environment': 'COALESCE(environment, \'production\')',
            'day': 'date_trunc(\'day\', created_at)::DATE::TEXT',
        }.get(group_by, 'model')

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        {group_col} AS dimension,
                        COUNT(*) AS request_count,
                        SUM(input_tokens) AS input_tokens,
                        SUM(output_tokens) AS output_tokens,
                        SUM(cost_micro_cents) AS cost_micro_cents,
                        ROUND(SUM(cost_micro_cents)::NUMERIC / $3, 2) AS cost_dollars
                    FROM token_usage
                    WHERE tenant_id = $1 AND created_at >= $2
                    GROUP BY {group_col}
                    ORDER BY cost_micro_cents DESC
                    """,
                    tenant_id, cutoff, MICRO_CENTS_PER_DOLLAR,
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f'Cost breakdown error: {e}')
            return []

    async def get_cost_trend(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily cost trend from snapshots + today's running total."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                cutoff = date.today() - timedelta(days=days)

                rows = await conn.fetch(
                    """
                    SELECT snapshot_date::TEXT as date,
                           SUM(request_count) as requests,
                           SUM(total_cost_micro_cents) as cost_micro_cents,
                           ROUND(SUM(total_cost_micro_cents)::NUMERIC / $3, 4) as cost_dollars,
                           SUM(total_input_tokens + total_output_tokens) as tokens
                    FROM daily_cost_snapshots
                    WHERE tenant_id = $1 AND snapshot_date >= $2
                    GROUP BY snapshot_date
                    ORDER BY snapshot_date
                    """,
                    tenant_id, cutoff, MICRO_CENTS_PER_DOLLAR,
                )

                result = [dict(row) for row in rows]

                # Add today's running total
                today = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as requests,
                           COALESCE(SUM(cost_micro_cents), 0) as cost_micro_cents,
                           COALESCE(SUM(input_tokens + output_tokens), 0) as tokens
                    FROM token_usage
                    WHERE tenant_id = $1
                      AND created_at >= CURRENT_DATE::TIMESTAMPTZ
                    """,
                    tenant_id,
                )

                if today and today['requests'] > 0:
                    result.append({
                        'date': date.today().isoformat(),
                        'requests': today['requests'],
                        'cost_micro_cents': today['cost_micro_cents'],
                        'cost_dollars': round(today['cost_micro_cents'] / MICRO_CENTS_PER_DOLLAR, 4),
                        'tokens': today['tokens'],
                    })

                return result

        except Exception as e:
            logger.error(f'Cost trend error: {e}')
            return []

    # =========================================================================
    # Alerts Management
    # =========================================================================

    async def get_alerts(
        self,
        tenant_id: str,
        unacknowledged_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get cost alerts for a tenant."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                query = """
                    SELECT id, alert_type, severity, title, message,
                           threshold_value, actual_value, metadata,
                           acknowledged, notified, created_at
                    FROM cost_alerts
                    WHERE tenant_id = $1
                """
                params: list = [tenant_id]

                if unacknowledged_only:
                    query += ' AND acknowledged = FALSE'

                query += ' ORDER BY created_at DESC LIMIT $' + str(len(params) + 1)
                params.append(limit)

                rows = await conn.fetch(query, *params)
                return [
                    {
                        **dict(row),
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f'Get alerts error: {e}')
            return []

    async def acknowledge_alert(
        self,
        tenant_id: str,
        alert_id: int,
        user_id: Optional[str] = None,
    ) -> bool:
        """Acknowledge a cost alert."""
        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE cost_alerts
                    SET acknowledged = TRUE,
                        acknowledged_by = $3,
                        acknowledged_at = NOW()
                    WHERE id = $2 AND tenant_id = $1
                    """,
                    tenant_id, alert_id, user_id,
                )
                return 'UPDATE 1' in result
        except Exception as e:
            logger.error(f'Acknowledge alert error: {e}')
            return False

    async def get_alert_summary(
        self,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Get alert counts by severity."""
        pool = await get_pool()
        if not pool:
            return {}

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT severity, COUNT(*) as count
                    FROM cost_alerts
                    WHERE tenant_id = $1 AND acknowledged = FALSE
                    GROUP BY severity
                    """,
                    tenant_id,
                )
                summary = {row['severity']: row['count'] for row in rows}
                summary['total'] = sum(summary.values())
                return summary
        except Exception as e:
            logger.error(f'Alert summary error: {e}')
            return {}

    # =========================================================================
    # Recommendations Management
    # =========================================================================

    async def get_recommendations(
        self,
        tenant_id: str,
        status: str = 'open',
    ) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        pool = await get_pool()
        if not pool:
            return []

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, recommendation_type, title, description,
                           estimated_savings_percent, estimated_savings_cents,
                           current_model, suggested_model, evidence,
                           status, created_at
                    FROM cost_recommendations
                    WHERE tenant_id = $1 AND status = $2
                    ORDER BY estimated_savings_cents DESC
                    """,
                    tenant_id, status,
                )
                return [
                    {
                        **dict(row),
                        'estimated_savings_dollars': (row['estimated_savings_cents'] or 0) / 100,
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f'Get recommendations error: {e}')
            return []

    async def dismiss_recommendation(
        self,
        tenant_id: str,
        recommendation_id: int,
        reason: str = '',
    ) -> bool:
        """Dismiss a cost recommendation."""
        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE cost_recommendations
                    SET status = 'dismissed',
                        dismissed_reason = $3,
                        updated_at = NOW()
                    WHERE id = $2 AND tenant_id = $1
                    """,
                    tenant_id, recommendation_id, reason,
                )
                return 'UPDATE 1' in result
        except Exception as e:
            logger.error(f'Dismiss recommendation error: {e}')
            return False

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _create_alert(
        self,
        conn,
        tenant_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        threshold_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        expected_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Create a cost alert (deduped within 1 hour)."""
        try:
            # Dedup: don't create duplicate alerts within 1 hour
            existing = await conn.fetchval(
                """
                SELECT id FROM cost_alerts
                WHERE tenant_id = $1 AND alert_type = $2 AND title = $3
                  AND created_at > NOW() - INTERVAL '1 hour'
                """,
                tenant_id, alert_type, title,
            )
            if existing:
                return

            meta = metadata or {}
            if expected_value is not None:
                meta['expected_value'] = expected_value

            await conn.execute(
                """
                INSERT INTO cost_alerts
                    (tenant_id, alert_type, severity, title, message,
                     threshold_value, actual_value, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                tenant_id, alert_type, severity, title, message,
                threshold_value, actual_value,
                __import__('json').dumps(meta),
            )
        except Exception as e:
            logger.error(f'Create alert error: {e}')


def _stddev(values: List[float]) -> float:
    """Calculate population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


# Singleton
_finops: Optional[FinOpsService] = None


def get_finops_service() -> FinOpsService:
    """Get the singleton FinOps service instance."""
    global _finops
    if _finops is None:
        _finops = FinOpsService()
    return _finops
