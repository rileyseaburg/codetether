"""
Tests for the marketing orchestrator.

Tests playbook execution, step sequencing, conditional steps, daily caps,
event handling, and audit logging.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_server.marketing_orchestrator import (
    MarketingOrchestrator,
    PlaybookResult,
    PlaybookStep,
    PLAYBOOKS,
    get_orchestrator,
    start_orchestrator,
    stop_orchestrator,
)


# ============================================================================
# Helpers
# ============================================================================


def _mock_httpx_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(json_data or {})
    resp.json.return_value = json_data or {}
    return resp


# ============================================================================
# Lifecycle Tests
# ============================================================================


class TestOrchestratorLifecycle:

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        orch = MarketingOrchestrator()
        await orch.start()
        assert orch._running is True
        await orch.stop()
        assert orch._running is False

    def test_get_health(self):
        orch = MarketingOrchestrator()
        health = orch.get_health()
        assert health['running'] is False
        assert health['total_executions'] == 0

    def test_playbook_result_to_dict(self):
        result = PlaybookResult('test_playbook', {'key': 'value'})
        d = result.to_dict()
        assert d['playbook'] == 'test_playbook'
        assert d['trigger_data'] == {'key': 'value'}
        assert d['steps_completed'] == 0


# ============================================================================
# Playbook Definition Tests
# ============================================================================


class TestPlaybookDefinitions:

    def test_roas_recovery_exists(self):
        assert 'roas_recovery' in PLAYBOOKS
        steps = PLAYBOOKS['roas_recovery']
        assert len(steps) >= 3
        assert steps[0].action == 'fetch_report'

    def test_conversion_spike_exists(self):
        assert 'conversion_spike' in PLAYBOOKS
        steps = PLAYBOOKS['conversion_spike']
        assert len(steps) >= 2

    def test_creative_refresh_exists(self):
        assert 'creative_refresh' in PLAYBOOKS
        steps = PLAYBOOKS['creative_refresh']
        assert len(steps) >= 2


# ============================================================================
# Step Execution Tests
# ============================================================================


class TestStepExecution:

    @pytest.mark.asyncio
    async def test_fetch_report_action(self):
        orch = MarketingOrchestrator()

        report = {'funnelBrain': {}, 'adBrain': {}}
        resp = _mock_httpx_response(200, report)

        with patch('a2a_server.http_client.http_request', new_callable=AsyncMock, return_value=resp):
            result = await orch._action_fetch_report()

        assert result == report

    @pytest.mark.asyncio
    async def test_fetch_report_failure(self):
        orch = MarketingOrchestrator()

        resp = _mock_httpx_response(500)

        with patch('a2a_server.http_client.http_request', new_callable=AsyncMock, return_value=resp):
            with pytest.raises(RuntimeError, match='500'):
                await orch._action_fetch_report()

    @pytest.mark.asyncio
    async def test_ad_sync_action(self):
        orch = MarketingOrchestrator()

        sync_data = {'campaignsSynced': 4, 'overallRoas': 2.5}
        resp = _mock_httpx_response(200, sync_data)

        with patch('a2a_server.http_client.http_request', new_callable=AsyncMock, return_value=resp):
            result = await orch._action_ad_sync({'dry_run': False})

        assert result['campaignsSynced'] == 4

    @pytest.mark.asyncio
    async def test_generate_video_action(self):
        orch = MarketingOrchestrator()

        video_data = {'creatify': {'videoId': 'v-1'}, 'youtube': {'videoId': 'yt-1'}}
        resp = _mock_httpx_response(200, video_data)

        with patch('a2a_server.http_client.http_request', new_callable=AsyncMock, return_value=resp):
            result = await orch._action_generate_video({'script_style': 'result_focused'})

        assert result['creatify']['videoId'] == 'v-1'

    @pytest.mark.asyncio
    async def test_snapshot_funnel_action(self):
        orch = MarketingOrchestrator()

        mock_tracker = MagicMock()
        mock_tracker._snapshot_funnel_state = AsyncMock()

        with patch('a2a_server.conversion_tracker.get_conversion_tracker', return_value=mock_tracker):
            result = await orch._action_snapshot_funnel()

        assert result['status'] == 'snapshot_saved'
        mock_tracker._snapshot_funnel_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_funnel_no_tracker(self):
        orch = MarketingOrchestrator()

        with patch('a2a_server.conversion_tracker.get_conversion_tracker', return_value=None):
            result = await orch._action_snapshot_funnel()

        assert result['status'] == 'tracker_not_running'


class TestExecuteStep:

    @pytest.mark.asyncio
    async def test_execute_step_success(self):
        orch = MarketingOrchestrator()

        step = PlaybookStep('test', 'Test step', 'fetch_report')

        with patch.object(orch, '_action_fetch_report', new_callable=AsyncMock, return_value={'data': True}):
            result = await orch._execute_step(step, {})

        assert result['status'] == 'success'
        assert result['step'] == 'test'

    @pytest.mark.asyncio
    async def test_execute_step_failure(self):
        orch = MarketingOrchestrator()

        step = PlaybookStep('test', 'Test step', 'fetch_report')

        with patch.object(orch, '_action_fetch_report', new_callable=AsyncMock, side_effect=RuntimeError('boom')):
            result = await orch._execute_step(step, {})

        assert result['status'] == 'error'
        assert 'boom' in result['error']

    @pytest.mark.asyncio
    async def test_execute_step_unknown_action(self):
        orch = MarketingOrchestrator()

        step = PlaybookStep('test', 'Test step', 'nonexistent_action')
        result = await orch._execute_step(step, {})

        assert result['status'] == 'error'
        assert 'Unknown action' in result['error']


# ============================================================================
# Playbook Execution Tests
# ============================================================================


class TestPlaybookExecution:

    @pytest.mark.asyncio
    async def test_run_full_playbook(self):
        orch = MarketingOrchestrator()
        orch._running = True

        with patch.object(orch, '_execute_step', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {'step': 'test', 'status': 'success', 'data': {}}

            with patch.object(orch, '_audit', new_callable=AsyncMock):
                result = await orch.run_playbook('roas_recovery', trigger_data={'roas': 1.2})

        assert result.success is True
        assert result.steps_completed >= 1
        assert result.playbook_name == 'roas_recovery'

    @pytest.mark.asyncio
    async def test_conditional_step_skipped_on_failure(self):
        orch = MarketingOrchestrator()
        orch._running = True

        call_count = 0

        async def mock_execute(step, trigger):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {'step': step.name, 'status': 'error', 'error': 'fail'}
            return {'step': step.name, 'status': 'success', 'data': {}}

        with patch.object(orch, '_execute_step', side_effect=mock_execute), \
             patch.object(orch, '_audit', new_callable=AsyncMock):
            result = await orch.run_playbook('roas_recovery')

        # First step fails, second should be skipped (previous_success condition)
        assert result.steps_failed >= 1
        skipped = [s for s in result.step_results if s.get('status') == 'skipped']
        assert len(skipped) >= 1

    @pytest.mark.asyncio
    async def test_daily_cap_enforced(self):
        orch = MarketingOrchestrator()
        orch._running = True
        orch._day_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        orch._executions_today['roas_recovery'] = 3

        with patch.object(orch, '_audit', new_callable=AsyncMock):
            result = await orch.run_playbook('roas_recovery', max_daily_runs=3)

        assert result.steps_completed == 0
        assert any(s.get('reason', '').startswith('Daily cap') for s in result.step_results)

    @pytest.mark.asyncio
    async def test_unknown_playbook(self):
        orch = MarketingOrchestrator()
        orch._running = True

        result = await orch.run_playbook('nonexistent')
        assert result.steps_completed == 0

    @pytest.mark.asyncio
    async def test_disabled_orchestrator(self):
        orch = MarketingOrchestrator()

        with patch('a2a_server.marketing_orchestrator.ORCHESTRATOR_ENABLED', False):
            result = await orch.run_playbook('roas_recovery')

        assert result.steps_completed == 0

    @pytest.mark.asyncio
    async def test_day_rollover_resets_counter(self):
        orch = MarketingOrchestrator()
        orch._running = True
        orch._day_key = '2020-01-01'  # old day
        orch._executions_today['roas_recovery'] = 99

        with patch.object(orch, '_execute_step', new_callable=AsyncMock,
                          return_value={'step': 'test', 'status': 'success', 'data': {}}), \
             patch.object(orch, '_audit', new_callable=AsyncMock):
            result = await orch.run_playbook('roas_recovery')

        assert result.steps_completed >= 1  # counter was reset


# ============================================================================
# Event Handler Tests
# ============================================================================


class TestEventHandler:

    @pytest.mark.asyncio
    async def test_roas_low_triggers_recovery(self):
        orch = MarketingOrchestrator()
        orch._running = True

        run_mock = AsyncMock(return_value=PlaybookResult('roas_recovery', {}))
        orch.run_playbook = run_mock

        await orch.handle_marketing_event('marketing.roas_low', {'roas': 1.2})

        run_mock.assert_called_once_with('roas_recovery', trigger_data={'roas': 1.2})

    @pytest.mark.asyncio
    async def test_conversion_triggers_spike(self):
        orch = MarketingOrchestrator()
        orch._running = True

        run_mock = AsyncMock(return_value=PlaybookResult('conversion_spike', {}))
        orch.run_playbook = run_mock

        await orch.handle_marketing_event('conversion.subscription', {
            'event_type': 'subscription',
            'value_dollars': 29.0,
        })

        run_mock.assert_called_once()
        assert run_mock.call_args[0][0] == 'conversion_spike'

    @pytest.mark.asyncio
    async def test_unknown_event_ignored(self):
        orch = MarketingOrchestrator()
        orch._running = True

        with patch.object(orch, 'run_playbook', new_callable=AsyncMock) as mock_run:
            await orch.handle_marketing_event('unknown.event', {})

        mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_ignores_events(self):
        orch = MarketingOrchestrator()

        with patch('a2a_server.marketing_orchestrator.ORCHESTRATOR_ENABLED', False), \
             patch.object(orch, 'run_playbook', new_callable=AsyncMock) as mock_run:
            await orch.handle_marketing_event('marketing.roas_low', {})

        mock_run.assert_not_called()


# ============================================================================
# Global Instance Tests
# ============================================================================


class TestGlobalInstance:

    @pytest.mark.asyncio
    async def test_start_and_stop_global(self):
        import a2a_server.marketing_orchestrator as mod
        original = mod._orchestrator
        try:
            mod._orchestrator = None
            orch = await start_orchestrator()
            assert orch is not None
            assert get_orchestrator() is orch
            await stop_orchestrator()
            assert get_orchestrator() is None
        finally:
            mod._orchestrator = original
