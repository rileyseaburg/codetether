#!/usr/bin/env python3
"""
A2A Agent Worker - Runs on machines with codebases, connects to A2A server

This worker:
1. Registers itself with the A2A server
2. Registers local codebases it can work on
3. Connects via SSE to receive task assignments pushed from server
4. Executes tasks using OpenCode
5. Reports results back to the server
6. Reports OpenCode session history to the server

Usage:
    python worker.py --server https://api.codetether.run --name "dev-vm-worker"
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Callable, Set

import aiohttp


# =============================================================================
# VaultClient - HashiCorp Vault integration for secrets
# =============================================================================


class VaultClient:
    """
    Simple Vault client for fetching secrets.

    Supports KV v2 secrets engine.
    """

    def __init__(
        self,
        addr: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.addr = addr or os.environ.get('VAULT_ADDR')
        self.token = token or os.environ.get('VAULT_TOKEN')
        self._session: Optional[aiohttp.ClientSession] = None

    def is_configured(self) -> bool:
        """Check if Vault is configured."""
        return bool(self.addr and self.token)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'X-Vault-Token': self.token or ''},
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get a secret from Vault KV v2.

        Args:
            path: Secret path (e.g., 'secret/spotlessbinco/sendgrid')

        Returns:
            Dictionary of secret data, or None if not found.
        """
        if not self.is_configured():
            return None

        try:
            session = await self._get_session()

            # KV v2 requires /data/ in the path
            # Convert 'secret/foo' to 'secret/data/foo'
            parts = path.split('/', 1)
            if len(parts) == 2:
                mount = parts[0]
                secret_path = parts[1]
                url = f'{self.addr}/v1/{mount}/data/{secret_path}'
            else:
                url = f'{self.addr}/v1/{path}'

            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('data', {}).get('data', {})
                else:
                    return None

        except Exception as e:
            logging.getLogger('a2a-worker').warning(
                f'Failed to fetch secret from Vault: {e}'
            )
            return None


class TaskStatus(StrEnum):
    """Status values for tasks in the task queue."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class SpecialCodebaseId(StrEnum):
    """Special codebase ID values with semantic meaning."""

    PENDING = '__pending__'  # Tasks awaiting codebase assignment
    GLOBAL = 'global'  # Global sessions not tied to a specific project


class AgentType(StrEnum):
    """Agent types that determine how tasks are executed."""

    BUILD = 'build'  # Default OpenCode build agent
    ECHO = 'echo'  # Lightweight test agent that echoes input
    NOOP = 'noop'  # Lightweight test agent that does nothing
    REGISTER_CODEBASE = (
        'register_codebase'  # Special task for codebase registration
    )


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger('a2a-worker')


@dataclass
class WorkerConfig:
    """Configuration for the agent worker."""

    server_url: str
    worker_name: str
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    codebases: List[Dict[str, str]] = field(default_factory=list)
    poll_interval: int = 5  # Fallback poll interval when SSE is unavailable
    opencode_bin: Optional[str] = None
    # Optional override for OpenCode storage location (directory that contains
    # subdirs like project/, session/, message/, part/).
    opencode_storage_path: Optional[str] = None
    # Optional message sync (for session detail view on remote codebases)
    session_message_sync_max_sessions: int = 3
    session_message_sync_max_messages: int = 100
    capabilities: List[str] = field(
        default_factory=lambda: ['opencode', 'build', 'deploy']
    )
    # Max concurrent tasks (bounded worker pool)
    max_concurrent_tasks: int = 2
    # SSE reconnection settings
    sse_reconnect_delay: float = 1.0
    sse_max_reconnect_delay: float = 60.0
    sse_heartbeat_timeout: float = (
        45.0  # Server should send heartbeats every 30s
    )
    # Auth token for SSE endpoint (from A2A_AUTH_TOKEN env var)
    auth_token: Optional[str] = None
    # Email notifications via SendGrid
    sendgrid_api_key: Optional[str] = None
    sendgrid_from_email: Optional[str] = None
    notification_email: Optional[str] = None  # Recipient for task reports
    # Email reply-to configuration for task continuation
    email_inbound_domain: Optional[str] = None  # e.g., 'inbound.codetether.run'
    email_reply_prefix: str = 'task'  # Prefix for reply-to addresses
    # Email debugging options
    email_dry_run: bool = False  # Log emails instead of sending
    email_verbose: bool = False  # Verbose logging for email operations
    # Auto-compaction settings for task handoffs
    compaction_max_tokens: int = 100000  # Trigger compaction above this
    compaction_target_tokens: int = 50000  # Target size after compaction
    auto_summarize_handoffs: bool = (
        True  # Enable auto-summarization for session resumes
    )
    # Agent registration: Register worker as a discoverable agent in the A2A network
    # This allows other agents to find this worker via discover_agents MCP tool
    register_as_agent: bool = True  # Auto-register as discoverable agent
    agent_name: Optional[str] = (
        None  # Name for agent discovery (defaults to worker_name)
    )
    agent_description: Optional[str] = None  # Description for agent discovery
    agent_url: Optional[str] = (
        None  # URL where this agent can be reached (optional)
    )
    # Instance ID for unique agent identity (role:instance pattern)
    # If not set, generated as hostname:short_uuid
    agent_instance_id: Optional[str] = None
    agent_description: Optional[str] = None  # Description for agent discovery
    agent_url: Optional[str] = (
        None  # URL where this agent can be reached (optional)
    )


@dataclass
class LocalCodebase:
    """A codebase registered with this worker."""

    id: str  # Server-assigned ID
    name: str
    path: str
    description: str = ''


# =============================================================================
# WorkerClient - HTTP/SSE communication with the A2A server
# =============================================================================


class WorkerClient:
    """
    Handles HTTP and SSE communication with the A2A server.

    Responsibilities:
    - Manage aiohttp session lifecycle and connection pooling
    - SSE connection establishment and event handling
    - API calls for task status updates, output streaming
    - Worker registration/unregistration and heartbeat management
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # SSE connection state
        self._sse_connected = False
        self._sse_reconnect_delay = config.sse_reconnect_delay
        self._last_heartbeat: float = 0.0

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling."""
        if self.session is None or self.session.closed:
            # Configure connection pool for better performance under load
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=30,  # Max connections per host
                ttl_dns_cache=300,  # DNS cache TTL in seconds
                enable_cleanup_closed=True,  # Clean up closed connections
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'Content-Type': 'application/json'},
            )
        return self.session

    async def close(self):
        """Close the HTTP session."""
        if self.session is not None and not self.session.closed:
            await self.session.close()
            # Wait for underlying connector to close
            await asyncio.sleep(0.1)

    async def register_worker(
        self,
        models: List[Dict[str, Any]],
        global_codebase_id: Optional[str],
    ) -> bool:
        """Register this worker with the A2A server."""
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/workers/register'

            import platform

            payload = {
                'worker_id': self.config.worker_id,
                'name': self.config.worker_name,
                'capabilities': self.config.capabilities,
                'hostname': platform.node(),  # Cross-platform (works on Windows)
                'models': models,
                'global_codebase_id': global_codebase_id,
            }

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f'Worker registered successfully: {data}')
                    return True
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Worker registration returned {resp.status}: {text}'
                    )
                    return False

        except Exception as e:
            logger.warning(
                f'Failed to register worker (continuing anyway): {e}'
            )
            return False

    async def unregister_worker(self):
        """Unregister this worker from the A2A server."""
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/workers/{self.config.worker_id}/unregister'

            async with session.post(url) as resp:
                if resp.status == 200:
                    logger.info('Worker unregistered successfully')

        except Exception as e:
            logger.debug(f'Failed to unregister worker: {e}')

    async def send_heartbeat(self) -> bool:
        """Send heartbeat to the A2A server to indicate worker is alive.

        Returns True if heartbeat was successful, False otherwise.
        """
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/workers/{self.config.worker_id}/heartbeat'

            async with session.post(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.debug('Heartbeat sent successfully')
                    return True
                else:
                    logger.warning(f'Heartbeat returned {resp.status}')
                    return False

        except Exception as e:
            logger.debug(f'Failed to send heartbeat: {e}')
            return False

    async def register_as_agent(
        self,
        agent_name: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        routing_capabilities: Optional[List[str]] = None,
    ) -> bool:
        """
        Register this worker as a discoverable agent in the A2A network.

        This makes the worker visible to other agents via the discover_agents
        MCP tool, enabling agent-to-agent communication.

        Uses the role:instance pattern for unique identity:
        - role (agent_name): stable role like "code-reviewer" for routing
        - instance_id: unique per-worker instance for disambiguation

        The full discovery name is "{role}:{instance_id}" to handle multiple
        workers with the same role. Routing (send_to_agent) uses the role.

        Args:
            agent_name: Name for agent discovery (defaults to config.agent_name or worker_name)
            description: Human-readable description of what this agent does
            url: Optional URL where this agent can be reached directly
            routing_capabilities: List of task routing capabilities (e.g., ["pytest", "terraform"])

        Returns:
            True if registration succeeded, False otherwise.
        """
        import platform

        try:
            session = await self.get_session()
            # Use the proper MCP JSON-RPC endpoint
            url_endpoint = f'{self.config.server_url}/mcp/v1/rpc'

            # Use platform.node() for cross-platform hostname (works on Windows too)
            hostname = platform.node()

            # Build instance_id for unique identity
            # Format: hostname:short_uuid (e.g., "dev-vm:a1b2c3")
            instance_id = (
                self.config.agent_instance_id
                or f'{hostname}:{self.config.worker_id[:6]}'
            )

            # Role is the routing identity (used by send_to_agent)
            role = (
                agent_name or self.config.agent_name or self.config.worker_name
            )

            # Full discovery name is role:instance for uniqueness
            # This prevents registry collisions when multiple workers have the same role
            discovery_name = f'{role}:{instance_id}'

            # Store the resolved names for heartbeat refresh
            self._agent_role = role
            self._agent_discovery_name = discovery_name

            # Build routing capabilities list for task matching
            caps_list = routing_capabilities or self.config.capabilities or []
            caps_str = ', '.join(caps_list) if caps_list else 'general'

            agent_description = description or (
                f'OpenCode worker agent (role={role}, instance={instance_id}). '
                f'Routing capabilities: {caps_str}'
            )
            agent_url = url or self.config.agent_url or self.config.server_url

            # JSON-RPC 2.0 request to call register_agent tool
            # Note: 'capabilities' here is the A2A protocol AgentCapabilities (dict)
            # for streaming/push_notifications - NOT the routing capabilities (list)
            payload = {
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': 'tools/call',
                'params': {
                    'name': 'register_agent',
                    'arguments': {
                        'name': discovery_name,
                        'description': agent_description,
                        'url': agent_url,
                        # A2A protocol capabilities (dict) - for streaming/push features
                        'capabilities': {
                            'streaming': True,
                            'push_notifications': True,
                        },
                    },
                },
            }

            headers = {'Content-Type': 'application/json'}
            if self.config.auth_token:
                headers['Authorization'] = f'Bearer {self.config.auth_token}'

            async with session.post(
                url_endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(
                    total=10
                ),  # Best-effort, don't block startup
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get('error'):
                        logger.warning(
                            f'Agent registration failed: {result["error"]}'
                        )
                        return False
                    logger.info(
                        f"Registered as discoverable agent: '{discovery_name}' (role='{role}')"
                    )
                    return True
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Agent registration returned {resp.status}: {text}'
                    )
                    return False

        except asyncio.TimeoutError:
            logger.warning(
                'Agent registration timed out (continuing without discovery registration)'
            )
            return False
        except Exception as e:
            logger.warning(f'Failed to register as agent (non-fatal): {e}')
            return False

    async def refresh_agent_heartbeat(self) -> bool:
        """
        Refresh the agent's last_seen timestamp to keep it visible in discovery.

        Should be called periodically (every 30-60s). Agents not seen within
        120s are filtered from discover_agents results.

        Returns:
            True if heartbeat was refreshed, False otherwise.
        """
        if (
            not hasattr(self, '_agent_discovery_name')
            or not self._agent_discovery_name
        ):
            return False  # Not registered as agent

        try:
            session = await self.get_session()
            url_endpoint = f'{self.config.server_url}/mcp/v1/rpc'

            payload = {
                'jsonrpc': '2.0',
                'id': str(uuid.uuid4()),
                'method': 'tools/call',
                'params': {
                    'name': 'refresh_agent_heartbeat',
                    'arguments': {
                        'agent_name': self._agent_discovery_name,
                    },
                },
            }

            headers = {'Content-Type': 'application/json'}
            if self.config.auth_token:
                headers['Authorization'] = f'Bearer {self.config.auth_token}'

            async with session.post(
                url_endpoint,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get('error'):
                        logger.debug(
                            f'Agent heartbeat failed: {result["error"]}'
                        )
                        return False
                    logger.debug(
                        f'Agent heartbeat refreshed: {self._agent_discovery_name}'
                    )
                    return True
                return False

        except Exception as e:
            logger.debug(f'Agent heartbeat error: {e}')
            return False

    async def unregister_agent(self) -> bool:
        """
        Unregister this worker from the agent discovery registry.

        Called during graceful shutdown.

        Returns:
            True if unregistration succeeded, False otherwise.
        """
        # Note: There's no explicit unregister_agent MCP tool currently,
        # but the agent will be marked inactive when heartbeats stop (TTL).
        agent_name = (
            getattr(self, '_agent_discovery_name', None)
            or self.config.agent_name
            or self.config.worker_name
        )
        logger.debug(
            f"Agent '{agent_name}' will be filtered from discovery after TTL expires"
        )
        return True

    async def register_codebase(
        self, name: str, path: str, description: str = ''
    ) -> Optional[str]:
        """Register a local codebase with the A2A server.

        Returns the server-assigned codebase ID, or None on failure.
        """
        # Validate path exists locally
        if not os.path.isdir(path):
            logger.error(f'Codebase path does not exist: {path}')
            return None

        # Normalize for comparisons / de-duping when re-registering.
        normalized_path = os.path.abspath(os.path.expanduser(path))

        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/codebases'

            payload = {
                'name': name,
                'path': normalized_path,
                'description': description,
                'worker_id': self.config.worker_id,  # Associate with this worker
            }

            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    codebase_data = data.get('codebase', data)
                    codebase_id = codebase_data.get('id')

                    logger.info(
                        f"Registered codebase '{name}' (ID: {codebase_id}) at {path}"
                    )
                    return codebase_id
                else:
                    text = await resp.text()
                    logger.error(
                        f'Failed to register codebase: {resp.status} - {text}'
                    )
                    return None

        except Exception as e:
            logger.error(f'Failed to register codebase: {e}')
            return None

    async def get_pending_tasks(
        self, codebase_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get pending tasks from the server (fallback polling method)."""
        try:
            session = await self.get_session()

            url = f'{self.config.server_url}/v1/opencode/tasks'
            params = {
                'status': TaskStatus.PENDING,
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    tasks = await resp.json()
                    return tasks
                else:
                    return []

        except Exception as e:
            logger.debug(f'Failed to get pending tasks: {e}')
            return []

    async def claim_task(self, task_id: str) -> bool:
        """
        Atomically claim a task on the server.

        Returns True if claim succeeded, False if task was already claimed
        by another worker.
        """
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/worker/tasks/claim'

            # Build headers including auth token if available
            headers = {'Content-Type': 'application/json'}
            if self.config.auth_token:
                headers['Authorization'] = f'Bearer {self.config.auth_token}'
            headers['X-Worker-ID'] = self.config.worker_id

            payload = {'task_id': task_id}

            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    logger.info(f'Successfully claimed task {task_id}')
                    return True
                elif resp.status == 409:
                    # Task already claimed by another worker
                    logger.debug(
                        f'Task {task_id} already claimed by another worker'
                    )
                    return False
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Failed to claim task {task_id}: {resp.status} - {text}'
                    )
                    # On unexpected errors, don't process to be safe
                    return False

        except Exception as e:
            logger.warning(f'Error claiming task {task_id}: {e}')
            # On network errors, don't process to avoid potential duplicates
            return False

    async def release_task(self, task_id: str) -> bool:
        """
        Release a task claim on the server after processing.

        This notifies the server that the worker is done with the task
        (whether successful or failed).
        """
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/worker/tasks/release'

            # Build headers including auth token if available
            headers = {'Content-Type': 'application/json'}
            if self.config.auth_token:
                headers['Authorization'] = f'Bearer {self.config.auth_token}'
            headers['X-Worker-ID'] = self.config.worker_id

            payload = {'task_id': task_id}

            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    logger.debug(f'Released task {task_id}')
                    return True
                else:
                    text = await resp.text()
                    logger.debug(
                        f'Failed to release task {task_id}: {resp.status} - {text}'
                    )
                    return False

        except Exception as e:
            logger.debug(f'Error releasing task {task_id}: {e}')
            return False

    async def stream_task_output(self, task_id: str, output: str):
        """Stream output chunk to the server."""
        if not output:
            return
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/tasks/{task_id}/output'

            payload = {
                'worker_id': self.config.worker_id,
                'output': output,
                'timestamp': datetime.now().isoformat(),
            }

            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    logger.debug(f'Failed to stream output: {resp.status}')
        except Exception as e:
            logger.debug(f'Failed to stream output: {e}')

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        max_retries: int = 4,
        base_delay: float = 1.0,
    ):
        """Update task status on the server with exponential backoff retry.

        Status updates are critical for maintaining consistency between worker
        and server state. This method retries failed updates with exponential
        backoff to handle transient network issues.

        The operation is idempotent - multiple updates to the same status are
        safe as the server will simply acknowledge the current state.

        Args:
            task_id: The task ID to update
            status: New status value
            result: Optional result data
            error: Optional error message
            session_id: Optional session ID
            max_retries: Maximum number of retry attempts (default: 4, total 5 attempts)
            base_delay: Initial delay in seconds before first retry (default: 1.0)
        """
        url = f'{self.config.server_url}/v1/opencode/tasks/{task_id}/status'

        payload = {
            'status': status,
            'worker_id': self.config.worker_id,
        }
        if session_id:
            payload['session_id'] = session_id
        if result:
            payload['result'] = result
        if error:
            payload['error'] = error

        last_exception: Optional[Exception] = None
        last_status_code: Optional[int] = None
        last_response_text: Optional[str] = None

        for attempt in range(max_retries + 1):
            try:
                session = await self.get_session()
                async with session.put(url, json=payload) as resp:
                    if resp.status == 200:
                        if attempt > 0:
                            logger.info(
                                f'Task {task_id} status update to "{status}" succeeded on retry {attempt}'
                            )
                        return  # Success

                    last_status_code = resp.status
                    last_response_text = await resp.text()

                    # Don't retry client errors (4xx) except 429 (rate limit)
                    if 400 <= resp.status < 500 and resp.status != 429:
                        logger.warning(
                            f'Task {task_id} status update failed with client error: '
                            f'{resp.status} - {last_response_text}'
                        )
                        return  # Don't retry client errors

            except asyncio.CancelledError:
                raise  # Don't retry on cancellation
            except Exception as e:
                last_exception = e

            # Calculate delay with exponential backoff (1s, 2s, 4s, 8s)
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f'Task {task_id} status update to "{status}" failed '
                    f'(attempt {attempt + 1}/{max_retries + 1}), '
                    f'retrying in {delay:.1f}s...'
                )
                await asyncio.sleep(delay)

        # All retries exhausted - log the final failure
        if last_exception:
            logger.error(
                f'Task {task_id} status update to "{status}" failed after '
                f'{max_retries + 1} attempts. Last error: {last_exception}'
            )
        elif last_status_code:
            logger.error(
                f'Task {task_id} status update to "{status}" failed after '
                f'{max_retries + 1} attempts. Last response: {last_status_code} - '
                f'{last_response_text}'
            )

    async def sync_api_keys_from_server(
        self, user_id: Optional[str] = None
    ) -> bool:
        """
        Sync API keys from the server (Vault-backed) to local OpenCode auth.json.

        This allows users to manage their API keys in the web UI and have them
        automatically synced to workers.

        Args:
            user_id: Optional user ID to sync keys for. If not provided,
                     syncs keys for the codebase owner.

        Returns:
            True if sync was successful, False otherwise.
        """
        try:
            session = await self.get_session()

            # Build sync URL with optional user_id
            sync_url = f'{self.config.server_url}/v1/opencode/api-keys/sync'
            params = {'worker_id': self.config.worker_id}
            if user_id:
                params['user_id'] = user_id

            async with session.get(sync_url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(
                        f'Failed to sync API keys: HTTP {resp.status}'
                    )
                    return False

                data = await resp.json()

            # Get paths for auth.json and opencode.json
            data_home = os.environ.get('XDG_DATA_HOME') or os.path.expanduser(
                '~/.local/share'
            )
            config_home = os.environ.get(
                'XDG_CONFIG_HOME'
            ) or os.path.expanduser('~/.config')

            auth_path = Path(data_home) / 'opencode' / 'auth.json'
            config_path = Path(config_home) / 'opencode' / 'opencode.json'

            # Merge server keys with existing local auth.json
            server_auth = data.get('auth', {})
            if server_auth:
                existing_auth = {}
                if auth_path.exists():
                    try:
                        with open(auth_path, 'r', encoding='utf-8') as f:
                            existing_auth = json.load(f)
                    except Exception as e:
                        logger.warning(
                            f'Failed to read existing auth.json: {e}'
                        )

                # Merge: server keys override local for same provider
                merged_auth = {**existing_auth, **server_auth}

                # Write merged auth
                auth_path.parent.mkdir(parents=True, exist_ok=True)
                with open(auth_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_auth, f, indent=2)

                logger.info(
                    f'Synced {len(server_auth)} API keys from server '
                    f'(total: {len(merged_auth)} providers)'
                )

            # Merge server provider configs with existing opencode.json
            server_providers = data.get('providers', {})
            if server_providers:
                existing_config = {}
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            existing_config = json.load(f)
                    except Exception as e:
                        logger.warning(
                            f'Failed to read existing opencode.json: {e}'
                        )

                # Merge provider configs
                existing_providers = existing_config.get('provider', {})
                merged_providers = {**existing_providers, **server_providers}
                existing_config['provider'] = merged_providers

                # Write merged config
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_config, f, indent=2)

                logger.info(
                    f'Synced {len(server_providers)} provider configs from server'
                )

            return True

        except Exception as e:
            logger.error(f'Failed to sync API keys from server: {e}')
            return False

    async def sync_sessions(
        self,
        codebase_id: str,
        sessions: List[Dict[str, Any]],
    ) -> int:
        """Sync sessions to the server for a codebase.

        Returns the HTTP status code.
        """
        try:
            session = await self.get_session()
            url = f'{self.config.server_url}/v1/opencode/codebases/{codebase_id}/sessions/sync'
            payload = {
                'worker_id': self.config.worker_id,
                'sessions': sessions,
            }
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.debug(
                        f'Synced {len(sessions)} sessions (codebase_id={codebase_id})'
                    )
                else:
                    text = await resp.text()
                    logger.warning(
                        f'Session sync failed for codebase_id={codebase_id}: {resp.status} {text[:200]}'
                    )
                return resp.status
        except Exception as e:
            logger.debug(f'Failed to sync sessions: {e}')
            return 0

    async def sync_session_messages(
        self,
        codebase_id: str,
        session_id: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """Sync messages for a single session. Returns True on HTTP 200."""
        try:
            if not messages:
                return False

            session = await self.get_session()
            url = (
                f'{self.config.server_url}/v1/opencode/codebases/{codebase_id}'
                f'/sessions/{session_id}/messages/sync'
            )
            payload = {
                'worker_id': self.config.worker_id,
                'messages': messages,
            }
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.debug(
                        f'Synced {len(messages)} messages for session {session_id}'
                    )
                    return True
                else:
                    text = await resp.text()
                    logger.debug(f'Message sync returned {resp.status}: {text}')
                    return False
        except Exception as e:
            logger.debug(f'Message sync failed for session {session_id}: {e}')
            return False

    @property
    def sse_connected(self) -> bool:
        return self._sse_connected

    @sse_connected.setter
    def sse_connected(self, value: bool):
        self._sse_connected = value

    @property
    def sse_reconnect_delay(self) -> float:
        return self._sse_reconnect_delay

    @sse_reconnect_delay.setter
    def sse_reconnect_delay(self, value: float):
        self._sse_reconnect_delay = value

    @property
    def last_heartbeat(self) -> float:
        return self._last_heartbeat

    @last_heartbeat.setter
    def last_heartbeat(self, value: float):
        self._last_heartbeat = value


# =============================================================================
# EmailNotificationService - SendGrid email notifications
# =============================================================================


def _sanitize_email_for_log(email: str) -> str:
    """
    Sanitize email address for logging (mask local part).

    Security: Prevents sensitive email addresses from appearing in logs.

    Args:
        email: Full email address

    Returns:
        Sanitized email (e.g., 'r***y@example.com')
    """
    if not email or '@' not in email:
        return '***@***'
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        return f'***@{domain}'
    return f'{local[0]}***{local[-1]}@{domain}'


class EmailNotificationService:
    """
    Handles email notifications via SendGrid.

    Sends task completion/failure reports to configured recipients.

    Supports dry-run mode for testing (logs instead of sends) and
    verbose logging for debugging email operations.
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._dry_run = config.email_dry_run
        self._verbose = config.email_verbose

    def is_configured(self) -> bool:
        """Check if email notifications are properly configured."""
        return bool(
            self.config.sendgrid_api_key
            and self.config.sendgrid_from_email
            and self.config.notification_email
        )

    def get_config_status(self) -> Dict[str, Any]:
        """
        Get email configuration status for debugging.

        Returns dict with configuration details and any issues.
        """
        issues = []

        if not self.config.sendgrid_api_key:
            issues.append('SENDGRID_API_KEY not set')
        elif not self.config.sendgrid_api_key.startswith('SG.'):
            issues.append(
                'SENDGRID_API_KEY does not appear valid (should start with SG.)'
            )

        if not self.config.sendgrid_from_email:
            issues.append('SENDGRID_FROM_EMAIL not set')
        elif '@' not in self.config.sendgrid_from_email:
            issues.append(
                'SENDGRID_FROM_EMAIL does not appear to be a valid email'
            )

        if not self.config.notification_email:
            issues.append('notification_email not set')

        return {
            'configured': self.is_configured(),
            'dry_run': self._dry_run,
            'verbose': self._verbose,
            'sendgrid_api_key_set': bool(self.config.sendgrid_api_key),
            'sendgrid_from_email': _sanitize_email_for_log(
                self.config.sendgrid_from_email or ''
            ),
            'notification_email': _sanitize_email_for_log(
                self.config.notification_email or ''
            ),
            'inbound_domain': self.config.email_inbound_domain,
            'reply_prefix': self.config.email_reply_prefix,
            'issues': issues,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for SendGrid API."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_reply_to_address(
        self,
        session_id: Optional[str],
        codebase_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Build the reply-to address for email replies to continue tasks.

        Format: {prefix}+{session_id}@{domain}
        Or: {prefix}+{session_id}+{codebase_id}@{domain}
        """
        if not session_id:
            return None
        if not self.config.email_inbound_domain:
            return None

        prefix = self.config.email_reply_prefix or 'task'
        domain = self.config.email_inbound_domain

        if codebase_id:
            return f'{prefix}+{session_id}+{codebase_id}@{domain}'
        return f'{prefix}+{session_id}@{domain}'

    async def send_task_report(
        self,
        task_id: str,
        title: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        session_id: Optional[str] = None,
        codebase_id: Optional[str] = None,
    ) -> bool:
        """Send a task completion/failure email report.

        Returns True if email was sent successfully (or logged in dry-run mode).

        In dry-run mode (--email-dry-run), emails are logged instead of sent.
        In verbose mode (--email-verbose), additional debugging info is logged.
        """
        if self._verbose:
            logger.info(
                f'[EMAIL-DEBUG] send_task_report called: task_id={task_id}, '
                f'status={status}, session_id={session_id}'
            )

        if not self.is_configured():
            if self._verbose:
                config_status = self.get_config_status()
                logger.info(
                    f'[EMAIL-DEBUG] Not configured: {config_status["issues"]}'
                )
            else:
                logger.debug('Email notifications not configured, skipping')
            return False

        try:
            session = await self._get_session()

            # Format duration
            duration_str = 'N/A'
            if duration_ms:
                seconds = duration_ms // 1000
                minutes = seconds // 60
                if minutes > 0:
                    duration_str = f'{minutes}m {seconds % 60}s'
                else:
                    duration_str = f'{seconds}s'

            # Build email content
            status_color = '#22c55e' if status == 'completed' else '#ef4444'
            status_icon = '✓' if status == 'completed' else '✗'

            result_section = ''
            if result and status == 'completed':
                # Try to parse and extract meaningful content
                display_result = result
                import json as json_module
                import html as html_module

                # Handle NDJSON (newline-delimited JSON) from OpenCode streaming
                # Extract text content from streaming events
                text_parts = []
                try:
                    lines = result.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parsed = json_module.loads(line)
                            # OpenCode streaming format: look for text events
                            if isinstance(parsed, dict):
                                event_type = parsed.get('type', '')
                                part = parsed.get('part', {})

                                # Extract text from "text" type events
                                if event_type == 'text' and isinstance(
                                    part, dict
                                ):
                                    text = part.get('text', '')
                                    if text:
                                        text_parts.append(text)
                                # Also check for direct text field
                                elif 'text' in parsed and isinstance(
                                    parsed['text'], str
                                ):
                                    text_parts.append(parsed['text'])
                                # Check for result/output/message fields
                                elif 'result' in parsed:
                                    text_parts.append(str(parsed['result']))
                                elif 'output' in parsed:
                                    text_parts.append(str(parsed['output']))
                                elif 'message' in parsed and isinstance(
                                    parsed['message'], str
                                ):
                                    text_parts.append(parsed['message'])
                        except json_module.JSONDecodeError:
                            # Not JSON, might be plain text
                            if line and not line.startswith('{'):
                                text_parts.append(line)

                    if text_parts:
                        # Join all extracted text
                        display_result = ' '.join(text_parts)
                    else:
                        # Fallback: try parsing as single JSON
                        try:
                            parsed = json_module.loads(result)
                            if isinstance(parsed, dict):
                                for key in [
                                    'result',
                                    'output',
                                    'message',
                                    'content',
                                    'response',
                                    'text',
                                ]:
                                    if key in parsed:
                                        display_result = str(parsed[key])
                                        break
                        except json_module.JSONDecodeError:
                            pass

                except Exception:
                    # If all parsing fails, use as-is
                    pass

                # Escape HTML for safety
                display_result = html_module.escape(display_result)

                # Convert newlines to <br> for display
                display_result = display_result.replace('\n', '<br>')

                truncated = (
                    display_result[:3000] + '...'
                    if len(display_result) > 3000
                    else display_result
                )
                result_section = f"""
                <tr>
                  <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px; vertical-align: top;">Output</td>
                  <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <div style="font-size: 14px; line-height: 1.6; color: #1f2937;">{truncated}</div>
                  </td>
                </tr>"""

            error_section = ''
            if error:
                truncated = error[:1000] + '...' if len(error) > 1000 else error
                error_section = f"""
                <tr>
                  <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Error</td>
                  <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #fef2f2; padding: 12px; border-radius: 6px; color: #dc2626;">{truncated}</pre>
                  </td>
                </tr>"""

            # Build footer with reply instructions if email reply is configured
            reply_enabled = bool(
                self.config.email_inbound_domain and session_id
            )
            if reply_enabled:
                footer_html = f"""
    <div style="background: #f9fafb; padding: 16px; text-align: center;">
      <p style="margin: 0 0 8px 0; font-size: 13px; color: #374151; font-weight: 500;">
        Reply to this email to continue the conversation
      </p>
      <p style="margin: 0; font-size: 12px; color: #6b7280;">
        Your reply will be sent to the worker to continue working on this task.
      </p>
      <p style="margin: 8px 0 0 0; font-size: 11px; color: #9ca3af;">
        Sent by A2A Worker - {self.config.worker_name}
      </p>
    </div>"""
            else:
                footer_html = f"""
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Sent by A2A Worker - {self.config.worker_name}
    </div>"""

            html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">A2A Task Report</h1>
    </div>
    <div style="padding: 24px;">
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: {status_color}20; color: {status_color}; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        {status_icon} {status.upper()}
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">{task_id}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Title</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{title}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Session ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">{session_id or 'N/A'}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Worker</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{self.config.worker_name}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Duration</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{duration_str}</td>
        </tr>
        {result_section}
        {error_section}
      </table>
    </div>
    {footer_html}
  </div>
</body>
</html>"""

            subject = f'[A2A] Task {status}: {title}'

            payload = {
                'personalizations': [
                    {'to': [{'email': self.config.notification_email}]}
                ],
                'from': {'email': self.config.sendgrid_from_email},
                'subject': subject,
                'content': [{'type': 'text/html', 'value': html}],
            }

            # Add reply-to address if configured for email reply continuation
            reply_to = self._build_reply_to_address(session_id, codebase_id)
            if reply_to:
                payload['reply_to'] = {'email': reply_to}
                if self._verbose:
                    logger.info(f'[EMAIL-DEBUG] Reply-to set to: {reply_to}')
                else:
                    logger.debug(f'Email reply-to set to: {reply_to}')

            # Verbose logging of email details (with sanitized addresses)
            if self._verbose:
                logger.info(
                    f'[EMAIL-DEBUG] Email payload: subject="{subject}", '
                    f'from={_sanitize_email_for_log(self.config.sendgrid_from_email or "")}, '
                    f'to={_sanitize_email_for_log(self.config.notification_email or "")}, '
                    f'reply_to={reply_to or "none"}'
                )

            # Dry-run mode: log instead of sending
            if self._dry_run:
                logger.info(
                    f'[EMAIL-DRY-RUN] Would send email for task {task_id}:\n'
                    f'  Subject: {subject}\n'
                    f'  To: {_sanitize_email_for_log(self.config.notification_email or "")}\n'
                    f'  From: {_sanitize_email_for_log(self.config.sendgrid_from_email or "")}\n'
                    f'  Reply-To: {reply_to or "none"}\n'
                    f'  Status: {status}'
                )
                return True  # Return success in dry-run mode

            headers = {
                'Authorization': f'Bearer {self.config.sendgrid_api_key}',
                'Content-Type': 'application/json',
            }

            if self._verbose:
                logger.info('[EMAIL-DEBUG] Sending to SendGrid API...')

            async with session.post(
                'https://api.sendgrid.com/v3/mail/send',
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status in (200, 202):
                    logger.info(
                        f'Email report sent for task {task_id} to '
                        f'{_sanitize_email_for_log(self.config.notification_email or "")}'
                    )
                    return True
                else:
                    text = await resp.text()
                    logger.error(
                        f'Failed to send email: {resp.status} - {text}'
                    )
                    if self._verbose:
                        logger.error(f'[EMAIL-DEBUG] SendGrid response: {text}')
                    return False

        except Exception as e:
            logger.error(f'Failed to send email notification: {e}')
            if self._verbose:
                import traceback

                logger.error(
                    f'[EMAIL-DEBUG] Traceback: {traceback.format_exc()}'
                )
            return False

    async def send_test_email(self) -> Dict[str, Any]:
        """
        Send a test email to validate email configuration.

        This sends a simple test email to verify SendGrid is properly configured.
        Returns a dict with success status and any errors.

        Used by the --test-email CLI flag.
        """
        result: Dict[str, Any] = {
            'success': False,
            'configured': self.is_configured(),
            'config_status': self.get_config_status(),
            'dry_run': self._dry_run,
            'message': '',
        }

        if not self.is_configured():
            result['message'] = (
                'Email not fully configured. Issues: '
                + ', '.join(result['config_status']['issues'])
            )
            return result

        # Generate a test task ID
        test_task_id = f'test-{uuid.uuid4().hex[:8]}'
        test_session_id = f'ses_test_{uuid.uuid4().hex[:8]}'

        logger.info(f'Sending test email (dry_run={self._dry_run})...')
        logger.info(
            f'  To: {_sanitize_email_for_log(self.config.notification_email or "")}'
        )
        logger.info(
            f'  From: {_sanitize_email_for_log(self.config.sendgrid_from_email or "")}'
        )

        try:
            success = await self.send_task_report(
                task_id=test_task_id,
                title='Test Email from A2A Worker',
                status='completed',
                result='This is a test email to verify your email notification configuration is working correctly.',
                duration_ms=1234,
                session_id=test_session_id,
            )

            if success:
                result['success'] = True
                if self._dry_run:
                    result['message'] = (
                        'Test email logged successfully (dry-run mode - no email sent)'
                    )
                else:
                    result['message'] = (
                        f'Test email sent successfully to {_sanitize_email_for_log(self.config.notification_email or "")}'
                    )
            else:
                result['message'] = (
                    'Failed to send test email - check logs for details'
                )

        except Exception as e:
            result['message'] = f'Exception while sending test email: {e}'
            logger.error(f'Test email failed: {e}')

        return result


# =============================================================================
# ConfigManager - Configuration and setup
# =============================================================================


class ConfigManager:
    """
    Handles configuration and setup for the worker.

    Responsibilities:
    - Finding OpenCode binary
    - Managing storage paths
    - Provider authentication discovery
    - Model discovery
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        self._opencode_storage_path: Optional[Path] = None

    def find_opencode_binary(self) -> str:
        """Find the opencode binary."""
        locations = [
            str(Path.home() / '.local' / 'bin' / 'opencode'),
            str(Path.home() / 'bin' / 'opencode'),
            '/usr/local/bin/opencode',
            '/usr/bin/opencode',
            # Check in the A2A project
            str(
                Path(__file__).parent.parent
                / 'opencode'
                / 'packages'
                / 'opencode'
                / 'bin'
                / 'opencode'
            ),
        ]

        for loc in locations:
            if Path(loc).exists() and os.access(loc, os.X_OK):
                logger.info(f'Found opencode at: {loc}')
                return loc

        # Try PATH
        try:
            result = subprocess.run(
                ['which', 'opencode'], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f'Binary search via PATH failed: {e}')

        logger.warning('OpenCode binary not found, some features may not work')
        return 'opencode'

    def get_authenticated_providers(self) -> set:
        """Get set of provider IDs that have authentication configured."""
        authenticated = set()
        try:
            data_home = os.environ.get('XDG_DATA_HOME') or os.path.expanduser(
                '~/.local/share'
            )
            auth_path = (
                Path(os.path.expanduser(data_home)) / 'opencode' / 'auth.json'
            )
            if auth_path.exists():
                with open(auth_path, 'r', encoding='utf-8') as f:
                    auth_data = json.load(f)
                for provider_id, provider_auth in auth_data.items():
                    if isinstance(provider_auth, dict):
                        # Check if provider has valid auth (key or oauth tokens)
                        has_key = bool(provider_auth.get('key'))
                        has_oauth = bool(
                            provider_auth.get('access')
                            or provider_auth.get('refresh')
                        )
                        if has_key or has_oauth:
                            authenticated.add(provider_id)
                            logger.debug(
                                f"Provider '{provider_id}' has authentication configured"
                            )
                logger.info(
                    f'Found {len(authenticated)} authenticated providers: {sorted(authenticated)}'
                )
        except Exception as e:
            logger.warning(f'Failed to read OpenCode auth.json: {e}')
        return authenticated

    async def get_available_models(
        self, opencode_bin: str
    ) -> List[Dict[str, Any]]:
        """Fetch available models from local OpenCode instance.

        Only returns models from providers that have authentication configured.
        """
        # Get authenticated providers first
        authenticated_providers = self.get_authenticated_providers()
        if not authenticated_providers:
            logger.warning(
                'No authenticated providers found - no models will be registered'
            )
            return []

        all_models = []

        # Try default port first
        port = 9777
        try:
            url = f'http://localhost:{port}/provider'
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=2)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        all_providers = data.get('all', [])
                        for provider in all_providers:
                            provider_id = provider.get('id')
                            provider_name = provider.get('name', provider_id)
                            for model_id, model_info in provider.get(
                                'models', {}
                            ).items():
                                all_models.append(
                                    {
                                        'id': f'{provider_id}/{model_id}',
                                        'name': model_info.get(
                                            'name', model_id
                                        ),
                                        'provider': provider_name,
                                        'provider_id': provider_id,
                                        'capabilities': {
                                            'reasoning': model_info.get(
                                                'reasoning', False
                                            ),
                                            'attachment': model_info.get(
                                                'attachment', False
                                            ),
                                            'tool_call': model_info.get(
                                                'tool_call', False
                                            ),
                                        },
                                    }
                                )
        except Exception as e:
            # OpenCode might not be running
            logger.debug(f'Model discovery via API failed: {e}')

        # Fallback: Try CLI if no models found via API
        if not all_models:
            try:
                logger.info(f'Trying CLI: {opencode_bin} models')
                if opencode_bin and os.path.exists(opencode_bin):
                    proc = await asyncio.create_subprocess_exec(
                        opencode_bin,
                        'models',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    if proc.returncode == 0:
                        lines = stdout.decode().strip().splitlines()
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            # Format is provider/model
                            parts = line.split('/', 1)
                            if len(parts) == 2:
                                provider, model_name = parts
                                all_models.append(
                                    {
                                        'id': line,
                                        'name': model_name,
                                        'provider': provider,
                                        'provider_id': provider,
                                        'capabilities': {
                                            'reasoning': False,
                                            'attachment': False,
                                            'tool_call': True,
                                        },
                                    }
                                )
                    else:
                        logger.warning(
                            f'CLI failed with code {proc.returncode}: {stderr.decode()}'
                        )
                else:
                    logger.warning(
                        f'OpenCode binary not found or not executable: {opencode_bin}'
                    )
            except Exception as e:
                logger.warning(f'Failed to list models via CLI: {e}')

        # Filter to only authenticated providers
        authenticated_models = []
        for model in all_models:
            provider_id = model.get('provider_id') or model.get('provider', '')
            if provider_id in authenticated_providers:
                authenticated_models.append(model)

        logger.info(
            f'Discovered {len(all_models)} total models, '
            f'{len(authenticated_models)} from authenticated providers'
        )

        if authenticated_models:
            providers_with_models = sorted(
                set(
                    m.get('provider_id', m.get('provider'))
                    for m in authenticated_models
                )
            )
            logger.info(
                f'Authenticated providers with models: {providers_with_models}'
            )

        return authenticated_models

    def get_opencode_storage_path(self) -> Path:
        """Get the OpenCode global storage path.

        We prefer an explicit override, but we also try to "do what I mean" in
        common deployments where the worker runs as a service account while the
        codebases (and OpenCode storage) live under /home/<user>/.
        """

        if self._opencode_storage_path is not None:
            return self._opencode_storage_path

        def _dir_has_any_children(p: Path) -> bool:
            try:
                if not p.exists() or not p.is_dir():
                    return False
                # Fast path: check for any entry without materializing a list.
                for _ in p.iterdir():
                    return True
                return False
            except Exception as e:
                logger.debug(f'Error checking directory children for {p}: {e}')
                return False

        def _storage_has_message_data(storage: Path) -> bool:
            """Return True if this storage appears to contain message/part data."""
            return _dir_has_any_children(
                storage / 'message'
            ) and _dir_has_any_children(storage / 'part')

        def _storage_match_score(storage: Path) -> int:
            """Return how many registered codebases appear in this OpenCode storage's project list."""
            codebase_paths: List[str] = [
                str(cb.get('path'))
                for cb in (self.config.codebases or [])
                if cb.get('path')
            ]
            if not codebase_paths:
                return 0

            project_dir = storage / 'project'
            if not project_dir.exists() or not project_dir.is_dir():
                return 0

            # Compare resolved paths to handle symlinks/relative config.
            try:
                resolved_codebases = {
                    str(Path(p).resolve()) for p in codebase_paths
                }
            except Exception as e:
                logger.debug(
                    f'Failed to resolve codebase paths, using raw paths: {e}'
                )
                resolved_codebases = set(codebase_paths)

            matched: set[str] = set()

            for project_file in project_dir.glob('*.json'):
                if project_file.stem == 'global':
                    continue
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project = json.load(f)
                    worktree = project.get('worktree')
                    if not worktree:
                        continue
                    try:
                        wt = str(Path(worktree).resolve())
                        if wt in resolved_codebases:
                            matched.add(wt)
                    except Exception as e:
                        logger.debug(
                            f'Failed to resolve worktree path {worktree}: {e}'
                        )
                        if worktree in resolved_codebases:
                            matched.add(worktree)
                except Exception as e:
                    logger.debug(
                        f'Error reading project file {project_file}: {e}'
                    )
                    continue

            return len(matched)

        candidates: List[Path] = []
        override_path: Optional[Path] = None

        # 1) Explicit override (config/env)
        override = (
            self.config.opencode_storage_path
            or os.environ.get('A2A_OPENCODE_STORAGE_PATH')
            or os.environ.get('OPENCODE_STORAGE_PATH')
        )
        if override:
            override_path = Path(os.path.expanduser(override)).resolve()
            candidates.append(override_path)

        # 2) Standard per-user location for the current service user
        xdg_data = os.environ.get(
            'XDG_DATA_HOME', str(Path.home() / '.local' / 'share')
        )
        candidates.append(
            Path(os.path.expanduser(xdg_data)) / 'opencode' / 'storage'
        )

        # 3) Heuristic: infer /home/<user> from codebase paths
        inferred_users: List[str] = []
        for cb in self.config.codebases:
            p = cb.get('path')
            if not p:
                continue
            parts = Path(p).parts
            if len(parts) >= 3 and parts[0] == '/' and parts[1] == 'home':
                inferred_users.append(parts[2])

        # Also infer from the opencode binary path (often /home/<user>/.opencode/bin/opencode)
        opencode_bin = self.config.opencode_bin
        if opencode_bin:
            try:
                bin_parts = Path(opencode_bin).parts
                if (
                    len(bin_parts) >= 3
                    and bin_parts[0] == '/'
                    and bin_parts[1] == 'home'
                ):
                    inferred_users.append(bin_parts[2])
            except Exception as e:
                logger.debug(
                    f'Failed to infer user from opencode binary path: {e}'
                )

        for user in dict.fromkeys(inferred_users):  # preserve order, de-dupe
            candidates.append(
                Path('/home')
                / user
                / '.local'
                / 'share'
                / 'opencode'
                / 'storage'
            )

        inferred_candidate_paths = {
            (
                Path('/home')
                / user
                / '.local'
                / 'share'
                / 'opencode'
                / 'storage'
            ).resolve()
            for user in dict.fromkeys(inferred_users)
        }

        # Pick the best existing candidate.
        first_existing: Optional[Path] = None
        best_match: Optional[Path] = None
        best_tuple: Optional[tuple] = None
        for c in candidates:
            try:
                if c.exists() and c.is_dir():
                    if first_existing is None:
                        first_existing = c

                    # Explicit override wins if it exists.
                    if override_path is not None and c == override_path:
                        self._opencode_storage_path = c
                        logger.info(
                            f'Using OpenCode storage at (override): {c}'
                        )
                        return c

                    # Otherwise, score by how many registered codebases this storage contains.
                    score_codebases = _storage_match_score(c)
                    has_message_data = 1 if _storage_has_message_data(c) else 0
                    inferred_bonus = (
                        1 if c.resolve() in inferred_candidate_paths else 0
                    )

                    # Prefer:
                    #  1) Storage that matches registered codebases
                    #  2) Storage that actually contains message/part data (for session detail UI)
                    #  3) Inferred /home/<user> storage over service-account storage when tied
                    score_tuple = (
                        score_codebases,
                        has_message_data,
                        inferred_bonus,
                    )

                    if best_tuple is None or score_tuple > best_tuple:
                        best_tuple = score_tuple
                        best_match = c
            except Exception as e:
                logger.debug(f'Error evaluating storage candidate {c}: {e}')
                continue

        if best_match is not None and best_tuple is not None:
            if best_tuple[0] > 0:
                self._opencode_storage_path = best_match
                logger.info(
                    f'Using OpenCode storage at: {best_match} (matched {best_tuple[0]} codebase(s))'
                )
                return best_match

            # No project→codebase matches found. Prefer a storage that still looks
            # "real" (has message/part data) and/or was inferred from /home/<user>.
            if best_tuple[1] > 0 or best_tuple[2] > 0:
                self._opencode_storage_path = best_match
                logger.info(
                    'Using OpenCode storage at: %s (best available; message_data=%s, inferred_home=%s)',
                    best_match,
                    bool(best_tuple[1]),
                    bool(best_tuple[2]),
                )
                return best_match

        if first_existing is not None:
            # Fall back to *something* that exists, but warn because it might be empty/wrong.
            self._opencode_storage_path = first_existing
            logger.warning(
                'OpenCode storage path exists but did not match any registered codebase projects; '
                f'falling back to: {first_existing}'
            )
            return first_existing

        # Final fallback (even if it doesn't exist yet)
        self._opencode_storage_path = (
            candidates[0]
            if candidates
            else (Path.home() / '.local' / 'share' / 'opencode' / 'storage')
        )
        logger.warning(
            f'OpenCode storage path not found on disk; defaulting to: {self._opencode_storage_path}'
        )
        return self._opencode_storage_path


# =============================================================================
# SessionSyncService - Session management and syncing
# =============================================================================


class SessionSyncService:
    """
    Handles session management and syncing with the server.

    Responsibilities:
    - Reading sessions from OpenCode storage
    - Reporting sessions to server
    - Message sync for remote codebases
    """

    def __init__(
        self,
        config: WorkerConfig,
        config_manager: ConfigManager,
        client: WorkerClient,
    ):
        self.config = config
        self.config_manager = config_manager
        self.client = client

    def _get_project_id_for_path(self, codebase_path: str) -> Optional[str]:
        """Get the OpenCode project ID (hash) for a given codebase path."""
        storage_path = self.config_manager.get_opencode_storage_path()
        project_dir = storage_path / 'project'

        if not project_dir.exists():
            return None

        # Read all project files to find the matching worktree
        for project_file in project_dir.glob('*.json'):
            if project_file.stem == 'global':
                continue
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project = json.load(f)
                worktree = project.get('worktree')
                if worktree:
                    try:
                        if (
                            Path(worktree).resolve()
                            == Path(codebase_path).resolve()
                        ):
                            return project.get('id')
                    except Exception as e:
                        logger.debug(
                            f'Failed to resolve paths for comparison ({worktree} vs {codebase_path}): {e}'
                        )
                        if worktree == codebase_path:
                            return project.get('id')
            except Exception as e:
                logger.debug(f'Error reading project file {project_file}: {e}')
                continue

        return None

    def get_sessions_for_codebase(
        self, codebase_path: str
    ) -> List[Dict[str, Any]]:
        """Get all OpenCode sessions for a codebase."""
        project_id = self._get_project_id_for_path(codebase_path)
        if not project_id:
            logger.debug(f'No OpenCode project ID found for {codebase_path}')
            return []

        storage_path = self.config_manager.get_opencode_storage_path()
        session_dir = storage_path / 'session' / project_id

        if not session_dir.exists():
            return []

        sessions: List[Dict[str, Any]] = []
        for session_file in session_dir.glob('ses_*.json'):
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                    # Convert timestamps from milliseconds to ISO format
                    time_data = session_data.get('time', {})
                    created_ms = time_data.get('created', 0)
                    updated_ms = time_data.get('updated', 0)

                    session_id = session_data.get('id')
                    # OpenCode stores messages separately; count message files for UI convenience.
                    msg_count = 0
                    if session_id:
                        msg_dir = storage_path / 'message' / str(session_id)
                        try:
                            if msg_dir.exists():
                                msg_count = len(
                                    list(msg_dir.glob('msg_*.json'))
                                )
                        except Exception:
                            msg_count = 0

                    created_iso = (
                        datetime.fromtimestamp(created_ms / 1000).isoformat()
                        if created_ms
                        else None
                    )
                    updated_iso = (
                        datetime.fromtimestamp(updated_ms / 1000).isoformat()
                        if updated_ms
                        else None
                    )

                    sessions.append(
                        {
                            'id': session_id,
                            'title': session_data.get('title', 'Untitled'),
                            'directory': session_data.get('directory'),
                            'project_id': project_id,
                            # Match the UI expectations from monitor-tailwind.html
                            'created': created_iso,
                            'updated': updated_iso,
                            'messageCount': msg_count,
                            'summary': session_data.get('summary', {}),
                            'version': session_data.get('version'),
                        }
                    )
            except Exception as e:
                logger.debug(f'Error reading session file {session_file}: {e}')
                continue

        # Sort by updated time descending
        sessions.sort(key=lambda s: s.get('updated') or '', reverse=True)
        return sessions

    def get_global_sessions(self) -> List[Dict[str, Any]]:
        """Get all global OpenCode sessions (not associated with a specific project)."""
        storage_path = self.config_manager.get_opencode_storage_path()
        session_dir = storage_path / 'session' / 'global'

        if not session_dir.exists():
            return []

        sessions: List[Dict[str, Any]] = []
        for session_file in session_dir.glob('ses_*.json'):
            try:
                with open(session_file) as f:
                    session_data = json.load(f)
                    time_data = session_data.get('time', {})
                    created_ms = time_data.get('created', 0)
                    updated_ms = time_data.get('updated', 0)

                    session_id = session_data.get('id')
                    msg_count = 0
                    if session_id:
                        msg_dir = storage_path / 'message' / str(session_id)
                        try:
                            if msg_dir.exists():
                                msg_count = len(
                                    list(msg_dir.glob('msg_*.json'))
                                )
                        except Exception:
                            msg_count = 0

                    created_iso = (
                        datetime.fromtimestamp(created_ms / 1000).isoformat()
                        if created_ms
                        else None
                    )
                    updated_iso = (
                        datetime.fromtimestamp(updated_ms / 1000).isoformat()
                        if updated_ms
                        else None
                    )

                    sessions.append(
                        {
                            'id': session_id,
                            'title': session_data.get('title', 'Untitled'),
                            'directory': session_data.get('directory'),
                            'project_id': SpecialCodebaseId.GLOBAL,
                            'created': created_iso,
                            'updated': updated_iso,
                            'messageCount': msg_count,
                            'summary': session_data.get('summary', {}),
                            'version': session_data.get('version'),
                        }
                    )
            except Exception as e:
                logger.debug(
                    f'Error reading global session file {session_file}: {e}'
                )
                continue

        sessions.sort(key=lambda s: s.get('updated') or '', reverse=True)
        return sessions

    def get_session_messages(
        self, session_id: str, max_messages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages (including parts) for a specific session from OpenCode storage."""
        storage_path = self.config_manager.get_opencode_storage_path()
        message_dir = storage_path / 'message' / session_id

        if not message_dir.exists():
            return []

        msg_files = sorted(message_dir.glob('msg_*.json'))
        if (
            max_messages is not None
            and max_messages > 0
            and len(msg_files) > max_messages
        ):
            msg_files = msg_files[-max_messages:]

        messages: List[Dict[str, Any]] = []
        for msg_file in msg_files:
            try:
                with open(msg_file) as f:
                    msg_data = json.load(f)

                msg_id = msg_data.get('id')
                role = msg_data.get('role')
                agent = msg_data.get('agent')
                model_obj = msg_data.get('model') or {}
                model = None
                if isinstance(model_obj, dict):
                    provider_id = model_obj.get('providerID')
                    model_id = model_obj.get('modelID')
                    if provider_id and model_id:
                        model = f'{provider_id}/{model_id}'
                elif isinstance(model_obj, str):
                    model = model_obj

                time_data = msg_data.get('time', {}) or {}
                created_ms = time_data.get('created', 0)
                created_iso = (
                    datetime.fromtimestamp(created_ms / 1000).isoformat()
                    if created_ms
                    else None
                )

                # Load message parts (text/tool/step/etc)
                parts: List[Dict[str, Any]] = []
                if msg_id:
                    parts_dir = storage_path / 'part' / str(msg_id)
                    if parts_dir.exists() and parts_dir.is_dir():
                        for part_file in sorted(parts_dir.glob('prt_*.json')):
                            try:
                                with open(
                                    part_file, 'r', encoding='utf-8'
                                ) as f:
                                    part_data = json.load(f)
                                part_obj: Dict[str, Any] = {
                                    'id': part_data.get('id'),
                                    'type': part_data.get('type'),
                                }
                                for k in (
                                    'text',
                                    'tool',
                                    'state',
                                    'reason',
                                    'callID',
                                    'cost',
                                    'tokens',
                                ):
                                    if k in part_data:
                                        part_obj[k] = part_data.get(k)
                                parts.append(part_obj)
                            except Exception as e:
                                logger.debug(
                                    f'Error reading part file {part_file}: {e}'
                                )

                messages.append(
                    {
                        'id': msg_id,
                        'sessionID': msg_data.get('sessionID') or session_id,
                        'role': role,
                        'time': {'created': created_iso},
                        'agent': agent,
                        'model': model,
                        # OpenCode message-level metadata (preferred for UI stats)
                        'cost': msg_data.get('cost'),
                        'tokens': msg_data.get('tokens'),
                        'tool_calls': msg_data.get('tool_calls')
                        or msg_data.get('toolCalls')
                        or [],
                        'parts': parts,
                    }
                )
            except Exception as e:
                logger.debug(f'Error reading message file {msg_file}: {e}')
                continue

        # Sort by created time ascending (ISO or None)
        messages.sort(key=lambda m: (m.get('time') or {}).get('created') or '')
        return messages

    async def report_sessions_to_server(
        self,
        codebases: Dict[str, LocalCodebase],
        global_codebase_id: Optional[str],
        register_codebase_fn: Callable,
    ):
        """Report all sessions for registered codebases to the server."""
        # Iterate over a snapshot since we may update codebases if we need
        # to re-register a codebase (e.g., after a server restart).
        for codebase_id, codebase in list(codebases.items()):
            try:
                sessions = self.get_sessions_for_codebase(codebase.path)
                logger.info(
                    f"Discovered {len(sessions)} OpenCode sessions for codebase '{codebase.name}' "
                    f'(id={codebase_id}, path={codebase.path})'
                )
                if not sessions:
                    continue

                status = await self.client.sync_sessions(codebase_id, sessions)

                # Self-heal common failure modes:
                # - 404: server lost codebase registry (restart / db reset)
                # - 403: worker_id mismatch for this codebase
                # In either case, re-register the codebase and retry once.
                if status in (403, 404):
                    logger.info(
                        "Attempting to re-register codebase '%s' after session sync %s (old_id=%s)",
                        codebase.name,
                        status,
                        codebase_id,
                    )
                    new_codebase_id = await register_codebase_fn(
                        name=codebase.name,
                        path=codebase.path,
                        description=codebase.description,
                    )

                    # If a new ID was created/returned, drop the stale mapping.
                    if new_codebase_id and new_codebase_id != codebase_id:
                        codebases.pop(codebase_id, None)
                        codebase_id = new_codebase_id

                    if new_codebase_id:
                        await self.client.sync_sessions(codebase_id, sessions)

                # Optionally sync recent session messages so the UI can show session details
                max_sessions = (
                    getattr(self.config, 'session_message_sync_max_sessions', 0)
                    or 0
                )
                max_messages = (
                    getattr(self.config, 'session_message_sync_max_messages', 0)
                    or 0
                )
                if max_sessions > 0 and max_messages > 0:
                    await self._report_recent_session_messages_to_server(
                        codebase_id=codebase_id,
                        sessions=sessions[:max_sessions],
                        max_messages=max_messages,
                    )

            except Exception as e:
                logger.debug(
                    f'Failed to sync sessions for {codebase.name}: {e}'
                )

        # Also sync global sessions (not associated with any specific project)
        await self._report_global_sessions_to_server(
            global_codebase_id, register_codebase_fn
        )

    async def _report_global_sessions_to_server(
        self,
        global_codebase_id: Optional[str],
        register_codebase_fn: Callable,
    ):
        """Report global sessions to the server under a 'global' pseudo-codebase."""
        try:
            global_sessions = self.get_global_sessions()
            if not global_sessions:
                return

            logger.info(
                f'Discovered {len(global_sessions)} global OpenCode sessions'
            )

            # Ensure we have a "global" codebase registered
            if not global_codebase_id:
                return

            status = await self.client.sync_sessions(
                global_codebase_id, global_sessions
            )

            # Optionally sync recent session messages so the remote UI can show session detail.
            async def _sync_recent_global_messages(
                target_codebase_id: str,
            ) -> None:
                max_sessions = (
                    getattr(self.config, 'session_message_sync_max_sessions', 0)
                    or 0
                )
                max_messages = (
                    getattr(self.config, 'session_message_sync_max_messages', 0)
                    or 0
                )
                if max_sessions > 0 and max_messages > 0:
                    await self._report_recent_session_messages_to_server(
                        codebase_id=target_codebase_id,
                        sessions=global_sessions[:max_sessions],
                        max_messages=max_messages,
                    )

            if status == 200:
                await _sync_recent_global_messages(global_codebase_id)
            elif status in (403, 404):
                # Re-register and retry
                new_id = await register_codebase_fn(
                    name=SpecialCodebaseId.GLOBAL,
                    path=str(Path.home()),
                    description='Global OpenCode sessions (not project-specific)',
                )
                if new_id:
                    retry_status = await self.client.sync_sessions(
                        new_id, global_sessions
                    )
                    if retry_status == 200:
                        await _sync_recent_global_messages(new_id)
                    # Return new_id to caller to update global_codebase_id
                    return new_id

        except Exception as e:
            logger.warning(f'Failed to sync global sessions: {e}')

        return None

    async def _report_recent_session_messages_to_server(
        self,
        codebase_id: str,
        sessions: List[Dict[str, Any]],
        max_messages: int,
    ):
        """Best-effort sync for the most recent sessions' messages."""
        try:
            for ses in sessions:
                session_id = ses.get('id')
                if not session_id:
                    continue

                messages = self.get_session_messages(
                    str(session_id), max_messages=max_messages
                )
                if not messages:
                    continue

                await self.client.sync_session_messages(
                    codebase_id, str(session_id), messages
                )
        except Exception as e:
            logger.debug(
                f'Failed to sync session messages for codebase {codebase_id}: {e}'
            )


# =============================================================================
# ContextCompactionService - Auto-compaction and summarization for sessions
# =============================================================================


class ContextCompactionService:
    """
    Handles automatic context compaction and summarization for task handoffs.

    When sessions grow large or tasks are handed off between workers/agents,
    this service:
    1. Estimates token count from session messages
    2. Generates a summary of completed work
    3. Creates a compacted context for the next agent

    This prevents context overflow errors and ensures clean handoffs.
    """

    # Rough estimate: 1 token ≈ 4 characters for English text
    CHARS_PER_TOKEN = 4

    # Thresholds for compaction
    DEFAULT_MAX_TOKENS = 100000  # Trigger compaction above this
    DEFAULT_TARGET_TOKENS = 50000  # Target size after compaction
    SUMMARY_MAX_TOKENS = 2000  # Max tokens for summary

    def __init__(
        self,
        session_sync: 'SessionSyncService',
        opencode_bin: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        target_tokens: int = DEFAULT_TARGET_TOKENS,
    ):
        self.session_sync = session_sync
        self.opencode_bin = opencode_bin
        self.max_tokens = max_tokens
        self.target_tokens = target_tokens

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // self.CHARS_PER_TOKEN

    def estimate_session_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate total tokens in session messages."""
        total_chars = 0
        for msg in messages:
            # Count message content
            parts = msg.get('parts', [])
            for part in parts:
                if isinstance(part, dict):
                    content = part.get('content', '') or part.get('text', '')
                    if isinstance(content, str):
                        total_chars += len(content)
                elif isinstance(part, str):
                    total_chars += len(part)
        return total_chars // self.CHARS_PER_TOKEN

    def needs_compaction(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if session needs compaction based on estimated tokens."""
        return self.estimate_session_tokens(messages) > self.max_tokens

    def extract_key_context(
        self, messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract key context from messages for summarization.

        Returns a structured summary of:
        - Files modified
        - Tools used
        - Key decisions made
        - Current state/progress
        """
        context = {
            'files_modified': set(),
            'files_read': set(),
            'tools_used': set(),
            'errors_encountered': [],
            'key_outputs': [],
            'message_count': len(messages),
        }

        for msg in messages:
            parts = msg.get('parts', [])
            for part in parts:
                if not isinstance(part, dict):
                    continue

                part_type = part.get('type', '')

                # Track tool usage
                if part_type == 'tool-invocation':
                    tool_name = part.get('toolInvocation', {}).get(
                        'toolName', ''
                    )
                    if tool_name:
                        context['tools_used'].add(tool_name)

                    # Track file operations
                    args = part.get('toolInvocation', {}).get('args', {})
                    if isinstance(args, dict):
                        file_path = (
                            args.get('filePath')
                            or args.get('path')
                            or args.get('file')
                        )
                        if file_path:
                            if tool_name in ('write', 'edit', 'Write', 'Edit'):
                                context['files_modified'].add(file_path)
                            elif tool_name in ('read', 'Read', 'glob', 'Glob'):
                                context['files_read'].add(file_path)

                # Track errors
                if part_type == 'tool-result':
                    result = part.get('toolResult', {})
                    if isinstance(result, dict) and result.get('isError'):
                        error_text = str(result.get('content', ''))[:200]
                        context['errors_encountered'].append(error_text)

                # Track key text outputs (assistant messages)
                if part_type == 'text' and msg.get('role') == 'assistant':
                    text = part.get('text', '')
                    if text and len(text) > 50:
                        # Keep first 500 chars of significant outputs
                        context['key_outputs'].append(text[:500])

        # Convert sets to lists for JSON serialization
        context['files_modified'] = list(context['files_modified'])
        context['files_read'] = list(context['files_read'])
        context['tools_used'] = list(context['tools_used'])

        # Limit key outputs to last 5
        context['key_outputs'] = context['key_outputs'][-5:]

        return context

    def generate_summary_prompt(
        self,
        messages: List[Dict[str, Any]],
        original_task: str,
    ) -> str:
        """
        Generate a prompt for the LLM to create a session summary.

        This summary will be prepended to the next task for context.
        """
        context = self.extract_key_context(messages)

        # Get the last few assistant messages for recent context
        recent_outputs = []
        for msg in reversed(messages[-10:]):
            if msg.get('role') == 'assistant':
                for part in msg.get('parts', []):
                    if isinstance(part, dict) and part.get('type') == 'text':
                        text = part.get('text', '')
                        if text:
                            recent_outputs.append(text[:1000])
                            if len(recent_outputs) >= 3:
                                break

        summary_prompt = f"""Summarize the work done in this coding session for handoff to another agent.

ORIGINAL TASK: {original_task}

SESSION STATISTICS:
- Total messages: {context['message_count']}
- Files modified: {', '.join(context['files_modified'][:20]) or 'None'}
- Files read: {', '.join(context['files_read'][:20]) or 'None'}
- Tools used: {', '.join(context['tools_used']) or 'None'}
- Errors encountered: {len(context['errors_encountered'])}

RECENT WORK:
{chr(10).join(recent_outputs[:3])}

Please provide a concise summary (max 500 words) covering:
1. What was accomplished
2. Current state of the work
3. Any blockers or issues encountered
4. What remains to be done
5. Key files/code that was changed

Format as a handoff note for the next agent."""

        return summary_prompt

    async def generate_summary(
        self,
        session_id: str,
        codebase_path: str,
        original_task: str,
    ) -> Optional[str]:
        """
        Generate a summary of the session using OpenCode.

        Returns the summary text or None if generation fails.
        """
        messages = self.session_sync.get_session_messages(
            session_id, max_messages=100
        )
        if not messages:
            return None

        # Check if compaction is needed
        if not self.needs_compaction(messages):
            logger.debug(f'Session {session_id} does not need compaction')
            return None

        logger.info(
            f'Generating summary for session {session_id} (estimated {self.estimate_session_tokens(messages)} tokens)'
        )

        summary_prompt = self.generate_summary_prompt(messages, original_task)

        # Run a quick summarization using OpenCode with a fast model
        try:
            cmd = [
                self.opencode_bin,
                'run',
                '--agent',
                'general',  # Use general agent for summarization
                '--model',
                'anthropic/claude-3-5-haiku-latest',  # Fast, cheap model
                '--format',
                'json',
                '--',
                summary_prompt,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=codebase_path,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, 'NO_COLOR': '1'},
                limit=16 * 1024 * 1024,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60,  # 1 minute timeout for summarization
            )

            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='replace')
                # Try to extract the summary from JSON output
                for line in output.split('\n'):
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            # Look for text content in the response
                            content = (
                                obj.get('content')
                                or obj.get('text')
                                or obj.get('output')
                            )
                            if content:
                                return content[
                                    : self.SUMMARY_MAX_TOKENS
                                    * self.CHARS_PER_TOKEN
                                ]
                    except json.JSONDecodeError:
                        continue
                # Fallback: return raw output truncated
                return output[: self.SUMMARY_MAX_TOKENS * self.CHARS_PER_TOKEN]
            else:
                logger.warning(
                    f'Summary generation failed: {stderr.decode("utf-8", errors="replace")[:500]}'
                )
                return None

        except asyncio.TimeoutError:
            logger.warning(
                f'Summary generation timed out for session {session_id}'
            )
            return None
        except Exception as e:
            logger.warning(f'Summary generation error: {e}')
            return None

    def create_handoff_context(
        self,
        original_prompt: str,
        summary: Optional[str],
        session_id: Optional[str],
    ) -> str:
        """
        Create a compacted context for task handoff.

        Prepends summary and context to the original prompt.
        """
        if not summary:
            return original_prompt

        handoff_context = f"""## Previous Session Summary

{summary}

## Continuation Task

{original_prompt}

---
Note: This task continues from a previous session. The summary above describes what was already done. 
Please review and continue the work, avoiding redundant actions on files already modified."""

        return handoff_context

    async def prepare_task_context(
        self,
        prompt: str,
        resume_session_id: Optional[str],
        codebase_path: str,
        auto_summarize: bool = True,
    ) -> str:
        """
        Prepare task context with auto-compaction if needed.

        Args:
            prompt: The original task prompt
            resume_session_id: Session ID to resume (if any)
            codebase_path: Path to the codebase
            auto_summarize: Whether to auto-generate summary for large sessions

        Returns:
            The (possibly enhanced) prompt with summary context
        """
        if not resume_session_id or not auto_summarize:
            return prompt

        # Check if session needs compaction
        messages = self.session_sync.get_session_messages(
            resume_session_id, max_messages=100
        )
        if not messages or not self.needs_compaction(messages):
            return prompt

        # Generate summary
        summary = await self.generate_summary(
            session_id=resume_session_id,
            codebase_path=codebase_path,
            original_task=prompt,
        )

        # Create handoff context
        return self.create_handoff_context(prompt, summary, resume_session_id)


# =============================================================================
# TaskExecutor - Task execution logic
# =============================================================================


class TaskExecutor:
    """
    Handles task execution logic.

    Responsibilities:
    - OpenCode subprocess management
    - Task claiming/releasing (via client)
    - Special task handlers (register_codebase, echo, noop)
    - Semaphore-based concurrency control
    - Email notifications on task completion/failure
    - Auto-compaction and summarization for task handoffs
    """

    def __init__(
        self,
        config: WorkerConfig,
        client: WorkerClient,
        config_manager: ConfigManager,
        session_sync: SessionSyncService,
        opencode_bin: str,
        email_service: Optional[EmailNotificationService] = None,
    ):
        self.config = config
        self.client = client
        self.config_manager = config_manager
        self.session_sync = session_sync
        self.opencode_bin = opencode_bin
        self.email_service = email_service
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        # Task processing state
        self._task_semaphore: Optional[asyncio.Semaphore] = None
        self._active_task_ids: Set[str] = set()
        # Context compaction service for auto-summarization
        self.compaction_service = ContextCompactionService(
            session_sync=session_sync,
            opencode_bin=opencode_bin,
            max_tokens=getattr(config, 'compaction_max_tokens', 100000),
            target_tokens=getattr(config, 'compaction_target_tokens', 50000),
        )

    def init_semaphore(self):
        """Initialize the task semaphore for bounded concurrency."""
        if self._task_semaphore is None:
            self._task_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_tasks
            )

    async def terminate_all_processes(self):
        """Terminate all active processes."""
        for task_id, process in list(self.active_processes.items()):
            logger.info(f'Terminating process for task {task_id}')
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()

    async def process_task_with_semaphore(
        self,
        task: Dict[str, Any],
        codebases: Dict[str, LocalCodebase],
        global_codebase_id: Optional[str],
        register_codebase_fn: Callable,
    ):
        """Process a task with bounded concurrency using semaphore."""
        task_id = task.get('id') or task.get('task_id') or ''

        if self._task_semaphore is None:
            self._task_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_tasks
            )

        if not task_id:
            logger.warning('Task has no ID, skipping')
            return

        # -------------------------------------------------------------------------
        # Belt-and-suspenders validation: ensure this worker can handle the task
        # Server-side routing should already filter, but we validate here for
        # defense-in-depth to prevent workers from claiming tasks they can't execute.
        # -------------------------------------------------------------------------
        codebase_id = task.get('codebase_id', '')
        can_handle = (
            codebase_id in codebases
            or codebase_id == SpecialCodebaseId.PENDING
            or (
                codebase_id == SpecialCodebaseId.GLOBAL
                and global_codebase_id is not None
            )
        )
        if not can_handle:
            logger.warning(
                f'Task {task_id} has codebase_id={codebase_id!r} which this worker '
                f'cannot handle (registered: {list(codebases.keys())}). '
                f'Skipping to prevent incorrect claim.'
            )
            return

        # Mark task as active
        self._active_task_ids.add(task_id)

        try:
            async with self._task_semaphore:
                logger.debug(f'Acquired semaphore for task {task_id}')
                # Atomically claim the task before processing to prevent duplicate work
                claimed = await self.client.claim_task(task_id)
                if not claimed:
                    logger.debug(
                        f'Task {task_id} already claimed by another worker, skipping'
                    )
                    return
                try:
                    await self.execute_task(
                        task,
                        codebases,
                        global_codebase_id,
                        register_codebase_fn,
                    )
                finally:
                    # Release the claim when done (success or failure)
                    await self.client.release_task(task_id)
        finally:
            self._active_task_ids.discard(task_id)

    def is_task_active(self, task_id: str) -> bool:
        """Check if a task is currently being processed."""
        return task_id in self._active_task_ids

    async def execute_task(
        self,
        task: Dict[str, Any],
        codebases: Dict[str, LocalCodebase],
        global_codebase_id: Optional[str],
        register_codebase_fn: Callable,
    ):
        """Execute a task using OpenCode or handle special task types."""
        task_id: str = task.get('id') or task.get('task_id') or ''
        codebase_id: str = task.get('codebase_id') or ''
        agent_type: str = (
            task.get('agent_type', AgentType.BUILD) or AgentType.BUILD
        )

        if not task_id:
            logger.error('Task has no ID, cannot execute')
            return

        # Handle special task types
        if agent_type == AgentType.REGISTER_CODEBASE:
            await self.handle_register_codebase_task(task, register_codebase_fn)
            return

        # Lightweight test/utility agent types that do not require OpenCode.
        # Useful for end-to-end validation of the CodeTether task queue.
        if agent_type in (AgentType.ECHO, AgentType.NOOP):
            title = task.get('title')
            logger.info(
                f'Executing lightweight task {task_id}: {title} (agent_type={agent_type})'
            )

            await self.client.update_task_status(task_id, TaskStatus.RUNNING)
            try:
                if agent_type == AgentType.NOOP:
                    result = 'ok'
                else:
                    # Echo returns the prompt/description verbatim.
                    result = task.get('prompt', task.get('description', ''))

                await self.client.update_task_status(
                    task_id, TaskStatus.COMPLETED, result=result
                )
                logger.info(
                    f'Task {task_id} completed successfully (agent_type={agent_type})'
                )
            except Exception as e:
                logger.error(
                    f'Task {task_id} execution error (agent_type={agent_type}): {e}'
                )
                await self.client.update_task_status(
                    task_id, TaskStatus.FAILED, error=str(e)
                )
            return

        # Regular task - requires existing codebase
        # Handle special 'global' codebase_id from MCP/UI clients
        effective_codebase_id = codebase_id
        if codebase_id == SpecialCodebaseId.GLOBAL:
            if not global_codebase_id:
                logger.error(
                    f'Cannot process global task {task_id}: worker has no global codebase registered'
                )
                return
            effective_codebase_id = global_codebase_id

        codebase = codebases.get(effective_codebase_id)

        if not codebase:
            logger.error(f'Codebase {codebase_id} not found for task {task_id}')
            return

        # -------------------------------------------------------------------------
        # Defense-in-depth: verify codebase path exists on disk before executing
        # This catches stale registrations, mount issues, or path misconfigurations
        # -------------------------------------------------------------------------
        codebase_path = Path(codebase.path)
        if not codebase_path.exists():
            error_msg = (
                f'Codebase path does not exist on disk: {codebase.path} '
                f'(codebase_id={effective_codebase_id}, task_id={task_id})'
            )
            logger.error(error_msg)
            await self.client.update_task_status(
                task_id, TaskStatus.FAILED, error=error_msg
            )
            return

        if not codebase_path.is_dir():
            error_msg = (
                f'Codebase path is not a directory: {codebase.path} '
                f'(codebase_id={effective_codebase_id}, task_id={task_id})'
            )
            logger.error(error_msg)
            await self.client.update_task_status(
                task_id, TaskStatus.FAILED, error=error_msg
            )
            return

        logger.info(f'Executing task {task_id}: {task.get("title")}')

        # Claim the task
        await self.client.update_task_status(task_id, TaskStatus.RUNNING)

        start_time = time.time()
        try:
            # Build the prompt
            prompt = task.get('prompt', task.get('description', ''))
            metadata = task.get('metadata', {})
            model = metadata.get(
                'model'
            )  # e.g., "anthropic/claude-sonnet-4-20250514"
            resume_session_id = metadata.get(
                'resume_session_id'
            )  # Session to resume

            # Auto-compaction: If resuming a session with large context,
            # generate a summary and prepend it to the prompt
            auto_summarize = metadata.get('auto_summarize', True)
            if resume_session_id and auto_summarize:
                try:
                    enhanced_prompt = (
                        await self.compaction_service.prepare_task_context(
                            prompt=prompt,
                            resume_session_id=resume_session_id,
                            codebase_path=codebase.path,
                            auto_summarize=True,
                        )
                    )
                    if enhanced_prompt != prompt:
                        logger.info(
                            f'Task {task_id}: Added session summary for handoff'
                        )
                        prompt = enhanced_prompt
                except Exception as e:
                    logger.warning(
                        f'Auto-summarization failed for task {task_id}: {e}'
                    )
                    # Continue with original prompt

            # Run OpenCode
            result = await self.run_opencode(
                codebase_id=codebase_id,
                codebase_path=codebase.path,
                prompt=prompt,
                agent_type=agent_type,
                task_id=task_id,
                model=model,
                session_id=resume_session_id,
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            if result['success']:
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    result=result.get('output', 'Task completed successfully'),
                )
                logger.info(f'Task {task_id} completed successfully')

                # Send email notification
                if self.email_service:
                    await self.email_service.send_task_report(
                        task_id=task_id,
                        title=task.get('title', 'Untitled'),
                        status='completed',
                        result=result.get('output'),
                        duration_ms=duration_ms,
                        session_id=resume_session_id,
                        codebase_id=codebase_id,
                    )
            else:
                error_msg = result.get('error', 'Unknown error')
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=error_msg,
                )
                logger.error(f'Task {task_id} failed: {error_msg}')

                # Send email notification
                if self.email_service:
                    await self.email_service.send_task_report(
                        task_id=task_id,
                        title=task.get('title', 'Untitled'),
                        status='failed',
                        error=error_msg,
                        duration_ms=duration_ms,
                        session_id=resume_session_id,
                        codebase_id=codebase_id,
                    )

        except Exception as e:
            logger.error(f'Task {task_id} execution error: {e}')
            await self.client.update_task_status(
                task_id, TaskStatus.FAILED, error=str(e)
            )

            # Send email notification for exception
            if self.email_service:
                await self.email_service.send_task_report(
                    task_id=task_id,
                    title=task.get('title', 'Untitled'),
                    status='failed',
                    error=str(e),
                    codebase_id=codebase_id,
                )

    async def handle_register_codebase_task(
        self,
        task: Dict[str, Any],
        register_codebase_fn: Callable,
    ):
        """
        Handle a codebase registration task from the server.

        This validates the path exists locally and registers the codebase
        with this worker's ID.
        """
        task_id: str = task.get('id') or task.get('task_id') or ''
        metadata: Dict[str, Any] = task.get('metadata', {}) or {}

        name = metadata.get('name', 'Unknown')
        path = metadata.get('path')
        description = metadata.get('description', '')

        logger.info(f'Handling registration task {task_id}: {name} at {path}')

        # Claim the task
        await self.client.update_task_status(task_id, TaskStatus.RUNNING)

        try:
            # Validate path exists locally on this worker
            if not path:
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error='No path provided in registration task',
                )
                return

            if not os.path.isdir(path):
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=f'Path does not exist on this worker: {path}',
                )
                logger.warning(f'Registration failed - path not found: {path}')
                return

            # Path exists! Register it with the server (with our worker_id)
            codebase_id = await register_codebase_fn(
                name=name,
                path=path,
                description=description,
            )

            if codebase_id:
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    result=f'Codebase registered successfully with ID: {codebase_id}',
                )
                logger.info(
                    f'Registration task {task_id} completed: {name} -> {codebase_id}'
                )
            else:
                await self.client.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error='Failed to register codebase with server',
                )

        except Exception as e:
            logger.error(f'Registration task {task_id} error: {e}')
            await self.client.update_task_status(
                task_id, TaskStatus.FAILED, error=str(e)
            )

    async def run_opencode(
        self,
        codebase_id: str,
        codebase_path: str,
        prompt: str,
        agent_type: str = 'build',
        task_id: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run OpenCode agent on a codebase."""

        def _extract_session_id(obj: Any) -> Optional[str]:
            """Best-effort extraction of an OpenCode session id from JSON output."""
            if isinstance(obj, dict):
                for k in ('sessionID', 'session_id', 'sessionId', 'session'):
                    v = obj.get(k)
                    if isinstance(v, str) and v.startswith('ses_'):
                        return v
                for v in obj.values():
                    found = _extract_session_id(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for v in obj:
                    found = _extract_session_id(v)
                    if found:
                        return found
            return None

        async def _sync_session_messages_once(
            *,
            target_session_id: str,
            messages: List[Dict[str, Any]],
        ) -> bool:
            """Sync messages for a single session. Returns True on HTTP 200."""
            return await self.client.sync_session_messages(
                codebase_id, target_session_id, messages
            )

        def _messages_fingerprint(messages: List[Dict[str, Any]]) -> str:
            """Fingerprint that detects any message update for reliable sync.

            Computes a fingerprint based on:
            - Total message count
            - Last message ID and parts count
            - Sum of all parts across all messages (detects updates to any message)
            - Last part ID from each message (detects new parts added anywhere)

            This ensures the worker syncs to the database every time any message
            is updated, not just when new messages are added.
            """
            if not messages:
                return ''
            last = messages[-1]
            last_id = last.get('id') or ''
            last_parts = last.get('parts')
            last_parts_len = (
                len(last_parts) if isinstance(last_parts, list) else 0
            )
            # Include total message count and last created timestamp when available.
            created = (
                (last.get('time') or {})
                if isinstance(last.get('time'), dict)
                else {}
            ).get('created') or ''

            # Sum all parts across all messages to detect any message update
            total_parts = 0
            last_part_ids = []
            for msg in messages:
                parts = msg.get('parts')
                if isinstance(parts, list):
                    total_parts += len(parts)
                    # Track the last part ID from each message to detect new parts
                    if parts:
                        last_part = parts[-1]
                        if isinstance(last_part, dict):
                            last_part_ids.append(last_part.get('id') or '')

            # Include hash of last part IDs to detect updates within messages
            part_ids_hash = (
                hash(tuple(last_part_ids)) & 0xFFFFFFFF
            )  # 32-bit hash

            return f'{len(messages)}|{last_id}|{last_parts_len}|{created}|{total_parts}|{part_ids_hash}'

        async def _infer_active_session_id(
            *,
            known_before: set[str],
            start_epoch_s: float,
        ) -> Optional[str]:
            """Infer the active session by looking for the most recently updated session."""
            try:
                sessions = self.session_sync.get_sessions_for_codebase(
                    codebase_path
                )
                if not sessions:
                    return None
                top = sessions[0]
                sid = top.get('id')
                if not isinstance(sid, str) or not sid:
                    return None

                # Prefer brand-new sessions.
                if sid not in known_before:
                    return sid

                # Or sessions updated after the task started.
                updated = top.get('updated')
                if isinstance(updated, str) and updated:
                    try:
                        # worker writes naive isoformat; treat as local time.
                        updated_dt = datetime.fromisoformat(updated)
                        if updated_dt.timestamp() >= (start_epoch_s - 2.0):
                            return sid
                    except Exception:
                        return sid  # best-effort
                return sid
            except Exception:
                return None

        def _recent_opencode_log_hint(returncode: int) -> Optional[str]:
            """Best-effort hint for failures where OpenCode logs to file.

            Avoid dumping full logs into task output (can be huge / sensitive).
            Instead, point operators to the most recent log file and surface
            common actionable errors (like missing API keys).
            """

            try:
                data_home = os.environ.get(
                    'XDG_DATA_HOME', str(Path.home() / '.local' / 'share')
                )
                log_dir = (
                    Path(os.path.expanduser(data_home)) / 'opencode' / 'log'
                )
                if not log_dir.exists() or not log_dir.is_dir():
                    return None

                logs = list(log_dir.glob('*.log'))
                if not logs:
                    return None

                latest = max(logs, key=lambda p: p.stat().st_mtime)
                age_s = time.time() - latest.stat().st_mtime
                if age_s > 300:  # don't point at stale logs
                    return None

                try:
                    tail_lines = latest.read_text(
                        encoding='utf-8', errors='replace'
                    ).splitlines()[-80:]
                except Exception:
                    tail_lines = []

                tail_text = '\n'.join(tail_lines)
                if (
                    'API key is missing' in tail_text
                    or 'AI_LoadAPIKeyError' in tail_text
                ):
                    return (
                        'OpenCode is missing LLM credentials (e.g. ANTHROPIC_API_KEY). '
                        'Set the required key(s) in /etc/a2a-worker/env and restart the worker. '
                        f'OpenCode log: {latest}'
                    )

                return f'OpenCode exited with code {returncode}. See OpenCode log: {latest}'
            except Exception:
                return None

        # Check if opencode exists
        if not Path(self.opencode_bin).exists():
            return {
                'success': False,
                'error': f'OpenCode not found at {self.opencode_bin}',
            }

        # Build command using 'opencode run' with proper flags
        cmd = [
            self.opencode_bin,
            'run',
            '--agent',
            agent_type,
            '--format',
            'json',
        ]

        # Add model if specified (format: provider/model)
        if model:
            cmd.extend(['--model', model])

        # Add session resumption if specified
        if session_id:
            cmd.extend(['--session', session_id])
            logger.info(f'Resuming session: {session_id}')

        # Add '--' separator and then the prompt as positional message argument
        # This ensures the prompt isn't interpreted as a flag
        if prompt:
            cmd.append('--')
            cmd.append(prompt)

        log_model = f' --model {model}' if model else ''
        log_session = f' --session {session_id}' if session_id else ''
        logger.info(
            f'Running: {self.opencode_bin} run --agent {agent_type}{log_model}{log_session} ...'
        )

        try:
            start_epoch_s = time.time()
            known_sessions_before: set[str] = set()
            if not session_id:
                try:
                    known_sessions_before = {
                        str(s.get('id'))
                        for s in self.session_sync.get_sessions_for_codebase(
                            codebase_path
                        )
                        if s.get('id')
                    }
                except Exception as e:
                    logger.debug(
                        f'Failed to get existing sessions before task start: {e}'
                    )
                    known_sessions_before = set()

            active_session_id: Optional[str] = session_id

            # Run the process using async subprocess to avoid blocking the event loop
            # Use a large buffer limit (16MB) to handle OpenCode's potentially very long
            # JSON output lines (e.g., file contents, large tool results). The default
            # 64KB limit causes "Separator is found, but chunk is longer than limit" errors.
            subprocess_limit = 16 * 1024 * 1024  # 16MB
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=codebase_path,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, 'NO_COLOR': '1'},
                limit=subprocess_limit,
            )

            if task_id:
                self.active_processes[task_id] = process

            # Eagerly sync the *active* session messages while the task runs.
            eager_sync_interval = 1.0
            try:
                eager_sync_interval = float(
                    os.environ.get(
                        'A2A_ACTIVE_SESSION_SYNC_INTERVAL', eager_sync_interval
                    )
                )
            except Exception:
                eager_sync_interval = 1.0

            max_messages = (
                getattr(self.config, 'session_message_sync_max_messages', 0)
                or 0
            )
            if max_messages <= 0:
                max_messages = 100

            async def _eager_sync_loop():
                nonlocal active_session_id
                last_fp: Optional[str] = None
                session_attached = False

                while process.returncode is None:
                    # Discover session id if needed.
                    if not active_session_id:
                        active_session_id = await _infer_active_session_id(
                            known_before=known_sessions_before,
                            start_epoch_s=start_epoch_s,
                        )

                    if active_session_id and task_id and not session_attached:
                        # Attach the session id to the running task so UIs can deep-link.
                        await self.client.update_task_status(
                            task_id,
                            TaskStatus.RUNNING,
                            session_id=active_session_id,
                        )
                        session_attached = True

                    if active_session_id:
                        # Sync whenever the message fingerprint changes (any message update).
                        try:
                            current_messages = (
                                self.session_sync.get_session_messages(
                                    str(active_session_id),
                                    max_messages=max_messages,
                                )
                            )
                            fp = _messages_fingerprint(current_messages)
                            if fp and fp != last_fp:
                                ok = await _sync_session_messages_once(
                                    target_session_id=str(active_session_id),
                                    messages=current_messages,
                                )
                                if ok:
                                    last_fp = fp
                                    logger.debug(
                                        f'Synced messages for session {active_session_id} (fingerprint changed)'
                                    )
                        except Exception as e:
                            logger.debug(f'Eager sync loop read failed: {e}')

                    await asyncio.sleep(max(0.2, eager_sync_interval))

                # Final flush after process ends.
                if active_session_id:
                    try:
                        final_messages = self.session_sync.get_session_messages(
                            str(active_session_id),
                            max_messages=max_messages,
                        )
                        await _sync_session_messages_once(
                            target_session_id=str(active_session_id),
                            messages=final_messages,
                        )
                    except Exception as e:
                        logger.debug(
                            f'Final message flush failed for session {active_session_id}: {e}'
                        )

            eager_task: Optional[asyncio.Task] = None
            if task_id:
                eager_task = asyncio.create_task(_eager_sync_loop())

            # Stream output in real-time using async iteration
            output_lines: List[str] = []
            stderr_lines: List[str] = []

            async def _read_stdout():
                """Read stdout lines asynchronously.

                Uses readline() with explicit error handling for very long lines.
                OpenCode can produce JSON lines >64KB when including file contents.
                """
                nonlocal active_session_id
                if process.stdout is None:
                    return

                while True:
                    try:
                        # Read line with the increased buffer limit
                        line_bytes = await process.stdout.readline()
                        if not line_bytes:
                            break  # EOF

                        line = line_bytes.decode('utf-8', errors='replace')
                        output_lines.append(line)

                        # Try to detect session id from OpenCode JSON output.
                        if not active_session_id:
                            try:
                                obj = json.loads(line)
                                active_session_id = (
                                    _extract_session_id(obj)
                                    or active_session_id
                                )
                            except json.JSONDecodeError:
                                pass  # Not JSON, skip session extraction

                        # Stream output to server (truncate very long lines to prevent issues)
                        if task_id:
                            # Truncate output for streaming to prevent overwhelming the server
                            stream_line = line.strip()
                            if len(stream_line) > 10000:
                                stream_line = (
                                    stream_line[:10000] + '... [truncated]'
                                )
                            await self.client.stream_task_output(
                                task_id, stream_line
                            )

                    except ValueError as e:
                        # Handle "Separator is found, but chunk is longer than limit"
                        # by reading raw bytes and chunking
                        logger.warning(
                            f'Line too long for readline, reading raw: {e}'
                        )
                        try:
                            raw_chunk = await process.stdout.read(
                                1024 * 1024
                            )  # 1MB chunk
                            if raw_chunk:
                                line = raw_chunk.decode(
                                    'utf-8', errors='replace'
                                )
                                output_lines.append(line)
                            else:
                                break  # EOF
                        except Exception as chunk_err:
                            logger.error(
                                f'Failed to read raw chunk: {chunk_err}'
                            )
                            break

            async def _read_stderr():
                """Read stderr lines asynchronously with error handling for long lines."""
                if process.stderr is None:
                    return

                while True:
                    try:
                        line_bytes = await process.stderr.readline()
                        if not line_bytes:
                            break  # EOF

                        line = line_bytes.decode('utf-8', errors='replace')
                        stderr_lines.append(line)
                        if task_id:
                            # Truncate very long stderr lines
                            stream_line = line.strip()
                            if len(stream_line) > 10000:
                                stream_line = (
                                    stream_line[:10000] + '... [truncated]'
                                )
                            await self.client.stream_task_output(
                                task_id, f'[stderr] {stream_line}'
                            )
                    except ValueError:
                        # Handle very long lines by reading raw
                        try:
                            raw_chunk = await process.stderr.read(1024 * 1024)
                            if raw_chunk:
                                stderr_lines.append(
                                    raw_chunk.decode('utf-8', errors='replace')
                                )
                            else:
                                break
                        except Exception:
                            break

            try:
                # Read stdout and stderr concurrently
                await asyncio.gather(_read_stdout(), _read_stderr())

                # Wait for process to complete
                await process.wait()

                stdout = ''.join(output_lines)
                stderr = ''.join(stderr_lines)

            except asyncio.CancelledError:
                process.kill()
                await process.wait()
                stdout = ''.join(output_lines)
                stderr = ''.join(stderr_lines)
                return {
                    'success': False,
                    'error': 'Task was cancelled',
                }
            finally:
                if task_id and task_id in self.active_processes:
                    del self.active_processes[task_id]
                if task_id and eager_task is not None:
                    try:
                        eager_task.cancel()
                        await eager_task
                    except asyncio.CancelledError:
                        pass  # Expected when cancelling
                    except Exception as e:
                        logger.debug(
                            f'Error awaiting cancelled eager sync task: {e}'
                        )

            returncode = process.returncode or 0
            if returncode == 0:
                return {'success': True, 'output': stdout}
            else:
                hint = _recent_opencode_log_hint(returncode)
                err = (stderr or '').strip()
                return {
                    'success': False,
                    'error': err or hint or f'Exit code: {returncode}',
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}


# =============================================================================
# AgentWorker - Thin orchestrator composing all services
# =============================================================================


class AgentWorker:
    """
    Agent worker that connects to A2A server and executes tasks locally.

    Uses SSE (Server-Sent Events) for real-time task streaming instead of polling.
    This class acts as a thin orchestrator that composes the following services:
    - WorkerClient: HTTP/SSE communication
    - ConfigManager: Configuration and setup
    - SessionSyncService: Session management and syncing
    - TaskExecutor: Task execution logic
    """

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.codebases: Dict[str, LocalCodebase] = {}
        self.running = False
        self._global_codebase_id: Optional[str] = (
            None  # Cached ID for global sessions codebase
        )
        # Track tasks we've seen to avoid duplicates (LRU cache with max size)
        self._known_task_ids: OrderedDict[str, None] = OrderedDict()
        self._known_task_ids_max_size: int = 10000

        # Initialize services
        self.client = WorkerClient(config)
        self.config_manager = ConfigManager(config)
        self.opencode_bin = (
            config.opencode_bin or self.config_manager.find_opencode_binary()
        )
        self.session_sync = SessionSyncService(
            config, self.config_manager, self.client
        )
        # Initialize email service if configured
        self.email_service = EmailNotificationService(config)
        if self.email_service.is_configured():
            logger.info(
                f'Email notifications enabled: {config.notification_email}'
            )
        else:
            logger.info('Email notifications not configured')

        self.task_executor = TaskExecutor(
            config,
            self.client,
            self.config_manager,
            self.session_sync,
            self.opencode_bin,
            self.email_service if self.email_service.is_configured() else None,
        )

    # -------------------------------------------------------------------------
    # Delegated methods for backward compatibility
    # -------------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling."""
        return await self.client.get_session()

    def _find_opencode_binary(self) -> str:
        """Find the opencode binary."""
        return self.config_manager.find_opencode_binary()

    def _get_authenticated_providers(self) -> set:
        """Get set of provider IDs that have authentication configured."""
        return self.config_manager.get_authenticated_providers()

    async def _get_available_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from local OpenCode instance."""
        return await self.config_manager.get_available_models(self.opencode_bin)

    def _get_opencode_storage_path(self) -> Path:
        """Get the OpenCode global storage path."""
        return self.config_manager.get_opencode_storage_path()

    def _get_project_id_for_path(self, codebase_path: str) -> Optional[str]:
        """Get the OpenCode project ID (hash) for a given codebase path."""
        return self.session_sync._get_project_id_for_path(codebase_path)

    def get_sessions_for_codebase(
        self, codebase_path: str
    ) -> List[Dict[str, Any]]:
        """Get all OpenCode sessions for a codebase."""
        return self.session_sync.get_sessions_for_codebase(codebase_path)

    def get_global_sessions(self) -> List[Dict[str, Any]]:
        """Get all global OpenCode sessions (not associated with a specific project)."""
        return self.session_sync.get_global_sessions()

    def get_session_messages(
        self, session_id: str, max_messages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages (including parts) for a specific session from OpenCode storage."""
        return self.session_sync.get_session_messages(session_id, max_messages)

    async def sync_api_keys_from_server(
        self, user_id: Optional[str] = None
    ) -> bool:
        """Sync API keys from the server to local OpenCode auth.json."""
        return await self.client.sync_api_keys_from_server(user_id)

    async def stream_task_output(self, task_id: str, output: str):
        """Stream output chunk to the server."""
        await self.client.stream_task_output(task_id, output)

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        max_retries: int = 4,
        base_delay: float = 1.0,
    ):
        """Update task status on the server with exponential backoff retry."""
        await self.client.update_task_status(
            task_id, status, result, error, session_id, max_retries, base_delay
        )

    async def _claim_task(self, task_id: str) -> bool:
        """Atomically claim a task on the server."""
        return await self.client.claim_task(task_id)

    async def _release_task(self, task_id: str) -> bool:
        """Release a task claim on the server after processing."""
        return await self.client.release_task(task_id)

    async def send_heartbeat(self) -> bool:
        """Send heartbeat to the A2A server to indicate worker is alive."""
        return await self.client.send_heartbeat()

    async def run_opencode(
        self,
        codebase_id: str,
        codebase_path: str,
        prompt: str,
        agent_type: str = 'build',
        task_id: Optional[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run OpenCode agent on a codebase."""
        return await self.task_executor.run_opencode(
            codebase_id,
            codebase_path,
            prompt,
            agent_type,
            task_id,
            model,
            session_id,
        )

    async def execute_task(self, task: Dict[str, Any]):
        """Execute a task using OpenCode or handle special task types."""
        await self.task_executor.execute_task(
            task,
            self.codebases,
            self._global_codebase_id,
            self.register_codebase,
        )

    async def handle_register_codebase_task(self, task: Dict[str, Any]):
        """Handle a codebase registration task from the server."""
        await self.task_executor.handle_register_codebase_task(
            task, self.register_codebase
        )

    async def _process_task_with_semaphore(self, task: Dict[str, Any]):
        """Process a task with bounded concurrency using semaphore."""
        await self.task_executor.process_task_with_semaphore(
            task,
            self.codebases,
            self._global_codebase_id,
            self.register_codebase,
        )

    async def report_sessions_to_server(self):
        """Report all sessions for registered codebases to the server."""
        result = await self.session_sync.report_sessions_to_server(
            self.codebases, self._global_codebase_id, self.register_codebase
        )
        # Update global_codebase_id if it was re-registered
        if result is not None:
            self._global_codebase_id = result

    async def _report_global_sessions_to_server(self):
        """Report global sessions to the server under a 'global' pseudo-codebase."""
        result = await self.session_sync._report_global_sessions_to_server(
            self._global_codebase_id, self.register_codebase
        )
        if result is not None:
            self._global_codebase_id = result

    async def _report_recent_session_messages_to_server(
        self,
        codebase_id: str,
        sessions: List[Dict[str, Any]],
        max_messages: int,
    ):
        """Best-effort sync for the most recent sessions' messages."""
        await self.session_sync._report_recent_session_messages_to_server(
            codebase_id, sessions, max_messages
        )

    # -------------------------------------------------------------------------
    # Core orchestration methods
    # -------------------------------------------------------------------------

    async def start(self):
        """Start the worker."""
        logger.info(
            f"Starting worker '{self.config.worker_name}' (ID: {self.config.worker_id})"
        )
        logger.info(f'Connecting to server: {self.config.server_url}')

        # Surface OpenCode credential discovery issues early (common when running under systemd).
        try:
            data_home = os.environ.get('XDG_DATA_HOME') or os.path.expanduser(
                '~/.local/share'
            )
            auth_path = (
                Path(os.path.expanduser(data_home)) / 'opencode' / 'auth.json'
            )
            if auth_path.exists():
                logger.info(f'OpenCode auth detected at: {auth_path}')
            else:
                logger.warning(
                    'OpenCode auth.json not found for this worker. '
                    f'Expected at: {auth_path}. '
                    "OpenCode agents may fail with 'missing API key' unless you authenticate as this service user "
                    "or import/copy auth.json into the worker's XDG data directory."
                )
        except Exception as e:
            logger.debug(f'Failed to check OpenCode auth.json presence: {e}')

        self.running = True

        # Initialize task semaphore for bounded concurrency
        self.task_executor.init_semaphore()

        # Register global pseudo-codebase first so we can include its ID in worker registration
        logger.info('Registering global pseudo-codebase...')
        self._global_codebase_id = await self.register_codebase(
            name=SpecialCodebaseId.GLOBAL,
            path=str(Path.home()),
            description='Global OpenCode sessions (not project-specific)',
        )

        # Register worker with server
        await self.register_worker()

        # Register configured codebases
        for cb_config in self.config.codebases:
            await self.register_codebase(
                name=cb_config.get('name', Path(cb_config['path']).name),
                path=cb_config['path'],
                description=cb_config.get('description', ''),
            )

        # Register as a discoverable agent (enables agent-to-agent communication)
        # This is done AFTER codebase registration so the worker is "ready"
        # Registration is best-effort and non-blocking
        if self.config.register_as_agent:
            logger.info('Registering as discoverable agent...')
            await self.client.register_as_agent(
                agent_name=self.config.agent_name,
                description=self.config.agent_description,
                url=self.config.agent_url,
                routing_capabilities=self.config.capabilities,
            )

        # Sync API keys from server (allows web UI key management)
        logger.info('Syncing API keys from server...')
        await self.sync_api_keys_from_server()

        # Immediately sync sessions on startup
        logger.info('Syncing sessions with server...')
        await self.report_sessions_to_server()

        # Start SSE task stream with fallback to polling
        await self._run_with_sse_and_fallback()

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info('Stopping worker...')
        self.running = False

        # Kill any active processes
        await self.task_executor.terminate_all_processes()

        # Unregister from server (best effort)
        try:
            await self.unregister_worker()
        except Exception as e:
            logger.debug(f'Failed to unregister worker during shutdown: {e}')

        # Close sessions properly
        await self.client.close()
        await self.email_service.close()

        logger.info('Worker stopped')

    async def register_worker(self):
        """Register this worker with the A2A server."""
        # Ensure global codebase is registered
        if not self._global_codebase_id:
            logger.info(
                'Global codebase not registered, attempting registration...'
            )
            self._global_codebase_id = await self.register_codebase(
                name=SpecialCodebaseId.GLOBAL,
                path=str(Path.home()),
                description='Global OpenCode sessions (not project-specific)',
            )

        # Get available models before registering
        models = await self._get_available_models()
        logger.info(f'Models to register: {len(models)}')

        await self.client.register_worker(models, self._global_codebase_id)

    async def unregister_worker(self):
        """Unregister this worker from the A2A server."""
        await self.client.unregister_worker()

    async def register_codebase(
        self, name: str, path: str, description: str = ''
    ) -> Optional[str]:
        """Register a local codebase with the A2A server."""
        # Normalize for comparisons / de-duping when re-registering.
        normalized_path = os.path.abspath(os.path.expanduser(path))

        codebase_id = await self.client.register_codebase(
            name, path, description
        )

        if codebase_id:
            # If we're re-registering after a server restart, the
            # server may assign a new codebase ID for the same path.
            # Remove any stale local entries for this path.
            stale_ids = [
                cid
                for cid, cb in self.codebases.items()
                if os.path.abspath(os.path.expanduser(cb.path))
                == normalized_path
                and cid != codebase_id
            ]
            for cid in stale_ids:
                self.codebases.pop(cid, None)

            self.codebases[codebase_id] = LocalCodebase(
                id=codebase_id,
                name=name,
                path=normalized_path,
                description=description,
            )

        return codebase_id

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get pending tasks from the server (fallback polling method)."""
        codebase_ids = list(self.codebases.keys())
        tasks = await self.client.get_pending_tasks(codebase_ids)
        # Filter to:
        # 1. Tasks for our registered codebases
        # 2. Registration tasks (codebase_id = '__pending__') that any worker can claim
        # 3. Global tasks (codebase_id = 'global') for workers with global codebase
        matching = [
            t
            for t in tasks
            if t.get('codebase_id') in self.codebases
            or t.get('codebase_id') == SpecialCodebaseId.PENDING
            or (
                t.get('codebase_id') == SpecialCodebaseId.GLOBAL
                and self._global_codebase_id is not None
            )
        ]
        if matching:
            logger.info(
                f'Found {len(matching)} pending tasks for our codebases'
            )
        return matching

    async def _run_with_sse_and_fallback(self):
        """Run the main loop with SSE streaming, falling back to polling if needed."""
        session_sync_counter = 0
        session_sync_interval = 12  # Sync sessions every 12 cycles (60s at 5s)

        while self.running:
            try:
                # Try SSE streaming first
                logger.info('Attempting SSE connection for task streaming...')
                await self._sse_task_stream()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f'SSE connection failed: {e}')
                self.client.sse_connected = False

            if not self.running:
                break

            # SSE failed or disconnected - fall back to polling temporarily
            logger.info(
                f'Falling back to polling (reconnect in {self.client.sse_reconnect_delay}s)...'
            )

            # Do one poll cycle while waiting to reconnect
            try:
                tasks = await self.get_pending_tasks()
                for task in tasks:
                    if not self.running:
                        break
                    codebase_id = task.get('codebase_id')
                    if (
                        codebase_id in self.codebases
                        or codebase_id == SpecialCodebaseId.PENDING
                        or (
                            codebase_id == SpecialCodebaseId.GLOBAL
                            and self._global_codebase_id is not None
                        )
                    ):
                        # Process task with bounded concurrency
                        asyncio.create_task(
                            self._process_task_with_semaphore(task)
                        )

                # Periodic maintenance
                session_sync_counter += 1
                if session_sync_counter >= session_sync_interval:
                    session_sync_counter = 0
                    await self.register_worker()
                    for cb_config in self.config.codebases:
                        await self.register_codebase(
                            name=cb_config.get(
                                'name', Path(cb_config['path']).name
                            ),
                            path=cb_config['path'],
                            description=cb_config.get('description', ''),
                        )
                    await self.report_sessions_to_server()

            except Exception as e:
                logger.error(f'Error in fallback poll: {e}')

            # Wait before trying SSE again (with exponential backoff)
            await asyncio.sleep(self.client.sse_reconnect_delay)
            self.client.sse_reconnect_delay = min(
                self.client.sse_reconnect_delay * 2,
                self.config.sse_max_reconnect_delay,
            )

    async def _sse_task_stream(self):
        """Connect to SSE endpoint and receive task assignments in real-time."""
        session = await self._get_session()

        # Build SSE URL with worker_id and agent_name
        # Use agent_name if set, otherwise fall back to worker_name
        # This ensures SSE routing identity matches discovery identity
        sse_url = f'{self.config.server_url}/v1/worker/tasks/stream'
        resolved_agent_name = self.config.agent_name or self.config.worker_name
        params = {
            'worker_id': self.config.worker_id,
            'agent_name': resolved_agent_name,  # Required by SSE endpoint
        }

        logger.info(f'Connecting to SSE stream: {sse_url}')

        # Use a longer timeout for SSE connections
        sse_timeout = aiohttp.ClientTimeout(
            total=None,  # No total timeout
            connect=30,
            sock_read=self.config.sse_heartbeat_timeout
            + 15,  # Allow some slack
        )

        # Build headers including auth token if available
        sse_headers = {'Accept': 'text/event-stream'}
        if self.config.auth_token:
            sse_headers['Authorization'] = f'Bearer {self.config.auth_token}'

        # Add codebase IDs as header for SSE routing
        # Always include 'global' so worker accepts tasks for any codebase
        codebase_ids = list(self.codebases.keys())
        codebase_ids.append('global')
        sse_headers['X-Codebases'] = ','.join(codebase_ids)

        # Add capabilities header
        sse_headers['X-Capabilities'] = 'opencode,build,deploy,test'

        async with session.get(
            sse_url,
            params=params,
            timeout=sse_timeout,
            headers=sse_headers,
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(
                    f'SSE connection failed: {response.status} - {text}'
                )

            self.client.sse_connected = True
            self.client.sse_reconnect_delay = (
                self.config.sse_reconnect_delay
            )  # Reset backoff
            self.client.last_heartbeat = time.time()
            logger.info('SSE connection established')

            # Start background tasks
            heartbeat_checker = asyncio.create_task(
                self._check_heartbeat_timeout()
            )
            periodic_maintenance = asyncio.create_task(
                self._periodic_maintenance()
            )

            try:
                event_type = None
                event_data_lines = []

                async for line in response.content:
                    if not self.running:
                        break

                    line = line.decode('utf-8').rstrip('\r\n')

                    if line.startswith('event:'):
                        event_type = line[6:].strip()
                    elif line.startswith('data:'):
                        event_data_lines.append(line[5:].strip())
                    elif line == '':
                        # Empty line signals end of event
                        if event_data_lines:
                            event_data = '\n'.join(event_data_lines)
                            await self._handle_sse_event(event_type, event_data)
                            event_data_lines = []
                            event_type = None
                    # Handle comment lines (heartbeats often sent as : comment)
                    elif line.startswith(':'):
                        self.client.last_heartbeat = time.time()
                        logger.debug('Received SSE heartbeat (comment)')

            finally:
                heartbeat_checker.cancel()
                periodic_maintenance.cancel()
                try:
                    await heartbeat_checker
                except asyncio.CancelledError:
                    pass
                try:
                    await periodic_maintenance
                except asyncio.CancelledError:
                    pass

    async def _handle_sse_event(self, event_type: Optional[str], data: str):
        """Handle an SSE event from the server."""
        self.client.last_heartbeat = time.time()

        # Handle heartbeat events
        if event_type == 'heartbeat' or event_type == 'ping':
            logger.debug('Received SSE heartbeat event')
            return

        # Handle task events
        if event_type in (
            'task',
            'task_available',
            'task_assigned',
            'task.created',
            'task.assigned',
        ):
            try:
                task = json.loads(data)
                task_id = task.get('id') or task.get('task_id')

                # Skip if we've already seen this task (LRU deduplication)
                if task_id in self._known_task_ids:
                    logger.debug(f'Skipping duplicate task: {task_id}')
                    return
                # Add to LRU cache, evicting oldest if at capacity
                self._known_task_ids[task_id] = None
                if len(self._known_task_ids) > self._known_task_ids_max_size:
                    self._known_task_ids.popitem(last=False)

                # Skip if already processing
                if self.task_executor.is_task_active(task_id):
                    logger.debug(f'Task already being processed: {task_id}')
                    return

                codebase_id = task.get('codebase_id')
                if (
                    codebase_id in self.codebases
                    or codebase_id == SpecialCodebaseId.PENDING
                    or (
                        codebase_id == SpecialCodebaseId.GLOBAL
                        and self._global_codebase_id is not None
                    )
                ):
                    logger.info(
                        f'Received task via SSE: {task_id} - {task.get("title", "Untitled")}'
                    )
                    # Process task with bounded concurrency (don't await)
                    asyncio.create_task(self._process_task_with_semaphore(task))
                else:
                    logger.debug(
                        f'Task {task_id} not for our codebases, ignoring'
                    )

            except json.JSONDecodeError as e:
                logger.warning(f'Failed to parse task data: {e}')
            except Exception as e:
                logger.error(f'Error handling task event: {e}')

        elif event_type == 'connected':
            logger.info(f'SSE connection confirmed: {data}')

        elif event_type == 'error':
            logger.warning(f'SSE server error: {data}')

        else:
            logger.debug(
                f'Unknown SSE event type: {event_type}, data: {data[:100]}...'
            )

    async def _check_heartbeat_timeout(self):
        """Check if we've received a heartbeat recently."""
        while self.running and self.client.sse_connected:
            await asyncio.sleep(10)

            if not self.client.sse_connected:
                break

            elapsed = time.time() - self.client.last_heartbeat
            if elapsed > self.config.sse_heartbeat_timeout:
                logger.warning(
                    f'No SSE heartbeat for {elapsed:.1f}s (timeout: {self.config.sse_heartbeat_timeout}s)'
                )
                # Force reconnection by breaking the SSE loop
                self.client.sse_connected = False
                break

    async def _periodic_maintenance(self):
        """Perform periodic maintenance tasks while SSE is connected."""
        sync_interval = 60  # seconds
        heartbeat_interval = 15  # seconds
        agent_heartbeat_interval = 45  # seconds (must be < 120s TTL)
        last_sync = time.time()
        last_heartbeat = time.time()
        last_agent_heartbeat = time.time()

        while self.running and self.client.sse_connected:
            await asyncio.sleep(5)

            now = time.time()

            # Send heartbeat to server periodically (worker heartbeat)
            if now - last_heartbeat >= heartbeat_interval:
                last_heartbeat = now
                await self.send_heartbeat()

            # Refresh agent discovery heartbeat (keeps agent visible in discover_agents)
            if (
                self.config.register_as_agent
                and now - last_agent_heartbeat >= agent_heartbeat_interval
            ):
                last_agent_heartbeat = now
                await self.client.refresh_agent_heartbeat()

            # Sync sessions and re-register periodically
            if now - last_sync >= sync_interval:
                last_sync = now
                try:
                    await self.register_worker()
                    for cb_config in self.config.codebases:
                        await self.register_codebase(
                            name=cb_config.get(
                                'name', Path(cb_config['path']).name
                            ),
                            path=cb_config['path'],
                            description=cb_config.get('description', ''),
                        )
                    await self.report_sessions_to_server()
                except Exception as e:
                    logger.warning(f'Periodic maintenance error: {e}')


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    if config_path and Path(config_path).exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f'Failed to load config from {config_path}: {e}')

    # Check default locations
    default_paths = [
        Path.home() / '.config' / 'a2a-worker' / 'config.json',
        Path('/etc/a2a-worker/config.json'),
        Path('worker-config.json'),
    ]

    for path in default_paths:
        try:
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        except Exception:
            # Skip if we can't read it (e.g. permission denied)
            continue

    return {}


async def main():
    parser = argparse.ArgumentParser(description='A2A Agent Worker')
    parser.add_argument('--server', '-s', default=None, help='A2A server URL')
    parser.add_argument('--name', '-n', default=None, help='Worker name')
    parser.add_argument(
        '--worker-id',
        default=None,
        help='Stable worker id (recommended for systemd/k8s). If omitted, a random id is generated.',
    )
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument(
        '--codebase',
        '-b',
        action='append',
        help='Codebase to register (format: name:path or just path)',
    )
    parser.add_argument(
        '--poll-interval',
        '-i',
        type=int,
        default=None,
        help='Fallback poll interval in seconds (when SSE unavailable)',
    )
    parser.add_argument('--opencode', help='Path to opencode binary')

    parser.add_argument(
        '--opencode-storage-path',
        default=None,
        help='Override OpenCode storage path (directory containing project/, session/, message/, part/)',
    )
    parser.add_argument(
        '--session-message-sync-max-sessions',
        type=int,
        default=None,
        help='How many most-recent sessions per codebase to sync messages for (0 disables)',
    )
    parser.add_argument(
        '--session-message-sync-max-messages',
        type=int,
        default=None,
        help='How many most-recent messages per session to sync (0 disables)',
    )
    parser.add_argument(
        '--max-concurrent-tasks',
        type=int,
        default=None,
        help='Maximum number of tasks to process concurrently (default: 2)',
    )
    parser.add_argument(
        '--sse-heartbeat-timeout',
        type=float,
        default=None,
        help='SSE heartbeat timeout in seconds (default: 45)',
    )
    # Email notification options
    parser.add_argument(
        '--email',
        '-e',
        default=None,
        help='Email address for task completion reports',
    )
    parser.add_argument(
        '--sendgrid-key',
        default=None,
        help='SendGrid API key (or set SENDGRID_API_KEY env var)',
    )
    parser.add_argument(
        '--sendgrid-from',
        default=None,
        help='SendGrid verified sender email (or set SENDGRID_FROM_EMAIL env var)',
    )
    # Email debugging and testing options
    parser.add_argument(
        '--test-email',
        action='store_true',
        help='Send a test notification email and exit (validates email config)',
    )
    parser.add_argument(
        '--email-dry-run',
        action='store_true',
        help='Log emails instead of sending them (dry run mode)',
    )
    parser.add_argument(
        '--email-verbose',
        action='store_true',
        help='Enable verbose logging for email operations',
    )
    # Agent registration options (for A2A network discovery)
    parser.add_argument(
        '--no-agent-registration',
        action='store_true',
        help='Disable automatic agent registration (worker will not be discoverable via discover_agents)',
    )
    parser.add_argument(
        '--agent-name',
        default=None,
        help='Name for agent discovery and routing (defaults to worker name). '
        'This is the identity used for discover_agents and send_to_agent.',
    )
    parser.add_argument(
        '--agent-description',
        default=None,
        help='Description for agent discovery (what this agent does)',
    )
    parser.add_argument(
        '--agent-url',
        default=None,
        help='URL where this agent can be reached directly (optional, defaults to server URL)',
    )

    args = parser.parse_args()

    # Load config from file
    file_config = load_config(args.config)

    # Honor config file values when CLI flags are not explicitly provided.
    # Note: argparse does not tell us whether a value came from a default or
    # from an explicit flag, so we detect explicit flags via sys.argv.
    server_flag_set = ('--server' in sys.argv) or ('-s' in sys.argv)
    name_flag_set = ('--name' in sys.argv) or ('-n' in sys.argv)
    worker_id_flag_set = '--worker-id' in sys.argv
    poll_flag_set = ('--poll-interval' in sys.argv) or ('-i' in sys.argv)

    # Resolve server_url with precedence: CLI flag > env > config > default
    if server_flag_set and args.server:
        server_url = args.server
    elif os.environ.get('A2A_SERVER_URL'):
        server_url = os.environ['A2A_SERVER_URL']
    elif file_config.get('server_url'):
        server_url = file_config['server_url']
    else:
        server_url = 'https://api.codetether.run'

    # Resolve worker_name with precedence: CLI flag > env > config > hostname
    if name_flag_set and args.name:
        worker_name = args.name
    elif os.environ.get('A2A_WORKER_NAME'):
        worker_name = os.environ['A2A_WORKER_NAME']
    elif file_config.get('worker_name'):
        worker_name = file_config['worker_name']
    else:
        import platform

        worker_name = platform.node()  # Cross-platform (works on Windows)

    # Resolve worker_id with precedence: CLI flag > env > config > default
    worker_id: Optional[str] = None
    if worker_id_flag_set and args.worker_id:
        worker_id = args.worker_id
    elif os.environ.get('A2A_WORKER_ID'):
        worker_id = os.environ['A2A_WORKER_ID']
    elif file_config.get('worker_id'):
        worker_id = file_config['worker_id']

    # Resolve poll_interval with precedence: CLI flag > env > config > default
    poll_interval_raw = None
    if poll_flag_set and (args.poll_interval is not None):
        poll_interval_raw = args.poll_interval
    elif os.environ.get('A2A_POLL_INTERVAL'):
        poll_interval_raw = os.environ.get('A2A_POLL_INTERVAL')
    elif file_config.get('poll_interval') is not None:
        poll_interval_raw = file_config.get('poll_interval')
    else:
        poll_interval_raw = 5

    try:
        poll_interval = (
            int(poll_interval_raw) if poll_interval_raw is not None else 5
        )
    except (TypeError, ValueError):
        poll_interval = 5
        logger.warning('Invalid poll_interval value; falling back to 5 seconds')

    capabilities = file_config.get('capabilities')
    if not isinstance(capabilities, list):
        capabilities = None

    # Build codebase list
    codebases = file_config.get('codebases', [])
    if args.codebase:
        for cb in args.codebase:
            if ':' in cb:
                name, path = cb.split(':', 1)
            else:
                name = Path(cb).name
                path = cb
            codebases.append({'name': name, 'path': os.path.abspath(path)})

    # Create config
    config_kwargs: Dict[str, Any] = {
        'server_url': server_url,
        'worker_name': worker_name,
        'codebases': codebases,
        'poll_interval': poll_interval,
        'opencode_bin': args.opencode or file_config.get('opencode_bin'),
        'opencode_storage_path': (
            args.opencode_storage_path
            or os.environ.get('A2A_OPENCODE_STORAGE_PATH')
            or file_config.get('opencode_storage_path')
        ),
    }

    if worker_id:
        config_kwargs['worker_id'] = worker_id

    # Optional session message sync tuning
    if args.session_message_sync_max_sessions is not None:
        config_kwargs['session_message_sync_max_sessions'] = (
            args.session_message_sync_max_sessions
        )
    elif os.environ.get('A2A_SESSION_MESSAGE_SYNC_MAX_SESSIONS'):
        try:
            config_kwargs['session_message_sync_max_sessions'] = int(
                os.environ['A2A_SESSION_MESSAGE_SYNC_MAX_SESSIONS']
            )
        except ValueError as e:
            logger.warning(
                f'Invalid A2A_SESSION_MESSAGE_SYNC_MAX_SESSIONS value: {e}'
            )
    elif file_config.get('session_message_sync_max_sessions') is not None:
        config_kwargs['session_message_sync_max_sessions'] = file_config.get(
            'session_message_sync_max_sessions'
        )

    if args.session_message_sync_max_messages is not None:
        config_kwargs['session_message_sync_max_messages'] = (
            args.session_message_sync_max_messages
        )
    elif os.environ.get('A2A_SESSION_MESSAGE_SYNC_MAX_MESSAGES'):
        try:
            config_kwargs['session_message_sync_max_messages'] = int(
                os.environ['A2A_SESSION_MESSAGE_SYNC_MAX_MESSAGES']
            )
        except ValueError as e:
            logger.warning(
                f'Invalid A2A_SESSION_MESSAGE_SYNC_MAX_MESSAGES value: {e}'
            )
    elif file_config.get('session_message_sync_max_messages') is not None:
        config_kwargs['session_message_sync_max_messages'] = file_config.get(
            'session_message_sync_max_messages'
        )

    # Max concurrent tasks
    if args.max_concurrent_tasks is not None:
        config_kwargs['max_concurrent_tasks'] = args.max_concurrent_tasks
    elif os.environ.get('A2A_MAX_CONCURRENT_TASKS'):
        try:
            config_kwargs['max_concurrent_tasks'] = int(
                os.environ['A2A_MAX_CONCURRENT_TASKS']
            )
        except ValueError as e:
            logger.warning(f'Invalid A2A_MAX_CONCURRENT_TASKS value: {e}')
    elif file_config.get('max_concurrent_tasks') is not None:
        config_kwargs['max_concurrent_tasks'] = file_config.get(
            'max_concurrent_tasks'
        )

    # SSE heartbeat timeout
    if args.sse_heartbeat_timeout is not None:
        config_kwargs['sse_heartbeat_timeout'] = args.sse_heartbeat_timeout
    elif os.environ.get('A2A_SSE_HEARTBEAT_TIMEOUT'):
        try:
            config_kwargs['sse_heartbeat_timeout'] = float(
                os.environ['A2A_SSE_HEARTBEAT_TIMEOUT']
            )
        except ValueError as e:
            logger.warning(f'Invalid A2A_SSE_HEARTBEAT_TIMEOUT value: {e}')
    elif file_config.get('sse_heartbeat_timeout') is not None:
        config_kwargs['sse_heartbeat_timeout'] = file_config.get(
            'sse_heartbeat_timeout'
        )

    if capabilities is not None:
        config_kwargs['capabilities'] = capabilities

    # Auth token for SSE endpoint
    auth_token = os.environ.get('A2A_AUTH_TOKEN')
    if auth_token:
        config_kwargs['auth_token'] = auth_token

    # SendGrid email notification config
    # Precedence: CLI flag > env var > Vault > config file
    sendgrid_key = (
        args.sendgrid_key
        or os.environ.get('SENDGRID_API_KEY')
        or file_config.get('sendgrid_api_key')
    )
    sendgrid_from = (
        args.sendgrid_from
        or os.environ.get('SENDGRID_FROM_EMAIL')
        or file_config.get('sendgrid_from_email')
    )
    notification_email = (
        args.email
        or os.environ.get('A2A_NOTIFICATION_EMAIL')
        or file_config.get('notification_email')
    )

    # Try to fetch from Vault if not configured via CLI/env/config
    vault_path = file_config.get(
        'vault_sendgrid_path', 'secret/spotlessbinco/sendgrid'
    )
    if not sendgrid_key or not sendgrid_from or not notification_email:
        vault = VaultClient()
        if vault.is_configured():
            logger.info(f'Fetching SendGrid config from Vault: {vault_path}')
            try:
                # Run sync in event loop
                import asyncio as _asyncio

                async def _fetch_vault():
                    try:
                        secrets = await vault.get_secret(vault_path)
                        return secrets
                    finally:
                        await vault.close()

                loop = _asyncio.new_event_loop()
                vault_secrets = loop.run_until_complete(_fetch_vault())
                loop.close()

                if vault_secrets:
                    if not sendgrid_key:
                        sendgrid_key = vault_secrets.get('SENDGRID_API_KEY')
                    if not sendgrid_from:
                        sendgrid_from = vault_secrets.get('SENDGRID_FROM_EMAIL')
                    if not notification_email:
                        notification_email = vault_secrets.get(
                            'NOTIFICATION_EMAIL'
                        )
                    logger.info('Loaded SendGrid config from Vault')
            except Exception as e:
                logger.warning(
                    f'Failed to fetch SendGrid config from Vault: {e}'
                )

    if sendgrid_key:
        config_kwargs['sendgrid_api_key'] = sendgrid_key
    if sendgrid_from:
        config_kwargs['sendgrid_from_email'] = sendgrid_from
    if notification_email:
        config_kwargs['notification_email'] = notification_email

    # Email debugging flags
    if args.email_dry_run:
        config_kwargs['email_dry_run'] = True
        logger.info(
            'Email dry-run mode enabled (emails will be logged, not sent)'
        )

    if args.email_verbose:
        config_kwargs['email_verbose'] = True
        logger.info('Email verbose logging enabled')

    # Add email inbound domain from config if available
    email_inbound_domain = os.environ.get(
        'EMAIL_INBOUND_DOMAIN'
    ) or file_config.get('email_inbound_domain')
    if email_inbound_domain:
        config_kwargs['email_inbound_domain'] = email_inbound_domain

    email_reply_prefix = os.environ.get(
        'EMAIL_REPLY_PREFIX'
    ) or file_config.get('email_reply_prefix')
    if email_reply_prefix:
        config_kwargs['email_reply_prefix'] = email_reply_prefix

    # Agent registration options
    # Disable agent registration if --no-agent-registration flag is set
    if args.no_agent_registration:
        config_kwargs['register_as_agent'] = False
        logger.info(
            'Agent registration disabled (worker will not be discoverable)'
        )
    else:
        # Default to True (register as discoverable agent)
        register_as_agent = file_config.get('register_as_agent', True)
        config_kwargs['register_as_agent'] = register_as_agent

    # Agent name (identity for discovery and routing - should match SSE agent_name)
    # This is the key identity used by discover_agents and send_to_agent
    agent_name = (
        args.agent_name
        or os.environ.get('A2A_AGENT_NAME')
        or file_config.get('agent_name')
    )
    if agent_name:
        config_kwargs['agent_name'] = agent_name
        logger.info(f"Agent name set to: '{agent_name}'")

    # Agent description (what this agent does)
    agent_description = (
        args.agent_description
        or os.environ.get('A2A_AGENT_DESCRIPTION')
        or file_config.get('agent_description')
    )
    if agent_description:
        config_kwargs['agent_description'] = agent_description

    # Agent URL (where this agent can be reached directly)
    agent_url = (
        args.agent_url
        or os.environ.get('A2A_AGENT_URL')
        or file_config.get('agent_url')
    )
    if agent_url:
        config_kwargs['agent_url'] = agent_url

    config = WorkerConfig(**config_kwargs)

    # Handle --test-email flag: send test email and exit
    if args.test_email:
        logger.info('=== Email Configuration Test ===')
        email_service = EmailNotificationService(config)

        # Print configuration status
        config_status = email_service.get_config_status()
        logger.info(f'Configuration status:')
        logger.info(f'  Configured: {config_status["configured"]}')
        logger.info(f'  Dry-run mode: {config_status["dry_run"]}')
        logger.info(f'  Verbose mode: {config_status["verbose"]}')
        logger.info(
            f'  SendGrid API key set: {config_status["sendgrid_api_key_set"]}'
        )
        logger.info(f'  From email: {config_status["sendgrid_from_email"]}')
        logger.info(f'  To email: {config_status["notification_email"]}')
        logger.info(f'  Inbound domain: {config_status["inbound_domain"]}')
        logger.info(f'  Reply prefix: {config_status["reply_prefix"]}')

        if config_status['issues']:
            logger.warning(f'Issues found:')
            for issue in config_status['issues']:
                logger.warning(f'  - {issue}')

        # Send test email
        result = await email_service.send_test_email()

        if result['success']:
            logger.info(f'SUCCESS: {result["message"]}')
        else:
            logger.error(f'FAILED: {result["message"]}')

        await email_service.close()

        # Exit after test
        return

    # Create and start worker
    worker = AgentWorker(config)

    # Handle signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info('Received shutdown signal')
        worker.running = False

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        pass
    finally:
        # Always ensure clean shutdown
        await worker.stop()
        # Give aiohttp time to close connections gracefully
        await asyncio.sleep(0.25)


if __name__ == '__main__':
    asyncio.run(main())
