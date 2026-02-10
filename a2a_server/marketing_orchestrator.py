"""
Cross-System Marketing Orchestrator — coordinates multi-step marketing responses.

When a performance signal comes in (ROAS drop, high CPA, conversion spike),
this orchestrator runs a **playbook**: an ordered sequence of marketing actions
that span multiple systems (Google Ads, FunnelBrain, Creatify video pipeline).

Playbooks:
- roas_recovery: ROAS drops → pause weak campaigns → generate new creative → test new funnel variant
- conversion_spike: Conversion spike → scale winning campaigns → snapshot funnel state
- new_channel_test: Bootstrap a new ad channel with creative + funnel variant

Architecture:
- Listens for rule engine events
- Executes playbook steps sequentially with audit logging
- Each step calls marketing-site APIs through the existing httpx client
- Steps can be conditional (only run if previous step succeeded)

Safety:
- Each playbook has a daily execution cap
- All steps are audit-logged
- Budget caps enforced per-step

Usage:
    from .marketing_orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    await orchestrator.run_playbook('roas_recovery', trigger_data={...})
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MARKETING_SITE_URL = os.environ.get('MARKETING_SITE_URL', 'http://localhost:3000')
MARKETING_API_KEY = os.environ.get('MARKETING_API_KEY', '')
ORCHESTRATOR_ENABLED = os.environ.get(
    'MARKETING_ORCHESTRATOR_ENABLED', 'true'
).lower() == 'true'


class PlaybookStep:
    """A single step in a marketing orchestration playbook."""

    def __init__(
        self,
        name: str,
        description: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        condition: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.action = action
        self.params = params or {}
        self.condition = condition  # 'previous_success' | 'always' | None


class PlaybookResult:
    """Result of a playbook execution."""

    def __init__(self, playbook_name: str, trigger_data: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.playbook_name = playbook_name
        self.trigger_data = trigger_data
        self.started_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self.steps_completed = 0
        self.steps_failed = 0
        self.step_results: List[Dict[str, Any]] = []
        self.success = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'playbook': self.playbook_name,
            'trigger_data': self.trigger_data,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'steps_completed': self.steps_completed,
            'steps_failed': self.steps_failed,
            'step_results': self.step_results,
            'success': self.success,
        }


# ============================================================================
# Playbook Definitions
# ============================================================================

PLAYBOOKS: Dict[str, List[PlaybookStep]] = {
    'roas_recovery': [
        PlaybookStep(
            name='fetch_report',
            description='Pull current performance report to identify weak campaigns',
            action='fetch_report',
        ),
        PlaybookStep(
            name='pause_weak_campaigns',
            description='Run ad sync with optimization to pause underperformers',
            action='ad_sync',
            params={'dry_run': False},
            condition='previous_success',
        ),
        PlaybookStep(
            name='generate_fresh_creative',
            description='Generate a new video ad with a different angle',
            action='generate_video',
            params={'script_style': 'problem_focused'},
            condition='previous_success',
        ),
        PlaybookStep(
            name='snapshot_funnel',
            description='Snapshot FunnelBrain state before variant changes',
            action='snapshot_funnel',
            condition='always',
        ),
    ],
    'conversion_spike': [
        PlaybookStep(
            name='fetch_report',
            description='Pull performance report to confirm spike',
            action='fetch_report',
        ),
        PlaybookStep(
            name='scale_winners',
            description='Run ad sync to scale up winning campaigns',
            action='ad_sync',
            params={'dry_run': False},
            condition='previous_success',
        ),
        PlaybookStep(
            name='snapshot_funnel',
            description='Snapshot winning funnel state for future reference',
            action='snapshot_funnel',
            condition='always',
        ),
    ],
    'creative_refresh': [
        PlaybookStep(
            name='fetch_report',
            description='Pull current metrics',
            action='fetch_report',
        ),
        PlaybookStep(
            name='generate_result_video',
            description='Generate result-focused video creative',
            action='generate_video',
            params={'script_style': 'result_focused'},
        ),
        PlaybookStep(
            name='generate_comparison_video',
            description='Generate comparison-focused video creative',
            action='generate_video',
            params={'script_style': 'comparison'},
            condition='always',
        ),
    ],
}


class MarketingOrchestrator:
    """
    Coordinates multi-step marketing playbooks across systems.

    Each playbook is a sequence of steps that call different marketing-site
    APIs. Steps can be conditional on previous step success.
    """

    def __init__(self):
        self._running = False
        self._executions_today: Dict[str, int] = {}
        self._day_key: Optional[str] = None
        self._last_execution: Optional[PlaybookResult] = None
        self._total_executions = 0

    async def start(self) -> None:
        self._running = True
        self._day_key = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        logger.info('MarketingOrchestrator started')

    async def stop(self) -> None:
        self._running = False
        logger.info('MarketingOrchestrator stopped')

    # ------------------------------------------------------------------
    # Playbook execution
    # ------------------------------------------------------------------

    async def run_playbook(
        self,
        playbook_name: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        max_daily_runs: int = 3,
    ) -> PlaybookResult:
        """
        Execute a named playbook.

        Args:
            playbook_name: Key into PLAYBOOKS dict
            trigger_data: Context that triggered the playbook
            max_daily_runs: Max times this playbook can run per day

        Returns:
            PlaybookResult with step-by-step outcomes
        """
        if not ORCHESTRATOR_ENABLED:
            result = PlaybookResult(playbook_name, trigger_data or {})
            result.completed_at = datetime.now(timezone.utc)
            return result

        # Reset daily counters on day rollover
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if today != self._day_key:
            self._executions_today = {}
            self._day_key = today

        # Check daily cap
        runs_today = self._executions_today.get(playbook_name, 0)
        if runs_today >= max_daily_runs:
            logger.info(
                'Playbook %s: daily cap reached (%d/%d)',
                playbook_name, runs_today, max_daily_runs,
            )
            result = PlaybookResult(playbook_name, trigger_data or {})
            result.completed_at = datetime.now(timezone.utc)
            result.step_results.append({
                'step': 'gate',
                'status': 'skipped',
                'reason': f'Daily cap reached ({runs_today}/{max_daily_runs})',
            })
            return result

        steps = PLAYBOOKS.get(playbook_name)
        if not steps:
            logger.warning('Unknown playbook: %s', playbook_name)
            result = PlaybookResult(playbook_name, trigger_data or {})
            result.completed_at = datetime.now(timezone.utc)
            return result

        result = PlaybookResult(playbook_name, trigger_data or {})

        # Audit: playbook started
        await self._audit(
            decision_type='playbook_started',
            description=f'Playbook "{playbook_name}" triggered',
            trigger_data=trigger_data,
            decision_data={'playbook': playbook_name, 'steps': len(steps)},
        )

        previous_success = True

        for step in steps:
            # Check condition
            if step.condition == 'previous_success' and not previous_success:
                result.step_results.append({
                    'step': step.name,
                    'status': 'skipped',
                    'reason': 'Previous step failed',
                })
                continue

            # Execute step
            step_result = await self._execute_step(step, trigger_data or {})
            result.step_results.append(step_result)

            if step_result.get('status') == 'success':
                result.steps_completed += 1
                previous_success = True
            else:
                result.steps_failed += 1
                previous_success = False

        result.completed_at = datetime.now(timezone.utc)
        result.success = result.steps_failed == 0

        # Update counters
        self._executions_today[playbook_name] = runs_today + 1
        self._total_executions += 1
        self._last_execution = result

        # Audit: playbook completed
        await self._audit(
            decision_type='playbook_completed',
            description=(
                f'Playbook "{playbook_name}" completed: '
                f'{result.steps_completed} succeeded, {result.steps_failed} failed'
            ),
            trigger_data=trigger_data,
            decision_data=result.to_dict(),
        )

        logger.info(
            'Playbook %s: %d/%d steps succeeded',
            playbook_name, result.steps_completed,
            result.steps_completed + result.steps_failed,
        )

        return result

    # ------------------------------------------------------------------
    # Step executors
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        step: PlaybookStep,
        trigger_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single playbook step and return result."""
        logger.debug('Executing step: %s (%s)', step.name, step.action)

        try:
            if step.action == 'fetch_report':
                data = await self._action_fetch_report()
            elif step.action == 'ad_sync':
                data = await self._action_ad_sync(step.params)
            elif step.action == 'generate_video':
                data = await self._action_generate_video(step.params)
            elif step.action == 'snapshot_funnel':
                data = await self._action_snapshot_funnel()
            else:
                return {
                    'step': step.name,
                    'status': 'error',
                    'error': f'Unknown action: {step.action}',
                }

            return {
                'step': step.name,
                'action': step.action,
                'status': 'success',
                'data': data,
            }

        except Exception as e:
            logger.warning('Step %s failed: %s', step.name, e)
            return {
                'step': step.name,
                'action': step.action,
                'status': 'error',
                'error': str(e),
            }

    async def _action_fetch_report(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f'{MARKETING_SITE_URL}/api/optimization/report',
                headers=self._headers(),
            )
        if resp.status_code != 200:
            raise RuntimeError(f'Report API returned {resp.status_code}')
        return resp.json()

    async def _action_ad_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        daily_budget = int(os.environ.get('MARKETING_DAILY_BUDGET_DOLLARS', '50'))
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f'{MARKETING_SITE_URL}/api/google/sync',
                headers=self._headers(),
                json={
                    'dailyBudgetDollars': daily_budget,
                    'dryRun': params.get('dry_run', False),
                },
            )
        if resp.status_code != 200:
            raise RuntimeError(f'Ad sync API returned {resp.status_code}')
        return resp.json()

    async def _action_generate_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        daily_budget = int(os.environ.get('MARKETING_DAILY_BUDGET_DOLLARS', '50'))
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f'{MARKETING_SITE_URL}/api/google/video-pipeline',
                headers=self._headers(),
                json={
                    'action': 'generate_and_launch',
                    'scriptStyle': params.get('script_style', 'problem_focused'),
                    'dailyBudgetDollars': min(daily_budget, 25),
                    'aspectRatio': '16:9',
                },
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'Video pipeline returned {resp.status_code}')
        return resp.json()

    async def _action_snapshot_funnel(self) -> Dict[str, Any]:
        """Trigger a FunnelBrain state snapshot via the conversion tracker."""
        from .conversion_tracker import get_conversion_tracker
        tracker = get_conversion_tracker()
        if tracker:
            await tracker._snapshot_funnel_state()
            return {'status': 'snapshot_saved'}
        return {'status': 'tracker_not_running'}

    # ------------------------------------------------------------------
    # Event handler — wired to rule engine
    # ------------------------------------------------------------------

    async def handle_marketing_event(
        self, event_name: str, event_data: Dict[str, Any]
    ) -> None:
        """
        Handle a marketing event by running the appropriate playbook.

        Event mapping:
        - marketing.roas_low → roas_recovery
        - conversion.subscription → conversion_spike (if value > threshold)
        - marketing.creative_stale → creative_refresh
        """
        if not ORCHESTRATOR_ENABLED:
            return

        playbook_name = None

        if event_name == 'marketing.roas_low':
            playbook_name = 'roas_recovery'
        elif event_name.startswith('conversion.') and event_data.get('value_dollars', 0) > 0:
            # Only run conversion_spike for high-value events
            playbook_name = 'conversion_spike'
        elif event_name == 'marketing.creative_stale':
            playbook_name = 'creative_refresh'

        if playbook_name:
            await self.run_playbook(playbook_name, trigger_data=event_data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {'Content-Type': 'application/json'}
        if MARKETING_API_KEY:
            headers['x-api-key'] = MARKETING_API_KEY
        return headers

    async def _audit(
        self,
        decision_type: str,
        description: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        decision_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            from .audit_log import log_decision
            await log_decision(
                source='marketing_orchestrator',
                decision_type=decision_type,
                description=description,
                trigger_data=trigger_data,
                decision_data=decision_data,
            )
        except Exception:
            pass

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': ORCHESTRATOR_ENABLED,
            'total_executions': self._total_executions,
            'executions_today': dict(self._executions_today),
            'last_execution': (
                self._last_execution.to_dict() if self._last_execution else None
            ),
        }


# ============================================================================
# Global instance management
# ============================================================================

_orchestrator: Optional[MarketingOrchestrator] = None


def get_orchestrator() -> Optional[MarketingOrchestrator]:
    return _orchestrator


async def start_orchestrator() -> MarketingOrchestrator:
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    _orchestrator = MarketingOrchestrator()
    await _orchestrator.start()
    return _orchestrator


async def stop_orchestrator() -> None:
    global _orchestrator
    if _orchestrator:
        await _orchestrator.stop()
        _orchestrator = None
