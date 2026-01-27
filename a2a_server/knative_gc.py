"""
Knative Garbage Collector for cleaning up idle session workers.

This module provides automated cleanup of Knative worker resources:
- Delete workers that have been idle for too long
- Delete workers for terminated sessions
- Background GC task that runs periodically

Configuration:
    GC_INTERVAL_MINUTES: Background GC interval (default: 60)
    GC_MAX_IDLE_HOURS: Maximum idle time before cleanup (default: 24)
    GC_ENABLED: Enable background GC (default: true when KNATIVE_ENABLED)

Usage:
    from a2a_server.knative_gc import knative_gc

    # Manual GC cycle
    result = await knative_gc.run_gc_cycle()

    # Start background GC
    knative_gc.start_background_gc(interval_minutes=60)

    # Stop background GC
    knative_gc.stop_background_gc()
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .database import get_pool
from .knative_spawner import (
    KNATIVE_ENABLED,
    KnativeSpawner,
    WorkerStatus,
    knative_spawner,
)

logger = logging.getLogger(__name__)

# Configuration from environment
GC_INTERVAL_MINUTES = int(os.environ.get('GC_INTERVAL_MINUTES', '60'))
GC_MAX_IDLE_HOURS = int(os.environ.get('GC_MAX_IDLE_HOURS', '24'))
GC_ENABLED = os.environ.get('GC_ENABLED', 'true').lower() == 'true'


@dataclass
class GCResult:
    """Result of a garbage collection operation."""

    deleted: List[str] = field(default_factory=list)
    errors: List[Tuple[str, str]] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_count(self) -> int:
        return len(self.deleted)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'deleted': self.deleted,
            'errors': [{'session_id': s, 'error': e} for s, e in self.errors],
            'skipped': self.skipped,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'duration_seconds': self.duration_seconds,
        }


@dataclass
class GCCycleResult:
    """Result of a complete GC cycle."""

    idle_workers: GCResult
    terminated_sessions: GCResult
    orphaned_workers: GCResult
    total_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'idle_workers': self.idle_workers.to_dict(),
            'terminated_sessions': self.terminated_sessions.to_dict(),
            'orphaned_workers': self.orphaned_workers.to_dict(),
            'total_deleted': (
                self.idle_workers.success_count
                + self.terminated_sessions.success_count
                + self.orphaned_workers.success_count
            ),
            'total_errors': (
                self.idle_workers.error_count
                + self.terminated_sessions.error_count
                + self.orphaned_workers.error_count
            ),
            'total_duration_seconds': self.total_duration_seconds,
        }


class KnativeGarbageCollector:
    """
    Garbage collector for Knative session workers.

    Provides cleanup operations for:
    - Idle workers (no activity for N hours)
    - Terminated session workers (session ended but worker exists)
    - Orphaned workers (worker exists but no session in DB)
    """

    def __init__(self, spawner: Optional[KnativeSpawner] = None):
        """
        Initialize the garbage collector.

        Args:
            spawner: KnativeSpawner instance (uses global if not provided)
        """
        self.spawner = spawner or knative_spawner
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def cleanup_idle_workers(
        self, max_idle_hours: int = GC_MAX_IDLE_HOURS
    ) -> GCResult:
        """
        Delete Knative workers that have been idle for too long.

        Args:
            max_idle_hours: Maximum idle time in hours before cleanup

        Returns:
            GCResult with deleted sessions and any errors
        """
        start_time = datetime.now(timezone.utc)
        result = GCResult()

        if not KNATIVE_ENABLED:
            logger.debug('GC: Knative disabled, skipping idle worker cleanup')
            return result

        pool = await get_pool()
        if not pool:
            logger.warning('GC: Database not available')
            return result

        try:
            async with pool.acquire() as conn:
                # Query sessions with old last_activity_at
                # Only target workers that are not already terminated/pending
                rows = await conn.fetch(
                    """
                    SELECT id, knative_service_name, last_activity_at, worker_status
                    FROM sessions
                    WHERE knative_service_name IS NOT NULL
                    AND worker_status NOT IN ('terminated', 'pending')
                    AND (
                        last_activity_at < NOW() - INTERVAL '%s hours'
                        OR (last_activity_at IS NULL AND created_at < NOW() - INTERVAL '%s hours')
                    )
                    """,
                    max_idle_hours,
                    max_idle_hours,
                )

            logger.info(
                f'GC: Found {len(rows)} idle workers (>{max_idle_hours}h)'
            )

            for row in rows:
                session_id = row['id']
                service_name = row['knative_service_name']
                last_activity = row['last_activity_at']

                # Safety check: verify no recent activity
                if await self._has_recent_activity(session_id):
                    logger.info(
                        f'GC: Skipping {session_id} - has recent activity'
                    )
                    result.skipped.append(session_id)
                    continue

                # Safety check: verify not currently processing
                if await self._is_processing_task(session_id):
                    logger.info(
                        f'GC: Skipping {session_id} - currently processing task'
                    )
                    result.skipped.append(session_id)
                    continue

                try:
                    # Log before deleting for audit trail
                    logger.info(
                        f'GC: Deleting idle worker for session {session_id} '
                        f'(service: {service_name}, last_activity: {last_activity})'
                    )

                    # Delete the Knative worker
                    deleted = await self.spawner.delete_session_worker(
                        session_id
                    )

                    if deleted:
                        # Update session status
                        await self._update_session_worker_status(
                            session_id, 'terminated'
                        )
                        result.deleted.append(session_id)
                        logger.info(
                            f'GC: Successfully deleted idle worker '
                            f'for session {session_id}'
                        )
                    else:
                        result.errors.append(
                            (session_id, 'Failed to delete worker')
                        )

                except Exception as e:
                    error_msg = str(e)
                    result.errors.append((session_id, error_msg))
                    logger.error(
                        f'GC: Failed to delete worker for '
                        f'session {session_id}: {e}'
                    )

        except Exception as e:
            logger.error(f'GC: Error during idle worker cleanup: {e}')

        result.duration_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()
        return result

    async def cleanup_terminated_sessions(self) -> GCResult:
        """
        Delete workers for sessions that have been marked as terminated.

        These are sessions where the DB shows terminated but the Knative
        Service may still exist due to a previous cleanup failure.

        Returns:
            GCResult with deleted sessions and any errors
        """
        start_time = datetime.now(timezone.utc)
        result = GCResult()

        if not KNATIVE_ENABLED:
            logger.debug(
                'GC: Knative disabled, skipping terminated session cleanup'
            )
            return result

        pool = await get_pool()
        if not pool:
            logger.warning('GC: Database not available')
            return result

        try:
            async with pool.acquire() as conn:
                # Query sessions marked terminated but with service name
                # (indicates Knative resource may still exist)
                rows = await conn.fetch(
                    """
                    SELECT id, knative_service_name
                    FROM sessions
                    WHERE knative_service_name IS NOT NULL
                    AND worker_status = 'terminated'
                    """
                )

            logger.info(
                f'GC: Found {len(rows)} terminated sessions with services'
            )

            for row in rows:
                session_id = row['id']
                service_name = row['knative_service_name']

                try:
                    # Check if service actually exists
                    worker_info = await self.spawner.get_worker_status(
                        session_id
                    )

                    if worker_info.status == WorkerStatus.NOT_FOUND:
                        # Service already gone, just clear the name
                        await self._clear_session_service_name(session_id)
                        result.skipped.append(session_id)
                        logger.debug(
                            f'GC: Service already deleted for '
                            f'session {session_id}'
                        )
                        continue

                    logger.info(
                        f'GC: Deleting orphaned worker for terminated '
                        f'session {session_id} (service: {service_name})'
                    )

                    deleted = await self.spawner.delete_session_worker(
                        session_id
                    )

                    if deleted:
                        await self._clear_session_service_name(session_id)
                        result.deleted.append(session_id)
                        logger.info(
                            f'GC: Cleaned up orphaned worker '
                            f'for session {session_id}'
                        )
                    else:
                        result.errors.append(
                            (session_id, 'Failed to delete worker')
                        )

                except Exception as e:
                    error_msg = str(e)
                    result.errors.append((session_id, error_msg))
                    logger.error(
                        f'GC: Failed to cleanup terminated session '
                        f'{session_id}: {e}'
                    )

        except Exception as e:
            logger.error(f'GC: Error during terminated session cleanup: {e}')

        result.duration_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()
        return result

    async def cleanup_orphaned_workers(self) -> GCResult:
        """
        Delete Knative workers that exist but have no corresponding session.

        This handles cases where a session was deleted from the DB but the
        Knative resources were not cleaned up.

        Returns:
            GCResult with deleted workers and any errors
        """
        start_time = datetime.now(timezone.utc)
        result = GCResult()

        if not KNATIVE_ENABLED:
            logger.debug(
                'GC: Knative disabled, skipping orphaned worker cleanup'
            )
            return result

        pool = await get_pool()
        if not pool:
            logger.warning('GC: Database not available')
            return result

        try:
            # Get all Knative workers
            workers = await self.spawner.list_session_workers()

            if not workers:
                logger.debug('GC: No Knative workers found')
                return result

            logger.info(f'GC: Checking {len(workers)} workers for orphans')

            async with pool.acquire() as conn:
                for worker in workers:
                    session_id = worker.session_id

                    # Check if session exists in DB
                    row = await conn.fetchrow(
                        'SELECT id, worker_status FROM sessions WHERE id = $1',
                        session_id,
                    )

                    if row is not None:
                        # Session exists, not orphaned
                        continue

                    logger.info(
                        f'GC: Found orphaned worker for '
                        f'non-existent session {session_id}'
                    )

                    try:
                        deleted = await self.spawner.delete_session_worker(
                            session_id
                        )

                        if deleted:
                            result.deleted.append(session_id)
                            logger.info(
                                f'GC: Deleted orphaned worker '
                                f'for session {session_id}'
                            )
                        else:
                            result.errors.append(
                                (session_id, 'Failed to delete worker')
                            )

                    except Exception as e:
                        error_msg = str(e)
                        result.errors.append((session_id, error_msg))
                        logger.error(
                            f'GC: Failed to delete orphaned worker '
                            f'{session_id}: {e}'
                        )

        except Exception as e:
            logger.error(f'GC: Error during orphaned worker cleanup: {e}')

        result.duration_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()
        return result

    async def run_gc_cycle(
        self, max_idle_hours: int = GC_MAX_IDLE_HOURS
    ) -> GCCycleResult:
        """
        Run a complete garbage collection cycle.

        This performs all cleanup operations:
        1. Delete idle workers
        2. Delete workers for terminated sessions
        3. Delete orphaned workers

        Args:
            max_idle_hours: Maximum idle time for idle worker cleanup

        Returns:
            GCCycleResult with results from all cleanup operations
        """
        start_time = datetime.now(timezone.utc)

        logger.info('GC: Starting garbage collection cycle')

        # Run cleanup operations
        idle_result = await self.cleanup_idle_workers(
            max_idle_hours=max_idle_hours
        )
        terminated_result = await self.cleanup_terminated_sessions()
        orphaned_result = await self.cleanup_orphaned_workers()

        total_duration = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        result = GCCycleResult(
            idle_workers=idle_result,
            terminated_sessions=terminated_result,
            orphaned_workers=orphaned_result,
            total_duration_seconds=total_duration,
        )

        total_deleted = (
            idle_result.success_count
            + terminated_result.success_count
            + orphaned_result.success_count
        )
        total_errors = (
            idle_result.error_count
            + terminated_result.error_count
            + orphaned_result.error_count
        )

        logger.info(
            f'GC: Cycle complete - deleted {total_deleted} workers, '
            f'{total_errors} errors, {total_duration:.2f}s'
        )

        return result

    def start_background_gc(
        self, interval_minutes: int = GC_INTERVAL_MINUTES
    ) -> bool:
        """
        Start the background garbage collection task.

        Args:
            interval_minutes: Time between GC cycles in minutes

        Returns:
            True if started successfully, False if already running
        """
        if self._running:
            logger.warning('GC: Background task already running')
            return False

        if not KNATIVE_ENABLED:
            logger.info('GC: Knative disabled, not starting background GC')
            return False

        if not GC_ENABLED:
            logger.info('GC: Background GC disabled via GC_ENABLED=false')
            return False

        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._background_gc_loop(interval_minutes)
        )

        logger.info(
            f'GC: Started background task (interval: {interval_minutes}m)'
        )
        return True

    def stop_background_gc(self) -> bool:
        """
        Stop the background garbage collection task.

        Returns:
            True if stopped successfully, False if not running
        """
        if not self._running:
            logger.debug('GC: Background task not running')
            return False

        self._running = False
        self._stop_event.set()

        if self._task:
            self._task.cancel()
            self._task = None

        logger.info('GC: Stopped background task')
        return True

    @property
    def is_running(self) -> bool:
        """Check if background GC is running."""
        return self._running

    async def _background_gc_loop(self, interval_minutes: int) -> None:
        """Background loop that runs GC cycles periodically."""
        interval_seconds = interval_minutes * 60

        logger.info(
            f'GC: Background loop started, interval: {interval_minutes}m'
        )

        while self._running:
            try:
                # Wait for interval or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=interval_seconds
                    )
                    # Stop event was set
                    break
                except asyncio.TimeoutError:
                    # Timeout reached, run GC cycle
                    pass

                if not self._running:
                    break

                # Run GC cycle
                await self.run_gc_cycle()

            except asyncio.CancelledError:
                logger.info('GC: Background loop cancelled')
                break
            except Exception as e:
                logger.error(f'GC: Error in background loop: {e}')
                # Continue running despite errors
                await asyncio.sleep(60)  # Brief pause before retry

        logger.info('GC: Background loop stopped')

    async def _has_recent_activity(
        self, session_id: str, minutes: int = 5
    ) -> bool:
        """
        Check if a session has recent activity.

        Args:
            session_id: Session ID to check
            minutes: How recent to consider (default 5 minutes)

        Returns:
            True if session has activity within the time window
        """
        pool = await get_pool()
        if not pool:
            return True  # Assume active if we can't check

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT last_activity_at
                    FROM sessions
                    WHERE id = $1
                    AND last_activity_at > NOW() - INTERVAL '%s minutes'
                    """,
                    session_id,
                    minutes,
                )
                return row is not None
        except Exception as e:
            logger.warning(f'GC: Error checking recent activity: {e}')
            return True  # Assume active on error

    async def _is_processing_task(self, session_id: str) -> bool:
        """
        Check if a session is currently processing a task.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has a task in 'running' status
        """
        pool = await get_pool()
        if not pool:
            return True  # Assume processing if we can't check

        try:
            async with pool.acquire() as conn:
                # Check for running tasks associated with this session's codebase
                row = await conn.fetchrow(
                    """
                    SELECT t.id
                    FROM tasks t
                    JOIN sessions s ON t.codebase_id = s.codebase_id
                    WHERE s.id = $1
                    AND t.status = 'running'
                    LIMIT 1
                    """,
                    session_id,
                )
                return row is not None
        except Exception as e:
            logger.warning(f'GC: Error checking processing tasks: {e}')
            return True  # Assume processing on error

    async def _update_session_worker_status(
        self, session_id: str, status: str
    ) -> bool:
        """
        Update session worker status in the database.

        Args:
            session_id: Session ID to update
            status: New worker status

        Returns:
            True if updated successfully
        """
        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE sessions
                    SET worker_status = $1
                    WHERE id = $2
                    """,
                    status,
                    session_id,
                )
                return True
        except Exception as e:
            logger.error(f'GC: Failed to update session worker status: {e}')
            return False

    async def _clear_session_service_name(self, session_id: str) -> bool:
        """
        Clear the Knative service name from a session.

        Args:
            session_id: Session ID to update

        Returns:
            True if updated successfully
        """
        pool = await get_pool()
        if not pool:
            return False

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE sessions
                    SET knative_service_name = NULL
                    WHERE id = $1
                    """,
                    session_id,
                )
                return True
        except Exception as e:
            logger.error(f'GC: Failed to clear session service name: {e}')
            return False


# Global garbage collector instance
knative_gc = KnativeGarbageCollector()


# Convenience functions
async def cleanup_idle_workers(
    max_idle_hours: int = GC_MAX_IDLE_HOURS,
) -> GCResult:
    """Delete Knative workers that have been idle for too long."""
    return await knative_gc.cleanup_idle_workers(max_idle_hours=max_idle_hours)


async def cleanup_terminated_sessions() -> GCResult:
    """Delete workers for terminated sessions."""
    return await knative_gc.cleanup_terminated_sessions()


async def cleanup_orphaned_workers() -> GCResult:
    """Delete orphaned Knative workers."""
    return await knative_gc.cleanup_orphaned_workers()


async def run_gc_cycle(
    max_idle_hours: int = GC_MAX_IDLE_HOURS,
) -> GCCycleResult:
    """Run a complete garbage collection cycle."""
    return await knative_gc.run_gc_cycle(max_idle_hours=max_idle_hours)


def start_background_gc(
    interval_minutes: int = GC_INTERVAL_MINUTES,
) -> bool:
    """Start background garbage collection."""
    return knative_gc.start_background_gc(interval_minutes=interval_minutes)


def stop_background_gc() -> bool:
    """Stop background garbage collection."""
    return knative_gc.stop_background_gc()


# Public API
__all__ = [
    # Classes
    'KnativeGarbageCollector',
    'GCResult',
    'GCCycleResult',
    # Global instance
    'knative_gc',
    # Convenience functions
    'cleanup_idle_workers',
    'cleanup_terminated_sessions',
    'cleanup_orphaned_workers',
    'run_gc_cycle',
    'start_background_gc',
    'stop_background_gc',
    # Configuration
    'GC_INTERVAL_MINUTES',
    'GC_MAX_IDLE_HOURS',
    'GC_ENABLED',
]
