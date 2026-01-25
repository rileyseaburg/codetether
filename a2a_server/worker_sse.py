"""
Worker SSE Task Stream - Push-based task distribution for A2A workers.

This module implements "reverse-polling" via Server-Sent Events (SSE) where workers
connect outbound to the server and receive task notifications pushed to them.

Design:
- Workers connect to GET /v1/worker/tasks/stream with their agent_name
- Server maintains a registry of connected workers
- When a task is created, server pushes it to an available connected worker
- Task claiming ensures only one worker gets each task
- Heartbeat/keepalive every 30 seconds

Security:
- Workers identify themselves via agent_name (query param or header)
- Optional Bearer token authentication via A2A_AUTH_TOKENS env var
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, Query, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Router for worker SSE endpoints
worker_sse_router = APIRouter(prefix='/v1/worker', tags=['worker-sse'])


@dataclass
class ConnectedWorker:
    """Represents a worker connected via SSE."""

    worker_id: str
    agent_name: str
    queue: asyncio.Queue
    connected_at: datetime
    last_heartbeat: datetime
    capabilities: List[str] = field(default_factory=list)
    codebases: Set[str] = field(default_factory=set)
    is_busy: bool = False  # True when worker is processing a task
    current_task_id: Optional[str] = None


class WorkerRegistry:
    """
    Registry of workers connected via SSE for push-based task distribution.

    Thread-safe via asyncio locks. Supports:
    - Worker registration/deregistration on SSE connect/disconnect
    - Task routing to available workers
    - Atomic task claiming to prevent double-assignment
    - Heartbeat tracking for connection health
    """

    def __init__(self):
        self._workers: Dict[str, ConnectedWorker] = {}
        self._lock = asyncio.Lock()
        # Track claimed tasks: task_id -> worker_id
        self._claimed_tasks: Dict[str, str] = {}
        # Callbacks for task creation events
        self._task_listeners: List[Callable] = []

    async def register_worker(
        self,
        worker_id: str,
        agent_name: str,
        queue: asyncio.Queue,
        capabilities: Optional[List[str]] = None,
        codebases: Optional[Set[str]] = None,
    ) -> ConnectedWorker:
        """Register a new SSE-connected worker."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            worker = ConnectedWorker(
                worker_id=worker_id,
                agent_name=agent_name,
                queue=queue,
                connected_at=now,
                last_heartbeat=now,
                capabilities=capabilities or [],
                codebases=codebases or set(),
            )
            self._workers[worker_id] = worker
            logger.info(
                f"Worker '{agent_name}' (id={worker_id}) connected via SSE. "
                f'Total connected: {len(self._workers)}'
            )
            return worker

    async def unregister_worker(
        self, worker_id: str
    ) -> Optional[ConnectedWorker]:
        """Unregister a disconnected worker."""
        async with self._lock:
            worker = self._workers.pop(worker_id, None)
            if worker:
                # Release any claimed tasks back to pending
                tasks_to_release = [
                    tid
                    for tid, wid in self._claimed_tasks.items()
                    if wid == worker_id
                ]
                for tid in tasks_to_release:
                    del self._claimed_tasks[tid]
                    logger.warning(
                        f'Task {tid} released due to worker disconnect (worker={worker_id})'
                    )

                logger.info(
                    f"Worker '{worker.agent_name}' (id={worker_id}) disconnected. "
                    f'Total connected: {len(self._workers)}'
                )
            return worker

    async def update_heartbeat(self, worker_id: str) -> bool:
        """Update the last heartbeat time for a worker."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.last_heartbeat = datetime.now(timezone.utc)
                return True
            return False

    async def update_worker_codebases(
        self, worker_id: str, codebases: Set[str]
    ) -> bool:
        """Update the codebases a worker can handle."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.codebases = codebases
                return True
            return False

    async def claim_task(self, task_id: str, worker_id: str) -> bool:
        """
        Atomically claim a task for a worker.

        Returns True if claim succeeded, False if task was already claimed
        or if the worker doesn't own the task's codebase.
        """
        # First, verify worker can handle this task's codebase (before acquiring lock)
        from .monitor_api import get_opencode_bridge

        bridge = get_opencode_bridge()
        if bridge:
            task = await bridge.get_task(task_id)
            if task:
                codebase_id = task.codebase_id
                # Check if this is a restricted codebase (not global/__pending__)
                if codebase_id and codebase_id not in ('global', '__pending__'):
                    # Worker must own this codebase to claim it
                    worker = self._workers.get(worker_id)
                    if worker:
                        can_handle = codebase_id in worker.codebases
                        if not can_handle:
                            logger.warning(
                                f'Worker {worker_id} ({worker.agent_name}) tried to claim task {task_id} '
                                f'for codebase {codebase_id} it does not own (worker codebases: {worker.codebases})'
                            )
                            return False

        async with self._lock:
            if task_id in self._claimed_tasks:
                existing_worker = self._claimed_tasks[task_id]
                if existing_worker == worker_id:
                    return True  # Already claimed by this worker
                return False  # Claimed by another worker

            worker = self._workers.get(worker_id)
            if not worker:
                return False

            self._claimed_tasks[task_id] = worker_id
            worker.is_busy = True
            worker.current_task_id = task_id
            logger.info(f'Task {task_id} claimed by worker {worker_id}')
            return True

    async def release_task(self, task_id: str, worker_id: str) -> bool:
        """Release a task claim (on completion or failure).

        After releasing, broadcasts any pending tasks to the now-available worker.
        """
        released = False
        worker_codebases = set()

        async with self._lock:
            if self._claimed_tasks.get(task_id) == worker_id:
                del self._claimed_tasks[task_id]
                worker = self._workers.get(worker_id)
                if worker:
                    worker.is_busy = False
                    worker.current_task_id = None
                    worker_codebases = set(worker.codebases)
                logger.info(f'Task {task_id} released by worker {worker_id}')
                released = True

        # After releasing, check for pending tasks and broadcast to newly available worker
        if released and worker_codebases:
            import asyncio

            asyncio.create_task(
                self._broadcast_pending_tasks_to_worker(
                    worker_id, worker_codebases
                )
            )

        return released

    async def _broadcast_pending_tasks_to_worker(
        self, worker_id: str, worker_codebases: set
    ) -> None:
        """Broadcast pending tasks to a worker that just became available."""
        try:
            from .monitor_api import get_opencode_bridge

            bridge = get_opencode_bridge()
            if not bridge:
                return

            # Get pending tasks for codebases this worker handles
            from .opencode_bridge import AgentTaskStatus

            pending_tasks = await bridge.list_tasks(
                status=AgentTaskStatus.PENDING
            )

            for task in pending_tasks:
                # Check if worker can handle this task's codebase
                task_codebase = task.codebase_id
                if task_codebase in worker_codebases or task_codebase in (
                    'global',
                    '__pending__',
                ):
                    task_data = {
                        'id': task.id,
                        'codebase_id': task.codebase_id,
                        'title': task.title,
                        'prompt': task.prompt,
                        'agent_type': task.agent_type,
                        'priority': task.priority,
                        'metadata': task.metadata,
                        'model': task.model,
                        'target_agent_name': getattr(
                            task, 'target_agent_name', None
                        ),
                        'created_at': task.created_at.isoformat()
                        if task.created_at
                        else None,
                    }

                    if await self.push_task_to_worker(worker_id, task_data):
                        logger.info(
                            f'Broadcast pending task {task.id} to newly available worker {worker_id}'
                        )
                        # Only send one task at a time - worker will release and get next
                        break
        except Exception as e:
            logger.warning(
                f'Error broadcasting pending tasks to worker {worker_id}: {e}'
            )

    async def get_available_workers(
        self,
        codebase_id: Optional[str] = None,
        target_agent_name: Optional[str] = None,
        target_worker_id: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
    ) -> List[ConnectedWorker]:
        """
        Get workers available to accept a new task.

        Filters by:
        - Not currently busy
        - Handles the specified codebase (workers must explicitly register codebases)
        - Optionally: has required capabilities
        - Optionally: matches target_agent_name (for agent-targeted routing)
        - Optionally: matches target_worker_id (for worker-targeted routing)

        IMPORTANT: Workers with no registered codebases will ONLY receive
        'global' or '__pending__' tasks. This prevents cross-server task leakage
        where a worker picks up tasks for codebases it doesn't have access to.

        Agent Targeting:
        - If target_agent_name is set, ONLY notify workers with that agent_name
        - If target_worker_id is set, ONLY notify the specific worker
        - This reduces noise/wakeups for targeted tasks
        - Claim-time filtering is the real enforcement; this is for efficiency
        """
        async with self._lock:
            available = []
            for worker in self._workers.values():
                if worker.is_busy:
                    continue

                # Worker ID targeting filter - most specific, check first
                if target_worker_id:
                    if worker.worker_id != target_worker_id:
                        continue

                # Agent targeting filter (notify-time filtering for efficiency)
                # If task is targeted at a specific agent, only notify that agent
                if target_agent_name:
                    if worker.agent_name != target_agent_name:
                        continue

                # Check codebase filter
                if codebase_id:
                    # Special codebase IDs that any worker can handle
                    if codebase_id in ('global', '__pending__'):
                        pass  # Any worker can handle these
                    elif codebase_id in worker.codebases:
                        pass  # Worker explicitly registered this codebase
                    elif await self._worker_owns_codebase(
                        worker.worker_id, codebase_id
                    ):
                        pass  # Codebase registry says this worker handles it
                    else:
                        # Task is for a specific codebase the worker doesn't have
                        # Skip this worker even if it has no codebases registered
                        # (empty codebases does NOT mean "can handle anything")
                        continue

                # Check capabilities filter
                if required_capabilities:
                    if not all(
                        cap in worker.capabilities
                        for cap in required_capabilities
                    ):
                        continue

                available.append(worker)

            return available

    async def _worker_owns_codebase(
        self, worker_id: str, codebase_id: str
    ) -> bool:
        """Check if the codebase registry says this worker handles the codebase."""
        try:
            # First try in-memory bridge cache
            from .opencode_bridge import get_bridge

            bridge = get_bridge()
            codebase = bridge.get_codebase(codebase_id)
            if codebase and codebase.worker_id == worker_id:
                return True

            # Fall back to database query
            from . import database as db

            codebase_data = await db.db_get_codebase(codebase_id)
            if codebase_data and codebase_data.get('worker_id') == worker_id:
                return True
        except Exception as e:
            logger.debug(f'Error checking codebase ownership: {e}')
        return False

    async def get_worker(self, worker_id: str) -> Optional[ConnectedWorker]:
        """Get a specific worker by ID."""
        async with self._lock:
            return self._workers.get(worker_id)

    async def list_workers(self) -> List[Dict[str, Any]]:
        """List all connected workers."""
        async with self._lock:
            return [
                {
                    'worker_id': w.worker_id,
                    'agent_name': w.agent_name,
                    'connected_at': w.connected_at.isoformat(),
                    'last_heartbeat': w.last_heartbeat.isoformat(),
                    'is_busy': w.is_busy,
                    'current_task_id': w.current_task_id,
                    'capabilities': w.capabilities,
                    'codebases': list(w.codebases),
                }
                for w in self._workers.values()
            ]

    async def push_task_to_worker(
        self,
        worker_id: str,
        task: Dict[str, Any],
    ) -> bool:
        """
        Push a task notification to a specific worker.

        Returns True if the message was queued successfully.
        """
        async with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return False

            try:
                event = {
                    'event': 'task_available',
                    'data': task,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                }
                await worker.queue.put(event)
                return True
            except Exception as e:
                logger.error(f'Failed to push task to worker {worker_id}: {e}')
                return False

    async def broadcast_task(
        self,
        task: Dict[str, Any],
        codebase_id: Optional[str] = None,
        target_agent_name: Optional[str] = None,
        target_worker_id: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Broadcast a task to all available workers that can handle it.

        For targeted tasks (target_agent_name or target_worker_id set), only notifies the specific worker.
        This is notify-time filtering for efficiency; claim-time is the real enforcement.

        Returns list of worker_ids that received the notification.
        """
        # Check metadata for target_worker_id if not passed directly
        if not target_worker_id and task.get('metadata'):
            target_worker_id = task['metadata'].get('target_worker_id')

        available = await self.get_available_workers(
            codebase_id=codebase_id,
            target_agent_name=target_agent_name,
            target_worker_id=target_worker_id,
            required_capabilities=required_capabilities,
        )
        notified = []

        for worker in available:
            if await self.push_task_to_worker(worker.worker_id, task):
                notified.append(worker.worker_id)

        routing_info = ''
        if target_worker_id:
            routing_info = f' (targeted at worker {target_worker_id})'
        elif target_agent_name:
            routing_info = f' (targeted at agent {target_agent_name})'

        logger.info(
            f'Task {task.get("id", "unknown")} broadcast to {len(notified)} workers{routing_info}'
        )
        return notified

    async def broadcast_task_available(
        self,
        task_id: str,
        codebase_id: Optional[str] = None,
        target_agent_name: Optional[str] = None,
    ) -> List[str]:
        """
        Broadcast that a task is available to workers that can handle it.

        This fetches the task details and broadcasts to appropriate workers.
        Used when a task is created or becomes available for claiming.

        Args:
            task_id: The ID of the task that's available
            codebase_id: Optional codebase ID for routing
            target_agent_name: Optional specific agent to target

        Returns:
            List of worker_ids that received the notification
        """
        try:
            # Fetch task details from the bridge
            from .monitor_api import get_opencode_bridge

            bridge = get_opencode_bridge()
            if not bridge:
                logger.warning(
                    f'Cannot broadcast task {task_id}: bridge not available'
                )
                return []

            task = await bridge.get_task(task_id)
            if not task:
                logger.warning(
                    f'Cannot broadcast task {task_id}: task not found'
                )
                return []

            # Use getattr for backwards compatibility with AgentTask objects
            # that may not have target_agent_name attribute
            task_target_agent = getattr(task, 'target_agent_name', None)

            task_data = {
                'id': task.id,
                'codebase_id': task.codebase_id,
                'title': task.title,
                'prompt': task.prompt,
                'agent_type': task.agent_type,
                'priority': task.priority,
                'metadata': task.metadata,
                'model': task.model,
                'target_agent_name': task_target_agent,
                'created_at': task.created_at.isoformat()
                if task.created_at
                else None,
            }

            return await self.broadcast_task(
                task_data,
                codebase_id=codebase_id or task.codebase_id,
                target_agent_name=target_agent_name or task_target_agent,
            )
        except Exception as e:
            logger.error(f'Error broadcasting task {task_id}: {e}')
            return []

    def add_task_listener(self, callback: Callable) -> None:
        """Add a callback to be notified when tasks are created."""
        self._task_listeners.append(callback)

    def remove_task_listener(self, callback: Callable) -> None:
        """Remove a task listener callback."""
        if callback in self._task_listeners:
            self._task_listeners.remove(callback)

    async def notify_task_created(self, task: Dict[str, Any]) -> None:
        """Notify all listeners that a new task was created."""
        for callback in self._task_listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f'Error in task listener: {e}')


# Global worker registry singleton
_worker_registry: Optional[WorkerRegistry] = None


def get_worker_registry() -> WorkerRegistry:
    """Get or create the global worker registry."""
    global _worker_registry
    if _worker_registry is None:
        _worker_registry = WorkerRegistry()
    return _worker_registry


@lru_cache(maxsize=1)
def _get_auth_tokens_set() -> set:
    """Return the set of configured auth tokens (values only)."""
    raw = os.environ.get('A2A_AUTH_TOKENS')
    if not raw:
        return set()
    tokens: set = set()
    for pair in raw.split(','):
        pair = pair.strip()
        if not pair:
            continue
        if ':' in pair:
            _, token = pair.split(':', 1)
            token = token.strip()
            if token:
                tokens.add(token)
        else:
            # Single token without name prefix
            tokens.add(pair)
    return tokens


def _verify_auth(request: Request) -> Optional[str]:
    """
    Verify Bearer token if authentication is configured.

    Returns the token if valid, raises HTTPException if invalid,
    returns None if no auth is configured.
    """
    tokens = _get_auth_tokens_set()
    if not tokens:
        return None  # Auth not configured, allow all

    auth = (
        request.headers.get('authorization')
        or request.headers.get('Authorization')
        or ''
    )
    if not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing Bearer token')

    token = auth.removeprefix('Bearer ').strip()
    if not token or token not in tokens:
        raise HTTPException(status_code=403, detail='Invalid token')

    return token


class TaskClaimRequest(BaseModel):
    """Request to claim a task."""

    task_id: str


class TaskReleaseRequest(BaseModel):
    """Request to release a task."""

    task_id: str
    status: str = 'completed'  # completed, failed, cancelled
    result: Optional[str] = None
    error: Optional[str] = None


class CodebaseUpdateRequest(BaseModel):
    """Request to update worker's codebase list."""

    codebases: List[str]


@worker_sse_router.get('/tasks/stream')
async def worker_task_stream(
    request: Request,
    agent_name: Optional[str] = Query(None, description='Worker agent name'),
    worker_id: Optional[str] = Query(
        None, description='Worker ID (optional, generated if not provided)'
    ),
    x_agent_name: Optional[str] = Header(None, alias='X-Agent-Name'),
    x_worker_id: Optional[str] = Header(None, alias='X-Worker-ID'),
    x_capabilities: Optional[str] = Header(None, alias='X-Capabilities'),
    x_codebases: Optional[str] = Header(None, alias='X-Codebases'),
):
    """
    SSE endpoint for workers to receive task notifications.

    Workers connect to this endpoint and receive:
    - `task_available` events when new tasks are created
    - `heartbeat` events every 30 seconds
    - `task_claimed` confirmation when a task is successfully claimed

    Headers:
    - Authorization: Bearer <token> (required if A2A_AUTH_TOKENS is set)
    - X-Agent-Name: Worker's agent name (alternative to query param)
    - X-Worker-ID: Stable worker ID (optional)
    - X-Capabilities: Comma-separated list of capabilities
    - X-Codebases: Comma-separated list of codebase IDs this worker handles

    Query params:
    - agent_name: Worker's agent name
    - worker_id: Stable worker ID (optional)

    Events sent to worker:
    ```
    event: connected
    data: {"worker_id": "...", "message": "Connected to task stream"}

    event: task_available
    data: {"id": "...", "title": "...", "codebase_id": "...", ...}

    event: heartbeat
    data: {"timestamp": "..."}
    ```
    """
    # Verify authentication
    _verify_auth(request)

    # Resolve agent_name from query param or header
    resolved_agent_name = agent_name or x_agent_name
    if not resolved_agent_name:
        raise HTTPException(
            status_code=400,
            detail='agent_name is required (query param or X-Agent-Name header)',
        )

    # Resolve worker_id (generate if not provided)
    resolved_worker_id = worker_id or x_worker_id or str(uuid.uuid4())[:12]

    # Parse capabilities and codebases from headers
    capabilities = []
    if x_capabilities:
        capabilities = [
            c.strip() for c in x_capabilities.split(',') if c.strip()
        ]

    codebases = set()
    if x_codebases:
        codebases = {c.strip() for c in x_codebases.split(',') if c.strip()}

    registry = get_worker_registry()

    async def event_generator():
        """Generate SSE events for the connected worker."""
        queue: asyncio.Queue = asyncio.Queue()
        worker = None

        try:
            # Register this worker
            worker = await registry.register_worker(
                worker_id=resolved_worker_id,
                agent_name=resolved_agent_name,
                queue=queue,
                capabilities=capabilities,
                codebases=codebases,
            )

            # Send connection confirmation
            connect_event = {
                'event': 'connected',
                'worker_id': resolved_worker_id,
                'agent_name': resolved_agent_name,
                'message': 'Connected to task stream',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            yield f'event: connected\ndata: {json.dumps(connect_event)}\n\n'

            # Send any pending tasks to the newly connected worker
            try:
                from .monitor_api import get_opencode_bridge
                from .opencode_bridge import AgentTaskStatus

                bridge = get_opencode_bridge()
                if bridge:
                    # Get all pending tasks
                    pending_tasks = await bridge.list_tasks(
                        status=AgentTaskStatus.PENDING
                    )

                    # Filter tasks that this worker can handle (based on codebases)
                    worker_codebases = codebases or set()
                    sent_count = 0

                    for task in pending_tasks:
                        task_codebase = task.codebase_id
                        # Worker can handle task if:
                        # 1. Task has no specific codebase (global/__pending__)
                        # 2. Worker has the task's codebase in their list
                        # NOTE: Workers with no codebases can ONLY handle global/__pending__ tasks
                        # This prevents cross-server task leakage
                        can_handle = (
                            task_codebase in ('__pending__', 'global')
                            or task_codebase in worker_codebases
                        )

                        if can_handle:
                            task_data = {
                                'id': task.id,
                                'codebase_id': task.codebase_id,
                                'title': task.title,
                                'prompt': task.prompt,
                                'agent_type': task.agent_type,
                                'priority': task.priority,
                                'metadata': task.metadata,
                                'model': task.model,
                                'created_at': task.created_at.isoformat()
                                if task.created_at
                                else None,
                            }
                            yield f'event: task_available\ndata: {json.dumps(task_data)}\n\n'
                            sent_count += 1

                    if sent_count > 0:
                        logger.info(
                            f'Sent {sent_count} pending tasks to worker {resolved_worker_id} on connect'
                        )
            except Exception as e:
                logger.warning(f'Failed to send pending tasks on connect: {e}')

            # Main event loop
            heartbeat_interval = 30  # seconds
            last_heartbeat = asyncio.get_event_loop().time()

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(
                        f'Worker {resolved_worker_id} client disconnected'
                    )
                    break

                try:
                    # Wait for events with timeout for heartbeat
                    current_time = asyncio.get_event_loop().time()
                    timeout = max(
                        0.1,
                        heartbeat_interval - (current_time - last_heartbeat),
                    )

                    try:
                        event = await asyncio.wait_for(
                            queue.get(), timeout=timeout
                        )

                        # Format and send the event
                        event_type = event.get('event', 'message')
                        event_data = event.get('data', event)

                        yield f'event: {event_type}\ndata: {json.dumps(event_data)}\n\n'

                    except asyncio.TimeoutError:
                        pass  # No event, check if heartbeat needed

                    # Send heartbeat if interval elapsed
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        heartbeat_data = {
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'worker_id': resolved_worker_id,
                        }
                        yield f'event: heartbeat\ndata: {json.dumps(heartbeat_data)}\n\n'
                        last_heartbeat = current_time
                        await registry.update_heartbeat(resolved_worker_id)

                except asyncio.CancelledError:
                    logger.info(f'Worker {resolved_worker_id} stream cancelled')
                    break
                except Exception as e:
                    logger.error(
                        f'Error in worker stream {resolved_worker_id}: {e}'
                    )
                    break

        finally:
            # Unregister worker on disconnect
            if worker:
                await registry.unregister_worker(resolved_worker_id)

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@worker_sse_router.post('/tasks/claim')
async def claim_task(
    request: Request,
    claim: TaskClaimRequest,
    worker_id: Optional[str] = Query(None),
    x_worker_id: Optional[str] = Header(None, alias='X-Worker-ID'),
):
    """
    Claim a task for processing.

    Workers call this endpoint after receiving a task_available event
    to atomically claim the task. This prevents multiple workers from
    processing the same task.

    Returns 200 if claim succeeded, 409 if task already claimed.
    """
    _verify_auth(request)

    resolved_worker_id = worker_id or x_worker_id
    if not resolved_worker_id:
        raise HTTPException(
            status_code=400,
            detail='worker_id is required (query param or X-Worker-ID header)',
        )

    registry = get_worker_registry()

    success = await registry.claim_task(claim.task_id, resolved_worker_id)

    if success:
        return {
            'success': True,
            'task_id': claim.task_id,
            'worker_id': resolved_worker_id,
            'message': 'Task claimed successfully',
        }
    else:
        raise HTTPException(
            status_code=409,
            detail=f'Task {claim.task_id} already claimed by another worker',
        )


@worker_sse_router.post('/tasks/release')
async def release_task(
    request: Request,
    release: TaskReleaseRequest,
    worker_id: Optional[str] = Query(None),
    x_worker_id: Optional[str] = Header(None, alias='X-Worker-ID'),
):
    """
    Release a task after completion or failure.

    Workers call this endpoint when they finish processing a task
    to release the claim and report the result.
    """
    _verify_auth(request)

    resolved_worker_id = worker_id or x_worker_id
    if not resolved_worker_id:
        raise HTTPException(
            status_code=400,
            detail='worker_id is required (query param or X-Worker-ID header)',
        )

    registry = get_worker_registry()

    success = await registry.release_task(release.task_id, resolved_worker_id)

    if success:
        return {
            'success': True,
            'task_id': release.task_id,
            'worker_id': resolved_worker_id,
            'status': release.status,
            'message': 'Task released successfully',
        }
    else:
        raise HTTPException(
            status_code=404,
            detail=f'Task {release.task_id} not claimed by worker {resolved_worker_id}',
        )


@worker_sse_router.put('/codebases')
async def update_worker_codebases(
    request: Request,
    update: CodebaseUpdateRequest,
    worker_id: Optional[str] = Query(None),
    x_worker_id: Optional[str] = Header(None, alias='X-Worker-ID'),
):
    """
    Update the list of codebases a worker can handle.

    Workers call this endpoint after registering new codebases
    to update the server's routing table.
    """
    _verify_auth(request)

    resolved_worker_id = worker_id or x_worker_id
    if not resolved_worker_id:
        raise HTTPException(
            status_code=400,
            detail='worker_id is required (query param or X-Worker-ID header)',
        )

    registry = get_worker_registry()

    success = await registry.update_worker_codebases(
        resolved_worker_id, set(update.codebases)
    )

    if success:
        return {
            'success': True,
            'worker_id': resolved_worker_id,
            'codebases': update.codebases,
            'message': 'Codebases updated successfully',
        }
    else:
        raise HTTPException(
            status_code=404,
            detail=f'Worker {resolved_worker_id} not found (not connected via SSE?)',
        )


@worker_sse_router.get('/connected')
async def list_connected_workers(request: Request):
    """
    List all workers currently connected via SSE.

    Returns information about each connected worker including
    their capabilities, codebases, and current status.
    """
    _verify_auth(request)

    registry = get_worker_registry()
    workers = await registry.list_workers()

    return {
        'workers': workers,
        'count': len(workers),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


@worker_sse_router.get('/connected/{worker_id}')
async def get_connected_worker(
    request: Request,
    worker_id: str,
):
    """Get details about a specific connected worker."""
    _verify_auth(request)

    registry = get_worker_registry()
    worker = await registry.get_worker(worker_id)

    if not worker:
        raise HTTPException(
            status_code=404,
            detail=f'Worker {worker_id} not found or not connected',
        )

    return {
        'worker_id': worker.worker_id,
        'agent_name': worker.agent_name,
        'connected_at': worker.connected_at.isoformat(),
        'last_heartbeat': worker.last_heartbeat.isoformat(),
        'is_busy': worker.is_busy,
        'current_task_id': worker.current_task_id,
        'capabilities': worker.capabilities,
        'codebases': list(worker.codebases),
    }


# ============================================================================
# Integration helpers for task creation
# ============================================================================


async def notify_workers_of_new_task(task: Dict[str, Any]) -> List[str]:
    """
    Notify connected workers of a new task.

    This function should be called when a new task is created to push
    it to available workers via SSE.

    Supports agent-targeted routing:
    - If task has target_agent_name, only notifies that specific agent
    - If task has required_capabilities, only notifies capable workers

    Returns list of worker_ids that received the notification.
    """
    registry = get_worker_registry()
    codebase_id = task.get('codebase_id')
    target_agent_name = task.get('target_agent_name')
    required_capabilities = task.get('required_capabilities')

    # Parse required_capabilities if it's a JSON string
    if isinstance(required_capabilities, str):
        import json

        try:
            required_capabilities = json.loads(required_capabilities)
        except (json.JSONDecodeError, TypeError):
            required_capabilities = None

    return await registry.broadcast_task(
        task,
        codebase_id=codebase_id,
        target_agent_name=target_agent_name,
        required_capabilities=required_capabilities,
    )


def setup_task_creation_hook(opencode_bridge) -> None:
    """
    Set up a hook to notify workers when tasks are created.

    This should be called during server initialization to connect
    the task queue to the SSE push system.
    """
    registry = get_worker_registry()

    async def on_task_created(task: Dict[str, Any]):
        await notify_workers_of_new_task(task)

    registry.add_task_listener(on_task_created)
    logger.info('Task creation hook installed for SSE worker notifications')
