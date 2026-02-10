"""
Tests for the marketing automation service.

Tests the MarketingAutomationService and its integration with the
proactive rule engine and audit trail.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_server.marketing_automation import (
    MarketingAutomationService,
    get_marketing_automation,
    start_marketing_automation,
    stop_marketing_automation,
    DAILY_BUDGET_DOLLARS,
    MAX_VIDEOS_PER_WEEK,
    VIDEO_SCRIPT_STYLES,
)


# ============================================================================
# Helpers
# ============================================================================


def _mock_httpx_response(status_code=200, json_data=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(json_data or {})
    resp.json.return_value = json_data or {}
    return resp


def _sample_report():
    """Sample self-selling performance report."""
    return {
        'funnelBrain': {
            'totalVariants': 18,
            'activeTests': 5,
            'winningVariants': [],
            'allVariants': [],
        },
        'adBrain': {
            'overallRoas': 2.1,
            'totalAdSpendCents': 15000,
            'totalRevenueCents': 31500,
            'customerAcquisitionCost': 3000,
            'campaignAllocations': [],
            'campaignDecisions': [],
        },
    }


def _sample_sync_result(roas=2.1, conversions=15):
    """Sample Google Ads sync result."""
    return {
        'syncedAt': datetime.now(timezone.utc).isoformat(),
        'campaignsSynced': 4,
        'optimizationRun': True,
        'decisions': [
            {
                'campaignId': 'ct-google-ai-agent',
                'action': 'maintain',
                'reason': 'Performance acceptable',
                'applied': False,
            },
            {
                'campaignId': 'ct-google-security',
                'action': 'scale_up',
                'reason': 'ROAS 3.2x, CAC $25',
                'applied': True,
            },
        ],
        'totalSpendDollars': 150.0,
        'totalConversions': conversions,
        'overallRoas': roas,
    }


def _sample_video_result():
    """Sample video pipeline result."""
    return {
        'pipeline': 'full_pipeline_complete',
        'creatify': {
            'videoId': 'creatify-123',
            'videoUrl': 'https://creatify.ai/video/123.mp4',
        },
        'youtube': {
            'videoId': 'yt-abc123',
            'youtubeUrl': 'https://youtube.com/watch?v=yt-abc123',
        },
        'googleAds': {
            'campaignId': 'campaign-456',
            'campaignResourceName': 'customers/123/campaigns/456',
            'adGroupId': 'ag-789',
            'adResourceName': 'customers/123/ads/789',
            'status': 'PAUSED',
        },
    }


# ============================================================================
# Service lifecycle tests
# ============================================================================


class TestServiceLifecycle:
    """Test service start/stop and health."""

    def test_health_when_not_started(self):
        service = MarketingAutomationService()
        health = service.get_health()
        assert health['running'] is False
        assert health['videos_this_week'] == 0
        assert health['last_cycle'] is None

    def test_health_reports_config(self):
        service = MarketingAutomationService(poll_interval=7200)
        health = service.get_health()
        assert health['poll_interval_seconds'] == 7200
        assert health['max_videos_per_week'] == MAX_VIDEOS_PER_WEEK
        assert health['daily_budget_dollars'] == DAILY_BUDGET_DOLLARS

    def test_get_last_report_empty(self):
        service = MarketingAutomationService()
        assert service.get_last_report() is None

    @pytest.mark.asyncio
    async def test_start_disabled(self):
        """Service should not start when MARKETING_AUTOMATION_ENABLED is false."""
        service = MarketingAutomationService()
        with patch('a2a_server.marketing_automation.MARKETING_AUTOMATION_ENABLED', False):
            await service.start()
            assert service._running is False
            assert service._task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Stop should be safe to call when not started."""
        service = MarketingAutomationService()
        await service.stop()  # Should not raise


# ============================================================================
# Report fetch tests
# ============================================================================


class TestReportFetch:
    """Test the performance report fetching step."""

    @pytest.mark.asyncio
    async def test_fetch_report_success(self):
        service = MarketingAutomationService()
        report = _sample_report()

        mock_resp = _mock_httpx_response(200, report)

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock):
                result = await service._fetch_report()

        assert result is not None
        assert result['funnelBrain']['totalVariants'] == 18
        assert service._last_report is not None

    @pytest.mark.asyncio
    async def test_fetch_report_failure(self):
        service = MarketingAutomationService()

        mock_resp = _mock_httpx_response(500, {'error': 'Internal error'})

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock):
                result = await service._fetch_report()

        assert result is None


# ============================================================================
# Ad sync tests
# ============================================================================


class TestAdSync:
    """Test the Google Ads sync step."""

    @pytest.mark.asyncio
    async def test_ad_sync_success(self):
        service = MarketingAutomationService()
        sync = _sample_sync_result()

        mock_resp = _mock_httpx_response(200, sync)

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock):
                result = await service._run_ad_sync()

        assert result is not None
        assert result['campaignsSynced'] == 4
        assert result['overallRoas'] == 2.1

    @pytest.mark.asyncio
    async def test_ad_sync_publishes_roas_event_when_low(self):
        service = MarketingAutomationService()
        sync = _sample_sync_result(roas=1.2, conversions=20)

        mock_resp = _mock_httpx_response(200, sync)
        mock_engine = MagicMock()
        mock_engine.evaluate_event_rules = AsyncMock()

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock):
                with patch('a2a_server.rule_engine.get_rule_engine', return_value=mock_engine):
                    result = await service._run_ad_sync()

        assert result is not None
        assert result['overallRoas'] == 1.2
        # Verify the low ROAS event was published to the rule engine
        mock_engine.evaluate_event_rules.assert_called_once()
        call_args = mock_engine.evaluate_event_rules.call_args
        assert call_args[0][0] == 'marketing.roas_low'
        assert call_args[0][1]['roas'] == 1.2

    @pytest.mark.asyncio
    async def test_ad_sync_failure(self):
        service = MarketingAutomationService()

        mock_resp = _mock_httpx_response(401, {'error': 'Unauthorized'})

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock):
                result = await service._run_ad_sync()

        assert result is None


# ============================================================================
# Video generation evaluation
# ============================================================================


class TestVideoGeneration:
    """Test the video generation decision logic."""

    @pytest.mark.asyncio
    async def test_no_video_when_roas_high(self):
        """Should not generate video when ROAS is healthy."""
        service = MarketingAutomationService()
        service._week_start = datetime.now(timezone.utc)

        sync = _sample_sync_result(roas=3.0, conversions=20)

        with patch.object(service, '_generate_video', new_callable=AsyncMock) as mock_gen:
            await service._evaluate_video_generation(None, sync)

        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_video_when_roas_low(self):
        """Should generate video when ROAS drops below 1.5x."""
        service = MarketingAutomationService()
        service._week_start = datetime.now(timezone.utc)

        sync = _sample_sync_result(roas=1.0, conversions=15)

        with patch.object(service, '_generate_video', new_callable=AsyncMock) as mock_gen:
            await service._evaluate_video_generation(None, sync)

        mock_gen.assert_called_once()
        args = mock_gen.call_args
        assert args[0][0] == 'problem_focused'  # first script style
        assert 'below 1.5x' in args[0][1]

    @pytest.mark.asyncio
    async def test_video_bootstrap_no_conversions(self):
        """Should generate first video when no conversions yet."""
        service = MarketingAutomationService()
        service._week_start = datetime.now(timezone.utc)

        sync = _sample_sync_result(roas=0, conversions=0)

        with patch.object(service, '_generate_video', new_callable=AsyncMock) as mock_gen:
            await service._evaluate_video_generation(None, sync)

        mock_gen.assert_called_once()
        assert 'bootstrapping' in mock_gen.call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_video_weekly_cap(self):
        """Should not generate video once weekly cap is reached."""
        service = MarketingAutomationService()
        service._week_start = datetime.now(timezone.utc)
        service._videos_this_week = MAX_VIDEOS_PER_WEEK

        sync = _sample_sync_result(roas=0.5, conversions=20)

        with patch.object(service, '_generate_video', new_callable=AsyncMock) as mock_gen:
            await service._evaluate_video_generation(None, sync)

        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_video_style_rotation(self):
        """Should rotate through script styles."""
        service = MarketingAutomationService()
        service._week_start = datetime.now(timezone.utc)
        service._videos_this_week = 1  # already generated one

        sync = _sample_sync_result(roas=1.0, conversions=15)

        with patch.object(service, '_generate_video', new_callable=AsyncMock) as mock_gen:
            await service._evaluate_video_generation(None, sync)

        mock_gen.assert_called_once()
        # Second video should use second script style
        assert mock_gen.call_args[0][0] == 'result_focused'

    @pytest.mark.asyncio
    async def test_generate_video_success(self):
        """Test actual video generation API call."""
        service = MarketingAutomationService()
        video_result = _sample_video_result()

        mock_resp = _mock_httpx_response(201, video_result)

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock) as mock_audit:
                await service._generate_video('problem_focused', 'Low ROAS')

        assert service._videos_this_week == 1
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs['decision_type'] == 'video_generated'


# ============================================================================
# Headers and configuration
# ============================================================================


class TestConfiguration:
    """Test configuration and helper methods."""

    def test_headers_without_api_key(self):
        service = MarketingAutomationService()
        with patch('a2a_server.marketing_automation.MARKETING_API_KEY', ''):
            headers = service._headers()
        assert 'x-api-key' not in headers
        assert headers['Content-Type'] == 'application/json'

    def test_headers_with_api_key(self):
        service = MarketingAutomationService()
        with patch('a2a_server.marketing_automation.MARKETING_API_KEY', 'test-key-123'):
            headers = service._headers()
        assert headers['x-api-key'] == 'test-key-123'

    def test_video_script_styles(self):
        """Verify all 3 script styles are defined."""
        assert len(VIDEO_SCRIPT_STYLES) == 3
        assert 'problem_focused' in VIDEO_SCRIPT_STYLES
        assert 'result_focused' in VIDEO_SCRIPT_STYLES
        assert 'comparison' in VIDEO_SCRIPT_STYLES


# ============================================================================
# Audit integration
# ============================================================================


class TestAuditIntegration:
    """Test that marketing decisions are audit-logged."""

    @pytest.mark.asyncio
    async def test_audit_called_on_report(self):
        service = MarketingAutomationService()
        report = _sample_report()

        mock_resp = _mock_httpx_response(200, report)

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock) as mock_audit:
                await service._fetch_report()

        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs['decision_type'] == 'report_fetched'

    @pytest.mark.asyncio
    async def test_audit_called_on_sync(self):
        service = MarketingAutomationService()
        sync = _sample_sync_result()

        mock_resp = _mock_httpx_response(200, sync)

        with patch('a2a_server.marketing_automation.httpx.AsyncClient') as mock_client_cls:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=ctx)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(service, '_audit', new_callable=AsyncMock) as mock_audit:
                await service._run_ad_sync()

        mock_audit.assert_called()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs['decision_type'] == 'ad_sync_complete'

    @pytest.mark.asyncio
    async def test_audit_never_raises(self):
        """Audit errors should never break the automation loop."""
        service = MarketingAutomationService()

        # _audit catches exceptions from log_decision internally (lazy import)
        # Patch at the source module
        with patch('a2a_server.audit_log.log_decision', new_callable=AsyncMock, side_effect=Exception('DB down')):
            # Should not raise
            await service._audit(
                decision_type='test',
                description='test decision',
            )


# ============================================================================
# Global instance management
# ============================================================================


class TestGlobalManagement:
    """Test module-level start/stop functions."""

    def test_get_returns_none_initially(self):
        import a2a_server.marketing_automation as mod
        original = mod._service
        try:
            mod._service = None
            assert get_marketing_automation() is None
        finally:
            mod._service = original

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        import a2a_server.marketing_automation as mod
        original = mod._service
        try:
            mod._service = None

            with patch('a2a_server.marketing_automation.MARKETING_AUTOMATION_ENABLED', False):
                service = await start_marketing_automation()
                assert service is not None
                assert mod._service is service

                await stop_marketing_automation()
                assert mod._service is None
        finally:
            mod._service = original
