"""
Tests for FinOps Service and Budget Enforcement Middleware.

Tests cover:
- Budget enforcement (prepaid balance, monthly limits, policy-based blocking)
- Cost anomaly detection (cost spikes, volume spikes, per-model anomalies)
- Cost forecasting (projection, trend detection, confidence levels)
- Cost optimization recommendations (model downgrade, cache, outliers)
- Budget policy management (create, list, evaluate)
- Alert management (create, acknowledge, dedup, summary)
- Daily snapshots (build, idempotent)
- Budget enforcement middleware (route matching, 402 blocking)
- Cost breakdown and trend queries
"""

import json
import math
import unittest
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_server.finops import (
    CostAlert,
    CostAnomaly,
    CostForecast,
    FinOpsService,
    OptimizationRecommendation,
    BudgetPolicyResult,
    MODEL_TIERS,
    _stddev,
    get_finops_service,
)
from a2a_server.budget_middleware import (
    BudgetEnforcementMiddleware,
    _requires_budget_check,
)


# =========================================================================
# Helpers
# =========================================================================


@asynccontextmanager
async def _mock_pool():
    """Create a mock database pool with acquire context manager."""
    conn = AsyncMock()
    pool = AsyncMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    yield pool, conn


# =========================================================================
# Unit Tests: stddev helper
# =========================================================================


class TestStddev(unittest.TestCase):
    def test_empty_list(self):
        assert _stddev([]) == 0.0

    def test_single_value(self):
        assert _stddev([5.0]) == 0.0

    def test_identical_values(self):
        assert _stddev([3.0, 3.0, 3.0]) == 0.0

    def test_known_values(self):
        # stddev of [2, 4, 4, 4, 5, 5, 7, 9] = 2.0
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        result = _stddev(values)
        assert abs(result - 2.0) < 0.01

    def test_two_values(self):
        result = _stddev([0.0, 10.0])
        assert abs(result - 5.0) < 0.01


# =========================================================================
# Unit Tests: Route matching
# =========================================================================


class TestBudgetRouteMatching(unittest.TestCase):
    def test_task_creation_requires_check(self):
        assert _requires_budget_check('/v1/agent/tasks', 'POST') is True
        assert _requires_budget_check('/v1/agent/tasks/', 'POST') is True

    def test_automation_task_requires_check(self):
        assert _requires_budget_check('/v1/automation/tasks', 'POST') is True
        assert _requires_budget_check('/v1/automation/tasks/', 'POST') is True

    def test_mcp_requires_check(self):
        assert _requires_budget_check('/mcp', 'POST') is True

    def test_session_message_requires_check(self):
        assert _requires_budget_check(
            '/v1/agent/codebases/abc123/sessions/sess1/messages', 'POST'
        ) is True

    def test_get_requests_skip(self):
        assert _requires_budget_check('/v1/agent/tasks', 'GET') is False
        assert _requires_budget_check('/mcp', 'GET') is False

    def test_unrelated_routes_skip(self):
        assert _requires_budget_check('/v1/finops/forecast', 'GET') is False
        assert _requires_budget_check('/v1/token-billing/usage/summary', 'GET') is False
        assert _requires_budget_check('/health', 'GET') is False

    def test_send_message_requires_check(self):
        assert _requires_budget_check('/v1/agent/send-message', 'POST') is True
        assert _requires_budget_check('/v1/agent/send-message/', 'POST') is True


# =========================================================================
# Unit Tests: Model tiers
# =========================================================================


class TestModelTiers(unittest.TestCase):
    def test_opus_has_downgrade(self):
        tier = MODEL_TIERS['claude-opus-4-6']
        assert tier['alternative'] == 'claude-sonnet-4'
        assert tier['tier'] == 1

    def test_haiku_no_downgrade(self):
        tier = MODEL_TIERS['claude-haiku-3-5']
        assert tier['alternative'] is None
        assert tier['tier'] == 4

    def test_gpt52_has_downgrade(self):
        tier = MODEL_TIERS['gpt-5.2']
        assert tier['alternative'] == 'gpt-4.1'

    def test_gemini_flash_no_downgrade(self):
        tier = MODEL_TIERS['gemini-2.5-flash']
        assert tier['alternative'] is None


# =========================================================================
# Async Tests: Budget Enforcement
# =========================================================================


@pytest.mark.asyncio
async def test_enforce_budget_no_pool():
    """Should fail open when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        allowed, reason = await svc.enforce_budget('tenant-1')
        assert allowed is True
        assert reason is None


@pytest.mark.asyncio
async def test_enforce_budget_tenant_not_found():
    """Should deny when tenant doesn't exist."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = None
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            allowed, reason = await svc.enforce_budget('nonexistent')
            assert allowed is False
            assert 'not found' in reason.lower()


@pytest.mark.asyncio
async def test_enforce_budget_prepaid_exhausted():
    """Should block when prepaid balance <= 0."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = {
            'billing_model': 'prepaid',
            'token_balance_micro_cents': 0,
            'monthly_spend_limit_cents': None,
            'monthly_spend_alert_cents': None,
            'auto_topup_enabled': False,
            'auto_topup_threshold_cents': None,
        }
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            allowed, reason = await svc.enforce_budget('tenant-1')
            assert allowed is False
            assert 'exhausted' in reason.lower()


@pytest.mark.asyncio
async def test_enforce_budget_prepaid_has_balance():
    """Should allow when prepaid balance > 0 and no limit."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = {
            'billing_model': 'prepaid',
            'token_balance_micro_cents': 50000000,  # $5
            'monthly_spend_limit_cents': None,
            'monthly_spend_alert_cents': None,
            'auto_topup_enabled': False,
            'auto_topup_threshold_cents': None,
        }
        conn.fetch.return_value = []  # No budget policies
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            allowed, reason = await svc.enforce_budget('tenant-1')
            assert allowed is True


@pytest.mark.asyncio
async def test_enforce_budget_monthly_limit_exceeded():
    """Should block when monthly spending limit reached."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = {
            'billing_model': 'subscription',
            'token_balance_micro_cents': 0,
            'monthly_spend_limit_cents': 5000,  # $50
            'monthly_spend_alert_cents': None,
            'auto_topup_enabled': False,
            'auto_topup_threshold_cents': None,
        }
        conn.fetchval.return_value = 50001 * 10000  # $50.001 > $50 limit
        conn.fetch.return_value = []
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            allowed, reason = await svc.enforce_budget('tenant-1')
            assert allowed is False
            assert '$50' in reason


@pytest.mark.asyncio
async def test_enforce_budget_subscription_under_limit():
    """Should allow subscription tenant under monthly limit."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = {
            'billing_model': 'subscription',
            'token_balance_micro_cents': 0,
            'monthly_spend_limit_cents': 5000,  # $50
            'monthly_spend_alert_cents': None,
            'auto_topup_enabled': False,
            'auto_topup_threshold_cents': None,
        }
        conn.fetchval.return_value = 2000 * 10000  # $20 < $50
        conn.fetch.return_value = []
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            allowed, reason = await svc.enforce_budget('tenant-1')
            assert allowed is True


# =========================================================================
# Async Tests: Anomaly Detection
# =========================================================================


@pytest.mark.asyncio
async def test_detect_anomalies_not_enough_data():
    """Should return empty if fewer than 3 days of data."""
    async with _mock_pool() as (pool, conn):
        conn.fetchrow.return_value = {'anomaly_sensitivity': 2.0}
        conn.fetch.side_effect = [
            # daily_totals: only 2 days
            [
                {'snapshot_date': date.today() - timedelta(days=2), 'daily_cost': 1000, 'daily_requests': 5, 'daily_tokens': 500},
                {'snapshot_date': date.today() - timedelta(days=1), 'daily_cost': 1200, 'daily_requests': 6, 'daily_tokens': 600},
            ],
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.detect_anomalies('tenant-1')
            assert result == []


@pytest.mark.asyncio
async def test_detect_anomalies_no_pool():
    """Should return empty when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.detect_anomalies('tenant-1')
        assert result == []


# =========================================================================
# Async Tests: Forecasting
# =========================================================================


@pytest.mark.asyncio
async def test_forecast_no_pool():
    """Should return None when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.forecast_monthly_cost('tenant-1')
        assert result is None


@pytest.mark.asyncio
async def test_forecast_no_data():
    """Should return zero forecast when no usage data."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = []
        conn.fetchval.side_effect = [0, 0]  # today_cost, last_month
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.forecast_monthly_cost('tenant-1')
            assert result is not None
            assert result.projected_cost_dollars == 0
            assert result.confidence == 'low'
            assert result.trend == 'stable'


@pytest.mark.asyncio
async def test_forecast_with_data():
    """Should project cost based on daily averages."""
    async with _mock_pool() as (pool, conn):
        today = date.today()
        month_start = today.replace(day=1)
        days_elapsed = (today - month_start).days + 1

        # Simulate 5 days at $10/day = $50 total, ~$300/month projection
        fake_daily = [
            {'snapshot_date': month_start + timedelta(days=i), 'daily_cost': 10_000_000}
            for i in range(min(5, days_elapsed))
        ]
        conn.fetch.return_value = fake_daily
        conn.fetchval.side_effect = [10_000_000, 0]  # today, last_month

        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.forecast_monthly_cost('tenant-1')
            assert result is not None
            assert result.projected_cost_dollars > 0
            assert result.daily_average_dollars == 10.0


# =========================================================================
# Async Tests: Cost Optimization Recommendations
# =========================================================================


@pytest.mark.asyncio
async def test_recommendations_no_pool():
    """Should return empty when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.generate_recommendations('tenant-1')
        assert result == []


# =========================================================================
# Async Tests: Budget Policy Management
# =========================================================================


@pytest.mark.asyncio
async def test_create_budget_policy():
    """Should create a budget policy and return its ID."""
    async with _mock_pool() as (pool, conn):
        conn.fetchval.return_value = 42
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            policy_id = await svc.create_budget_policy(
                tenant_id='tenant-1',
                name='Monthly Cap',
                soft_limit_cents=5000,
                hard_limit_cents=10000,
            )
            assert policy_id == 42


@pytest.mark.asyncio
async def test_create_budget_policy_no_pool():
    """Should return None when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.create_budget_policy('t', 'test')
        assert result is None


@pytest.mark.asyncio
async def test_list_budget_policies():
    """Should return list of policies."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = [
            {
                'id': 1, 'name': 'Cap', 'scope': 'tenant', 'scope_filter': None,
                'period': 'monthly', 'soft_limit_cents': 5000, 'hard_limit_cents': 10000,
                'action_on_soft': 'alert', 'action_on_hard': 'block',
                'webhook_url': None, 'is_active': True,
                'last_evaluated_at': None, 'created_at': datetime.now(tz=timezone.utc),
            }
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            policies = await svc.list_budget_policies('tenant-1')
            assert len(policies) == 1
            assert policies[0]['name'] == 'Cap'


# =========================================================================
# Async Tests: Alert Management
# =========================================================================


@pytest.mark.asyncio
async def test_get_alerts():
    """Should return alert list."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = [
            {
                'id': 1, 'alert_type': 'budget_threshold', 'severity': 'warning',
                'title': 'Limit reached', 'message': 'Spending at $50',
                'threshold_value': 50.0, 'actual_value': 51.0,
                'metadata': '{}', 'acknowledged': False, 'notified': False,
                'created_at': datetime.now(tz=timezone.utc),
            }
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            alerts = await svc.get_alerts('tenant-1')
            assert len(alerts) == 1
            assert alerts[0]['title'] == 'Limit reached'


@pytest.mark.asyncio
async def test_acknowledge_alert():
    """Should update alert as acknowledged."""
    async with _mock_pool() as (pool, conn):
        conn.execute.return_value = 'UPDATE 1'
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.acknowledge_alert('tenant-1', 1, 'user-1')
            assert result is True


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found():
    """Should return False when alert not found."""
    async with _mock_pool() as (pool, conn):
        conn.execute.return_value = 'UPDATE 0'
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.acknowledge_alert('tenant-1', 999)
            assert result is False


@pytest.mark.asyncio
async def test_alert_summary():
    """Should return counts by severity."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = [
            {'severity': 'critical', 'count': 2},
            {'severity': 'warning', 'count': 5},
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            summary = await svc.get_alert_summary('tenant-1')
            assert summary['critical'] == 2
            assert summary['warning'] == 5
            assert summary['total'] == 7


# =========================================================================
# Async Tests: Daily Snapshots
# =========================================================================


@pytest.mark.asyncio
async def test_build_snapshots_single_tenant():
    """Should build snapshots for a single tenant."""
    async with _mock_pool() as (pool, conn):
        conn.fetchval.return_value = 3  # 3 model snapshots created
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            count = await svc.build_daily_snapshots(tenant_id='tenant-1')
            assert count == 3


@pytest.mark.asyncio
async def test_build_snapshots_no_pool():
    """Should return 0 when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        count = await svc.build_daily_snapshots()
        assert count == 0


# =========================================================================
# Async Tests: Cost Breakdown & Trend
# =========================================================================


@pytest.mark.asyncio
async def test_cost_breakdown_no_pool():
    """Should return empty list when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.get_cost_breakdown('tenant-1')
        assert result == []


@pytest.mark.asyncio
async def test_cost_trend_no_pool():
    """Should return empty list when DB pool unavailable."""
    with patch('a2a_server.finops.get_pool', return_value=None):
        svc = FinOpsService()
        result = await svc.get_cost_trend('tenant-1')
        assert result == []


@pytest.mark.asyncio
async def test_cost_breakdown_with_data():
    """Should return breakdown rows."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = [
            {
                'dimension': 'anthropic/claude-sonnet-4',
                'request_count': 100,
                'input_tokens': 50000,
                'output_tokens': 25000,
                'cost_micro_cents': 15000000,
                'cost_dollars': 15.0,
            }
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.get_cost_breakdown('tenant-1', group_by='model')
            assert len(result) == 1
            assert result[0]['dimension'] == 'anthropic/claude-sonnet-4'


# =========================================================================
# Async Tests: Recommendations Management
# =========================================================================


@pytest.mark.asyncio
async def test_get_recommendations():
    """Should return open recommendations."""
    async with _mock_pool() as (pool, conn):
        conn.fetch.return_value = [
            {
                'id': 1,
                'recommendation_type': 'model_downgrade',
                'title': 'Switch opus to sonnet',
                'description': 'You can save money',
                'estimated_savings_percent': 40.0,
                'estimated_savings_cents': 500,
                'current_model': 'claude-opus-4-6',
                'suggested_model': 'claude-sonnet-4',
                'evidence': '{}',
                'status': 'open',
                'created_at': datetime.now(tz=timezone.utc),
            }
        ]
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            recs = await svc.get_recommendations('tenant-1')
            assert len(recs) == 1
            assert recs[0]['estimated_savings_dollars'] == 5.0


@pytest.mark.asyncio
async def test_dismiss_recommendation():
    """Should dismiss a recommendation."""
    async with _mock_pool() as (pool, conn):
        conn.execute.return_value = 'UPDATE 1'
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.dismiss_recommendation('tenant-1', 1, 'not needed')
            assert result is True


@pytest.mark.asyncio
async def test_dismiss_recommendation_not_found():
    """Should return False when recommendation not found."""
    async with _mock_pool() as (pool, conn):
        conn.execute.return_value = 'UPDATE 0'
        with patch('a2a_server.finops.get_pool', return_value=pool):
            svc = FinOpsService()
            result = await svc.dismiss_recommendation('tenant-1', 999)
            assert result is False


# =========================================================================
# Unit Tests: Singleton
# =========================================================================


class TestSingleton(unittest.TestCase):
    def test_get_finops_service_returns_same_instance(self):
        svc1 = get_finops_service()
        svc2 = get_finops_service()
        assert svc1 is svc2
        assert isinstance(svc1, FinOpsService)


# =========================================================================
# Unit Tests: Data classes
# =========================================================================


class TestDataClasses(unittest.TestCase):
    def test_cost_alert_creation(self):
        alert = CostAlert(
            alert_type='anomaly',
            severity='critical',
            title='Cost spike',
            message='3x normal',
        )
        assert alert.alert_type == 'anomaly'
        assert alert.metadata == {}

    def test_cost_forecast(self):
        forecast = CostForecast(
            tenant_id='t1',
            period='monthly',
            projected_cost_dollars=150.0,
            daily_average_dollars=5.0,
            days_in_period=30,
            days_elapsed=15,
            confidence='high',
            trend='stable',
        )
        assert forecast.projected_cost_dollars == 150.0
        assert forecast.pct_change_vs_last_period is None

    def test_cost_anomaly(self):
        anomaly = CostAnomaly(
            anomaly_type='cost_jump',
            severity='critical',
            model=None,
            provider=None,
            description='3x above average',
            expected_value=10.0,
            actual_value=30.0,
            deviation_factor=3.0,
        )
        assert anomaly.deviation_factor == 3.0

    def test_optimization_recommendation(self):
        rec = OptimizationRecommendation(
            recommendation_type='model_downgrade',
            title='Switch to cheaper model',
            description='Save money',
            estimated_savings_percent=40.0,
            estimated_savings_cents=500,
            current_model='claude-opus-4-6',
            suggested_model='claude-sonnet-4',
        )
        assert rec.estimated_savings_cents == 500

    def test_budget_policy_result(self):
        result = BudgetPolicyResult(
            policy_id=1,
            policy_name='Cap',
            breached_level='hard',
            current_spend_cents=5100.0,
            limit_cents=5000,
            action='block',
        )
        assert result.breached_level == 'hard'


if __name__ == '__main__':
    unittest.main()
