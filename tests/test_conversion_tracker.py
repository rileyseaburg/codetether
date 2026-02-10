"""
Tests for the conversion tracker service.

Tests ConversionTracker: local storage, forwarding to FunnelBrain and Google Ads,
FunnelBrain state persistence, conversion analytics, and retry logic.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a_server.conversion_tracker import (
    ConversionTracker,
    track_conversion,
    get_conversion_tracker,
    start_conversion_tracker,
    stop_conversion_tracker,
    DEFAULT_CONVERSION_VALUES,
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


def _make_mock_pool():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetchval = AsyncMock(return_value=0)
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_pool = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_ctx

    return mock_pool, mock_conn


# ============================================================================
# ConversionTracker Unit Tests
# ============================================================================


class TestConversionTrackerLifecycle:
    """Test service lifecycle."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        tracker = ConversionTracker(persist_interval=999999)
        await tracker.start()
        assert tracker._running is True
        await tracker.stop()
        assert tracker._running is False

    @pytest.mark.asyncio
    async def test_double_start(self):
        tracker = ConversionTracker(persist_interval=999999)
        await tracker.start()
        await tracker.start()  # idempotent
        assert tracker._running is True
        await tracker.stop()

    def test_get_health(self):
        tracker = ConversionTracker()
        health = tracker.get_health()
        assert health['running'] is False
        assert health['enabled'] is True
        assert health['conversions_tracked'] == 0


class TestConversionStorage:
    """Test local conversion event storage."""

    @pytest.mark.asyncio
    async def test_store_conversion(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await tracker._store_conversion(
                conversion_id='conv-1',
                event_type='signup',
                email='user@test.com',
                user_id='u-1',
                session_id='sess-1',
                gclid='gclid-1',
                variant_ids={'hero_headline': 'var-1'},
                value_dollars=5.0,
                order_id='order-1',
                metadata={'source': 'organic'},
            )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert 'conversion_events' in call_args[0][0]
        assert call_args[0][1] == 'conv-1'
        assert call_args[0][2] == 'signup'

    @pytest.mark.asyncio
    async def test_store_conversion_no_pool(self):
        """Storage gracefully handles missing DB."""
        tracker = ConversionTracker()

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=None):
            await tracker._store_conversion(
                conversion_id='conv-1',
                event_type='signup',
                email=None, user_id=None, session_id=None,
                gclid=None, variant_ids=None,
                value_dollars=5.0, order_id=None, metadata=None,
            )
            # Should not raise


class TestFunnelBrainForwarding:
    """Test forwarding conversions to FunnelBrain."""

    @pytest.mark.asyncio
    async def test_forward_to_funnel_brain_success(self):
        tracker = ConversionTracker()

        resp = _mock_httpx_response(200, {'recorded': True})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tracker._forward_to_funnel_brain(
                session_id='sess-1',
                event_type='signup',
                variant_ids={'hero_headline': 'var-1'},
                value_cents=500,
            )

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert '/api/optimization/assemble' in call_args[0][0]
        body = call_args[1]['json']
        assert body['sessionId'] == 'sess-1'
        assert body['eventType'] == 'signup'

    @pytest.mark.asyncio
    async def test_forward_to_funnel_brain_failure(self):
        tracker = ConversionTracker()

        resp = _mock_httpx_response(500, {'error': 'Internal'})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tracker._forward_to_funnel_brain(
                session_id='sess-1',
                event_type='signup',
                variant_ids=None,
                value_cents=500,
            )

        assert result is False


class TestGoogleAdsForwarding:
    """Test forwarding conversions to Google Ads."""

    @pytest.mark.asyncio
    async def test_forward_to_google_ads_success(self):
        tracker = ConversionTracker()

        resp = _mock_httpx_response(200, {'tracked': True})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tracker._forward_to_google_ads(
                event_type='subscription',
                email='user@test.com',
                gclid='gclid-1',
                value_dollars=29.0,
                order_id='sub-1',
            )

        assert result is True
        call_args = mock_client.post.call_args
        assert '/api/google/conversions' in call_args[0][0]

    @pytest.mark.asyncio
    async def test_forward_to_google_ads_network_error(self):
        tracker = ConversionTracker()

        import httpx
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError('timeout'))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tracker._forward_to_google_ads(
                event_type='subscription',
                email='user@test.com',
                gclid=None,
                value_dollars=29.0,
                order_id=None,
            )

        assert result is False


class TestForwardConversion:
    """Test the full forwarding pipeline."""

    @pytest.mark.asyncio
    async def test_forwards_to_both_systems(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        fb_mock = AsyncMock(return_value=True)
        ga_mock = AsyncMock(return_value=True)
        tracker._forward_to_funnel_brain = fb_mock
        tracker._forward_to_google_ads = ga_mock

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await tracker._forward_conversion(
                conversion_id='conv-1',
                event_type='subscription',
                email='user@test.com',
                session_id='sess-1',
                gclid='gclid-1',
                variant_ids={'hero_headline': 'var-1'},
                value_dollars=29.0,
                order_id='sub-1',
            )

        fb_mock.assert_called_once()
        ga_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_funnel_without_session(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        fb_mock = AsyncMock(return_value=True)
        ga_mock = AsyncMock(return_value=True)
        tracker._forward_to_funnel_brain = fb_mock
        tracker._forward_to_google_ads = ga_mock

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await tracker._forward_conversion(
                conversion_id='conv-1',
                event_type='subscription',
                email='user@test.com',
                session_id=None,
                gclid=None,
                variant_ids=None,
                value_dollars=29.0,
                order_id=None,
            )

        fb_mock.assert_not_called()


class TestTrackConversion:
    """Test the main track() method."""

    @pytest.mark.asyncio
    async def test_track_stores_and_forwards(self):
        tracker = ConversionTracker()
        tracker._running = True

        store_mock = AsyncMock()
        tracker._store_conversion = store_mock
        tracker._forward_conversion = AsyncMock()
        tracker._publish_conversion_event = AsyncMock()

        with patch('a2a_server.conversion_tracker.CONVERSION_TRACKING_ENABLED', True):
            result = await tracker.track(
                event_type='signup',
                email='user@test.com',
                user_id='u-1',
            )

        assert result is not None
        store_mock.assert_called_once()
        assert tracker._conversions_tracked == 1

    @pytest.mark.asyncio
    async def test_track_disabled(self):
        tracker = ConversionTracker()

        with patch('a2a_server.conversion_tracker.CONVERSION_TRACKING_ENABLED', False):
            result = await tracker.track(event_type='signup')

        assert result is None

    @pytest.mark.asyncio
    async def test_track_uses_default_values(self):
        tracker = ConversionTracker()
        tracker._running = True

        store_mock = AsyncMock()
        tracker._store_conversion = store_mock
        tracker._forward_conversion = AsyncMock()
        tracker._publish_conversion_event = AsyncMock()

        with patch('a2a_server.conversion_tracker.CONVERSION_TRACKING_ENABLED', True):
            await tracker.track(event_type='subscription')

        call_kwargs = store_mock.call_args[1]
        assert call_kwargs['value_dollars'] == DEFAULT_CONVERSION_VALUES['subscription']


class TestFunnelStatePersistence:
    """Test FunnelBrain state snapshots."""

    @pytest.mark.asyncio
    async def test_snapshot_funnel_state(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        report = {
            'funnelBrain': {'totalVariants': 18, 'variants': []},
            'adBrain': {'overallRoas': 2.5},
        }
        resp = _mock_httpx_response(200, report)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            await tracker._snapshot_funnel_state()

        assert mock_conn.execute.call_count >= 1
        insert_call = mock_conn.execute.call_args_list[0]
        assert 'funnel_state_snapshots' in insert_call[0][0]

    @pytest.mark.asyncio
    async def test_restore_funnel_state(self):
        tracker = ConversionTracker()

        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetchrow.return_value = {
            'funnel_brain_state': {'totalVariants': 18},
            'ad_brain_state': {'overallRoas': 2.5},
            'created_at': datetime.now(timezone.utc),
        }

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await tracker.restore_funnel_state()

        assert result is not None
        assert result['funnelBrain'] == {'totalVariants': 18}
        assert result['adBrain'] == {'overallRoas': 2.5}

    @pytest.mark.asyncio
    async def test_restore_funnel_state_empty(self):
        tracker = ConversionTracker()

        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetchrow.return_value = None

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            result = await tracker.restore_funnel_state()

        assert result is None


class TestConversionStats:
    """Test conversion analytics."""

    @pytest.mark.asyncio
    async def test_get_conversion_stats(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetch.return_value = [
            {
                'event_type': 'signup',
                'count': 10,
                'total_value': 50.0,
                'avg_value': 5.0,
                'funnel_tracked': 8,
                'google_tracked': 9,
            },
            {
                'event_type': 'subscription',
                'count': 3,
                'total_value': 87.0,
                'avg_value': 29.0,
                'funnel_tracked': 3,
                'google_tracked': 3,
            },
        ]

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            stats = await tracker.get_conversion_stats(days=30)

        assert stats['total_conversions'] == 13
        assert stats['total_value'] == 137.0
        assert len(stats['by_type']) == 2


class TestConversionRetry:
    """Test retry of failed conversions."""

    @pytest.mark.asyncio
    async def test_retry_failed_forwards(self):
        tracker = ConversionTracker()
        mock_pool, mock_conn = _make_mock_pool()

        mock_conn.fetch.return_value = [
            {
                'id': 'conv-1',
                'event_type': 'signup',
                'email': 'user@test.com',
                'session_id': 'sess-1',
                'gclid': None,
                'variant_ids': '{}',
                'value_dollars': 5.0,
                'order_id': None,
                'funnel_forwarded': False,
                'google_forwarded': True,
            },
        ]

        fwd_mock = AsyncMock()
        tracker._forward_conversion = fwd_mock

        with patch('a2a_server.database.get_pool', new_callable=AsyncMock, return_value=mock_pool):
            retried = await tracker.retry_failed_forwards(limit=10)

        assert retried == 1
        fwd_mock.assert_called_once()


class TestRuleEngineEvent:
    """Test publishing conversion events to the rule engine."""

    @pytest.mark.asyncio
    async def test_publish_conversion_event(self):
        tracker = ConversionTracker()

        mock_engine = MagicMock()
        mock_engine.evaluate_event_rules = AsyncMock()

        with patch('a2a_server.conversion_tracker.get_conversion_tracker', return_value=tracker), \
             patch('a2a_server.rule_engine.get_rule_engine', return_value=mock_engine):
            await tracker._publish_conversion_event(
                event_type='subscription',
                value_dollars=29.0,
                user_id='u-1',
            )

        mock_engine.evaluate_event_rules.assert_called_once()
        event_name = mock_engine.evaluate_event_rules.call_args[0][0]
        assert event_name == 'conversion.subscription'


class TestGlobalInstance:
    """Test global singleton management."""

    @pytest.mark.asyncio
    async def test_start_and_stop_global(self):
        import a2a_server.conversion_tracker as mod

        original = mod._tracker

        try:
            mod._tracker = None
            tracker = await start_conversion_tracker()
            assert tracker is not None
            assert get_conversion_tracker() is tracker

            await stop_conversion_tracker()
            assert get_conversion_tracker() is None
        finally:
            mod._tracker = original

    @pytest.mark.asyncio
    async def test_track_conversion_no_tracker(self):
        import a2a_server.conversion_tracker as mod
        original = mod._tracker
        try:
            mod._tracker = None
            result = await track_conversion(event_type='signup')
            assert result is None
        finally:
            mod._tracker = original
