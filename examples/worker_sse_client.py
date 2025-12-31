#!/usr/bin/env python3
"""
Example: SSE Worker Client for Push-Based Task Distribution

This example demonstrates how a worker can connect to the A2A server
via SSE to receive task notifications in real-time instead of polling.

Usage:
    python worker_sse_client.py --server https://api.codetether.run --name my-worker

The worker will:
1. Connect to GET /v1/worker/tasks/stream via SSE
2. Receive task_available events when new tasks are created
3. Claim tasks atomically via POST /v1/worker/tasks/claim
4. Process the task and release it via POST /v1/worker/tasks/release

This implements "reverse-polling" as described in the CISO whitepaper.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Set

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('worker-sse-client')


class SSEWorkerClient:
    """
    Worker client that connects via SSE for push-based task notifications.
    """

    def __init__(
        self,
        server_url: str,
        worker_name: str,
        worker_id: Optional[str] = None,
        codebases: Optional[Set[str]] = None,
        capabilities: Optional[list] = None,
        auth_token: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip('/')
        self.worker_name = worker_name
        self.worker_id = worker_id or f'{worker_name}-{os.getpid()}'
        self.codebases = codebases or set()
        self.capabilities = capabilities or ['opencode', 'build']
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False

    def _get_headers(self) -> dict:
        """Build headers for requests."""
        headers = {
            'X-Agent-Name': self.worker_name,
            'X-Worker-ID': self.worker_id,
            'X-Capabilities': ','.join(self.capabilities),
            'X-Codebases': ','.join(self.codebases),
        }
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(
                    total=None
                ),  # SSE needs no timeout
            )
        return self.session

    async def claim_task(self, task_id: str) -> bool:
        """
        Atomically claim a task.

        Returns True if claim succeeded, False if already claimed.
        """
        session = await self._get_session()
        url = f'{self.server_url}/v1/worker/tasks/claim'

        headers = self._get_headers()
        payload = {'task_id': task_id}

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f'Successfully claimed task {task_id}')
                    return True
                elif resp.status == 409:
                    logger.info(
                        f'Task {task_id} already claimed by another worker'
                    )
                    return False
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Failed to claim task: {resp.status} {text}'
                    )
                    return False
        except Exception as e:
            logger.error(f'Error claiming task {task_id}: {e}')
            return False

    async def release_task(
        self,
        task_id: str,
        status: str = 'completed',
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Release a task after processing.

        Args:
            task_id: ID of the task to release
            status: 'completed', 'failed', or 'cancelled'
            result: Result message (for completed tasks)
            error: Error message (for failed tasks)
        """
        session = await self._get_session()
        url = f'{self.server_url}/v1/worker/tasks/release'

        headers = self._get_headers()
        payload = {
            'task_id': task_id,
            'status': status,
        }
        if result:
            payload['result'] = result
        if error:
            payload['error'] = error

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f'Released task {task_id} with status {status}')
                    return True
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Failed to release task: {resp.status} {text}'
                    )
                    return False
        except Exception as e:
            logger.error(f'Error releasing task {task_id}: {e}')
            return False

    async def update_codebases(self, codebases: Set[str]) -> bool:
        """Update the server with our list of codebases."""
        session = await self._get_session()
        url = f'{self.server_url}/v1/worker/codebases'

        headers = self._get_headers()
        payload = {'codebases': list(codebases)}

        try:
            async with session.put(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f'Updated codebases: {codebases}')
                    self.codebases = codebases
                    return True
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Failed to update codebases: {resp.status} {text}'
                    )
                    return False
        except Exception as e:
            logger.error(f'Error updating codebases: {e}')
            return False

    async def process_task(self, task: dict) -> str:
        """
        Process a received task.

        Override this method to implement your task processing logic.
        """
        task_id = task.get('id', 'unknown')
        title = task.get('title', 'Unknown')
        codebase_id = task.get('codebase_id', 'unknown')

        logger.info(
            f'Processing task: {title} (id={task_id}, codebase={codebase_id})'
        )

        # Simulate task processing
        await asyncio.sleep(2)

        # In a real implementation, you would:
        # 1. Run OpenCode or other agent on the task
        # 2. Capture the output/result
        # 3. Handle errors appropriately

        result = f"Task '{title}' completed at {datetime.now().isoformat()}"
        logger.info(f'Task {task_id} result: {result}')

        return result

    async def handle_task_available(self, task: dict) -> None:
        """Handle a task_available event from the SSE stream."""
        task_id = task.get('id', '')
        codebase_id = task.get('codebase_id', '')

        if not task_id:
            logger.warning('Received task without ID, ignoring')
            return

        # Check if this task is for one of our codebases
        if codebase_id and codebase_id not in self.codebases:
            if codebase_id not in ('global', '__pending__'):
                logger.debug(
                    f'Ignoring task {task_id} for codebase {codebase_id}'
                )
                return

        # Try to claim the task
        claimed = await self.claim_task(task_id)
        if not claimed:
            return  # Another worker got it

        # Process the task
        try:
            result = await self.process_task(task)
            await self.release_task(task_id, status='completed', result=result)
        except Exception as e:
            logger.error(f'Task {task_id} failed: {e}')
            await self.release_task(task_id, status='failed', error=str(e))

    async def connect_sse(self) -> None:
        """
        Connect to the SSE stream and process events.

        This is the main loop that receives push notifications from the server.
        """
        session = await self._get_session()
        url = f'{self.server_url}/v1/worker/tasks/stream'

        headers = self._get_headers()
        headers['Accept'] = 'text/event-stream'

        logger.info(f'Connecting to SSE stream: {url}')
        logger.info(f'Worker ID: {self.worker_id}')
        logger.info(f'Codebases: {self.codebases or "(all)"}')

        while self.running:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(
                            f'SSE connection failed: {resp.status} {text}'
                        )
                        await asyncio.sleep(5)
                        continue

                    logger.info('Connected to SSE stream')

                    # Read SSE events
                    event_type = None
                    data_lines = []

                    async for line in resp.content:
                        if not self.running:
                            break

                        line = line.decode('utf-8').rstrip('\r\n')

                        if line.startswith('event:'):
                            event_type = line[6:].strip()
                        elif line.startswith('data:'):
                            data_lines.append(line[5:].strip())
                        elif line == '':
                            # End of event
                            if data_lines:
                                data_str = '\n'.join(data_lines)
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    data = {'raw': data_str}

                                await self.handle_event(
                                    event_type or 'message', data
                                )

                            event_type = None
                            data_lines = []

            except aiohttp.ClientError as e:
                logger.error(f'SSE connection error: {e}')
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f'Unexpected error in SSE loop: {e}')
                await asyncio.sleep(5)

    async def handle_event(self, event_type: str, data: dict) -> None:
        """Handle an SSE event."""
        timestamp = datetime.now().isoformat()

        if event_type == 'connected':
            logger.info(f'[{timestamp}] Connected: {data.get("message", "")}')

        elif event_type == 'heartbeat':
            logger.debug(f'[{timestamp}] Heartbeat received')

        elif event_type == 'task_available':
            logger.info(
                f'[{timestamp}] Task available: {data.get("title", data.get("id", "?"))}'
            )
            # Process in background to not block the event loop
            asyncio.create_task(self.handle_task_available(data))

        elif event_type == 'task_claimed':
            logger.info(f'[{timestamp}] Task claimed confirmation: {data}')

        else:
            logger.debug(f"[{timestamp}] Event '{event_type}': {data}")

    async def start(self) -> None:
        """Start the SSE worker client."""
        self.running = True
        logger.info(
            f'Starting SSE worker: {self.worker_name} (id={self.worker_id})'
        )

        try:
            await self.connect_sse()
        finally:
            self.running = False
            if self.session:
                await self.session.close()

    async def stop(self) -> None:
        """Stop the SSE worker client."""
        self.running = False
        if self.session:
            await self.session.close()


async def main():
    parser = argparse.ArgumentParser(description='SSE Worker Client Example')
    parser.add_argument(
        '--server',
        '-s',
        default=os.environ.get('A2A_SERVER_URL', 'http://localhost:9000'),
        help='A2A server URL',
    )
    parser.add_argument(
        '--name',
        '-n',
        default=os.environ.get('A2A_WORKER_NAME', 'sse-worker'),
        help='Worker name',
    )
    parser.add_argument(
        '--worker-id',
        default=os.environ.get('A2A_WORKER_ID'),
        help='Stable worker ID',
    )
    parser.add_argument(
        '--codebase',
        '-b',
        action='append',
        default=[],
        help='Codebase ID this worker handles (can specify multiple)',
    )
    parser.add_argument(
        '--token',
        '-t',
        default=os.environ.get('A2A_AUTH_TOKEN'),
        help='Bearer auth token',
    )

    args = parser.parse_args()

    codebases = set(args.codebase) if args.codebase else {'global'}

    client = SSEWorkerClient(
        server_url=args.server,
        worker_name=args.name,
        worker_id=args.worker_id,
        codebases=codebases,
        auth_token=args.token,
    )

    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        await client.stop()


if __name__ == '__main__':
    asyncio.run(main())
