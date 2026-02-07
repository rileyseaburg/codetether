"""
OpenCode Bridge - Integrates OpenCode AI coding agent with A2A Server

This module provides a bridge between the A2A protocol server and OpenCode,
allowing web UI triggers to start AI agents working on registered codebases.

Architecture:
- Workers sync codebases, tasks, and sessions to PostgreSQL (via database.py)
- Bridge reads from PostgreSQL for a consistent view across replicas
- No SQLite persistence - all durable storage is in PostgreSQL
- In-memory caches are used for performance but are not authoritative

Production usage:
- Configure DATABASE_URL environment variable to point to PostgreSQL
- Workers register codebases and sync session state to PostgreSQL
- Multiple server replicas can read the same PostgreSQL data
- Monitor API queries PostgreSQL directly for session listings
"""

import asyncio
import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import aiohttp

# Import PostgreSQL database module
from . import database as db

# Import Knative modules for event-driven worker spawning
from .knative_spawner import (
    knative_spawner,
    KnativeSpawnerError,
    WorkerStatus,
    KNATIVE_ENABLED as KNATIVE_SPAWNER_ENABLED,
)
from .knative_events import (
    publish_task_event,
    is_enabled as is_knative_events_enabled,
    KnativeEventError,
)

logger = logging.getLogger(__name__)

# OpenCode host configuration - allows container to connect to host VM's opencode
# Use 'host.docker.internal' when running in Docker on Linux/Mac/Windows
# Use the actual host IP when host.docker.internal is not available
OPENCODE_HOST = os.environ.get('OPENCODE_HOST', 'localhost')
OPENCODE_DEFAULT_PORT = int(os.environ.get('OPENCODE_PORT', '9777'))


class AgentStatus(str, Enum):
    """Status of an OpenCode agent instance."""

    IDLE = 'idle'
    RUNNING = 'running'
    BUSY = 'busy'
    ERROR = 'error'
    STOPPED = 'stopped'
    WATCHING = 'watching'  # Agent is watching for tasks


class AgentTaskStatus(str, Enum):
    """Status of an agent task."""

    PENDING = 'pending'
    QUEUED = 'queued'  # Task queued for Knative worker
    ASSIGNED = 'assigned'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


# Model selector mapping: user-friendly names -> provider/model-id
# This allows users to say "use minimax" instead of "minimax/minimax-m2.1"
MODEL_SELECTOR = {
    # Anthropic models
    'claude-sonnet': 'anthropic/claude-sonnet-4-20250514',
    'claude-sonnet-4': 'anthropic/claude-sonnet-4-20250514',
    'sonnet': 'anthropic/claude-sonnet-4-20250514',
    'claude-opus': 'anthropic/claude-opus-4-20250514',
    'opus': 'anthropic/claude-opus-4-20250514',
    'claude-haiku': 'anthropic/claude-haiku',
    'haiku': 'anthropic/claude-haiku',
    # Minimax models
    'minimax': 'minimax/minimax-m2.1',
    'minimax-m2': 'minimax/minimax-m2.1',
    'minimax-m2.1': 'minimax/minimax-m2.1',
    'm2.1': 'minimax/minimax-m2.1',
    # OpenAI models
    'gpt-4': 'openai/gpt-4',
    'gpt-4o': 'openai/gpt-4o',
    'gpt-4-turbo': 'openai/gpt-4-turbo',
    'gpt-4.1': 'openai/gpt-4.1',
    'o1': 'openai/o1',
    'o1-mini': 'openai/o1-mini',
    'o3': 'openai/o3',
    'o3-mini': 'openai/o3-mini',
    # Google models
    'gemini': 'google/gemini-2.5-pro',
    'gemini-pro': 'google/gemini-2.5-pro',
    'gemini-2.5-pro': 'google/gemini-2.5-pro',
    'gemini-flash': 'google/gemini-2.5-flash',
    'gemini-2.5-flash': 'google/gemini-2.5-flash',
    # xAI models
    'grok': 'xai/grok-3',
    'grok-3': 'xai/grok-3',
    # Default (empty string or None uses agent default)
    'default': '',
    '': '',
}

# List of valid model selector keys for enum validation
MODEL_SELECTOR_KEYS = list(MODEL_SELECTOR.keys())


def is_knative_enabled() -> bool:
    """
    Check if Knative worker spawning is enabled.

    Returns True if both Knative spawning and Knative events are enabled.
    """
    return KNATIVE_SPAWNER_ENABLED and is_knative_events_enabled()


def resolve_model(model_input: Optional[str]) -> Optional[str]:
    """
    Resolve a user-friendly model name to the full provider/model-id format.

    Args:
        model_input: User input like 'minimax', 'claude-sonnet', or full 'provider/model-id'

    Returns:
        Full provider/model-id string, or None if default should be used
    """
    if not model_input:
        return None

    model_lower = model_input.lower().strip()

    # Check if it's already in provider/model format
    if '/' in model_input:
        return model_input

    # Look up in selector mapping
    if model_lower in MODEL_SELECTOR:
        resolved = MODEL_SELECTOR[model_lower]
        return resolved if resolved else None

    # If not found, return as-is (let the worker handle validation)
    logger.warning(
        f"Unknown model selector '{model_input}', passing through as-is"
    )
    return model_input


@dataclass
class AgentTask:
    """Represents a task assigned to an agent."""

    id: str
    codebase_id: str
    title: str
    prompt: str
    agent_type: str = 'build'  # build, plan, general, explore
    model: Optional[str] = (
        None  # Full provider/model-id (e.g., 'minimax/minimax-m2.1')
    )
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    priority: int = 0  # Higher = more urgent
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    target_agent_name: Optional[str] = None  # If set, only this agent can claim
    worker_id: Optional[str] = None  # ID of the worker that executed this task
    model_ref: Optional[str] = None  # Requested model (provider:model format)
    model_used: Optional[str] = (
        None  # Actual model used (may differ if fallback)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'codebase_id': self.codebase_id,
            'title': self.title,
            'prompt': self.prompt,
            'agent_type': self.agent_type,
            'model': self.model,
            'status': self.status.value,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat()
            if self.started_at
            else None,
            'completed_at': self.completed_at.isoformat()
            if self.completed_at
            else None,
            'result': self.result,
            'error': self.error,
            'session_id': self.session_id,
            'metadata': self.metadata,
            'target_agent_name': self.target_agent_name,
            'worker_id': self.worker_id,
            'model_ref': self.model_ref,
            'model_used': self.model_used,
        }


@dataclass
class RegisteredCodebase:
    """Represents a codebase registered for agent work."""

    id: str
    name: str
    path: str
    description: str = ''
    registered_at: datetime = field(default_factory=datetime.utcnow)
    agent_config: Dict[str, Any] = field(default_factory=dict)
    last_triggered: Optional[datetime] = None
    status: AgentStatus = AgentStatus.IDLE
    opencode_port: Optional[int] = None
    session_id: Optional[str] = None
    watch_mode: bool = False  # Whether agent is in watch mode
    watch_interval: int = 5  # Seconds between task checks
    worker_id: Optional[str] = None  # ID of the worker that owns this codebase

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'description': self.description,
            'registered_at': self.registered_at.isoformat(),
            'agent_config': self.agent_config,
            'last_triggered': self.last_triggered.isoformat()
            if self.last_triggered
            else None,
            'status': self.status.value,
            'opencode_port': self.opencode_port,
            'session_id': self.session_id,
            'watch_mode': self.watch_mode,
            'watch_interval': self.watch_interval,
            'worker_id': self.worker_id,
        }


@dataclass
class AgentTriggerRequest:
    """Request to trigger an agent on a codebase."""

    codebase_id: str
    prompt: str
    agent: str = 'build'  # build, plan, general, explore
    model: Optional[str] = None
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTriggerResponse:
    """Response from triggering an agent."""

    success: bool
    session_id: Optional[str] = None
    message: str = ''
    codebase_id: Optional[str] = None
    agent: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'session_id': self.session_id,
            'message': self.message,
            'codebase_id': self.codebase_id,
            'agent': self.agent,
            'error': self.error,
        }


class OpenCodeBridge:
    """
    Bridge between A2A Server and OpenCode.

    Manages codebase registrations, task queues, and triggers OpenCode agents
    through its HTTP API. Supports watch mode where agents poll for tasks.
    """

    def __init__(
        self,
        opencode_bin: Optional[str] = None,
        default_port: int = None,
        auto_start: bool = True,
        db_path: Optional[str] = None,
        opencode_host: Optional[str] = None,
    ):
        """
        Initialize the OpenCode bridge.

        Args:
            opencode_bin: Path to opencode binary (auto-detected if None)
            default_port: Default port for OpenCode server
            auto_start: Whether to auto-start OpenCode when triggering
            db_path: DEPRECATED - bridge now uses PostgreSQL from database.py
            opencode_host: Host where OpenCode API is running (for container->host)
        """
        self.opencode_bin = opencode_bin or self._find_opencode_binary()
        self.default_port = default_port or OPENCODE_DEFAULT_PORT
        self.auto_start = auto_start
        # OpenCode host - allows container to connect to host VM's opencode
        self.opencode_host = opencode_host or OPENCODE_HOST

        # In-memory caches (populated from PostgreSQL on demand)
        self._codebases: Dict[str, RegisteredCodebase] = {}
        self._tasks: Dict[str, AgentTask] = {}  # task_id -> task
        self._codebase_tasks: Dict[
            str, List[str]
        ] = {}  # codebase_id -> [task_ids]

        # Watch mode background tasks
        self._watch_tasks: Dict[
            str, asyncio.Task
        ] = {}  # codebase_id -> asyncio task

        # Active OpenCode processes
        self._processes: Dict[str, subprocess.Popen] = {}

        # Port allocations
        self._port_allocations: Dict[str, int] = {}
        self._next_port = self.default_port

        # Event callbacks
        self._on_status_change: List[Callable] = []
        self._on_message: List[Callable] = []
        self._on_task_update: List[Callable] = []

        # HTTP session for API calls
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(
            f'OpenCode bridge initialized with binary: {self.opencode_bin}'
        )
        logger.info(f'OpenCode host: {self.opencode_host}:{self.default_port}')
        logger.info(f'Using PostgreSQL database for persistence')

    def _get_opencode_base_url(self, port: Optional[int] = None) -> str:
        """
        Get the base URL for OpenCode API.

        Uses configured opencode_host to allow container->host communication.
        """
        p = port or self.default_port
        return f'http://{self.opencode_host}:{p}'

    async def _save_codebase(self, codebase: RegisteredCodebase):
        """Save or update a codebase in PostgreSQL."""
        try:
            await db.db_upsert_codebase(
                {
                    'id': codebase.id,
                    'name': codebase.name,
                    'path': codebase.path,
                    'description': codebase.description,
                    'worker_id': codebase.worker_id,
                    'agent_config': codebase.agent_config,
                    'created_at': codebase.registered_at.isoformat(),
                    'updated_at': datetime.utcnow().isoformat(),
                    'status': codebase.status.value,
                    'session_id': codebase.session_id,
                    'opencode_port': codebase.opencode_port,
                }
            )
        except Exception as e:
            logger.error(f'Failed to save codebase to PostgreSQL: {e}')

    async def _delete_codebase(self, codebase_id: str):
        """Delete a codebase from PostgreSQL."""
        try:
            await db.db_delete_codebase(codebase_id)
        except Exception as e:
            logger.error(f'Failed to delete codebase from PostgreSQL: {e}')

    async def _save_task(self, task: AgentTask):
        """Save or update a task in PostgreSQL."""
        try:
            metadata = dict(task.metadata or {})
            if task.model and 'model' not in metadata:
                metadata['model'] = task.model
            if task.model_ref and 'model_ref' not in metadata:
                metadata['model_ref'] = task.model_ref
            if task.target_agent_name and 'target_agent_name' not in metadata:
                metadata['target_agent_name'] = task.target_agent_name
            if task.model_used and 'model_used' not in metadata:
                metadata['model_used'] = task.model_used

            await db.db_upsert_task(
                {
                    'id': task.id,
                    'codebase_id': task.codebase_id,
                    'title': task.title,
                    'prompt': task.prompt,
                    'agent_type': task.agent_type,
                    'status': task.status.value,
                    'priority': task.priority,
                    'worker_id': None,  # Will be set by worker when claimed
                    'result': task.result,
                    'error': task.error,
                    'metadata': metadata,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': datetime.utcnow().isoformat(),
                    'started_at': task.started_at.isoformat()
                    if task.started_at
                    else None,
                    'completed_at': task.completed_at.isoformat()
                    if task.completed_at
                    else None,
                }
            )
        except Exception as e:
            logger.error(f'Failed to save task to PostgreSQL: {e}')

    def _task_from_db_row(self, row: Dict[str, Any]) -> AgentTask:
        """Convert a database row to an AgentTask object."""

        def parse_dt(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                # Handle ISO format with or without timezone
                try:
                    return datetime.fromisoformat(val.replace('Z', '+00:00'))
                except ValueError:
                    return datetime.strptime(val, '%Y-%m-%dT%H:%M:%S.%f')
            return None

        metadata = row.get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return AgentTask(
            id=row['id'],
            codebase_id=row.get('codebase_id', 'global'),
            title=row.get('title', ''),
            prompt=row.get('prompt', row.get('title', '')),
            agent_type=row.get('agent_type', 'build'),
            status=AgentTaskStatus(row.get('status', 'pending')),
            model=metadata.get('model'),
            priority=row.get('priority', 0),
            created_at=parse_dt(row.get('created_at')) or datetime.utcnow(),
            started_at=parse_dt(row.get('started_at')),
            completed_at=parse_dt(row.get('completed_at')),
            result=row.get('result'),
            error=row.get('error'),
            session_id=row.get('session_id'),
            metadata=metadata,
            target_agent_name=metadata.get('target_agent_name'),
            model_ref=metadata.get('model_ref'),
            model_used=metadata.get('model_used'),
        )

    async def _load_task_from_db(self, task_id: str) -> Optional[AgentTask]:
        """Load a task from PostgreSQL and cache it in memory.

        IMPORTANT: Does NOT overwrite an existing in-memory task, because the
        in-memory version may have been updated (e.g., status=completed) but
        not yet flushed to the database.
        """
        # If already in memory, return that version (it may be more current)
        existing = self._tasks.get(task_id)
        if existing is not None:
            return existing
        try:
            row = await db.db_get_task(task_id)
            if row:
                task = self._task_from_db_row(row)
                # Cache in memory only if still absent (race guard)
                if task_id not in self._tasks:
                    self._tasks[task_id] = task
                else:
                    return self._tasks[task_id]
                if task.codebase_id not in self._codebase_tasks:
                    self._codebase_tasks[task.codebase_id] = []
                if task_id not in self._codebase_tasks[task.codebase_id]:
                    self._codebase_tasks[task.codebase_id].append(task_id)
                return task
        except Exception as e:
            logger.error(f'Failed to load task {task_id}: {e}')
        return None

    async def _load_codebases_from_db(self):
        """Load all codebases from PostgreSQL and cache in memory."""

        def parse_dt(val):
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val.replace('Z', '+00:00'))
                except ValueError:
                    return datetime.strptime(val, '%Y-%m-%dT%H:%M:%S.%f')
            return None

        try:
            codebases = await db.db_list_codebases()
            loaded_count = 0
            for row in codebases:
                codebase_id = row.get('id')
                if not codebase_id:
                    continue

                self._codebases[codebase_id] = RegisteredCodebase(
                    id=codebase_id,
                    name=row.get('name', ''),
                    path=row.get('path', ''),
                    description=row.get('description', ''),
                    registered_at=parse_dt(row.get('created_at'))
                    or datetime.utcnow(),
                    agent_config=row.get('agent_config') or {},
                    last_triggered=parse_dt(row.get('last_triggered')),
                    status=AgentStatus(row.get('status', 'idle')),
                    opencode_port=row.get('opencode_port'),
                    session_id=row.get('session_id'),
                    watch_mode=row.get('watch_mode', False),
                    watch_interval=row.get('watch_interval', 5),
                    worker_id=row.get('worker_id'),
                )
                loaded_count += 1
            logger.info(f'Loaded {loaded_count} codebases from PostgreSQL')
        except Exception as e:
            logger.error(f'Failed to load codebases from PostgreSQL: {e}')

    async def _load_tasks_from_db(
        self,
        codebase_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentTask]:
        """Load tasks from PostgreSQL and cache them in memory."""
        try:
            rows = await db.db_list_tasks(
                codebase_id=codebase_id,
                status=status,
                limit=limit,
            )
            tasks = []
            for row in rows:
                # Prefer in-memory version (it may have updates not yet in DB)
                existing = self._tasks.get(row.get('id') or row.get('task_id'))
                if existing is not None:
                    tasks.append(existing)
                    continue
                task = self._task_from_db_row(row)
                # Cache in memory only if still absent (race guard)
                if task.id not in self._tasks:
                    self._tasks[task.id] = task
                else:
                    tasks.append(self._tasks[task.id])
                    continue
                if task.codebase_id not in self._codebase_tasks:
                    self._codebase_tasks[task.codebase_id] = []
                if task.id not in self._codebase_tasks[task.codebase_id]:
                    self._codebase_tasks[task.codebase_id].append(task.id)
                tasks.append(task)
            return tasks
        except Exception as e:
            logger.error(f'Failed to load tasks from PostgreSQL: {e}')
        return []

    async def _update_codebase_status(
        self, codebase: RegisteredCodebase, status: AgentStatus
    ):
        """Update codebase status and persist to PostgreSQL."""
        codebase.status = status
        await self._save_codebase(codebase)

    def _find_opencode_binary(self) -> str:
        """Find the opencode binary in common locations."""
        # Check environment variable first
        env_bin = os.environ.get('OPENCODE_BIN_PATH')
        if env_bin and os.path.exists(env_bin):
            return env_bin

        # Check common locations
        locations = [
            # Local project
            str(
                Path(__file__).parent.parent
                / 'opencode'
                / 'packages'
                / 'opencode'
                / 'bin'
                / 'opencode'
            ),
            # System paths
            '/usr/local/bin/opencode',
            '/usr/bin/opencode',
            # User paths
            str(Path.home() / '.local' / 'bin' / 'opencode'),
            str(Path.home() / 'bin' / 'opencode'),
            str(Path.home() / '.opencode' / 'bin' / 'opencode'),
            # npm/bun global
            str(Path.home() / '.bun' / 'bin' / 'opencode'),
            str(Path.home() / '.npm-global' / 'bin' / 'opencode'),
        ]

        for loc in locations:
            if Path(loc).exists() and os.access(loc, os.X_OK):
                return loc

        # Try which command
        try:
            result = subprocess.run(
                ['which', 'opencode'], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback to just "opencode" (assume in PATH)
        return 'opencode'

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close the bridge and cleanup resources."""
        # Stop all running processes
        for codebase_id in list(self._processes.keys()):
            await self.stop_agent(codebase_id)

        # Close HTTP session
        if self._session and not self._session.closed:
            await self._session.close()

    async def register_codebase(
        self,
        name: str,
        path: str,
        description: str = '',
        agent_config: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
        codebase_id: Optional[str] = None,
    ) -> RegisteredCodebase:
        """
        Register a codebase for agent work.

        Args:
            name: Display name for the codebase
            path: Absolute path to the codebase directory (on worker machine)
            description: Optional description
            agent_config: Optional OpenCode agent configuration
            worker_id: ID of the worker that owns this codebase (for remote execution)

        Returns:
            The registered codebase entry

        Note: Path validation is skipped when a worker_id is provided, as the path
        exists on the remote worker machine, not on the A2A server.
        """
        # Normalize path
        path = os.path.abspath(os.path.expanduser(path))

        # NOTE: Path validation removed - the control plane never executes locally.
        # Paths are validated by workers when they register codebases.

        # If the caller provided a specific ID and we already have it in-memory,
        # update that entry in-place.
        if codebase_id and codebase_id in self._codebases:
            codebase = self._codebases[codebase_id]
            codebase.name = name
            codebase.description = description
            codebase.agent_config = agent_config or {}
            if worker_id:
                codebase.worker_id = worker_id
                codebase.opencode_port = (
                    None  # Clear local port if it's now remote
                )
            codebase.status = AgentStatus.IDLE
            await self._save_codebase(codebase)  # Persist update

            worker_info = f' (worker: {worker_id})' if worker_id else ''
            logger.info(
                f'Updated existing codebase: {name} ({codebase_id}) at {path}{worker_info}'
            )
            return codebase

        # Check for existing codebase with same path - update instead of duplicate
        existing_id = None
        for cid, cb in self._codebases.items():
            if cb.path == path:
                existing_id = cid
                break

        if existing_id:
            # Update existing codebase instead of creating duplicate.
            # If the caller supplied a different codebase_id (e.g., from DB rehydration),
            # migrate to use that ID to stay in sync with persistent storage.
            if codebase_id and codebase_id != existing_id:
                logger.info(
                    f'register_codebase: migrating in-memory ID from {existing_id} '
                    f'to {codebase_id} (from DB) for path {path}'
                )
                # Move the codebase entry to the new ID
                codebase = self._codebases.pop(existing_id)
                codebase.id = codebase_id
                self._codebases[codebase_id] = codebase
                existing_id = codebase_id
            else:
                codebase = self._codebases[existing_id]

            codebase.name = name
            codebase.description = description
            codebase.agent_config = agent_config or {}
            if worker_id:
                codebase.worker_id = worker_id
                codebase.opencode_port = (
                    None  # Clear local port if it's now remote
                )
            codebase.status = AgentStatus.IDLE
            await self._save_codebase(codebase)  # Persist update

            worker_info = f' (worker: {worker_id})' if worker_id else ''
            logger.info(
                f'Updated existing codebase: {name} ({existing_id}) at {path}{worker_info}'
            )
            return codebase

        # Use caller-provided ID when available (e.g., when rehydrating from
        # PostgreSQL/Redis after a restart), otherwise generate a new ID.
        if not codebase_id:
            codebase_id = str(uuid.uuid4())[:8]

        codebase = RegisteredCodebase(
            id=codebase_id,
            name=name,
            path=path,
            description=description,
            agent_config=agent_config or {},
            worker_id=worker_id,
        )

        self._codebases[codebase_id] = codebase
        await self._save_codebase(codebase)  # Persist to database

        worker_info = f' (worker: {worker_id})' if worker_id else ''
        logger.info(
            f'Registered codebase: {name} ({codebase_id}) at {path}{worker_info}'
        )

        return codebase

    async def unregister_codebase(self, codebase_id: str) -> bool:
        """Remove a codebase from the registry."""
        if codebase_id in self._codebases:
            # Stop any running agent
            if codebase_id in self._processes:
                await self.stop_agent(codebase_id)

            del self._codebases[codebase_id]
            await self._delete_codebase(codebase_id)  # Remove from database
            logger.info(f'Unregistered codebase: {codebase_id}')
            return True
        return False

    def get_codebase(self, codebase_id: str) -> Optional[RegisteredCodebase]:
        """Get a registered codebase by ID."""
        return self._codebases.get(codebase_id)

    def list_codebases(self) -> List[RegisteredCodebase]:
        """List all registered codebases."""
        return list(self._codebases.values())

    def _allocate_port(self, codebase_id: str) -> int:
        """Allocate a port for an OpenCode instance."""
        if codebase_id in self._port_allocations:
            return self._port_allocations[codebase_id]

        port = self._next_port
        self._port_allocations[codebase_id] = port
        self._next_port += 1
        return port

    async def _start_opencode_server(self, codebase: RegisteredCodebase) -> int:
        """
        Start an OpenCode server for a codebase.

        Returns the port number.
        """
        port = self._allocate_port(codebase.id)

        # Build command
        cmd = [
            self.opencode_bin,
            'serve',
            '--port',
            str(port),
        ]

        logger.info(
            f'Starting OpenCode server for {codebase.name} on port {port}'
        )
        logger.debug(f'Command: {" ".join(cmd)}')

        try:
            # Start process in the codebase directory
            process = subprocess.Popen(
                cmd,
                cwd=codebase.path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, 'NO_COLOR': '1'},
            )

            self._processes[codebase.id] = process
            codebase.opencode_port = port
            await self._update_codebase_status(codebase, AgentStatus.RUNNING)

            # Wait a moment for server to start
            await asyncio.sleep(2)

            # Verify server is running
            if process.poll() is not None:
                # Process exited
                stderr = (
                    process.stderr.read().decode() if process.stderr else ''
                )
                raise RuntimeError(f'OpenCode server failed to start: {stderr}')

            logger.info(f'OpenCode server started successfully on port {port}')
            return port

        except Exception as e:
            logger.error(f'Failed to start OpenCode server: {e}')
            await self._update_codebase_status(codebase, AgentStatus.ERROR)
            raise

    async def stop_agent(self, codebase_id: str) -> bool:
        """Stop a running OpenCode agent."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return False

        process = self._processes.get(codebase_id)
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

            del self._processes[codebase_id]

        await self._update_codebase_status(codebase, AgentStatus.STOPPED)
        codebase.opencode_port = None

        # Free port allocation
        if codebase_id in self._port_allocations:
            del self._port_allocations[codebase_id]

        logger.info(f'Stopped OpenCode agent for {codebase.name}')
        return True

    async def trigger_agent(
        self,
        request: AgentTriggerRequest,
    ) -> AgentTriggerResponse:
        """
        Trigger an OpenCode agent to work on a codebase.

        Args:
            request: The trigger request with prompt and configuration

        Returns:
            Response with session ID and status
        """
        codebase = self._codebases.get(request.codebase_id)
        if not codebase:
            return AgentTriggerResponse(
                success=False,
                error=f'Codebase not found: {request.codebase_id}',
            )

        # Check if Knative is enabled - use Knative workers for task execution
        if is_knative_enabled():
            return await self._trigger_agent_knative(request, codebase)

        # For remote workers (SSE-based), create a task instead of local execution
        if codebase.worker_id:
            task = await self.create_task(
                codebase_id=request.codebase_id,
                title=request.prompt[:80]
                + ('...' if len(request.prompt) > 80 else ''),
                prompt=request.prompt,
                agent_type=request.agent,
                metadata={
                    'model': request.model,
                    'files': request.files,
                    **request.metadata,
                },
            )
            if task:
                logger.info(
                    f'Created task {task.id} for remote worker {codebase.worker_id}'
                )
                return AgentTriggerResponse(
                    success=True,
                    session_id=task.id,  # Use task ID as session ID for tracking
                    message=f'Task queued for remote worker (task: {task.id})',
                    codebase_id=request.codebase_id,
                    agent=request.agent,
                )
            else:
                return AgentTriggerResponse(
                    success=False,
                    error='Failed to create task for remote worker',
                )

        try:
            # Local execution: Ensure OpenCode server is running
            if (
                not codebase.opencode_port
                or codebase.status != AgentStatus.RUNNING
            ):
                if self.auto_start:
                    await self._start_opencode_server(codebase)
                else:
                    return AgentTriggerResponse(
                        success=False,
                        error='OpenCode server not running and auto_start is disabled',
                    )

            # Build API URL - use configured host for container->host communication
            base_url = self._get_opencode_base_url(codebase.opencode_port)

            session = await self._get_session()

            # Create a new session
            async with session.post(f'{base_url}/session') as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f'Failed to create session: {await resp.text()}'
                    )
                session_data = await resp.json()
                session_id = session_data.get('id')

            codebase.session_id = session_id
            codebase.last_triggered = datetime.utcnow()
            await self._update_codebase_status(codebase, AgentStatus.BUSY)

            # Build prompt parts
            parts = [{'type': 'text', 'text': request.prompt}]

            # Add file references if specified
            for file_path in request.files:
                full_path = os.path.join(codebase.path, file_path)
                if os.path.exists(full_path):
                    parts.append(
                        {
                            'type': 'file',
                            'url': f'file://{full_path}',
                            'filename': file_path,
                            'mime': 'text/plain',
                        }
                    )

            # Trigger prompt
            prompt_payload = {
                'sessionID': session_id,
                'parts': parts,
                'agent': request.agent,
            }

            if request.model:
                parts_model = request.model.split('/')
                if len(parts_model) == 2:
                    prompt_payload['model'] = {
                        'providerID': parts_model[0],
                        'modelID': parts_model[1],
                    }

            async with session.post(
                f'{base_url}/session/{session_id}/prompt',
                json=prompt_payload,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f'Failed to send prompt: {await resp.text()}'
                    )

            # Notify callbacks
            await self._notify_status_change(codebase)

            logger.info(
                f'Triggered agent {request.agent} on {codebase.name} (session: {session_id})'
            )

            return AgentTriggerResponse(
                success=True,
                session_id=session_id,
                message=f"Agent '{request.agent}' triggered successfully",
                codebase_id=codebase.id,
                agent=request.agent,
            )

        except Exception as e:
            logger.error(f'Failed to trigger agent: {e}')
            await self._update_codebase_status(codebase, AgentStatus.ERROR)
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=codebase.id,
            )

    async def _trigger_agent_knative(
        self,
        request: AgentTriggerRequest,
        codebase: RegisteredCodebase,
    ) -> AgentTriggerResponse:
        """
        Trigger an agent using Knative worker infrastructure.

        This method:
        1. Creates a task in PostgreSQL
        2. Ensures a Knative worker exists for the session
        3. Publishes a task CloudEvent to route to the worker
        4. Returns immediately (async execution)

        Args:
            request: The trigger request with prompt and configuration
            codebase: The registered codebase

        Returns:
            Response with session/task ID and QUEUED status
        """
        # Generate session ID (or use existing)
        session_id = request.metadata.get('session_id') or str(uuid.uuid4())[:8]
        task_id = str(uuid.uuid4())

        # Prepare model specification for CloudEvent
        model_spec = None
        if request.model:
            parts_model = request.model.split('/')
            if len(parts_model) == 2:
                model_spec = {
                    'providerID': parts_model[0],
                    'modelID': parts_model[1],
                }

        try:
            # 1. Create task in PostgreSQL (for tracking and as source of truth)
            task = await self.create_task(
                codebase_id=request.codebase_id,
                title=request.prompt[:80]
                + ('...' if len(request.prompt) > 80 else ''),
                prompt=request.prompt,
                agent_type=request.agent,
                model=request.model,
                metadata={
                    'session_id': session_id,
                    'files': request.files,
                    'knative': True,
                    **request.metadata,
                },
            )

            if not task:
                return AgentTriggerResponse(
                    success=False,
                    error='Failed to create task in database',
                    codebase_id=request.codebase_id,
                )

            # Update task with session_id
            task.session_id = session_id
            await self._save_task(task)

            # 2. Ensure Knative worker exists for this session
            worker_info = await knative_spawner.get_worker_status(session_id)

            if worker_info.status == WorkerStatus.NOT_FOUND:
                # Get tenant_id from codebase agent_config or default
                tenant_id = codebase.agent_config.get('tenant_id', 'default')

                logger.info(
                    f'Creating Knative worker for session {session_id}, '
                    f'codebase {codebase.id}'
                )

                spawn_result = await knative_spawner.create_session_worker(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    codebase_id=codebase.id,
                )

                if not spawn_result.success:
                    # Update task to failed if worker creation fails
                    await self.update_task_status(
                        task_id=task.id,
                        status=AgentTaskStatus.FAILED,
                        error=f'Failed to create Knative worker: {spawn_result.error_message}',
                    )
                    return AgentTriggerResponse(
                        success=False,
                        error=spawn_result.error_message,
                        codebase_id=request.codebase_id,
                    )

                # Store Knative service name in session metadata
                if spawn_result.service_name:
                    task.metadata['knative_service_name'] = (
                        spawn_result.service_name
                    )
                    await self._save_task(task)

                logger.info(
                    f'Created Knative worker: service={spawn_result.service_name}, '
                    f'url={spawn_result.url}'
                )

            elif worker_info.status == WorkerStatus.FAILED:
                # Worker exists but failed - try to recreate
                logger.warning(
                    f'Knative worker for session {session_id} is in failed state, '
                    f'attempting recreation'
                )
                await knative_spawner.delete_session_worker(session_id)

                tenant_id = codebase.agent_config.get('tenant_id', 'default')
                spawn_result = await knative_spawner.create_session_worker(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    codebase_id=codebase.id,
                )

                if not spawn_result.success:
                    await self.update_task_status(
                        task_id=task.id,
                        status=AgentTaskStatus.FAILED,
                        error=f'Failed to recreate Knative worker: {spawn_result.error_message}',
                    )
                    return AgentTriggerResponse(
                        success=False,
                        error=spawn_result.error_message,
                        codebase_id=request.codebase_id,
                    )

            # 3. Publish task CloudEvent for routing to worker
            # Get tenant_id from codebase config or use default
            tenant_id = codebase.agent_config.get('tenant_id', 'default')
            # Get notify_email from request metadata if provided
            notify_email = (
                request.metadata.get('notify_email')
                if hasattr(request, 'metadata')
                else None
            )

            try:
                await publish_task_event(
                    session_id=session_id,
                    task_id=task.id,
                    prompt=request.prompt,
                    agent=request.agent,
                    model=json.dumps(model_spec) if model_spec else None,
                    metadata={
                        'codebase_id': codebase.id,
                        'codebase_path': codebase.path,
                        'files': request.files,
                        **request.metadata,
                    },
                    tenant_id=tenant_id,
                    notify_email=notify_email,
                )

                logger.info(
                    f'Published task event: task_id={task.id}, session_id={session_id}'
                )

            except KnativeEventError as e:
                # Event publishing failed - update task status
                logger.error(f'Failed to publish task event: {e}')
                await self.update_task_status(
                    task_id=task.id,
                    status=AgentTaskStatus.FAILED,
                    error=f'Failed to publish task event: {e}',
                )
                return AgentTriggerResponse(
                    success=False,
                    error=str(e),
                    codebase_id=request.codebase_id,
                )

            # 4. Update task status to QUEUED
            await self.update_task_status(
                task_id=task.id,
                status=AgentTaskStatus.QUEUED,
                session_id=session_id,
            )

            # Update codebase with session info
            codebase.session_id = session_id
            codebase.last_triggered = datetime.utcnow()
            await self._save_codebase(codebase)

            return AgentTriggerResponse(
                success=True,
                session_id=session_id,
                message=f'Task queued for Knative worker (task: {task.id})',
                codebase_id=codebase.id,
                agent=request.agent,
            )

        except KnativeSpawnerError as e:
            logger.error(f'Knative spawner error: {e}')
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=request.codebase_id,
            )
        except Exception as e:
            logger.error(f'Failed to trigger agent via Knative: {e}')
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=request.codebase_id,
            )

    async def end_session(self, session_id: str) -> bool:
        """
        End a session and optionally clean up its Knative worker.

        This method:
        1. Marks the session as ended in PostgreSQL
        2. Triggers final MinIO sync (via CloudEvent)
        3. Optionally schedules worker deletion (or lets GC handle it)

        Args:
            session_id: The session ID to end

        Returns:
            True if session was ended successfully
        """
        logger.info(f'Ending session: {session_id}')

        # Find tasks associated with this session
        try:
            tasks = await self._load_tasks_from_db(status=None, limit=100)
            session_tasks = [t for t in tasks if t.session_id == session_id]

            # Mark any running tasks as cancelled
            for task in session_tasks:
                if task.status in (
                    AgentTaskStatus.PENDING,
                    AgentTaskStatus.QUEUED,
                    AgentTaskStatus.ASSIGNED,
                    AgentTaskStatus.RUNNING,
                ):
                    await self.update_task_status(
                        task_id=task.id,
                        status=AgentTaskStatus.CANCELLED,
                        error='Session ended',
                    )
                    logger.info(f'Cancelled task {task.id} due to session end')

        except Exception as e:
            logger.error(
                f'Error cancelling tasks for session {session_id}: {e}'
            )

        # If Knative is enabled, publish session end event and optionally delete worker
        if is_knative_enabled():
            try:
                # Publish session end event (for final sync, cleanup, etc.)
                from .knative_events import publish_session_event

                await publish_session_event(
                    session_id=session_id,
                    event_type='session.ended',
                    data={'reason': 'user_requested'},
                )
                logger.info(f'Published session.ended event for {session_id}')

            except Exception as e:
                logger.error(
                    f'Failed to publish session end event for {session_id}: {e}'
                )

            # Note: We don't delete the worker immediately to allow for:
            # - Final sync to complete
            # - Potential session resumption
            # The garbage collector will clean up idle workers after max_age_hours

        return True

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Fetch available models from OpenCode.

        Tries to query an active OpenCode instance. If none are running,
        it may start a temporary one or fall back to reading config.
        """
        # 1. Try to find an active OpenCode instance
        active_port = None
        for codebase in self._codebases.values():
            if (
                codebase.opencode_port
                and codebase.status == AgentStatus.RUNNING
            ):
                active_port = codebase.opencode_port
                break

        if not active_port:
            # Try default port
            active_port = self.default_port

        try:
            base_url = self._get_opencode_base_url(active_port)
            session = await self._get_session()

            async with session.get(f'{base_url}/provider') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Transform OpenCode provider/model format to A2A format
                    models = []
                    all_providers = data.get('all', [])
                    for provider in all_providers:
                        provider_id = provider.get('id')
                        provider_name = provider.get('name', provider_id)
                        for model_id, model_info in provider.get(
                            'models', {}
                        ).items():
                            models.append(
                                {
                                    'id': f'{provider_id}/{model_id}',
                                    'name': model_info.get('name', model_id),
                                    'provider': provider_name,
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

                    # Sort models: Gemini 3 Flash first, then by provider
                    models.sort(
                        key=lambda x: (
                            0 if 'gemini-3-flash' in x['id'].lower() else 1,
                            x['provider'],
                            x['name'],
                        )
                    )

                    return models
        except Exception as e:
            logger.debug(f'Failed to fetch models from OpenCode API: {e}')

        return []

    async def get_agent_status(
        self, codebase_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return None

        result = codebase.to_dict()

        # If running, try to get more info from OpenCode API
        if codebase.opencode_port and codebase.session_id:
            try:
                session = await self._get_session()
                base_url = self._get_opencode_base_url(codebase.opencode_port)

                async with session.get(
                    f'{base_url}/session/{codebase.session_id}/message',
                    params={'limit': 10},
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        result['recent_messages'] = messages

            except Exception as e:
                logger.debug(f'Could not fetch session info: {e}')

        return result

    async def send_message(
        self,
        codebase_id: str,
        message: str,
        agent: Optional[str] = None,
    ) -> AgentTriggerResponse:
        """Send an additional message to an active agent session."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return AgentTriggerResponse(
                success=False,
                error=f'Codebase not found: {codebase_id}',
            )

        if not codebase.session_id or not codebase.opencode_port:
            return AgentTriggerResponse(
                success=False,
                error='No active session for this codebase',
            )

        try:
            session = await self._get_session()
            base_url = self._get_opencode_base_url(codebase.opencode_port)

            payload = {
                'sessionID': codebase.session_id,
                'parts': [{'type': 'text', 'text': message}],
            }

            if agent:
                payload['agent'] = agent

            async with session.post(
                f'{base_url}/session/{codebase.session_id}/prompt',
                json=payload,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f'Failed to send message: {await resp.text()}'
                    )

            await self._update_codebase_status(codebase, AgentStatus.BUSY)
            codebase.last_triggered = datetime.utcnow()

            return AgentTriggerResponse(
                success=True,
                session_id=codebase.session_id,
                message='Message sent successfully',
                codebase_id=codebase.id,
            )

        except Exception as e:
            logger.error(f'Failed to send message: {e}')
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=codebase.id,
            )

    async def interrupt_agent(self, codebase_id: str) -> bool:
        """Interrupt the current agent task."""
        codebase = self._codebases.get(codebase_id)
        if (
            not codebase
            or not codebase.session_id
            or not codebase.opencode_port
        ):
            return False

        try:
            session = await self._get_session()
            base_url = self._get_opencode_base_url(codebase.opencode_port)

            async with session.post(
                f'{base_url}/session/{codebase.session_id}/interrupt'
            ) as resp:
                if resp.status == 200:
                    await self._update_codebase_status(
                        codebase, AgentStatus.RUNNING
                    )
                    logger.info(f'Interrupted agent for {codebase.name}')
                    return True

        except Exception as e:
            logger.error(f'Failed to interrupt agent: {e}')

        return False

    def on_status_change(self, callback: Callable):
        """Register a callback for status changes."""
        self._on_status_change.append(callback)

    def on_message(self, callback: Callable):
        """Register a callback for agent messages."""
        self._on_message.append(callback)

    async def _notify_status_change(self, codebase: RegisteredCodebase):
        """Notify registered callbacks of status change."""
        for callback in self._on_status_change:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(codebase)
                else:
                    callback(codebase)
            except Exception as e:
                logger.error(f'Error in status change callback: {e}')

    # ========================================
    # Task Management
    # ========================================

    async def create_task(
        self,
        codebase_id: Optional[str],
        title: str,
        prompt: str,
        agent_type: str = 'build',
        priority: int = 0,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        model_ref: Optional[str] = None,
    ) -> Optional[AgentTask]:
        """
        Create a new task for an agent.

        Special codebase_id values:
        - None: Global tasks that any worker can claim
        - '__pending__': Registration tasks that any worker can claim
        - 'global': Alias for None (deprecated, use None instead)

        Args:
            model: Full provider/model-id (e.g., 'minimax/minimax-m2.1'). Use resolve_model() to convert friendly names.
            model_ref: Requested model for routing (provider:model format). Stored for visibility.
        """
        # Normalize 'global' to None for database compatibility
        if codebase_id == 'global':
            codebase_id = None

        # Allow special '__pending__' and None codebase_id values
        # None is for global tasks that any worker can pick up
        if codebase_id is not None and codebase_id != '__pending__':
            codebase = self._codebases.get(codebase_id)
            if not codebase:
                logger.error(
                    f'Cannot create task: codebase {codebase_id} not found'
                )
                return None
            codebase_name = codebase.name
        elif codebase_id == '__pending__':
            codebase_name = 'pending-registration'
        else:
            codebase_name = 'global'

        task_metadata = dict(metadata or {})
        if model and 'model' not in task_metadata:
            task_metadata['model'] = model
        if model_ref and 'model_ref' not in task_metadata:
            task_metadata['model_ref'] = model_ref

        task_target_agent = task_metadata.get('target_agent_name')
        if not isinstance(task_target_agent, str) or not task_target_agent:
            task_target_agent = None

        task_id = str(uuid.uuid4())
        task = AgentTask(
            id=task_id,
            codebase_id=codebase_id,
            title=title,
            prompt=prompt,
            agent_type=agent_type,
            model=model,
            priority=priority,
            metadata=task_metadata,
            target_agent_name=task_target_agent,
            model_ref=model_ref,
        )

        self._tasks[task_id] = task

        # Add to codebase task list
        if codebase_id not in self._codebase_tasks:
            self._codebase_tasks[codebase_id] = []
        self._codebase_tasks[codebase_id].append(task_id)

        # Persist to database
        await self._save_task(task)

        logger.info(f'Created task {task_id} for {codebase_name}: {title}')

        # Notify callbacks
        asyncio.create_task(self._notify_task_update(task))

        return task

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID. Checks in-memory cache first, then database."""
        # Check in-memory cache first
        task = self._tasks.get(task_id)
        if task:
            return task
        # Fall back to database
        return await self._load_task_from_db(task_id)

    async def list_tasks(
        self,
        codebase_id: Optional[str] = None,
        status: Optional[AgentTaskStatus] = None,
    ) -> List[AgentTask]:
        """List tasks, optionally filtered by codebase or status. Loads from database."""
        # Load tasks from database (this also caches them in memory)
        status_str = status.value if status else None
        tasks = await self._load_tasks_from_db(
            codebase_id=codebase_id,
            status=status_str,
            limit=1000,  # Reasonable limit
        )

        # Sort by priority (desc) then created_at (asc)
        tasks.sort(key=lambda t: (-t.priority, t.created_at))

        return tasks

    async def get_next_pending_task(
        self, codebase_id: str
    ) -> Optional[AgentTask]:
        """Get the next pending task for a codebase."""
        pending = await self.list_tasks(
            codebase_id=codebase_id, status=AgentTaskStatus.PENDING
        )
        return pending[0] if pending else None

    async def update_task_status(
        self,
        task_id: str,
        status: AgentTaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> Optional[AgentTask]:
        """Update task status.

        Args:
            task_id: The task ID to update
            status: New task status
            result: Optional result data
            error: Optional error message
            session_id: Optional OpenCode session ID
            worker_id: Optional worker ID that executed this task
            model_used: Optional model that was used (may differ from requested model_ref)
        """
        task = self._tasks.get(task_id)
        if not task:
            # Task not in memory - try to load from database
            # (handles tasks created via direct DB writes, e.g., trigger endpoint)
            task = await self._load_task_from_db(task_id)
            if not task:
                return None
            # Cache it for future updates
            self._tasks[task_id] = task

        task.status = status

        # Track which worker executed this task
        if worker_id:
            task.worker_id = worker_id

        # Idempotency: workers may send multiple RUNNING updates (e.g., once
        # to claim and later to attach session_id). Preserve the original
        # started/completed timestamps.
        if status == AgentTaskStatus.RUNNING:
            if task.started_at is None:
                task.started_at = datetime.utcnow()
        elif status in (
            AgentTaskStatus.COMPLETED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.CANCELLED,
        ):
            if task.completed_at is None:
                task.completed_at = datetime.utcnow()

        # Allow workers (or the control plane) to attach the active OpenCode
        # session ID for UI deep-linking and eager message sync.
        if session_id and session_id != task.session_id:
            task.session_id = session_id

        if result:
            task.result = result
        if error:
            task.error = error

        # Persist to database
        await self._save_task(task)

        asyncio.create_task(self._notify_task_update(task))

        return task

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status not in (
            AgentTaskStatus.PENDING,
            AgentTaskStatus.ASSIGNED,
        ):
            return False

        task.status = AgentTaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()

        # Persist to database
        await self._save_task(task)

        asyncio.create_task(self._notify_task_update(task))

        return True

    def on_task_update(self, callback: Callable):
        """Register a callback for task updates."""
        self._on_task_update.append(callback)

    async def _notify_task_update(self, task: AgentTask):
        """Notify registered callbacks of task update and broadcast to SSE workers."""
        # Notify registered callbacks
        for callback in self._on_task_update:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f'Error in task update callback: {e}')

        # Broadcast to SSE workers if task is pending (new task available)
        # Skip broadcast for Knative tasks - they're routed via CloudEvents
        if task.status == AgentTaskStatus.PENDING:
            is_knative_task = (
                task.metadata.get('knative', False) if task.metadata else False
            )
            logger.info(
                f'Task {task.id} notify_task_update: metadata={task.metadata}, is_knative={is_knative_task}'
            )
            if is_knative_task:
                logger.info(
                    f'Skipping SSE broadcast for Knative task {task.id}'
                )
            else:
                try:
                    from .worker_sse import get_worker_registry

                    registry = get_worker_registry()
                    if registry:
                        await registry.broadcast_task_available(task.id)
                        logger.debug(f'Broadcast task {task.id} to SSE workers')
                except Exception as e:
                    logger.debug(
                        f'Could not broadcast task to SSE workers: {e}'
                    )

    # ========================================
    # Watch Mode (Persistent Agent Workers)
    # ========================================

    async def start_watch_mode(
        self, codebase_id: str, interval: int = 5
    ) -> bool:
        """
        Start watch mode for a codebase - agent will poll for and execute tasks.

        Args:
            codebase_id: ID of the codebase
            interval: Seconds between task checks

        Returns:
            True if watch mode started successfully
        """
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            logger.error(
                f'Cannot start watch mode: codebase {codebase_id} not found'
            )
            return False

        if codebase_id in self._watch_tasks:
            logger.warning(f'Watch mode already running for {codebase.name}')
            return True

        # For remote workers, watch mode is just a flag - the worker polls automatically
        if codebase.worker_id:
            codebase.watch_mode = True
            codebase.watch_interval = interval
            await self._update_codebase_status(codebase, AgentStatus.WATCHING)
            logger.info(
                f'Watch mode enabled for {codebase.name} (remote worker: {codebase.worker_id})'
            )
            await self._notify_status_change(codebase)
            return True

        # For local execution, start the OpenCode server if not running
        if not codebase.opencode_port or codebase.status in (
            AgentStatus.IDLE,
            AgentStatus.STOPPED,
        ):
            try:
                await self._start_opencode_server(codebase)
            except Exception as e:
                logger.error(
                    f'Failed to start OpenCode server for watch mode: {e}'
                )
                return False

        codebase.watch_mode = True
        codebase.watch_interval = interval
        await self._update_codebase_status(codebase, AgentStatus.WATCHING)

        # Start background task for local execution
        watch_task = asyncio.create_task(self._watch_loop(codebase_id))
        self._watch_tasks[codebase_id] = watch_task

        logger.info(
            f'Started watch mode for {codebase.name} (interval: {interval}s)'
        )
        await self._notify_status_change(codebase)

        return True

    async def stop_watch_mode(self, codebase_id: str) -> bool:
        """Stop watch mode for a codebase."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return False

        # For remote workers, just update the flag
        if codebase.worker_id:
            codebase.watch_mode = False
            await self._update_codebase_status(codebase, AgentStatus.IDLE)
            logger.info(
                f'Watch mode disabled for {codebase.name} (remote worker)'
            )
            await self._notify_status_change(codebase)
            return True

        # Cancel local watch task
        watch_task = self._watch_tasks.get(codebase_id)
        if watch_task:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
            del self._watch_tasks[codebase_id]

        codebase.watch_mode = False
        await self._update_codebase_status(
            codebase,
            AgentStatus.RUNNING if codebase.opencode_port else AgentStatus.IDLE,
        )

        logger.info(f'Stopped watch mode for {codebase.name}')
        await self._notify_status_change(codebase)

        return True

    async def _watch_loop(self, codebase_id: str):
        """Background loop that checks for and executes tasks."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return

        logger.info(f'Watch loop started for {codebase.name}')

        try:
            while True:
                # Check for pending tasks
                task = await self.get_next_pending_task(codebase_id)

                if task:
                    logger.info(f'Watch loop found task: {task.title}')
                    await self._execute_task(task)

                # Wait before next check
                await asyncio.sleep(codebase.watch_interval)

        except asyncio.CancelledError:
            logger.info(f'Watch loop cancelled for {codebase.name}')
            raise
        except Exception as e:
            logger.error(f'Watch loop error for {codebase.name}: {e}')
            self._update_codebase_status(codebase, AgentStatus.ERROR)

    async def _execute_task(self, task: AgentTask):
        """Execute a task using the OpenCode agent."""
        codebase = self._codebases.get(task.codebase_id)
        if not codebase:
            task.status = AgentTaskStatus.FAILED
            task.error = 'Codebase not found'
            return

        # Update task status
        task.status = AgentTaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await self._notify_task_update(task)

        # Update codebase status
        await self._update_codebase_status(codebase, AgentStatus.BUSY)
        await self._notify_status_change(codebase)

        try:
            # Create trigger request
            request = AgentTriggerRequest(
                codebase_id=task.codebase_id,
                prompt=task.prompt,
                agent=task.agent_type,
                metadata=task.metadata,
            )

            # Trigger the agent
            response = await self.trigger_agent(request)

            if response.success:
                task.session_id = response.session_id

                # Wait for agent to finish (poll status)
                await self._wait_for_agent_completion(task, codebase)

            else:
                task.status = AgentTaskStatus.FAILED
                task.error = response.error
                task.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f'Task execution failed: {e}')
            task.status = AgentTaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()

        finally:
            # Restore codebase status if in watch mode
            if codebase.watch_mode:
                await self._update_codebase_status(
                    codebase, AgentStatus.WATCHING
                )
            else:
                await self._update_codebase_status(
                    codebase, AgentStatus.RUNNING
                )

            await self._notify_status_change(codebase)
            await self._notify_task_update(task)

    async def _wait_for_agent_completion(
        self, task: AgentTask, codebase: RegisteredCodebase, timeout: int = 600
    ):
        """Wait for an agent to complete its work."""
        if not codebase.opencode_port or not task.session_id:
            return

        base_url = self._get_opencode_base_url(codebase.opencode_port)
        session = await self._get_session()

        start_time = datetime.utcnow()

        while True:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                task.status = AgentTaskStatus.FAILED
                task.error = 'Timeout waiting for agent completion'
                task.completed_at = datetime.utcnow()
                return

            try:
                # Check session status
                async with session.get(
                    f'{base_url}/session/{task.session_id}',
                    params={'directory': codebase.path},
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get('status', {})

                        # Check if agent is idle (completed)
                        if (
                            status.get('idle', False)
                            or status.get('status') == 'idle'
                        ):
                            task.status = AgentTaskStatus.COMPLETED
                            task.completed_at = datetime.utcnow()

                            # Get last message as result
                            async with session.get(
                                f'{base_url}/session/{task.session_id}/message',
                                params={'limit': 1, 'directory': codebase.path},
                            ) as msg_resp:
                                if msg_resp.status == 200:
                                    messages = await msg_resp.json()
                                    if messages:
                                        # Extract text content
                                        parts = messages[0].get('parts', [])
                                        text_parts = [
                                            p.get('text', '')
                                            for p in parts
                                            if p.get('type') == 'text'
                                        ]
                                        task.result = '\n'.join(text_parts)[
                                            :5000
                                        ]  # Limit result size

                            return

            except Exception as e:
                logger.debug(f'Error checking agent status: {e}')

            # Wait before next check
            await asyncio.sleep(2)


# Global bridge instance
_bridge: Optional[OpenCodeBridge] = None


def get_bridge() -> OpenCodeBridge:
    """Get the global OpenCode bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = OpenCodeBridge()
    return _bridge


def init_bridge(
    opencode_bin: Optional[str] = None,
    default_port: int = None,
    auto_start: bool = True,
    opencode_host: Optional[str] = None,
) -> OpenCodeBridge:
    """Initialize the global OpenCode bridge instance."""
    global _bridge
    _bridge = OpenCodeBridge(
        opencode_bin=opencode_bin,
        default_port=default_port or OPENCODE_DEFAULT_PORT,
        auto_start=auto_start,
        opencode_host=opencode_host,
    )
    return _bridge


# Backward/forward-compatible aliases.
# New code uses AgentBridge/get_agent_bridge; legacy code may use
# OpenCodeBridge/get_bridge.
AgentBridge = OpenCodeBridge


def get_agent_bridge() -> AgentBridge:
    """Get the global AgentBridge instance."""
    return get_bridge()


def init_agent_bridge(
    agent_bin: Optional[str] = None,
    default_port: int = None,
    auto_start: bool = True,
    agent_host: Optional[str] = None,
) -> AgentBridge:
    """Initialize the global AgentBridge instance."""
    return init_bridge(
        opencode_bin=agent_bin,
        default_port=default_port,
        auto_start=auto_start,
        opencode_host=agent_host,
    )
