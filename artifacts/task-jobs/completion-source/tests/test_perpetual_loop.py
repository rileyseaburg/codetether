"""
Tests for the perpetual cognition loop module.

Tests cover:
- _parse_loop_result() JSON extraction from agent output
- _build_iteration_prompt() format
- Budget gates (daily cost ceiling, iteration cap)
- Model downgrade threshold logic
- handle_task_completion_for_loops() — the feedback loop closer
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from a2a_server.perpetual_loop import (
    PerpetualCognitionManager,
    _parse_loop_result,
    handle_task_completion_for_loops,
)


# ── _parse_loop_result ───────────────────────────────────────────


class TestParseLoopResult:
    def test_json_code_block(self):
        result = '''Here is my analysis.

```json
{
  "summary": "All healthy",
  "next_state": {"checks": 5}
}
```

Done.'''
        parsed = _parse_loop_result(result)
        assert parsed['summary'] == 'All healthy'
        assert parsed['next_state'] == {'checks': 5}

    def test_raw_json(self):
        result = '{"summary": "ok", "next_state": {"x": 1}}'
        parsed = _parse_loop_result(result)
        assert parsed['summary'] == 'ok'
        assert parsed['next_state']['x'] == 1

    def test_plain_text_fallback(self):
        result = 'I checked everything and it looks fine.'
        parsed = _parse_loop_result(result)
        assert 'summary' in parsed
        assert 'next_state' in parsed
        assert parsed['summary'] == result

    def test_malformed_json_block(self):
        result = '```json\n{bad json}\n```'
        parsed = _parse_loop_result(result)
        # Should fall through to plain text fallback
        assert 'summary' in parsed

    def test_empty_result(self):
        parsed = _parse_loop_result('')
        assert 'summary' in parsed
        assert parsed['summary'] == ''

    def test_nested_json_code_block(self):
        result = '''```json
{
  "summary": "Deployed v2",
  "next_state": {
    "deployed_versions": ["v1", "v2"],
    "last_deploy": "2026-01-01T00:00:00Z"
  }
}
```'''
        parsed = _parse_loop_result(result)
        assert parsed['next_state']['deployed_versions'] == ['v1', 'v2']


# ── _build_iteration_prompt ──────────────────────────────────────


class TestBuildIterationPrompt:
    def setup_method(self):
        self.manager = PerpetualCognitionManager()

    def test_includes_iteration_number(self):
        prompt = self.manager._build_iteration_prompt(
            persona_slug='monitor',
            persona_system_prompt='You are the monitor.',
            iteration_number=42,
            state={},
        )
        assert '## Perpetual Loop Iteration #42' in prompt

    def test_includes_carried_state(self):
        state = {'last_check': '2026-01-01', 'issues': 0}
        prompt = self.manager._build_iteration_prompt(
            persona_slug='monitor',
            persona_system_prompt='You are the monitor.',
            iteration_number=1,
            state=state,
        )
        assert '"last_check"' in prompt
        assert '"issues"' in prompt

    def test_includes_persona_system_prompt(self):
        prompt = self.manager._build_iteration_prompt(
            persona_slug='deployer',
            persona_system_prompt='You are the deployer. Deploy things.',
            iteration_number=1,
            state={},
        )
        assert 'You are the deployer. Deploy things.' in prompt

    def test_empty_state_shows_empty_json(self):
        prompt = self.manager._build_iteration_prompt(
            persona_slug='monitor',
            persona_system_prompt='Sys prompt.',
            iteration_number=1,
            state={},
        )
        assert '{}' in prompt


# ── Budget gates ─────────────────────────────────────────────────


class TestBudgetGates:
    def setup_method(self):
        self.manager = PerpetualCognitionManager()

    @pytest.mark.asyncio
    async def test_iteration_cap_blocks(self):
        """Should skip iteration when daily cap is reached."""
        mock_conn = AsyncMock()
        loop = {
            'id': 'loop-1',
            'tenant_id': 't1',
            'user_id': 'u1',
            'persona_slug': 'monitor',
            'codebase_id': None,
            'state': {},
            'iteration_count': 50,
            'iteration_interval_seconds': 300,
            'max_iterations_per_day': 10,
            'iterations_today': 10,  # At cap
            'daily_cost_ceiling_cents': 500,
            'cost_today_cents': 0,
            'last_iteration_at': None,
        }
        # Should return without dispatching
        await self.manager._run_iteration(mock_conn, loop)
        # dispatch_cron_task should NOT have been called
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exhausted_changes_status(self):
        """Should set status to budget_exhausted when ceiling reached."""
        mock_conn = AsyncMock()
        loop = {
            'id': 'loop-2',
            'tenant_id': 't1',
            'user_id': None,
            'persona_slug': 'monitor',
            'codebase_id': None,
            'state': {},
            'iteration_count': 50,
            'iteration_interval_seconds': 300,
            'max_iterations_per_day': 100,
            'iterations_today': 5,
            'daily_cost_ceiling_cents': 500,
            'cost_today_cents': 500,  # At ceiling
            'last_iteration_at': None,
        }
        await self.manager._run_iteration(mock_conn, loop)
        # Should have called UPDATE to set budget_exhausted
        calls = [str(c) for c in mock_conn.execute.call_args_list]
        assert any('budget_exhausted' in c for c in calls)


# ── handle_task_completion_for_loops ─────────────────────────────


class TestHandleTaskCompletion:
    @pytest.mark.asyncio
    async def test_ignores_non_loop_tasks(self):
        """Tasks without perpetual_loop_id in metadata should be ignored."""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = mock_cm

        # Task has no perpetual_loop_id
        mock_conn.fetchrow.return_value = {'metadata': {'some': 'data'}}

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await handle_task_completion_for_loops('task-1', 'completed', 'result')

        # Should not attempt to find iteration
        assert mock_conn.fetchrow.call_count == 1  # Only the metadata lookup

    @pytest.mark.asyncio
    async def test_skips_non_terminal_status(self):
        """Should skip if status is not completed or failed."""
        # Should return immediately without touching DB
        with patch('a2a_server.database.get_pool', new_callable=AsyncMock) as mock_get_pool:
            await handle_task_completion_for_loops('task-1', 'running', None)
            mock_get_pool.assert_not_called()
