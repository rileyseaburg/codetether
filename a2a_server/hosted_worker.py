"""
Hosted Worker - Managed task execution for mid-market users.

This module provides:
- Worker pool that claims and executes tasks from the queue
- Lease-based job locking with heartbeat renewal
- Automatic expired lease reclamation
- Graceful shutdown support

Usage:
    python -m a2a_server.hosted_worker --workers 2 --db-url postgresql://...

The worker process runs N concurrent workers that poll the task_runs queue.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

from .task_queue import TaskRunStatus

logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_WORKERS = 2
DEFAULT_POLL_INTERVAL = 2.0  # seconds
DEFAULT_LEASE_DURATION = 600  # 10 minutes
DEFAULT_HEARTBEAT_INTERVAL = 60  # 1 minute


class HostedWorker:
    """
    A single worker that claims and executes tasks from the queue.

    Multiple HostedWorker instances run concurrently in the same process.
    """

    def __init__(
        self,
        worker_id: str,
        db_pool: asyncpg.Pool,
        api_base_url: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        lease_duration: int = DEFAULT_LEASE_DURATION,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
    ):
        self.worker_id = worker_id
        self._pool = db_pool
        self._api_base_url = api_base_url.rstrip('/')
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        self._heartbeat_interval = heartbeat_interval

        self._running = False
        self._current_run_id: Optional[str] = None
        self._current_task_id: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None

        # Stats
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_runtime_seconds = 0

    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        self._http_client = httpx.AsyncClient(
            timeout=300.0
        )  # 5 min timeout for task execution

        logger.info(f'Worker {self.worker_id} starting')

        try:
            while self._running:
                try:
                    # Try to claim next job
                    claimed = await self._claim_next_job()

                    if claimed:
                        # Execute the task
                        await self._execute_current_task()
                    else:
                        # No work available, wait before polling again
                        await asyncio.sleep(self._poll_interval)

                except asyncio.CancelledError:
                    logger.info(f'Worker {self.worker_id} cancelled')
                    break
                except Exception as e:
                    logger.error(
                        f'Worker {self.worker_id} error: {e}', exc_info=True
                    )
                    await asyncio.sleep(self._poll_interval)
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        logger.info(f'Worker {self.worker_id} stopping')
        self._running = False

        # Stop heartbeat if running
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _claim_next_job(self) -> bool:
        """
        Attempt to claim the next available job from the queue.

        Uses the claim_next_task_run() SQL function for atomic claiming
        with concurrency limit enforcement.

        Returns True if a job was claimed.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM claim_next_task_run($1, $2)',
                self.worker_id,
                self._lease_duration,
            )

            if row and row['run_id']:
                self._current_run_id = row['run_id']
                self._current_task_id = row['task_id']
                logger.info(
                    f'Worker {self.worker_id} claimed run {self._current_run_id} '
                    f'(task={self._current_task_id}, priority={row["priority"]})'
                )
                return True

            return False

    async def _execute_current_task(self) -> None:
        """Execute the currently claimed task."""
        if not self._current_run_id or not self._current_task_id:
            return

        run_id = self._current_run_id
        task_id = self._current_task_id
        started_at = datetime.now(timezone.utc)

        # Start heartbeat to keep lease alive
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(run_id))

        try:
            logger.info(f'Worker {self.worker_id} executing task {task_id}')

            # Get task details from API
            task_data = await self._get_task_details(task_id)
            if not task_data:
                raise Exception(f'Task {task_id} not found')

            # Execute the task via API (this triggers the actual agent work)
            result = await self._run_task(task_id, task_data)

            # Mark completed
            runtime = int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )
            await self._complete_run(
                run_id,
                status='completed',
                result_summary=result.get('summary', 'Task completed'),
                result_full=result,
            )

            self.tasks_completed += 1
            self.total_runtime_seconds += runtime
            logger.info(
                f'Worker {self.worker_id} completed task {task_id} in {runtime}s'
            )

        except Exception as e:
            logger.error(
                f'Worker {self.worker_id} failed task {task_id}: {e}',
                exc_info=True,
            )

            await self._complete_run(
                run_id,
                status='failed',
                error=str(e),
            )

            self.tasks_failed += 1

        finally:
            # Stop heartbeat
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._heartbeat_task = None

            self._current_run_id = None
            self._current_task_id = None

    async def _get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task details from the API."""
        if not self._http_client:
            return None
        try:
            response = await self._http_client.post(
                f'{self._api_base_url}/mcp/v1/rpc',
                json={
                    'jsonrpc': '2.0',
                    'method': 'tools/call',
                    'params': {
                        'name': 'get_task',
                        'arguments': {'task_id': task_id},
                    },
                    'id': str(uuid.uuid4()),
                },
            )
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                logger.error(
                    f'API error getting task {task_id}: {data["error"]}'
                )
                return None

            result = data.get('result', {})
            # Handle MCP response format
            if isinstance(result, dict) and 'content' in result:
                for content in result['content']:
                    if content.get('type') == 'text':
                        return json.loads(content['text'])
            return result

        except Exception as e:
            logger.error(f'Failed to get task {task_id}: {e}')
            return None

    async def _run_task(
        self, task_id: str, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the task by invoking the appropriate agent.

        For now, this calls the existing worker SSE task execution path.
        In the future, this could run agents directly.
        """
        # Get the task prompt
        prompt = task_data.get('description') or task_data.get('prompt', '')
        codebase_id = task_data.get('codebase_id', 'global')
        agent_type = task_data.get('agent_type', 'build')
        model = task_data.get('model')

        logger.info(
            f'Running task {task_id}: agent={agent_type}, codebase={codebase_id}'
        )

        # For global/pending tasks, we can execute directly via API
        # This triggers the existing execution path which may use SSE workers
        # or we can implement direct execution here

        # Option 1: Use the continue_task endpoint to trigger execution
        # This works with the existing worker infrastructure
        if not self._http_client:
            raise Exception('HTTP client not initialized')
        try:
            response = await self._http_client.post(
                f'{self._api_base_url}/mcp/v1/rpc',
                json={
                    'jsonrpc': '2.0',
                    'method': 'tools/call',
                    'params': {
                        'name': 'continue_task',
                        'arguments': {
                            'task_id': task_id,
                            'input': prompt,  # Pass the prompt as continuation
                        },
                    },
                    'id': str(uuid.uuid4()),
                },
                timeout=self._lease_duration,  # Don't timeout before lease
            )
            response.raise_for_status()
            data = response.json()

            if 'error' in data:
                raise Exception(f'Task execution error: {data["error"]}')

            result = data.get('result', {})

            # Extract result from MCP format
            if isinstance(result, dict) and 'content' in result:
                for content in result['content']:
                    if content.get('type') == 'text':
                        try:
                            return json.loads(content['text'])
                        except json.JSONDecodeError:
                            return {
                                'summary': content['text'],
                                'raw': content['text'],
                            }

            return {'summary': 'Task completed', 'result': result}

        except httpx.TimeoutException:
            # Task took too long - it may still be running
            # Check task status
            task_details = await self._get_task_details(task_id)
            if task_details and task_details.get('status') == 'completed':
                return {
                    'summary': 'Task completed (timeout during response)',
                    'result': task_details,
                }
            raise Exception('Task execution timed out')

    async def _heartbeat_loop(self, run_id: str) -> None:
        """Periodically renew the lease on the current job."""
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)

                async with self._pool.acquire() as conn:
                    renewed = await conn.fetchval(
                        'SELECT renew_task_run_lease($1, $2, $3)',
                        run_id,
                        self.worker_id,
                        self._lease_duration,
                    )

                    if not renewed:
                        logger.warning(
                            f'Failed to renew lease for run {run_id}'
                        )
                        break

                    logger.debug(f'Renewed lease for run {run_id}')

        except asyncio.CancelledError:
            pass

    async def _complete_run(
        self,
        run_id: str,
        status: str,
        result_summary: Optional[str] = None,
        result_full: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Mark a task run as completed or failed."""
        async with self._pool.acquire() as conn:
            await conn.fetchval(
                'SELECT complete_task_run($1, $2, $3, $4, $5, $6)',
                run_id,
                self.worker_id,
                status,
                result_summary,
                json.dumps(result_full) if result_full else None,
                error,
            )

        logger.info(f'Run {run_id} marked as {status}')

        # TODO: Send notification (email/webhook) if configured
        await self._send_completion_notification(run_id, status)

    async def _send_completion_notification(
        self, run_id: str, status: str
    ) -> None:
        """
        Send completion notification (email/webhook) with retry-safe 3-state flow.

        Flow:
        1. Atomically claim notification for send (increments attempts)
        2. Try to send
        3. On success: mark_notification_sent()
        4. On failure: mark_notification_failed() with backoff for retry

        This prevents both duplicate sends AND permanent silence.
        """
        # Get notification settings and task details for this run
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT tr.notify_email, tr.notify_webhook_url, 
                       tr.notification_status, tr.webhook_status,
                       tr.result_summary, tr.result_full, tr.task_id,
                       tr.runtime_seconds, tr.last_error,
                       t.title, t.prompt
                FROM task_runs tr
                LEFT JOIN tasks t ON tr.task_id = t.id
                WHERE tr.id = $1
                """,
                run_id,
            )

            if not row:
                return

        # Send email notification with 3-state tracking
        if row['notify_email'] and row['notification_status'] != 'sent':
            await self._send_email_notification(run_id, row, status)

        # Send webhook notification with 3-state tracking
        if row['notify_webhook_url'] and row['webhook_status'] != 'sent':
            await self._send_webhook_notification(run_id, row, status)

    async def _send_email_notification(
        self, run_id: str, row: dict, status: str
    ) -> None:
        """Send email notification with atomic claim and retry support."""
        # Atomically claim the notification (prevents double-send)
        async with self._pool.acquire() as conn:
            claimed = await conn.fetchval(
                'SELECT claim_notification_for_send($1, $2)',
                run_id,
                3,  # max_attempts
            )

            if not claimed:
                logger.debug(
                    f'Notification already claimed or sent for run {run_id}'
                )
                return

        # Now try to send the email
        try:
            from .email_notifications import send_task_completion_email

            # Extract result from JSON if stored
            result_text = row['result_summary']
            if row['result_full']:
                try:
                    result_full = (
                        json.loads(row['result_full'])
                        if isinstance(row['result_full'], str)
                        else row['result_full']
                    )
                    result_text = (
                        result_full.get('summary')
                        or result_full.get('result')
                        or result_text
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            email_sent = await send_task_completion_email(
                to_email=row['notify_email'],
                task_id=row['task_id'],
                title=row['title'] or 'Task',
                status=status,
                result=result_text,
                error=row['last_error'] if status == 'failed' else None,
                runtime_seconds=row['runtime_seconds'],
                worker_name=self.worker_id,
            )

            if email_sent:
                # Mark as sent - success!
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        'SELECT mark_notification_sent($1)', run_id
                    )
                logger.info(
                    f'Completion email sent to {row["notify_email"]} for run {run_id}'
                )
            else:
                # Mark as failed with retry backoff
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        'SELECT mark_notification_failed($1, $2, $3)',
                        run_id,
                        'SendGrid returned failure (check API key/config)',
                        3,
                    )
                logger.warning(
                    f'Failed to send completion email for run {run_id}, will retry'
                )

        except ImportError as e:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    'SELECT mark_notification_failed($1, $2, $3)',
                    run_id,
                    f'email_notifications module not available: {e}',
                    3,
                )
            logger.warning('email_notifications module not available')
        except Exception as e:
            # Mark as failed with retry backoff
            async with self._pool.acquire() as conn:
                await conn.execute(
                    'SELECT mark_notification_failed($1, $2, $3)',
                    run_id,
                    str(e)[:500],  # Truncate error message
                    3,
                )
            logger.error(f'Error sending completion email: {e}')

    async def _send_webhook_notification(
        self, run_id: str, row: dict, status: str
    ) -> None:
        """Send webhook notification with atomic claim and retry support."""
        # Atomically claim the webhook notification
        async with self._pool.acquire() as conn:
            claimed = await conn.fetchval(
                'SELECT claim_webhook_for_send($1, $2)',
                run_id,
                3,  # max_attempts
            )

            if not claimed:
                logger.debug(
                    f'Webhook already claimed or sent for run {run_id}'
                )
                return

        # Now try to call the webhook
        try:
            await self._call_webhook(
                url=row['notify_webhook_url'],
                run_id=run_id,
                task_id=row['task_id'],
                status=status,
                result=row['result_summary'],
                error=row['last_error'],
            )

            # Mark as sent - success!
            async with self._pool.acquire() as conn:
                await conn.execute('SELECT mark_webhook_sent($1)', run_id)
            logger.info(f'Webhook called successfully for run {run_id}')

        except Exception as e:
            # Mark as failed with retry backoff
            async with self._pool.acquire() as conn:
                await conn.execute(
                    'SELECT mark_webhook_failed($1, $2, $3)',
                    run_id,
                    str(e)[:500],
                    3,
                )
            logger.error(f'Error calling webhook: {e}')

    async def _call_webhook(
        self,
        url: str,
        run_id: str,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Call webhook URL with task completion data."""
        if not self._http_client:
            return

        payload = {
            'event': 'task_completed',
            'run_id': run_id,
            'task_id': task_id,
            'status': status,
            'result': result,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = await self._http_client.post(
                url,
                json=payload,
                timeout=10.0,
            )
            if response.status_code < 300:
                logger.info(f'Webhook called successfully for run {run_id}')
            else:
                logger.warning(
                    f'Webhook returned {response.status_code} for run {run_id}'
                )
        except Exception as e:
            logger.error(f'Webhook call failed for run {run_id}: {e}')

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


class HostedWorkerPool:
    """
    Manages a pool of hosted workers.

    Handles:
    - Starting N workers
    - Periodic expired lease reclamation
    - Graceful shutdown
    - Health reporting
    """

    def __init__(
        self,
        db_url: str,
        api_base_url: str,
        num_workers: int = DEFAULT_WORKERS,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        lease_duration: int = DEFAULT_LEASE_DURATION,
    ):
        self._db_url = db_url
        self._api_base_url = api_base_url
        self._num_workers = num_workers
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration

        self._pool: Optional[asyncpg.Pool] = None
        self._workers: List[HostedWorker] = []
        self._worker_tasks: List[asyncio.Task] = []
        self._reclaim_task: Optional[asyncio.Task] = None
        self._running = False

        # Pool identification
        self._pool_id = (
            f'{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}'
        )

    async def start(self) -> None:
        """Start the worker pool."""
        logger.info(
            f'Starting hosted worker pool {self._pool_id} with {self._num_workers} workers'
        )

        # Connect to database
        self._pool = await asyncpg.create_pool(
            self._db_url,
            min_size=self._num_workers + 1,  # +1 for reclaim task
            max_size=self._num_workers * 2,
        )

        # Register this pool
        await self._register_pool()

        self._running = True

        # Start workers
        for i in range(self._num_workers):
            worker_id = f'{self._pool_id}-worker-{i}'
            worker = HostedWorker(
                worker_id=worker_id,
                db_pool=self._pool,
                api_base_url=self._api_base_url,
                poll_interval=self._poll_interval,
                lease_duration=self._lease_duration,
            )
            self._workers.append(worker)
            task = asyncio.create_task(worker.start())
            self._worker_tasks.append(task)

        # Start expired lease reclamation
        self._reclaim_task = asyncio.create_task(self._reclaim_loop())

        logger.info(f'Worker pool {self._pool_id} started')

    async def stop(self) -> None:
        """Gracefully stop the worker pool."""
        logger.info(f'Stopping worker pool {self._pool_id}')
        self._running = False

        # Stop all workers
        for worker in self._workers:
            await worker.stop()

        # Cancel worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for workers to finish
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        # Stop reclaim task
        if self._reclaim_task:
            self._reclaim_task.cancel()
            try:
                await self._reclaim_task
            except asyncio.CancelledError:
                pass

        # Unregister pool
        await self._unregister_pool()

        # Close database pool
        if self._pool:
            await self._pool.close()

        logger.info(f'Worker pool {self._pool_id} stopped')

    async def _register_pool(self) -> None:
        """Register this worker pool in the database."""
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hosted_workers (id, hostname, process_id, max_concurrent_tasks, started_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    status = 'active',
                    last_heartbeat = NOW(),
                    stopped_at = NULL
                """,
                self._pool_id,
                socket.gethostname(),
                os.getpid(),
                self._num_workers,
            )

    async def _unregister_pool(self) -> None:
        """Mark this worker pool as stopped."""
        if not self._pool:
            return

        try:
            async with self._pool.acquire() as conn:
                # Get stats from workers
                total_completed = sum(w.tasks_completed for w in self._workers)
                total_failed = sum(w.tasks_failed for w in self._workers)
                total_runtime = sum(
                    w.total_runtime_seconds for w in self._workers
                )

                await conn.execute(
                    """
                    UPDATE hosted_workers SET
                        status = 'stopped',
                        stopped_at = NOW(),
                        tasks_completed = $2,
                        tasks_failed = $3,
                        total_runtime_seconds = $4
                    WHERE id = $1
                    """,
                    self._pool_id,
                    total_completed,
                    total_failed,
                    total_runtime,
                )
        except Exception as e:
            logger.error(f'Failed to unregister pool: {e}')

    async def _reclaim_loop(self) -> None:
        """Periodically reclaim expired leases and retry failed notifications."""
        if not self._pool:
            return
        try:
            while self._running:
                await asyncio.sleep(60)  # Check every 60 seconds

                async with self._pool.acquire() as conn:
                    reclaimed = await conn.fetchval(
                        'SELECT reclaim_expired_task_runs()'
                    )
                    if reclaimed and reclaimed > 0:
                        logger.info(f'Reclaimed {reclaimed} expired task runs')

                    # Update pool heartbeat
                    current_tasks = sum(
                        1 for w in self._workers if w._current_run_id
                    )
                    await conn.execute(
                        """
                        UPDATE hosted_workers SET
                            last_heartbeat = NOW(),
                            current_tasks = $2
                        WHERE id = $1
                        """,
                        self._pool_id,
                        current_tasks,
                    )

                # Retry failed notifications
                await self._retry_failed_notifications()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f'Reclaim loop error: {e}', exc_info=True)

    async def _retry_failed_notifications(self) -> None:
        """
        Process failed notifications that are ready for retry.

        This runs periodically in the pool's reclaim loop to ensure
        no notifications are permanently lost due to transient failures.
        """
        if not self._pool:
            return

        try:
            async with self._pool.acquire() as conn:
                # Get notifications ready for retry
                rows = await conn.fetch(
                    'SELECT * FROM get_pending_notification_retries($1)',
                    10,  # Process up to 10 at a time
                )

            if not rows:
                return

            logger.info(f'Processing {len(rows)} notification retries')

            # Use one of our workers to send the notifications
            # (reuse their HTTP client and notification logic)
            if self._workers:
                worker = self._workers[0]

                for row in rows:
                    run_id = row['run_id']

                    # Get full task details for notification
                    async with self._pool.acquire() as conn:
                        full_row = await conn.fetchrow(
                            """
                            SELECT tr.notify_email, tr.notify_webhook_url, 
                                   tr.notification_status, tr.webhook_status,
                                   tr.result_summary, tr.result_full, tr.task_id,
                                   tr.runtime_seconds, tr.last_error, tr.status,
                                   t.title, t.prompt
                            FROM task_runs tr
                            LEFT JOIN tasks t ON tr.task_id = t.id
                            WHERE tr.id = $1
                            """,
                            run_id,
                        )

                    if not full_row:
                        continue

                    task_status = full_row['status'] or 'completed'

                    # Retry email if needed
                    if (
                        row['notification_status'] == 'failed'
                        and full_row['notify_email']
                    ):
                        logger.info(
                            f'Retrying email notification for run {run_id} '
                            f'(attempt {row["notification_attempts"] + 1})'
                        )
                        await worker._send_email_notification(
                            run_id, dict(full_row), task_status
                        )

                    # Retry webhook if needed
                    if (
                        row['webhook_status'] == 'failed'
                        and full_row['notify_webhook_url']
                    ):
                        logger.info(
                            f'Retrying webhook notification for run {run_id} '
                            f'(attempt {row["webhook_attempts"] + 1})'
                        )
                        await worker._send_webhook_notification(
                            run_id, dict(full_row), task_status
                        )

        except Exception as e:
            logger.error(f'Error retrying notifications: {e}', exc_info=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            'pool_id': self._pool_id,
            'num_workers': self._num_workers,
            'running': self._running,
            'workers': [
                {
                    'id': w.worker_id,
                    'current_run': w._current_run_id,
                    'tasks_completed': w.tasks_completed,
                    'tasks_failed': w.tasks_failed,
                    'total_runtime': w.total_runtime_seconds,
                }
                for w in self._workers
            ],
            'totals': {
                'completed': sum(w.tasks_completed for w in self._workers),
                'failed': sum(w.tasks_failed for w in self._workers),
                'runtime': sum(w.total_runtime_seconds for w in self._workers),
            },
        }


async def main():
    """Main entry point for hosted worker process."""
    parser = argparse.ArgumentParser(
        description='CodeTether Hosted Worker Pool'
    )
    parser.add_argument(
        '--workers',
        '-w',
        type=int,
        default=DEFAULT_WORKERS,
        help=f'Number of concurrent workers (default: {DEFAULT_WORKERS})',
    )
    parser.add_argument(
        '--db-url',
        default=os.environ.get(
            'DATABASE_URL',
            'postgresql://postgres:spike2@192.168.50.70:5432/a2a_server',
        ),
        help='PostgreSQL connection URL',
    )
    parser.add_argument(
        '--api-url',
        default=os.environ.get('API_BASE_URL', 'http://localhost:9001'),
        help='CodeTether API base URL',
    )
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})',
    )
    parser.add_argument(
        '--lease-duration',
        type=int,
        default=DEFAULT_LEASE_DURATION,
        help=f'Lease duration in seconds (default: {DEFAULT_LEASE_DURATION})',
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level (default: INFO)',
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    )

    # Create worker pool
    pool = HostedWorkerPool(
        db_url=args.db_url,
        api_base_url=args.api_url,
        num_workers=args.workers,
        poll_interval=args.poll_interval,
        lease_duration=args.lease_duration,
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info('Received shutdown signal')
        asyncio.create_task(pool.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Start pool
    await pool.start()

    # Wait for shutdown
    try:
        while pool._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass

    logger.info('Hosted worker pool shutdown complete')


if __name__ == '__main__':
    asyncio.run(main())
