"""
Cron Scheduler - Automatic task scheduling with cron expressions.

This module provides scheduled task execution based on cron expressions.
It periodically checks for due jobs and spawns tasks accordingly.

Features:
- Full cron expression support (5-field format: min hour day month weekday)
- Timezone support per job
- Execution history tracking
- Error handling and retry logic
- Integration with existing task queue system

Usage:
    # Start the scheduler (typically called from server startup)
    scheduler = CronScheduler()
    await scheduler.start()

    # Stop the scheduler (on shutdown)
    await scheduler.stop()

Configuration (environment variables):
    CRON_SCHEDULER_ENABLED: Enable/disable scheduler (default: true)
    CRON_CHECK_INTERVAL_SECONDS: How often to check for due jobs (default: 60)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .cron_dispatch import dispatch_cron_task
from .knative_cron import (
    get_cron_driver,
    is_knative_cron_available,
    reconcile_all_cronjob_resources,
)

logger = logging.getLogger(__name__)

# Configuration from environment
SCHEDULER_ENABLED = (
    os.environ.get('CRON_SCHEDULER_ENABLED', 'true').lower() == 'true'
)
CHECK_INTERVAL_SECONDS = int(
    os.environ.get('CRON_CHECK_INTERVAL_SECONDS', '60')
)


@dataclass
class SchedulerStats:
    """Statistics from a scheduler run."""

    checked_at: datetime = field(default_factory=datetime.utcnow)
    jobs_checked: int = 0
    jobs_triggered: int = 0
    jobs_failed: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checked_at': self.checked_at.isoformat(),
            'jobs_checked': self.jobs_checked,
            'jobs_triggered': self.jobs_triggered,
            'jobs_failed': self.jobs_failed,
            'errors': self.errors,
        }


class CronScheduler:
    """
    Background service that schedules and triggers cronjobs.

    Checks for jobs where next_run_at <= NOW() and triggers them.
    """

    def __init__(
        self,
        check_interval: int = CHECK_INTERVAL_SECONDS,
    ):
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_stats: Optional[SchedulerStats] = None

    async def start(self) -> None:
        """Start the background scheduler loop."""
        driver = get_cron_driver()
        if driver == 'disabled':
            logger.info('Cron scheduler disabled via CRON_DRIVER=disabled')
            return

        if not SCHEDULER_ENABLED and driver == 'app':
            logger.info('Cron scheduler disabled via CRON_SCHEDULER_ENABLED')
            return

        if driver == 'knative' and not is_knative_cron_available():
            logger.error(
                'Cron scheduler requested Knative mode but it is unavailable'
            )
            return

        if self._running:
            logger.warning('Cron scheduler already running')
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            'Cron scheduler started (driver=%s interval=%ss)',
            driver,
            self.check_interval,
        )

    async def stop(self) -> None:
        """Stop the background scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('Cron scheduler stopped')

    async def _scheduler_loop(self) -> None:
        """Main loop that periodically checks for due jobs."""
        # Wait a bit before first run to let server fully start
        await asyncio.sleep(10)

        while self._running:
            try:
                stats = await self.check_and_trigger_jobs()
                self._last_stats = stats

                if stats.jobs_triggered > 0:
                    logger.info(
                        f'Cron scheduler: triggered={stats.jobs_triggered}, failed={stats.jobs_failed}'
                    )

            except Exception as e:
                logger.error(f'Cron scheduler error: {e}', exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def check_and_trigger_jobs(self) -> SchedulerStats:
        """
        Check for and trigger due cronjobs.

        Returns statistics about the check operation.
        """
        stats = SchedulerStats()
        driver = get_cron_driver()

        if driver == 'disabled':
            stats.errors.append('Cron scheduler disabled')
            return stats

        if driver == 'knative':
            if not is_knative_cron_available():
                stats.errors.append('Knative cron driver unavailable')
                return stats
            try:
                sync = await reconcile_all_cronjob_resources()
                stats.jobs_checked = sync.checked
                stats.jobs_triggered = sync.reconciled
                stats.jobs_failed = sync.failed
                stats.errors.extend(sync.errors)
                return stats
            except Exception as e:
                stats.errors.append(f'Knative reconcile failed: {e}')
                logger.error(
                    'Cron scheduler Knative reconcile failed: %s',
                    e,
                    exc_info=True,
                )
                return stats

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                stats.errors.append('Database pool not available')
                return stats

            async with pool.acquire() as conn:
                # Find jobs that are due
                due_jobs = await conn.fetch(
                    """
                    SELECT id, tenant_id, user_id, name, cron_expression, 
                           task_template, timezone, run_count
                    FROM cronjobs
                    WHERE enabled = true
                      AND (next_run_at IS NULL OR next_run_at <= NOW())
                    ORDER BY next_run_at ASC NULLS FIRST
                    """
                )

                stats.jobs_checked = len(due_jobs)

                for job in due_jobs:
                    try:
                        await self._trigger_job(conn, job)
                        stats.jobs_triggered += 1
                    except Exception as e:
                        error_msg = f'Failed to trigger job {job["id"]}: {e}'
                        stats.errors.append(error_msg)
                        stats.jobs_failed += 1
                        logger.error(error_msg)

        except Exception as e:
            stats.errors.append(f'Scheduler check failed: {e}')
            logger.error(f'Cron scheduler check failed: {e}', exc_info=True)

        return stats

    async def _trigger_job(self, conn, job: dict) -> None:
        """Trigger a single cronjob."""
        import uuid

        job_id = job['id']
        tenant_id = job['tenant_id']
        user_id = job['user_id']
        task_template = job['task_template']

        # Create a task run record
        run_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO cronjob_runs (id, cronjob_id, tenant_id, status, started_at)
            VALUES ($1, $2, $3, 'running', NOW())
            """,
            run_id,
            job_id,
            tenant_id,
        )

        try:
            task_id, routing = await dispatch_cron_task(
                job_id=job_id,
                run_id=run_id,
                job_name=job['name'],
                task_template=task_template or {},
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
                trigger_mode='scheduled',
            )

            # Calculate next run time
            next_run = self._calculate_next_run(
                job['cron_expression'], job.get('timezone', 'UTC')
            )

            # Update job status
            await conn.execute(
                """
                UPDATE cronjobs SET
                    last_run_at = NOW(),
                    next_run_at = $2,
                    run_count = run_count + 1,
                    updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
                next_run,
            )

            # Update run record as completed
            await conn.execute(
                """
                UPDATE cronjob_runs SET
                    status = 'completed',
                    completed_at = NOW(),
                    duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000,
                    task_id = $2
                WHERE id = $1
                """,
                run_id,
                task_id,
            )

            logger.info(
                'Triggered cronjob %s: task=%s next_run=%s tier=%s model_ref=%s',
                job_id,
                task_id,
                next_run,
                routing.get('model_tier'),
                routing.get('model_ref'),
            )

        except Exception as e:
            # Update run record as failed
            await conn.execute(
                """
                UPDATE cronjob_runs SET
                    status = 'failed',
                    completed_at = NOW(),
                    duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000,
                    error_message = $2
                WHERE id = $1
                """,
                run_id,
                str(e),
            )

            # Increment error count on job
            await conn.execute(
                """
                UPDATE cronjobs SET
                    error_count = error_count + 1,
                    updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
            )

            raise

    def _calculate_next_run(
        self, cron_expression: str, timezone: str = 'UTC'
    ) -> datetime:
        """Calculate the next run time based on cron expression."""
        try:
            from croniter import croniter
            import pytz

            tz = pytz.timezone(timezone)
            now = datetime.now(tz)

            itr = croniter(cron_expression, now)
            next_run = itr.get_next(datetime)

            return next_run
        except Exception as e:
            logger.error(
                f'Failed to calculate next run for cron "{cron_expression}": {e}'
            )
            # Default to 1 hour from now if calculation fails
            return datetime.utcnow() + timedelta(hours=1)

    def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get the last scheduler run statistics."""
        if self._last_stats:
            return self._last_stats.to_dict()
        return None

    def get_health(self) -> Dict[str, Any]:
        """Get scheduler health status."""
        return {
            'running': self._running,
            'enabled': SCHEDULER_ENABLED,
            'check_interval_seconds': self.check_interval,
            'last_run': self._last_stats.to_dict()
            if self._last_stats
            else None,
        }

    async def calculate_next_run(
        self, cron_expression: str, timezone: str = 'UTC'
    ) -> Optional[datetime]:
        """Public method to calculate next run time for a cron expression."""
        try:
            return self._calculate_next_run(cron_expression, timezone)
        except Exception as e:
            logger.error(f'Failed to calculate next run: {e}')
            return None


# Global scheduler instance
_scheduler: Optional[CronScheduler] = None


def get_scheduler() -> Optional[CronScheduler]:
    """Get the global cron scheduler instance."""
    return _scheduler


async def start_cron_scheduler(
    check_interval: int = CHECK_INTERVAL_SECONDS,
) -> CronScheduler:
    """Start the global cron scheduler."""
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    _scheduler = CronScheduler(check_interval=check_interval)
    await _scheduler.start()
    return _scheduler


async def stop_cron_scheduler() -> None:
    """Stop the global cron scheduler."""
    global _scheduler

    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
