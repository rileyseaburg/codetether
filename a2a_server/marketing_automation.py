"""
Marketing Automation — Autonomous marketing loop backed by the proactive layer.

Connects the Python proactive rule engine and perpetual cognition loops to the
Next.js marketing site's self-selling infrastructure:

- **AdBrain sync**: Daily closed-loop Google Ads optimization via `/api/google/sync`
- **Video generation**: Weekly AI video ad creation via `/api/google/video-pipeline`
- **Performance reporting**: Pulls self-selling dashboards via `/api/optimization/report`
- **Cross-system orchestration**: When ROAS drops → generate new creative → test new funnel variant

Architecture:
- MarketingAutomationService: background poller that calls the marketing-site APIs
- Integrates with existing rule_engine (cron triggers) + audit_log (decision trail)
- All calls go through httpx with timeout + retry
- Every action is audit-logged in autonomous_decisions

Safety:
- Controlled by MARKETING_AUTOMATION_ENABLED env var (default false)
- Daily spend ceiling enforced at both AdBrain level and here
- Video generation capped at MAX_VIDEOS_PER_WEEK
- All decisions audit-logged and surfaced in proactive dashboard

Usage:
    from .marketing_automation import start_marketing_automation, stop_marketing_automation
    await start_marketing_automation()
    ...
    await stop_marketing_automation()
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

MARKETING_AUTOMATION_ENABLED = os.environ.get(
    'MARKETING_AUTOMATION_ENABLED', 'false'
).lower() == 'true'

# Base URL of the marketing-site (Next.js) — managed by http_client module

# Poll interval for the background service (default: 1 hour)
POLL_INTERVAL = int(os.environ.get('MARKETING_POLL_INTERVAL_SECONDS', '3600'))

# Daily budget for Google Ads optimization
DAILY_BUDGET_DOLLARS = int(os.environ.get('MARKETING_DAILY_BUDGET_DOLLARS', '50'))

# Video generation cap
MAX_VIDEOS_PER_WEEK = int(os.environ.get('MARKETING_MAX_VIDEOS_PER_WEEK', '3'))

# Script styles for video rotation
VIDEO_SCRIPT_STYLES = ['problem_focused', 'result_focused', 'comparison']


class MarketingAutomationService:
    """
    Background service that drives autonomous marketing actions.

    On each cycle:
      1. Pull self-selling performance report
      2. Run Google Ads ↔ Thompson Sampling sync
      3. Evaluate whether to generate new video ads
      4. Record all decisions in the audit trail
    """

    def __init__(self, poll_interval: int = POLL_INTERVAL):
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_cycle: Optional[datetime] = None
        self._last_report: Optional[Dict[str, Any]] = None
        self._videos_this_week = 0
        self._week_start: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not MARKETING_AUTOMATION_ENABLED:
            logger.info('Marketing automation disabled via MARKETING_AUTOMATION_ENABLED')
            return
        if self._running:
            return

        self._running = True
        self._week_start = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._main_loop())
        logger.info(
            'MarketingAutomationService started (poll=%ss, budget=$%d/day, site=%s)',
            self.poll_interval, DAILY_BUDGET_DOLLARS,
            os.environ.get('MARKETING_SITE_URL', 'auto'),
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('MarketingAutomationService stopped')

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _main_loop(self) -> None:
        await asyncio.sleep(30)  # let server settle

        while self._running:
            try:
                await self._run_cycle()
                self._last_cycle = datetime.now(timezone.utc)
            except Exception as e:
                logger.error('Marketing automation cycle error: %s', e, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _run_cycle(self) -> None:
        """Run one full marketing automation cycle."""
        logger.info('Marketing automation cycle starting')

        # 1. Pull performance report
        report = await self._fetch_report()

        # 2. Run Google Ads sync
        sync_result = await self._run_ad_sync()

        # 3. Evaluate creative generation
        await self._evaluate_video_generation(report, sync_result)

        logger.info('Marketing automation cycle complete')

    # ------------------------------------------------------------------
    # Step 1: Performance Report
    # ------------------------------------------------------------------

    async def _fetch_report(self) -> Optional[Dict[str, Any]]:
        """Pull the self-selling performance report from the marketing site."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request('GET', '/api/optimization/report', timeout=30.0)

            if resp.status_code != 200:
                logger.warning(
                    'Marketing report fetch failed: %d %s', resp.status_code, resp.text[:200]
                )
                await self._audit(
                    decision_type='report_fetch_failed',
                    description=f'Report API returned {resp.status_code}',
                    trigger_data={'status_code': resp.status_code},
                )
                return None

            report = resp.json()
            self._last_report = report

            await self._audit(
                decision_type='report_fetched',
                description='Self-selling performance report fetched',
                trigger_data={
                    'total_variants': report.get('funnelBrain', {}).get('totalVariants', 0),
                    'active_tests': report.get('funnelBrain', {}).get('activeTests', 0),
                    'overall_roas': report.get('adBrain', {}).get('overallRoas', 0),
                },
            )

            return report

        except CircuitBreakerOpenError:
            logger.warning('Marketing report fetch skipped: circuit breaker open')
            return None
        except Exception as e:
            logger.warning('Marketing report fetch error: %s', e)
            return None

    # ------------------------------------------------------------------
    # Step 2: Google Ads Sync
    # ------------------------------------------------------------------

    async def _run_ad_sync(self) -> Optional[Dict[str, Any]]:
        """Run the Google Ads ↔ Thompson Sampling sync cycle."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request(
                'POST', '/api/google/sync',
                json={
                    'dailyBudgetDollars': DAILY_BUDGET_DOLLARS,
                    'dryRun': False,
                },
                timeout=60.0,
            )

            if resp.status_code != 200:
                logger.warning(
                    'Ad sync failed: %d %s', resp.status_code, resp.text[:200]
                )
                await self._audit(
                    decision_type='ad_sync_failed',
                    description=f'Google Ads sync API returned {resp.status_code}',
                    trigger_data={'status_code': resp.status_code},
                )
                return None

            result = resp.json()

            # Audit each optimization decision
            decisions = result.get('decisions', [])
            applied = [d for d in decisions if d.get('applied')]
            skipped = [d for d in decisions if not d.get('applied')]

            await self._audit(
                decision_type='ad_sync_complete',
                description=(
                    f'Google Ads sync: {result.get("campaignsSynced", 0)} campaigns, '
                    f'{len(applied)} decisions applied, {len(skipped)} skipped, '
                    f'ROAS {result.get("overallRoas", 0):.2f}x'
                ),
                trigger_data={
                    'campaigns_synced': result.get('campaignsSynced', 0),
                    'decisions_applied': len(applied),
                    'decisions_skipped': len(skipped),
                    'overall_roas': result.get('overallRoas', 0),
                    'total_spend': result.get('totalSpendDollars', 0),
                    'total_conversions': result.get('totalConversions', 0),
                },
                decision_data={'decisions': decisions[:10]},  # cap audit size
            )

            if applied:
                logger.info(
                    'Ad sync applied %d decisions (ROAS=%.2f, spend=$%.2f)',
                    len(applied), result.get('overallRoas', 0),
                    result.get('totalSpendDollars', 0),
                )

            # Publish ROAS event if below threshold (triggers rule-marketing-roas-alert)
            roas = result.get('overallRoas', 0)
            if roas > 0 and roas < 1.5:
                try:
                    from .rule_engine import get_rule_engine
                    engine = get_rule_engine()
                    if engine:
                        await engine.evaluate_event_rules('marketing.roas_low', {
                            'roas': roas,
                            'spend_dollars': result.get('totalSpendDollars', 0),
                            'conversions': result.get('totalConversions', 0),
                            'campaigns_synced': result.get('campaignsSynced', 0),
                        })
                except Exception:
                    pass

            return result

        except CircuitBreakerOpenError:
            logger.warning('Ad sync skipped: circuit breaker open')
            return None
        except Exception as e:
            logger.warning('Ad sync request error: %s', e)
            return None

    # ------------------------------------------------------------------
    # Step 3: Video Generation
    # ------------------------------------------------------------------

    async def _evaluate_video_generation(
        self,
        report: Optional[Dict[str, Any]],
        sync_result: Optional[Dict[str, Any]],
    ) -> None:
        """Decide whether to generate a new video ad based on performance data."""
        # Reset weekly counter
        now = datetime.now(timezone.utc)
        if self._week_start and (now - self._week_start).days >= 7:
            self._videos_this_week = 0
            self._week_start = now

        # Gate: weekly cap
        if self._videos_this_week >= MAX_VIDEOS_PER_WEEK:
            logger.debug('Video generation: weekly cap reached (%d)', MAX_VIDEOS_PER_WEEK)
            return

        # Gate: only generate if ROAS is below threshold or we have no video yet
        should_generate = False
        reason = ''

        if sync_result:
            roas = sync_result.get('overallRoas', 0)
            conversions = sync_result.get('totalConversions', 0)

            if roas < 1.5 and conversions >= 10:
                # Underperforming — need fresh creative
                should_generate = True
                reason = f'ROAS {roas:.2f}x below 1.5x threshold with {conversions} conversions'
            elif conversions == 0 and self._videos_this_week == 0:
                # No conversions yet — bootstrap with a video
                should_generate = True
                reason = 'No conversions yet, bootstrapping with video ad'
        elif self._videos_this_week == 0:
            # No sync data available, generate one video to bootstrap
            should_generate = True
            reason = 'No sync data available, bootstrapping video pipeline'

        if not should_generate:
            return

        # Pick script style (rotate through available styles)
        style_idx = self._videos_this_week % len(VIDEO_SCRIPT_STYLES)
        script_style = VIDEO_SCRIPT_STYLES[style_idx]

        await self._generate_video(script_style, reason)

    async def _generate_video(self, script_style: str, reason: str) -> None:
        """Generate a video ad via the marketing-site pipeline."""
        try:
            from .http_client import http_request, CircuitBreakerOpenError

            resp = await http_request(
                'POST', '/api/google/video-pipeline',
                json={
                    'action': 'generate_and_launch',
                    'scriptStyle': script_style,
                    'dailyBudgetDollars': min(DAILY_BUDGET_DOLLARS, 25),
                    'aspectRatio': '16:9',
                },
                timeout=300.0,
            )

            if resp.status_code in (200, 201):
                result = resp.json()
                self._videos_this_week += 1

                await self._audit(
                    decision_type='video_generated',
                    description=(
                        f'Video ad generated and launched: style={script_style}, '
                        f'reason={reason}'
                    ),
                    trigger_data={'reason': reason, 'script_style': script_style},
                    decision_data={
                        'creatify_video_id': result.get('creatify', {}).get('videoId'),
                        'youtube_video_id': result.get('youtube', {}).get('videoId'),
                        'campaign_id': result.get('googleAds', {}).get('campaignId'),
                        'pipeline_status': result.get('pipeline'),
                    },
                )

                logger.info(
                    'Video ad generated: style=%s, yt=%s, campaign=%s',
                    script_style,
                    result.get('youtube', {}).get('videoId'),
                    result.get('googleAds', {}).get('campaignId'),
                )
            else:
                logger.warning(
                    'Video generation failed: %d %s', resp.status_code, resp.text[:200]
                )
                await self._audit(
                    decision_type='video_generation_failed',
                    description=f'Video pipeline returned {resp.status_code}: {script_style}',
                    trigger_data={
                        'status_code': resp.status_code,
                        'script_style': script_style,
                        'reason': reason,
                    },
                )

        except CircuitBreakerOpenError:
            logger.warning('Video generation skipped: circuit breaker open')
        except Exception as e:
            logger.warning('Video generation request error: %s', e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _audit(
        self,
        decision_type: str,
        description: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        decision_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a marketing automation decision in the audit trail."""
        try:
            from .audit_log import log_decision

            await log_decision(
                source='marketing_automation',
                decision_type=decision_type,
                description=description,
                trigger_data=trigger_data,
                decision_data=decision_data,
            )
        except Exception:
            pass  # Never break the automation loop for audit failures

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': MARKETING_AUTOMATION_ENABLED,
            'poll_interval_seconds': self.poll_interval,
            'daily_budget_dollars': DAILY_BUDGET_DOLLARS,
            'marketing_site_url': os.environ.get('MARKETING_SITE_URL', 'auto'),
            'last_cycle': self._last_cycle.isoformat() if self._last_cycle else None,
            'videos_this_week': self._videos_this_week,
            'max_videos_per_week': MAX_VIDEOS_PER_WEEK,
            'last_report_roas': (
                self._last_report.get('adBrain', {}).get('overallRoas')
                if self._last_report else None
            ),
        }

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        return self._last_report


# ============================================================================
# Global instance management
# ============================================================================

_service: Optional[MarketingAutomationService] = None


def get_marketing_automation() -> Optional[MarketingAutomationService]:
    return _service


async def start_marketing_automation() -> MarketingAutomationService:
    global _service
    if _service is not None:
        return _service
    _service = MarketingAutomationService()
    await _service.start()
    return _service


async def stop_marketing_automation() -> None:
    global _service
    if _service:
        await _service.stop()
        _service = None
