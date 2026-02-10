"""
Proactive Rule Engine - Event-driven and scheduled autonomous agent triggers.

This module provides the server-side rule engine that enables agents to act
proactively based on events, schedules, or threshold conditions. It backs the
marketing claims about "monitoring personas that watch your systems" and
"every autonomous decision audit-logged."

Architecture:
- Reuses the CronScheduler/TaskReaper background-loop pattern
- Event-triggered rules are evaluated inline via publish_event() hook
- Cron-triggered rules are evaluated on a polling loop (like CronScheduler)
- Threshold-triggered rules are evaluated when health check results arrive
- All triggers dispatch tasks via the existing cron_dispatch machinery

Safety:
- Per-rule cooldown prevents runaway trigger loops
- All triggers are audit-logged in agent_rule_runs
- Rules are tenant-isolated

Usage:
    engine = ProactiveRuleEngine()
    await engine.start()
    # Events flow in via evaluate_event_rules()
    await engine.stop()
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .cron_dispatch import dispatch_cron_task

logger = logging.getLogger(__name__)

# Configuration
RULE_ENGINE_ENABLED = os.environ.get('RULE_ENGINE_ENABLED', 'true').lower() == 'true'
RULE_CHECK_INTERVAL = int(os.environ.get('RULE_CHECK_INTERVAL_SECONDS', '30'))


@dataclass
class RuleEngineStats:
    """Statistics from a rule engine evaluation cycle."""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rules_evaluated: int = 0
    rules_triggered: int = 0
    rules_cooldown_skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checked_at': self.checked_at.isoformat(),
            'rules_evaluated': self.rules_evaluated,
            'rules_triggered': self.rules_triggered,
            'rules_cooldown_skipped': self.rules_cooldown_skipped,
            'errors': self.errors,
        }


class ProactiveRuleEngine:
    """
    Background service that evaluates and triggers proactive agent rules.

    Supports three trigger types:
    - event: evaluated in real-time when events are published
    - cron: evaluated on a polling loop (reuses CronScheduler pattern)
    - threshold: evaluated when health check results are published
    """

    def __init__(self, check_interval: int = RULE_CHECK_INTERVAL):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_stats: Optional[RuleEngineStats] = None

    async def start(self) -> None:
        """Start the rule engine background loop."""
        if not RULE_ENGINE_ENABLED:
            logger.info('Proactive rule engine disabled via RULE_ENGINE_ENABLED')
            return
        if self._running:
            logger.warning('Proactive rule engine already running')
            return

        self._running = True
        self._task = asyncio.create_task(self._engine_loop())
        logger.info(
            'Proactive rule engine started (interval=%ss)', self.check_interval
        )

    async def stop(self) -> None:
        """Stop the rule engine background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('Proactive rule engine stopped')

    # ------------------------------------------------------------------
    # Background loop for cron-type rules
    # ------------------------------------------------------------------

    async def _engine_loop(self) -> None:
        """Main loop for evaluating cron-type rules."""
        await asyncio.sleep(15)  # let server start

        while self._running:
            try:
                stats = await self._evaluate_cron_rules()
                self._last_stats = stats
                if stats.rules_triggered > 0:
                    logger.info(
                        'Rule engine: triggered=%d, cooldown_skipped=%d',
                        stats.rules_triggered,
                        stats.rules_cooldown_skipped,
                    )
            except Exception as e:
                logger.error('Rule engine loop error: %s', e, exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _evaluate_cron_rules(self) -> RuleEngineStats:
        """Evaluate cron-type rules that are due."""
        stats = RuleEngineStats()
        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                stats.errors.append('Database pool not available')
                return stats

            async with pool.acquire() as conn:
                due_rules = await conn.fetch(
                    """
                    SELECT id, tenant_id, user_id, name, trigger_config, action,
                           cooldown_seconds, last_triggered_at
                    FROM agent_rules
                    WHERE enabled = true
                      AND trigger_type = 'cron'
                      AND (next_run_at IS NULL OR next_run_at <= NOW())
                    ORDER BY next_run_at ASC NULLS FIRST
                    """
                )
                stats.rules_evaluated = len(due_rules)

                for rule in due_rules:
                    triggered = await self._try_trigger_rule(
                        conn, rule, trigger_payload={'trigger': 'cron'}, stats=stats
                    )
                    if triggered:
                        # Calculate next run
                        trigger_config = rule['trigger_config']
                        if isinstance(trigger_config, str):
                            trigger_config = json.loads(trigger_config)
                        cron_expr = trigger_config.get('cron_expression', '*/5 * * * *')
                        tz = trigger_config.get('timezone', 'UTC')
                        next_run = self._calculate_next_run(cron_expr, tz)
                        await conn.execute(
                            'UPDATE agent_rules SET next_run_at = $2 WHERE id = $1',
                            rule['id'], next_run,
                        )

        except Exception as e:
            stats.errors.append(f'Cron rule evaluation failed: {e}')
            logger.error('Cron rule evaluation failed: %s', e, exc_info=True)

        return stats

    # ------------------------------------------------------------------
    # Real-time event evaluation (called from publish_event hook)
    # ------------------------------------------------------------------

    async def evaluate_event_rules(self, event_type: str, event_data: Any) -> None:
        """
        Evaluate all event-triggered rules matching an event type.

        Called inline from MessageBroker.publish_event() for real-time
        event-driven triggering.
        """
        if not self._running:
            return

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return

            async with pool.acquire() as conn:
                # Find enabled event rules matching this event type
                rules = await conn.fetch(
                    """
                    SELECT id, tenant_id, user_id, name, trigger_config, action,
                           cooldown_seconds, last_triggered_at
                    FROM agent_rules
                    WHERE enabled = true
                      AND trigger_type = 'event'
                      AND trigger_config->>'event_type' = $1
                    """,
                    event_type,
                )

                stats = RuleEngineStats()
                stats.rules_evaluated = len(rules)

                for rule in rules:
                    trigger_config = rule['trigger_config']
                    if isinstance(trigger_config, str):
                        trigger_config = json.loads(trigger_config)

                    # Check optional filter conditions
                    if self._matches_filter(trigger_config.get('filter'), event_data):
                        await self._try_trigger_rule(
                            conn, rule,
                            trigger_payload={'trigger': 'event', 'event_type': event_type, 'event_data': event_data},
                            stats=stats,
                        )

        except Exception as e:
            logger.error('Event rule evaluation failed: %s', e, exc_info=True)

    # ------------------------------------------------------------------
    # Threshold evaluation (called from health monitor)
    # ------------------------------------------------------------------

    async def evaluate_threshold_rules(
        self, health_check_id: str, check_status: str, check_result: Dict[str, Any]
    ) -> None:
        """
        Evaluate threshold-triggered rules for a specific health check.

        Called by HealthMonitor after each health check execution.
        """
        if not self._running:
            return

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return

            async with pool.acquire() as conn:
                rules = await conn.fetch(
                    """
                    SELECT id, tenant_id, user_id, name, trigger_config, action,
                           cooldown_seconds, last_triggered_at
                    FROM agent_rules
                    WHERE enabled = true
                      AND trigger_type = 'threshold'
                      AND trigger_config->>'health_check_id' = $1
                    """,
                    health_check_id,
                )

                stats = RuleEngineStats()
                stats.rules_evaluated = len(rules)

                for rule in rules:
                    trigger_config = rule['trigger_config']
                    if isinstance(trigger_config, str):
                        trigger_config = json.loads(trigger_config)

                    # Check threshold condition
                    condition = trigger_config.get('condition', '')
                    if self._evaluate_threshold_condition(condition, check_status, check_result):
                        await self._try_trigger_rule(
                            conn, rule,
                            trigger_payload={
                                'trigger': 'threshold',
                                'health_check_id': health_check_id,
                                'check_status': check_status,
                                'check_result': check_result,
                            },
                            stats=stats,
                        )

        except Exception as e:
            logger.error('Threshold rule evaluation failed: %s', e, exc_info=True)

    # ------------------------------------------------------------------
    # Core trigger logic
    # ------------------------------------------------------------------

    async def _try_trigger_rule(
        self, conn, rule: dict, trigger_payload: Dict[str, Any], stats: RuleEngineStats
    ) -> bool:
        """
        Attempt to trigger a rule, respecting cooldown.

        Returns True if the rule was triggered, False if skipped.
        """
        rule_id = rule['id']
        cooldown = rule['cooldown_seconds'] or 0
        last_triggered = rule['last_triggered_at']

        # Check cooldown
        if last_triggered and cooldown > 0:
            now = datetime.now(timezone.utc)
            # Handle timezone-naive datetimes from DB
            if last_triggered.tzinfo is None:
                last_triggered = last_triggered.replace(tzinfo=timezone.utc)
            elapsed = (now - last_triggered).total_seconds()
            if elapsed < cooldown:
                stats.rules_cooldown_skipped += 1
                # Log skip for audit
                await self._record_rule_run(
                    conn, rule_id, rule.get('tenant_id'),
                    trigger_payload, status='cooldown_skipped',
                )
                return False

        # Trigger the rule
        run_id = str(uuid.uuid4())
        try:
            action = rule['action']
            if isinstance(action, str):
                action = json.loads(action)

            task_id, routing = await dispatch_cron_task(
                job_id=rule_id,
                run_id=run_id,
                job_name=f'rule:{rule["name"]}',
                task_template=action,
                tenant_id=str(rule['tenant_id']) if rule.get('tenant_id') else None,
                user_id=str(rule['user_id']) if rule.get('user_id') else None,
                trigger_mode='proactive_rule',
            )

            # Audit log the decision
            try:
                from .audit_log import log_decision
                await log_decision(
                    source='rule_engine',
                    decision_type='trigger_rule',
                    description=f'Rule "{rule["name"]}" triggered',
                    trigger_data=trigger_payload,
                    decision_data={'rule_id': rule_id, 'routing': routing},
                    task_id=task_id,
                    outcome='success',
                    tenant_id=str(rule['tenant_id']) if rule.get('tenant_id') else None,
                    user_id=str(rule['user_id']) if rule.get('user_id') else None,
                )
            except Exception:
                pass

            # Record success
            await self._record_rule_run(
                conn, rule_id, rule.get('tenant_id'),
                trigger_payload, status='task_created', task_id=task_id,
            )

            # Update rule metadata
            await conn.execute(
                """
                UPDATE agent_rules SET
                    last_triggered_at = NOW(),
                    trigger_count = trigger_count + 1,
                    updated_at = NOW()
                WHERE id = $1
                """,
                rule_id,
            )

            stats.rules_triggered += 1
            logger.info(
                'Proactive rule "%s" triggered → task %s (routing: %s)',
                rule['name'], task_id, routing.get('model_tier'),
            )
            return True

        except Exception as e:
            await self._record_rule_run(
                conn, rule_id, rule.get('tenant_id'),
                trigger_payload, status='failed', error_message=str(e),
            )
            stats.errors.append(f'Rule {rule_id} trigger failed: {e}')
            logger.error('Rule %s trigger failed: %s', rule_id, e)
            return False

    async def _record_rule_run(
        self, conn, rule_id: str, tenant_id: Optional[str],
        trigger_payload: Dict[str, Any], status: str,
        task_id: Optional[str] = None, error_message: Optional[str] = None,
    ) -> None:
        """Record a rule run in the audit trail."""
        run_id = str(uuid.uuid4())
        # Sanitize trigger_payload to be JSON-serializable
        safe_payload = json.dumps(trigger_payload, default=str)
        await conn.execute(
            """
            INSERT INTO agent_rule_runs
                (id, rule_id, tenant_id, trigger_payload, task_id, status, error_message, started_at, completed_at)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, NOW(), NOW())
            """,
            run_id, rule_id, tenant_id, safe_payload, task_id, status, error_message,
        )

    # ------------------------------------------------------------------
    # Filter / condition helpers
    # ------------------------------------------------------------------

    def _matches_filter(self, filter_config: Optional[Dict], event_data: Any) -> bool:
        """
        Check if event data matches a simple key-value filter.

        Filter format: { "key": "expected_value", ... }
        All conditions must match (AND logic).
        """
        if not filter_config:
            return True  # No filter = always match

        if not isinstance(event_data, dict):
            return False

        for key, expected in filter_config.items():
            actual = event_data.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def _evaluate_threshold_condition(
        self, condition: str, check_status: str, check_result: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a simple threshold condition string.

        Supported conditions:
        - "status == 'failed'"
        - "status == 'degraded'"
        - "status != 'healthy'"
        """
        condition = condition.strip()
        if not condition:
            return check_status != 'healthy'  # default: trigger on any non-healthy

        # Simple DSL: "status == 'value'" or "status != 'value'"
        if '==' in condition:
            parts = condition.split('==', 1)
            field_name = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            if field_name == 'status':
                return check_status == expected
            return str(check_result.get(field_name)) == expected
        elif '!=' in condition:
            parts = condition.split('!=', 1)
            field_name = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            if field_name == 'status':
                return check_status != expected
            return str(check_result.get(field_name)) != expected

        # Fallback: trigger on non-healthy
        return check_status != 'healthy'

    def _calculate_next_run(self, cron_expression: str, timezone_str: str = 'UTC') -> datetime:
        """Calculate next run time for a cron expression."""
        try:
            from croniter import croniter
            import pytz

            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            itr = croniter(cron_expression, now)
            return itr.get_next(datetime)
        except Exception as e:
            logger.error('Failed to calculate next run for "%s": %s', cron_expression, e)
            return datetime.now(timezone.utc) + timedelta(hours=1)

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Optional[Dict[str, Any]]:
        if self._last_stats:
            return self._last_stats.to_dict()
        return None

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': RULE_ENGINE_ENABLED,
            'check_interval_seconds': self.check_interval,
            'last_run': self._last_stats.to_dict() if self._last_stats else None,
        }


# ============================================================================
# Global instance management (same pattern as CronScheduler/TaskReaper)
# ============================================================================

_engine: Optional[ProactiveRuleEngine] = None


def get_rule_engine() -> Optional[ProactiveRuleEngine]:
    """Get the global rule engine instance."""
    return _engine


async def start_rule_engine(check_interval: int = RULE_CHECK_INTERVAL) -> ProactiveRuleEngine:
    """Start the global proactive rule engine."""
    global _engine
    if _engine is not None:
        return _engine
    _engine = ProactiveRuleEngine(check_interval=check_interval)
    await _engine.start()
    return _engine


async def stop_rule_engine() -> None:
    """Stop the global proactive rule engine."""
    global _engine
    if _engine:
        await _engine.stop()
        _engine = None
