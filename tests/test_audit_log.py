"""
Tests for the audit_log module.

Tests cover:
- log_decision() writes to autonomous_decisions table
- log_decision() never raises (best-effort pattern)
- update_decision_outcome() updates existing records
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from a2a_server.audit_log import log_decision, update_decision_outcome


def _make_mock_pool():
    """Create a mock asyncpg pool with context-manager-based acquire()."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = mock_cm
    return mock_pool, mock_conn


class TestLogDecision:
    @pytest.mark.asyncio
    async def test_returns_decision_id_on_success(self):
        mock_pool, mock_conn = _make_mock_pool()

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await log_decision(
                source='rule_engine',
                decision_type='trigger_rule',
                description='Test decision',
                trigger_data={'event': 'test'},
                decision_data={'rule_id': 'r1'},
                task_id='t1',
                tenant_id='tenant-1',
            )

        assert result is not None
        assert len(result) == 36  # UUID format
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pool(self):
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=None):
            result = await log_decision(
                source='perpetual_loop',
                decision_type='dispatch_iteration',
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_never_raises_on_db_error(self):
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, side_effect=Exception('DB down')):
            result = await log_decision(
                source='rule_engine',
                decision_type='trigger_rule',
            )
        assert result is None  # Should not raise

    @pytest.mark.asyncio
    async def test_valid_source_values(self):
        """All valid source values should be accepted."""
        mock_pool, mock_conn = _make_mock_pool()

        for source in ['rule_engine', 'perpetual_loop', 'ralph', 'health_monitor', 'cron_scheduler']:
            with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
                result = await log_decision(
                    source=source,
                    decision_type='test',
                )
            assert result is not None


class TestUpdateDecisionOutcome:
    @pytest.mark.asyncio
    async def test_updates_existing_record(self):
        mock_pool, mock_conn = _make_mock_pool()

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await update_decision_outcome('dec-1', 'success', cost_cents=42)

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert 'dec-1' in call_args[0]
        assert 'success' in call_args[0]

    @pytest.mark.asyncio
    async def test_never_raises_on_error(self):
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, side_effect=Exception('DB down')):
            # Should not raise
            await update_decision_outcome('dec-1', 'failed')
