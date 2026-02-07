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
import shutil
import signal
import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
        agent_name: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        models_supported: Optional[List[str]] = None,
        features: Optional[Dict[str, bool]] = None,
    ):
        self.worker_id = worker_id
        self._pool = db_pool
        self._api_base_url = api_base_url.rstrip('/')
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        self._heartbeat_interval = heartbeat_interval
        # Agent identity for targeted routing
        self.agent_name = agent_name
        self.capabilities = capabilities or []
        # Model routing: list of models this worker can use
        self.models_supported = models_supported or []
        # Feature flags (e.g., rlm: True for RLM support)
        self.features = features or {}

        # Auto-detect RLM capability if python3 is available and CODETETHER_RLM_ENABLED=1
        if 'rlm' not in self.features:
            self.features['rlm'] = self._detect_rlm_capability()

        self._running = False
        self._current_run_id: Optional[str] = None
        self._current_task_id: Optional[str] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None

        # Stats
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_runtime_seconds = 0

    def _detect_rlm_capability(self) -> bool:
        """Auto-detect if this worker can support RLM tasks."""
        import shutil

        # Check if RLM is explicitly enabled via env var
        rlm_enabled = os.environ.get('CODETETHER_RLM_ENABLED', '0') == '1'
        if not rlm_enabled:
            return False

        # Check if python3 is available
        python_available = shutil.which('python3') is not None

        # Check if we have at least one subcall-eligible model
        has_subcall_model = len(self.models_supported) > 0

        return python_available and has_subcall_model

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
                    claimed_job = await self._claim_next_job()

                    if claimed_job:
                        # Execute the task, passing model_ref from claim
                        await self._execute_current_task(
                            model_ref=claimed_job.get('model_ref')
                        )
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

    async def _claim_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to claim the next available job from the queue.

        Uses the claim_next_task_run() SQL function for atomic claiming
        with concurrency limit enforcement and agent-targeted routing.

        The agent_name, capabilities, and models_supported are passed to filter tasks:
        - Tasks with target_agent_name set will only be claimed by matching workers
        - Tasks with required_capabilities will only be claimed by workers with ALL required caps
        - Tasks with model_ref will only be claimed by workers supporting that model

        Returns claimed job info dict if a job was claimed, None otherwise.
        The dict includes: run_id, task_id, priority, target_agent_name, model_ref
        """
        import json

        # Convert capabilities list to JSONB format for SQL
        capabilities_json = (
            json.dumps(self.capabilities) if self.capabilities else '[]'
        )

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM claim_next_task_run($1, $2, $3, $4::jsonb, $5)',
                self.worker_id,
                self._lease_duration,
                self.agent_name,  # Pass agent_name for targeted routing
                capabilities_json,  # Pass capabilities for capability-based routing
                self.models_supported
                if self.models_supported
                else None,  # Pass models for model routing
            )

            if row and row['run_id']:
                self._current_run_id = row['run_id']
                self._current_task_id = row['task_id']
                model_ref = row.get('model_ref')
                target_info = (
                    f', targeted_at={row.get("target_agent_name")}'
                    if row.get('target_agent_name')
                    else ''
                )
                model_info = f', model={model_ref}' if model_ref else ''
                logger.info(
                    f'Worker {self.worker_id} (agent={self.agent_name}) claimed run {self._current_run_id} '
                    f'(task={self._current_task_id}, priority={row["priority"]}{target_info}{model_info})'
                )
                # Return claim info including model_ref
                return {
                    'run_id': row['run_id'],
                    'task_id': row['task_id'],
                    'priority': row['priority'],
                    'target_agent_name': row.get('target_agent_name'),
                    'model_ref': model_ref,
                }

            return None

    async def _execute_current_task(
        self, model_ref: Optional[str] = None
    ) -> None:
        """Execute the currently claimed task.

        Args:
            model_ref: The model identifier from the claimed task (provider:model format).
                      If set, this model should be used for execution.
        """
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
            # Pass model_ref from the claim - this takes precedence over task_data.model
            result = await self._run_task(
                task_id, task_data, model_ref=model_ref
            )

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
        """Get task details from the API or directly from DB."""
        # First try to get from database directly (faster, more reliable)
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, title, prompt, agent_type, codebase_id, status,
                           metadata, created_at
                    FROM tasks WHERE id = $1
                    """,
                    task_id,
                )
                if row:
                    return {
                        'id': row['id'],
                        'title': row['title'],
                        'description': row['prompt'],
                        'prompt': row['prompt'],
                        'agent_type': row['agent_type'],
                        'codebase_id': row['codebase_id'],
                        'status': row['status'],
                        'metadata': row['metadata'] or {},
                        'created_at': row['created_at'].isoformat()
                        if row['created_at']
                        else None,
                    }
        except Exception as e:
            logger.warning(f'Failed to get task {task_id} from DB: {e}')

        # Fallback to REST API
        if not self._http_client:
            return None
        try:
            response = await self._http_client.get(
                f'{self._api_base_url}/v1/agent/tasks/{task_id}',
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f'Failed to get task {task_id}: {e}')
            return None

    async def _run_task(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        model_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the task by invoking the appropriate agent.

        For now, this calls the existing worker SSE task execution path.
        In the future, this could run agents directly.

        Args:
            task_id: The task ID to execute
            task_data: Task details from the API
            model_ref: Model identifier from claim (provider:model format).
                      Takes precedence over task_data.model if set.
        """
        # Get the task prompt
        prompt = task_data.get('description') or task_data.get('prompt', '')
        codebase_id = task_data.get('codebase_id', 'global')
        agent_type = task_data.get('agent_type', 'build')
        # Use model_ref from claim if set, otherwise fall back to task_data.model
        model = model_ref or task_data.get('model')

        model_info = f', model={model}' if model else ''
        logger.info(
            f'Running task {task_id}: agent={agent_type}, codebase={codebase_id}{model_info}'
        )

        # For global/custom automation tasks, call LLM directly via Anthropic API
        # For codebase tasks, use the agent bridge
        if not codebase_id or codebase_id == 'global' or codebase_id == 'None':
            return await self._run_llm_task(task_id, prompt, model)

        # Execute codebase task via the agent bridge sync endpoint
        if not self._http_client:
            raise Exception('HTTP client not initialized')

        try:
            # Create a session for this task execution
            session_response = await self._http_client.post(
                f'{self._api_base_url}/v1/agent/sessions',
                json={
                    'codebase_id': codebase_id,
                    'agent_type': agent_type,
                    'model': model,
                },
                timeout=30,
            )

            if session_response.status_code != 200:
                logger.warning(f'Session creation failed, falling back to LLM')
                return await self._run_llm_task(task_id, prompt, model)

            session_data = session_response.json()
            session_id = session_data.get('session_id', f'task-{task_id}')

            # Send the message synchronously
            message_response = await self._http_client.post(
                f'{self._api_base_url}/v1/agent/sessions/{session_id}/messages/sync',
                json={
                    'content': prompt,
                    'model': model,
                },
                timeout=self._lease_duration,
            )
            message_response.raise_for_status()
            result = message_response.json()

            return {
                'summary': result.get('content', 'Task completed')[:500],
                'result': result,
                'session_id': session_id,
            }

        except httpx.TimeoutException:
            raise Exception('Task execution timed out')
        except Exception as e:
            logger.warning(
                f'Task execution via API failed: {e}, falling back to LLM'
            )
            return await self._run_llm_task(task_id, prompt, model)

    async def _run_llm_task(
        self, task_id: str, prompt: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a global task via codetether-agent CLI.

        This runs codetether-agent as a subprocess, which handles LLM provider
        authentication and execution.
        """
        # Find agent binary
        agent_bin = self._find_agent_binary()
        if not agent_bin:
            raise Exception(
                'Agent binary not found. Install codetether or set CODETETHER_BIN_PATH env var.'
            )

        # Map model to agent format if needed
        agent_model = self._normalize_model(model)

        logger.info(
            f'Running task {task_id} via agent CLI'
            f'{f" with model {agent_model}" if agent_model else ""}'
        )

        # Build command
        cmd = [
            agent_bin,
            'run',
            '--agent',
            'general',  # Use general agent for custom automation
            '--format',
            'json',  # Get structured output
        ]

        if agent_model:
            cmd.extend(['--model', agent_model])

        # Add the prompt
        cmd.append('--')
        cmd.append(prompt)

        # Execute agent as subprocess
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(Path.home()),  # Run in home directory for global tasks
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,
                    'NO_COLOR': '1',  # Disable color codes in output
                },
            )

            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._lease_duration - 60,  # Leave margin for cleanup
            )

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace').strip()
                logger.error(f'Agent failed for task {task_id}: {error_msg}')
                raise Exception(f'Agent execution failed: {error_msg}')

            # Parse agent streaming JSON output (NDJSON format)
            output = stdout.decode('utf-8', errors='replace').strip()
            content = self._parse_agent_output(output)

            # Truncate for summary
            summary = content[:500] + '...' if len(content) > 500 else content

            return {
                'summary': summary,
                'result': content,
                'model': agent_model,
                'exit_code': process.returncode,
            }

        except asyncio.TimeoutError:
            logger.error(f'Agent timed out for task {task_id}')
            raise Exception('Task execution timed out')
        except Exception as e:
            logger.error(f'Agent execution error for task {task_id}: {e}')
            raise

    def _find_agent_binary(self) -> Optional[str]:
        """Find the codetether agent binary path."""
        # Check environment variable first
        env_bin = os.environ.get('CODETETHER_BIN_PATH')
        if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
            return env_bin

        # Check common locations
        candidates = [
            '/opt/codetether-worker/bin/codetether',
            str(Path.home() / '.cargo' / 'bin' / 'codetether'),
            str(Path.home() / '.local' / 'bin' / 'codetether'),
            '/usr/local/bin/codetether',
            '/usr/bin/codetether',
        ]

        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

        # Try PATH
        path_bin = shutil.which('codetether')
        if path_bin:
            return path_bin

        return None

    def _normalize_model(
        self, model: Optional[str]
    ) -> Optional[str]:
        """
        Convert model identifier to provider/model format.

        Input formats:
        - "claude-sonnet" -> "anthropic/claude-sonnet-4-20250514"
        - "anthropic:claude-sonnet-4" -> "anthropic/claude-sonnet-4"
        - None -> None (use agent default)
        """
        if not model:
            return None

        # If already in provider/model format, use as-is
        if '/' in model:
            return model

        # Convert provider:model to provider/model
        if ':' in model:
            provider, model_name = model.split(':', 1)
            return f'{provider}/{model_name}'

        # Map friendly names to full model specs
        model_map = {
            'claude-sonnet': 'anthropic/claude-sonnet-4-20250514',
            'claude-opus': 'anthropic/claude-opus-4-20250514',
            'claude-haiku': 'anthropic/claude-3-5-haiku-20241022',
            'sonnet': 'anthropic/claude-sonnet-4-20250514',
            'opus': 'anthropic/claude-opus-4-20250514',
            'haiku': 'anthropic/claude-3-5-haiku-20241022',
            'gpt-4': 'openai/gpt-4',
            'gpt-4o': 'openai/gpt-4o',
            'gpt-4.1': 'openai/gpt-4.1',
            'o1': 'openai/o1',
            'o3': 'openai/o3',
            'gemini': 'google/gemini-2.5-pro',
            'gemini-pro': 'google/gemini-2.5-pro',
            'gemini-flash': 'google/gemini-2.5-flash',
            'minimax': 'minimax/minimax-m2.1',
            'grok': 'xai/grok-3',
            'default': None,  # Use agent default
        }

        return model_map.get(model.lower(), model)

    def _parse_agent_output(self, output: str) -> str:
        """
        Parse agent streaming JSON output to extract the text content.

        The agent outputs NDJSON (newline-delimited JSON) with various event types:
        - step_start: Agent starting
        - text: Actual text content from the LLM
        - tool_call: Tool being called
        - tool_result: Tool result
        - step_finish: Agent finished
        - summary: Session summary

        We extract all 'text' events and concatenate them.
        """
        text_parts = []

        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                event_type = event.get('type')

                if event_type == 'text':
                    # Extract text from the part
                    part = event.get('part', {})
                    text = part.get('text', '')
                    if text:
                        text_parts.append(text)
                elif event_type == 'summary':
                    # Summary event contains overall session summary
                    part = event.get('part', {})
                    summary = part.get('summary', '')
                    if summary and not text_parts:
                        # Use summary if we didn't get any text
                        text_parts.append(summary)

            except json.JSONDecodeError:
                # Not JSON, might be plain text output
                if line and not line.startswith('{'):
                    text_parts.append(line)

        if text_parts:
            return '\n'.join(text_parts)

        # Fallback: return raw output if we couldn't parse anything
        return output

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

        # Determine event type
        event_map = {
            'running': 'task_started',
            'needs_input': 'task_needs_input',
            'completed': 'task_completed',
            'failed': 'task_failed',
        }
        event = event_map.get(status, 'task_update')

        payload = {
            'event': event,
            'run_id': run_id,
            'task_id': task_id,
            'status': status,
            'result': result,
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        # Add webhook signature
        webhook_secret = os.environ.get('CODETETHER_WEBHOOK_SECRET')
        if webhook_secret:
            from .webhook_security import generate_webhook_signature
            import json

            payload_json = json.dumps(payload)
            signature = generate_webhook_signature(payload_json, webhook_secret)
            headers = {
                'X-CodeTether-Signature': signature,
                'X-CodeTether-Timestamp': str(
                    int(datetime.now(timezone.utc).timestamp())
                ),
            }
        else:
            headers = {}

        try:
            response = await self._http_client.post(
                url,
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            if response.status_code < 300:
                logger.info(
                    f'Webhook called successfully for run {run_id} (event={event})'
                )
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
        agent_name: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        models_supported: Optional[List[str]] = None,
    ):
        self._db_url = db_url
        self._api_base_url = api_base_url
        self._num_workers = num_workers
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        # Agent identity for targeted routing (shared by all workers in pool)
        self._agent_name = agent_name
        self._capabilities = capabilities or []
        # Model routing: list of models this worker pool supports
        self._models_supported = models_supported or []

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
                agent_name=self._agent_name,
                capabilities=self._capabilities,
                models_supported=self._models_supported,
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

                    # Fail tasks that exceeded their routing deadline
                    deadline_failed = await conn.fetchval(
                        'SELECT fail_deadline_exceeded_tasks()'
                    )
                    if deadline_failed and deadline_failed > 0:
                        logger.info(
                            f'Failed {deadline_failed} tasks that exceeded deadline'
                        )

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
    parser.add_argument(
        '--agent-name',
        default=os.environ.get('AGENT_NAME'),
        help='Agent name for targeted task routing (env: AGENT_NAME)',
    )
    parser.add_argument(
        '--capabilities',
        default=os.environ.get('AGENT_CAPABILITIES', ''),
        help='Comma-separated list of capabilities (env: AGENT_CAPABILITIES)',
    )
    parser.add_argument(
        '--models-supported',
        default=os.environ.get('A2A_MODELS_SUPPORTED', ''),
        help='Comma-separated list of model identifiers this worker supports '
        '(e.g., "anthropic:claude-sonnet-4.5,openai:gpt-5"). '
        'Tasks with model_ref will only route to workers supporting that model. '
        '(env: A2A_MODELS_SUPPORTED)',
    )

    args = parser.parse_args()

    # Parse capabilities
    capabilities = []
    if args.capabilities:
        capabilities = [
            c.strip() for c in args.capabilities.split(',') if c.strip()
        ]

    # Parse models_supported
    models_supported = []
    if args.models_supported:
        models_supported = [
            m.strip() for m in args.models_supported.split(',') if m.strip()
        ]

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
        agent_name=args.agent_name,
        capabilities=capabilities,
        models_supported=models_supported,
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
