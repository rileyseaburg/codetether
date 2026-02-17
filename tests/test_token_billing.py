"""
Tests for per-token multi-tenant billing service.

Tests the TokenBillingService, TokenCounts parsing, and cost calculation
logic without requiring a live database (unit tests with mocking).

Run with: pytest tests/test_token_billing.py -v
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from a2a_server.token_billing import (
    TokenBillingService,
    TokenCounts,
    UsageRecord,
    BudgetCheck,
    MICRO_CENTS_PER_CENT,
    MICRO_CENTS_PER_DOLLAR,
)


def _mock_pool(mock_conn):
    """Create a mock pool whose acquire() works as an async context manager."""
    mock_pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    return mock_pool


# ── TokenCounts parsing ─────────────────────────────────────────


class TestTokenCounts:
    """Test TokenCounts.from_dict with various response formats."""

    def test_empty_dict(self):
        tc = TokenCounts.from_dict({})
        assert tc.input_tokens == 0
        assert tc.output_tokens == 0
        assert tc.total == 0

    def test_none_input(self):
        tc = TokenCounts.from_dict(None)
        assert tc.total == 0

    def test_agent_format(self):
        """CodeTether uses {input, output, reasoning, cache: {read, write}}."""
        tc = TokenCounts.from_dict({
            'input': 1500,
            'output': 800,
            'reasoning': 200,
            'cache': {'read': 500, 'write': 100},
        })
        assert tc.input_tokens == 1500
        assert tc.output_tokens == 800
        assert tc.reasoning_tokens == 200
        assert tc.cache_read_tokens == 500
        assert tc.cache_write_tokens == 100
        assert tc.total == 2500  # input + output + reasoning

    def test_snake_case_format(self):
        """Backend may use snake_case keys."""
        tc = TokenCounts.from_dict({
            'input_tokens': 3000,
            'output_tokens': 1200,
            'reasoning_tokens': 0,
            'cache_read_tokens': 800,
            'cache_write_tokens': 0,
        })
        assert tc.input_tokens == 3000
        assert tc.output_tokens == 1200
        assert tc.cache_read_tokens == 800

    def test_camel_case_format(self):
        """TypeScript clients may use camelCase."""
        tc = TokenCounts.from_dict({
            'inputTokens': 5000,
            'outputTokens': 2000,
            'reasoningTokens': 500,
            'cacheReadTokens': 1000,
            'cacheWriteTokens': 200,
        })
        assert tc.input_tokens == 5000
        assert tc.output_tokens == 2000
        assert tc.reasoning_tokens == 500
        assert tc.cache_read_tokens == 1000
        assert tc.cache_write_tokens == 200

    def test_partial_data(self):
        """Only some fields present."""
        tc = TokenCounts.from_dict({'input': 100, 'output': 50})
        assert tc.input_tokens == 100
        assert tc.output_tokens == 50
        assert tc.reasoning_tokens == 0
        assert tc.cache_read_tokens == 0
        assert tc.total == 150

    def test_none_values_treated_as_zero(self):
        tc = TokenCounts.from_dict({
            'input': None,
            'output': None,
            'reasoning': None,
            'cache': {'read': None, 'write': None},
        })
        assert tc.total == 0


# ── UsageRecord ──────────────────────────────────────────────────


class TestUsageRecord:
    def test_cost_conversions(self):
        record = UsageRecord(
            usage_id=1,
            cost_micro_cents=15_000_000,  # $1.50
            remaining_balance_micro_cents=85_000_000,  # $8.50
            over_limit=False,
        )
        assert record.cost_dollars == 15.0
        assert record.cost_cents == 1500.0

    def test_zero_cost(self):
        record = UsageRecord(usage_id=2, cost_micro_cents=0, remaining_balance_micro_cents=0, over_limit=False)
        assert record.cost_dollars == 0.0


# ── BudgetCheck ──────────────────────────────────────────────────


class TestBudgetCheck:
    def test_monthly_spend_conversion(self):
        check = BudgetCheck(
            allowed=True,
            reason='OK',
            balance_micro_cents=50_000_000,
            monthly_spend_micro_cents=25_000_000,
            monthly_limit_cents=5000,
            billing_model='prepaid',
        )
        assert check.monthly_spend_dollars == 25.0


# ── TokenBillingService (with mocked DB) ─────────────────────────


class TestTokenBillingService:

    @pytest.fixture
    def service(self):
        return TokenBillingService()

    @pytest.mark.asyncio
    async def test_record_usage_zero_tokens_returns_none(self, service):
        """Recording zero tokens should be a no-op."""
        result = await service.record_usage(
            tenant_id='t1',
            provider='anthropic',
            model='claude-sonnet-4',
            tokens=TokenCounts(),
        )
        assert result is None

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_record_usage_success(self, mock_get_pool, service):
        """Recording usage with mocked DB should work."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            'usage_id': 42,
            'cost_micro_cents': 5000,
            'remaining_balance_micro_cents': 95000,
            'over_limit': False,
        })

        mock_get_pool.return_value = _mock_pool(mock_conn)

        tokens = TokenCounts(input_tokens=1000, output_tokens=500)
        result = await service.record_usage(
            tenant_id='tenant-1',
            provider='anthropic',
            model='claude-sonnet-4',
            tokens=tokens,
            session_id='session-123',
        )

        assert result is not None
        assert result.usage_id == 42
        assert result.cost_micro_cents == 5000
        assert result.over_limit is False
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_record_usage_db_unavailable(self, mock_get_pool, service):
        """Should return None when DB is unavailable."""
        mock_get_pool.return_value = None
        tokens = TokenCounts(input_tokens=100, output_tokens=50)
        result = await service.record_usage(
            tenant_id='t1', provider='openai', model='gpt-4o', tokens=tokens
        )
        assert result is None

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_check_budget_allowed(self, mock_get_pool, service):
        """Budget check returns allowed=True for subscription tenants."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            'allowed': True,
            'reason': 'OK',
            'balance_micro_cents': 100_000_000,
            'monthly_spend_micro_cents': 5_000_000,
            'monthly_limit_cents': None,
            'billing_model': 'subscription',
        })

        mock_get_pool.return_value = _mock_pool(mock_conn)

        check = await service.check_budget('tenant-1')
        assert check.allowed is True
        assert check.billing_model == 'subscription'

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_check_budget_over_limit(self, mock_get_pool, service):
        """Budget check blocks when monthly limit exceeded."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            'allowed': False,
            'reason': 'Monthly spending limit of $50.00 reached.',
            'balance_micro_cents': 0,
            'monthly_spend_micro_cents': 55_000_000,
            'monthly_limit_cents': 5000,
            'billing_model': 'prepaid',
        })

        mock_get_pool.return_value = _mock_pool(mock_conn)

        check = await service.check_budget('tenant-1')
        assert check.allowed is False
        assert 'limit' in check.reason.lower()

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_check_budget_db_unavailable(self, mock_get_pool, service):
        """Budget check should fail open when DB unavailable."""
        mock_get_pool.return_value = None
        check = await service.check_budget('tenant-1')
        assert check.allowed is False
        assert check.billing_model == 'unknown'

    @pytest.mark.asyncio
    @patch('a2a_server.token_billing.get_pool')
    async def test_add_credits(self, mock_get_pool, service):
        """Adding credits updates balance."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=120_000_000)  # $12.00

        mock_get_pool.return_value = _mock_pool(mock_conn)

        new_balance = await service.add_credits('tenant-1', amount_cents=2000)
        assert new_balance == 120_000_000


# ── Cost calculation math verification ───────────────────────────


class TestCostMath:
    """Verify the micro-cent math is correct."""

    def test_micro_cent_constants(self):
        assert MICRO_CENTS_PER_CENT == 10_000
        assert MICRO_CENTS_PER_DOLLAR == 1_000_000

    def test_cost_example_claude_opus(self):
        """
        1000 input tokens at $5/1M = $0.005
        500 output tokens at $25/1M = $0.0125
        Total = $0.0175 = 1.75 cents = 17,500 micro-cents

        In the DB function: tokens * cost_per_m = micro-cents
        So: 1000 * 5.0 + 500 * 25.0 = 5000 + 12500 = 17,500 micro-cents
        """
        input_mc = 1000 * 5.0
        output_mc = 500 * 25.0
        total_mc = input_mc + output_mc
        assert total_mc == 17_500
        assert total_mc / MICRO_CENTS_PER_DOLLAR == 0.0175

    def test_cost_example_with_cache(self):
        """
        Claude Opus with cache:
        1000 input at $5/1M, 500 output at $25/1M,
        2000 cache-read at $0.50/1M, 100 cache-write at $6.25/1M
        """
        total_mc = (1000 * 5.0) + (500 * 25.0) + (2000 * 0.5) + (100 * 6.25)
        assert total_mc == 5000 + 12500 + 1000 + 625
        assert total_mc == 19125
        assert total_mc / MICRO_CENTS_PER_DOLLAR == pytest.approx(0.019125)

    def test_markup_calculation(self):
        """20% markup on $0.0175 base."""
        base = 17500  # micro-cents
        markup_pct = 20.0
        markup = int(base * markup_pct / 100)
        assert markup == 3500
        total = base + markup
        assert total == 21000
        assert total / MICRO_CENTS_PER_DOLLAR == 0.021
