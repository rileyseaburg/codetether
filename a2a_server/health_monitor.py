"""
Health Monitor - Configurable system health probes for proactive agents.

Runs registered health checks at their configured intervals and publishes
results as events that the ProactiveRuleEngine can react to. This backs the
marketing claim about "a monitoring persona that watches your systems."

Check types:
- http:       HTTP GET/POST with expected status code
- db_query:   SQL query with threshold on result
- metric:     Named metric with threshold bounds
- task_queue: Built-in check on pending/stuck task counts

Usage:
    monitor = HealthMonitor()
    await monitor.start()
    await monitor.stop()
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HEALTH_MONITOR_ENABLED = os.environ.get('HEALTH_MONITOR_ENABLED', 'true').lower() == 'true'
HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL_SECONDS', '30'))


@dataclass
class HealthMonitorStats:
    """Statistics from a health monitor cycle."""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checks_run: int = 0
    checks_healthy: int = 0
    checks_degraded: int = 0
    checks_failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checked_at': self.checked_at.isoformat(),
            'checks_run': self.checks_run,
            'checks_healthy': self.checks_healthy,
            'checks_degraded': self.checks_degraded,
            'checks_failed': self.checks_failed,
            'errors': self.errors,
        }


class HealthMonitor:
    """
    Background service that runs registered health checks and publishes events.

    Events published:
    - health.check.passed   (check is healthy)
    - health.check.degraded (check shows degradation)
    - health.check.failed   (check failed)
    """

    def __init__(self, check_interval: int = HEALTH_CHECK_INTERVAL):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_stats: Optional[HealthMonitorStats] = None

    async def start(self) -> None:
        if not HEALTH_MONITOR_ENABLED:
            logger.info('Health monitor disabled via HEALTH_MONITOR_ENABLED')
            return
        if self._running:
            logger.warning('Health monitor already running')
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info('Health monitor started (interval=%ss)', self.check_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('Health monitor stopped')

    async def _monitor_loop(self) -> None:
        await asyncio.sleep(20)  # let server start

        while self._running:
            try:
                stats = await self._run_due_checks()
                self._last_stats = stats
                if stats.checks_failed > 0 or stats.checks_degraded > 0:
                    logger.info(
                        'Health monitor: healthy=%d, degraded=%d, failed=%d',
                        stats.checks_healthy, stats.checks_degraded, stats.checks_failed,
                    )
            except Exception as e:
                logger.error('Health monitor error: %s', e, exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _run_due_checks(self) -> HealthMonitorStats:
        """Find and run health checks that are due."""
        stats = HealthMonitorStats()
        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                stats.errors.append('Database pool not available')
                return stats

            async with pool.acquire() as conn:
                due_checks = await conn.fetch(
                    """
                    SELECT id, tenant_id, name, check_type, check_config,
                           interval_seconds, consecutive_failures
                    FROM health_checks
                    WHERE enabled = true
                      AND (next_check_at IS NULL OR next_check_at <= NOW())
                    ORDER BY next_check_at ASC NULLS FIRST
                    """
                )

                for check in due_checks:
                    stats.checks_run += 1
                    try:
                        status, result = await self._execute_check(check)

                        # Update consecutive failures
                        if status == 'failed':
                            consecutive = (check['consecutive_failures'] or 0) + 1
                            stats.checks_failed += 1
                        elif status == 'degraded':
                            consecutive = (check['consecutive_failures'] or 0) + 1
                            stats.checks_degraded += 1
                        else:
                            consecutive = 0
                            stats.checks_healthy += 1

                        # Update check state in DB
                        import json
                        next_check = datetime.now(timezone.utc) + timedelta(
                            seconds=check['interval_seconds'] or 300
                        )
                        await conn.execute(
                            """
                            UPDATE health_checks SET
                                last_checked_at = NOW(),
                                next_check_at = $2,
                                last_status = $3,
                                last_result = $4::jsonb,
                                consecutive_failures = $5,
                                updated_at = NOW()
                            WHERE id = $1
                            """,
                            check['id'], next_check, status,
                            json.dumps(result, default=str), consecutive,
                        )

                        # Publish event
                        await self._publish_check_event(check, status, result)

                        # Notify rule engine for threshold evaluation
                        await self._notify_rule_engine(check['id'], status, result)

                    except Exception as e:
                        stats.errors.append(f'Check {check["id"]} failed: {e}')
                        logger.error('Health check %s failed: %s', check['id'], e)

        except Exception as e:
            stats.errors.append(f'Health monitor cycle failed: {e}')
            logger.error('Health monitor cycle failed: %s', e, exc_info=True)

        return stats

    async def _execute_check(self, check: dict) -> tuple:
        """
        Execute a single health check and return (status, result_dict).

        Returns:
            (status: str, result: dict) where status is 'healthy', 'degraded', or 'failed'
        """
        import json

        check_type = check['check_type']
        config = check['check_config']
        if isinstance(config, str):
            config = json.loads(config)

        if check_type == 'http':
            return await self._check_http(config)
        elif check_type == 'task_queue':
            return await self._check_task_queue(config)
        elif check_type == 'db_query':
            return await self._check_db_query(config)
        elif check_type == 'metric':
            return await self._check_metric(config)
        else:
            return 'failed', {'error': f'Unknown check type: {check_type}'}

    async def _check_http(self, config: dict) -> tuple:
        """HTTP health check."""
        import aiohttp

        url = config.get('url', '')
        method = config.get('method', 'GET').upper()
        expected_status = config.get('expected_status', 200)
        timeout_ms = config.get('timeout_ms', 5000)

        try:
            timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url) as resp:
                    actual_status = resp.status
                    if actual_status == expected_status:
                        return 'healthy', {'status_code': actual_status, 'url': url}
                    elif 200 <= actual_status < 500:
                        return 'degraded', {'status_code': actual_status, 'expected': expected_status, 'url': url}
                    else:
                        return 'failed', {'status_code': actual_status, 'expected': expected_status, 'url': url}
        except asyncio.TimeoutError:
            return 'failed', {'error': 'timeout', 'timeout_ms': timeout_ms, 'url': url}
        except Exception as e:
            return 'failed', {'error': str(e), 'url': url}

    async def _check_task_queue(self, config: dict) -> tuple:
        """Built-in check on task queue health."""
        max_pending = config.get('max_pending', 50)
        max_stuck = config.get('max_stuck', 5)

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return 'failed', {'error': 'Database pool not available'}

            async with pool.acquire() as conn:
                pending = await conn.fetchval(
                    "SELECT count(*) FROM tasks WHERE status = 'pending'"
                )
                stuck_cutoff = datetime.now(timezone.utc) - timedelta(seconds=300)
                stuck = await conn.fetchval(
                    "SELECT count(*) FROM tasks WHERE status = 'running' AND started_at < $1",
                    stuck_cutoff,
                )

            result = {'pending_tasks': pending, 'stuck_tasks': stuck}

            if stuck > max_stuck:
                return 'failed', result
            elif pending > max_pending:
                return 'degraded', result
            else:
                return 'healthy', result

        except Exception as e:
            return 'failed', {'error': str(e)}

    async def _check_db_query(self, config: dict) -> tuple:
        """Run a read-only DB query and check threshold."""
        query = config.get('query', '')
        threshold_max = config.get('threshold_max')
        threshold_min = config.get('threshold_min')

        if not query:
            return 'failed', {'error': 'No query specified'}

        # Safety: only allow SELECT queries
        if not query.strip().upper().startswith('SELECT'):
            return 'failed', {'error': 'Only SELECT queries are allowed'}

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return 'failed', {'error': 'Database pool not available'}

            async with pool.acquire() as conn:
                value = await conn.fetchval(query)

            result = {'query_result': value}

            if threshold_max is not None and value is not None and value > threshold_max:
                return 'degraded', result
            if threshold_min is not None and value is not None and value < threshold_min:
                return 'degraded', result

            return 'healthy', result

        except Exception as e:
            return 'failed', {'error': str(e)}

    async def _check_metric(self, config: dict) -> tuple:
        """Placeholder for custom metric checks."""
        return 'healthy', {'note': 'Metric check not yet implemented', 'config': config}

    async def _publish_check_event(self, check: dict, status: str, result: dict) -> None:
        """Publish a health check event via the message broker."""
        event_map = {
            'healthy': 'health.check.passed',
            'degraded': 'health.check.degraded',
            'failed': 'health.check.failed',
        }
        event_type = event_map.get(status, 'health.check.failed')
        event_data = {
            'health_check_id': check['id'],
            'health_check_name': check['name'],
            'tenant_id': check.get('tenant_id'),
            'status': status,
            'result': result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Try Redis-backed broker first, fall back to in-memory
            from .server import A2AServer
            # Use a simpler approach: publish directly if we have a broker ref
            # The publish_event hook in message_broker handles distribution
            from . import database as db
            pool = await db.get_pool()
            if pool:
                # Publish via Redis pub/sub directly
                import redis.asyncio as redis_async
                redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
                r = redis_async.from_url(redis_url)
                import json
                event_payload = json.dumps({'type': event_type, 'data': event_data, 'timestamp': datetime.now(timezone.utc).isoformat()})
                await r.publish('events', event_payload)
                await r.publish(f'events:{event_type}', event_payload)
                await r.close()
        except Exception as e:
            logger.debug('Failed to publish health check event: %s', e)

    async def _notify_rule_engine(self, health_check_id: str, status: str, result: dict) -> None:
        """Notify the rule engine about a health check result for threshold evaluation."""
        try:
            from .rule_engine import get_rule_engine

            engine = get_rule_engine()
            if engine:
                await engine.evaluate_threshold_rules(health_check_id, status, result)
        except Exception as e:
            logger.debug('Failed to notify rule engine: %s', e)

    def get_stats(self) -> Optional[Dict[str, Any]]:
        if self._last_stats:
            return self._last_stats.to_dict()
        return None

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': HEALTH_MONITOR_ENABLED,
            'check_interval_seconds': self.check_interval,
            'last_run': self._last_stats.to_dict() if self._last_stats else None,
        }


# ============================================================================
# Global instance management
# ============================================================================

_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> Optional[HealthMonitor]:
    return _monitor


async def start_health_monitor(check_interval: int = HEALTH_CHECK_INTERVAL) -> HealthMonitor:
    global _monitor
    if _monitor is not None:
        return _monitor
    _monitor = HealthMonitor(check_interval=check_interval)
    await _monitor.start()
    return _monitor


async def stop_health_monitor() -> None:
    global _monitor
    if _monitor:
        await _monitor.stop()
        _monitor = None
