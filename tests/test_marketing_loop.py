"""
Tests for the marketing perpetual loop auto-starter.

Tests ensure_marketing_loop: creation, resumption, idempotency.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_server.marketing_loop import (
    ensure_marketing_loop,
    MARKETING_LOOP_ID,
    _build_initial_state,
)


# ============================================================================
# Helpers
# ============================================================================


def _make_mock_pool():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_ctx

    return mock_pool, mock_conn


# ============================================================================
# Tests
# ============================================================================


class TestEnsureMarketingLoop:

    @pytest.mark.asyncio
    async def test_creates_loop_when_none_exists(self):
        mock_pool, mock_conn = _make_mock_pool()

        # Persona exists, loop does not
        mock_conn.fetchrow.side_effect = [
            {'slug': 'marketer'},  # persona check
            None,                   # loop check
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool), \
             patch('a2a_server.audit_log.log_decision', new_callable=AsyncMock):
            result = await ensure_marketing_loop()

        assert result == MARKETING_LOOP_ID
        # Should INSERT into perpetual_loops
        insert_calls = [
            c for c in mock_conn.execute.call_args_list
            if 'perpetual_loops' in str(c)
        ]
        assert len(insert_calls) >= 1

    @pytest.mark.asyncio
    async def test_resumes_paused_loop(self):
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetchrow.side_effect = [
            {'slug': 'marketer'},
            {'id': MARKETING_LOOP_ID, 'status': 'paused'},
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await ensure_marketing_loop()

        assert result == MARKETING_LOOP_ID
        update_calls = [
            c for c in mock_conn.execute.call_args_list
            if 'running' in str(c)
        ]
        assert len(update_calls) >= 1

    @pytest.mark.asyncio
    async def test_resumes_budget_exhausted_loop(self):
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetchrow.side_effect = [
            {'slug': 'marketer'},
            {'id': MARKETING_LOOP_ID, 'status': 'budget_exhausted'},
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await ensure_marketing_loop()

        assert result == MARKETING_LOOP_ID

    @pytest.mark.asyncio
    async def test_already_running_noop(self):
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetchrow.side_effect = [
            {'slug': 'marketer'},
            {'id': MARKETING_LOOP_ID, 'status': 'running'},
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await ensure_marketing_loop()

        assert result == MARKETING_LOOP_ID
        # Should NOT insert or update
        assert mock_conn.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        with patch('a2a_server.marketing_loop.MARKETING_LOOP_ENABLED', False):
            result = await ensure_marketing_loop()

        assert result is None

    @pytest.mark.asyncio
    async def test_no_persona_returns_none(self):
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetchrow.side_effect = [
            None,  # persona not found
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await ensure_marketing_loop()

        assert result is None

    @pytest.mark.asyncio
    async def test_no_pool_returns_none(self):
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=None):
            result = await ensure_marketing_loop()

        assert result is None

    @pytest.mark.asyncio
    async def test_db_error_returns_none(self):
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, side_effect=Exception('DB down')):
            result = await ensure_marketing_loop()

        assert result is None


class TestBuildInitialState:

    def test_initial_state_structure(self):
        state = _build_initial_state()

        assert state['strategy_version'] == 1
        assert 'focus_areas' in state
        assert 'kpis' in state
        assert state['kpis']['target_roas'] == 3.0
        assert 'channels_active' in state
        assert 'learnings' in state
        assert state['learnings'] == []
        assert state['last_analysis'] is None
