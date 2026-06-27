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
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Request, Query, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .task_routing import (
    is_clone_task,
    is_targeted_clone_task,
    target_agent_mismatch,
)
from .worker_claim_routing import (
    db_worker_agent_name as _db_worker_agent_name,
    db_worker_capabilities as _db_worker_capabilities,
    db_worker_recent as _db_worker_recent,
    has_persistent_workspace_capability as _has_persistent_workspace_capability,
    normalize_capabilities as _normalize_capabilities,
)
from .worker_task_run_claims import (
    claim_task_run_for_worker as _claim_task_run_for_worker,
    mirror_release_to_task_run as _mirror_release_to_task_run,
)
from .worker_persistent_claim_loop import (
    start_persistent_claim_loop as _start_persistent_claim_loop,
    stop_persistent_claim_loop,
)
from .worker_auth import verify_auth as _verify_auth
from .worker_progress_routes import worker_progress_router
from .stream_emit import format_event
from .sequencer_store import SequencerStore
from .stream_resume_handshake import resume_frames
from .worker_queue import make_worker_queue, try_enqueue

logger = logging.getLogger(__name__)

# Router for worker SSE endpoints
worker_sse_router = APIRouter(prefix='/v1/worker', tags=['worker-sse'])
worker_sse_router.include_router(worker_progress_router)


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
        # Per-worker sequencers persist across reconnects for replay.
        self._sequencers = SequencerStore()

    def sequencer_for(self, worker_id: str):
        """Return the persistent sequencer for a worker (cross-connection)."""
        return self._sequencers.get_or_create(worker_id)

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
        """Update the last heartbeat time for a worker (in-memory and DB)."""
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.last_heartbeat = datetime.now(timezone.utc)
                # Persist to DB so task_reaper sees an active worker
                asyncio.create_task(self._persist_heartbeat(worker_id))
                return True
            return False

    async def _persist_heartbeat(self, worker_id: str) -> None:
        """Fire-and-forget DB write to keep workers.last_seen current."""
        try:
            from . import database as db

            await db.db_update_worker_heartbeat(worker_id)
        except Exception as e:
            logger.debug(f'Failed to persist heartbeat for {worker_id}: {e}')

    async def _lookup_worker_agent_name(self, worker_id: str) -> Optional[str]:
        """Resolve a worker's agent name from durable state.

        SSE connections are stored in-memory per API replica. A polling claim can
        land on a replica that does not hold the worker's stream, so targeted
        claim checks must not depend exclusively on the local registry.
        """
        try:
            from . import database as db

            worker = await db.db_get_worker(worker_id)
            if not worker:
                return None
            name = str(worker.get('name') or '').strip()
            return name or None
        except Exception as e:
            logger.debug(
                f'Failed to look up agent name for worker {worker_id}: {e}'
            )
            return None

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
        from .agent_bridge import get_bridge as get_agent_bridge

        bridge = get_agent_bridge()
        if bridge:
            task = await bridge.get_task(task_id)
            if task:
                task_metadata = task.metadata or {}
                target_worker_id = str(
                    task_metadata.get('target_worker_id') or ''
                ).strip()
                worker = await self.get_worker(worker_id)
                worker_agent_name = (
                    worker.agent_name
                    if worker
                    else await self._lookup_worker_agent_name(worker_id)
                )
                worker_capabilities = (
                    _normalize_capabilities(worker.capabilities)
                    if worker
                    else await _db_worker_capabilities(worker_id)
                )
                persistent_worker = _has_persistent_workspace_capability(
                    worker_capabilities
                )
                if target_worker_id and target_worker_id != worker_id:
                    if not persistent_worker or await _db_worker_recent(target_worker_id):
                        logger.debug(
                            f'Worker {worker_id} skipped task {task_id} '
                            f'(target_worker_id={target_worker_id})'
                        )
                        return False
                    logger.warning(
                        f'Worker {worker_id} recovering task {task_id} from stale '
                        f'target_worker_id={target_worker_id}'
                    )
                worker_agent_name = worker.agent_name if worker else None
                if not worker_agent_name:
                    worker_agent_name = await _db_worker_agent_name(worker_id)
                task_target_agent = getattr(
                    task, 'target_agent_name', None
                ) or task_metadata.get('target_agent_name')
                if target_agent_mismatch(worker_agent_name, task_target_agent):
                    logger.debug(
                        f'Worker {worker_id} skipped task {task_id} '
                        f'(agent_name={worker_agent_name}, '
                        f'target_agent_name={task_target_agent})'
                    )
                    return False

                required_capabilities = _normalize_capabilities(
                    task_metadata.get('required_capabilities')
                    or getattr(task, 'required_capabilities', None)
                )
                if required_capabilities:
                    if not all(
                        cap in worker_capabilities
                        for cap in required_capabilities
                    ):
                        logger.debug(
                            f'Worker {worker_id} skipped task {task_id} '
                            f'(required_capabilities={required_capabilities}, '
                            f'worker_capabilities={worker_capabilities})'
                        )
                        return False

                codebase_id = task.codebase_id
                # Clone/refresh tasks bypass codebase ownership — the whole
                # point is to CREATE the workspace, so no worker owns it yet.
                task_agent_type = getattr(task, 'agent_type', None) or (
                    task_metadata.get('agent_type')
                )
                if is_clone_task(task_agent_type):
                    logger.info(
                        f'Clone task {task_id} (codebase {codebase_id}) — '
                        f'skipping codebase affinity for worker {worker_id}'
                    )
                    # Fall through to the claim lock below
                elif codebase_id and codebase_id not in (
                    'global',
                    '__pending__',
                ):
                    stable_persistent_route = (
                        bool(task_target_agent)
                        and task_target_agent == worker_agent_name
                        and _has_persistent_workspace_capability(required_capabilities)
                        and persistent_worker
                    )
                    if stable_persistent_route:
                        logger.info(
                            f'Task {task_id} targeted to persistent agent '
                            f'{worker_agent_name}; skipping stale codebase affinity '
                            f'for codebase {codebase_id}'
                        )
                        # Fall through to the claim lock below.
                    else:
                        if not worker:
                            # Worker not SSE-connected; allow claim anyway so
                            # polling-only / reconnecting workers aren't locked out.
                            logger.debug(
                                f'Worker {worker_id} not in SSE registry, '
                                f'allowing claim attempt for task {task_id}'
                            )
                        else:
                            can_handle = codebase_id in worker.codebases
                            if not can_handle:
                                can_handle = await self._worker_owns_codebase(
                                    worker_id, codebase_id
                                )
                            if not can_handle:
                                # Check if ANY connected worker owns this codebase;
                                # if not, the codebase has a stale worker_id and we
                                # should let any worker pick it up rather than
                                # leaving the task stuck forever.
                                owner_connected = False
                                async with self._lock:
                                    for w in self._workers.values():
                                        if codebase_id in w.codebases:
                                            owner_connected = True
                                            break
                                if not owner_connected:
                                    owner_connected = await self._any_connected_worker_owns_codebase(
                                        codebase_id
                                    )

                                if owner_connected:
                                    logger.debug(
                                        f'Worker {worker_id} ({worker.agent_name}) skipped task {task_id} '
                                        f'for codebase {codebase_id} (worker codebases: {worker.codebases})'
                                    )
                                    return False
                                else:
                                    logger.warning(
                                        f'No connected worker owns codebase {codebase_id} — '
                                        f'allowing worker {worker_id} ({worker.agent_name}) '
                                        f'to claim orphaned task {task_id}'
                                    )

        async with self._lock:
            if task_id in self._claimed_tasks:
                existing_worker = self._claimed_tasks[task_id]
                if existing_worker == worker_id:
                    return True  # Already claimed by this worker

                # If the claiming worker is no longer connected, auto-release
                # the stale claim so another worker can pick up the task.
                if existing_worker not in self._workers:
                    logger.warning(
                        f'Task {task_id} was claimed by disconnected worker '
                        f'{existing_worker} — auto-releasing stale claim'
                    )
                    del self._claimed_tasks[task_id]
                    # Also reset the task status in the DB back to pending
                    try:
                        from . import database as db

                        pool = await db.get_pool()
                        if pool:
                            async with pool.acquire() as conn:
                                await conn.execute(
                                    "UPDATE tasks SET status = 'pending', "
                                    'worker_id = NULL, started_at = NULL '
                                    "WHERE id = $1 AND status = 'running'",
                                    task_id,
                                )
                    except Exception as e:
                        logger.debug(
                            f'Failed to reset task {task_id} in DB: {e}'
                        )
                    # Fall through to let the requesting worker claim it
                else:
                    return False  # Claimed by a connected worker

            self._claimed_tasks[task_id] = worker_id
            worker = self._workers.get(worker_id)
            if worker:
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
            from .agent_bridge import get_bridge as get_agent_bridge

            bridge = get_agent_bridge()
            if not bridge:
                return

            # Get pending tasks for codebases this worker handles
            from .agent_bridge import AgentTaskStatus

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
                        'model_ref': getattr(task, 'model_ref', None)
                        or (task.metadata or {}).get('model_ref'),
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
        task_agent_type: Optional[str] = None,
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
        - This reduces unnecessary notifications for targeted tasks
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
                    elif is_targeted_clone_task(
                        task_agent_type, target_agent_name, target_worker_id
                    ):
                        pass
                    elif codebase_id in worker.codebases:
                        pass  # Worker explicitly registered this codebase
                    elif (
                        target_agent_name
                        and worker.agent_name == target_agent_name
                        and _has_persistent_workspace_capability(
                            required_capabilities or []
                        )
                        and _has_persistent_workspace_capability(worker.capabilities)
                    ):
                        pass
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
            from .agent_bridge import get_bridge

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

    async def _any_connected_worker_owns_codebase(
        self, codebase_id: str
    ) -> bool:
        """Check if any currently connected SSE worker owns this codebase in the DB."""
        try:
            from .agent_bridge import get_bridge

            bridge = get_bridge()
            codebase = bridge.get_codebase(codebase_id)
            if codebase and codebase.worker_id:
                async with self._lock:
                    return codebase.worker_id in self._workers

            from . import database as db

            codebase_data = await db.db_get_codebase(codebase_id)
            if codebase_data and codebase_data.get('worker_id'):
                async with self._lock:
                    return codebase_data['worker_id'] in self._workers
        except Exception as e:
            logger.debug(f'Error checking connected codebase owners: {e}')
        return False

    async def get_worker(self, worker_id: str) -> Optional[ConnectedWorker]:
        """Get a specific worker by ID."""
        async with self._lock:
            return self._workers.get(worker_id)

    async def list_idle_persistent_workers(self) -> List[ConnectedWorker]:
        """Return connected, idle workers eligible for durable FF claims.

        Some deployed Rust workers register capabilities through the durable
        /v1/agent/workers/register endpoint but do not repeat them on the SSE
        stream headers. Fall back to the persisted worker row so the durable
        claim bridge can still recognize harvester/persistent workers.
        """
        async with self._lock:
            workers = [worker for worker in self._workers.values() if not worker.is_busy]

        eligible: List[ConnectedWorker] = []
        for worker in workers:
            capabilities = list(worker.capabilities or [])
            if not capabilities:
                capabilities = await _db_worker_capabilities(worker.worker_id)
                if capabilities:
                    worker.capabilities = capabilities
            if 'knative' in capabilities:
                continue
            if (
                'persistent' in capabilities
                or 'persistent-workspace' in capabilities
                or 'persistent_workspace' in capabilities
                or 'harvester' in capabilities
            ):
                eligible.append(worker)
        return eligible

    async def claimed_task_ids(self) -> Set[str]:
        """Return task IDs currently held by the in-memory claim registry."""
        async with self._lock:
            return set(self._claimed_tasks)

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
                return try_enqueue(worker.queue, event, worker_id)
            except Exception as e:
                logger.error(f'Failed to push task to worker {worker_id}: {e}')
                return False

    async def push_progress(
        self, worker_id: str, data: Dict[str, Any]
    ) -> bool:
        """Push a sequenced `progress` event to a specific worker.

        Unlike `push_task_to_worker` (advisory `task_available`), progress is a
        Class B event: it carries an id and is retained in the replay ring.
        """
        async with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return False
            return try_enqueue(
                worker.queue, {'event': 'progress', 'data': data}, worker_id
            )

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

        If the task has a worker_personality, the matching worker_profile's permission
        scoping (allowed_tools, allowed_paths, allowed_namespaces) is injected into
        the task metadata so the agent binary can enforce least-privilege access.

        Returns list of worker_ids that received the notification.
        """
        # Check metadata for target_worker_id if not passed directly
        if not target_worker_id and task.get('metadata'):
            target_worker_id = task['metadata'].get('target_worker_id')

        # Enrich task metadata with persona scoping from worker_profiles
        task = await self._enrich_task_with_persona_scoping(task)

        available = await self.get_available_workers(
            codebase_id=codebase_id,
            target_agent_name=target_agent_name,
            target_worker_id=target_worker_id,
            required_capabilities=required_capabilities,
            task_agent_type=task.get('agent_type'),
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

    async def _enrich_task_with_persona_scoping(
        self, task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich task metadata with permission scoping from the worker_profile
        matching the task's worker_personality. This backs the marketing claim:
        "each agent only has the permissions it needs."

        Scoping fields injected: allowed_tools, allowed_paths, allowed_namespaces.
        The Rust agent binary uses these to enforce least-privilege access.
        """
        metadata = task.get('metadata') or {}
        personality = metadata.get('worker_personality')
        if not personality:
            return task

        try:
            from . import database as db
            import json as _json

            pool = await db.get_pool()
            if not pool:
                return task

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT allowed_tools, allowed_paths, allowed_namespaces FROM worker_profiles WHERE slug = $1',
                    personality,
                )
                if not row:
                    return task

                scoping = {}
                for col in (
                    'allowed_tools',
                    'allowed_paths',
                    'allowed_namespaces',
                ):
                    val = row[col]
                    if val is not None:
                        if isinstance(val, str):
                            val = _json.loads(val)
                        scoping[col] = val

                if scoping:
                    # Merge into a copy of the task to avoid mutating the original
                    task = dict(task)
                    task_metadata = dict(metadata)
                    task_metadata['persona_scoping'] = scoping
                    task['metadata'] = task_metadata
                    logger.debug(
                        'Enriched task %s with persona scoping for %s: %s',
                        task.get('id', '?'),
                        personality,
                        list(scoping.keys()),
                    )

        except Exception as e:
            logger.debug('Failed to enrich task with persona scoping: %s', e)

        return task

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
            from .agent_bridge import get_bridge as get_agent_bridge

            bridge = get_agent_bridge()
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
                'model_ref': getattr(task, 'model_ref', None)
                or (task.metadata or {}).get('model_ref'),
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


def start_persistent_claim_loop() -> None:
    _start_persistent_claim_loop(get_worker_registry)


class TaskClaimRequest(BaseModel):
    """Request to claim a task."""

    task_id: str


async def _db_task_claimed_by_worker(task_id: str, worker_id: str) -> bool:
    """Return whether durable task state says this worker owns a running task."""
    try:
        from . import database as db

        task = await db.db_get_task(task_id)
        if not task:
            return False
        return (
            str(task.get('worker_id') or '') == worker_id
            and str(task.get('status') or '') == 'running'
        )
    except Exception as e:
        logger.debug(
            f'Failed to check DB task ownership for {task_id}/{worker_id}: {e}'
        )
        return False


class TaskReleaseRequest(BaseModel):
    """Request to release a task."""

    task_id: str
    status: str = 'completed'  # completed, failed, cancelled
    result: Optional[str] = None
    error: Optional[str] = None


async def _db_claim_allows_release(task_id: str, worker_id: str) -> bool:
    """Return true when Postgres shows this worker owns the running task.

    Worker claims are tracked in-memory for fast SSE routing, but API traffic is
    load-balanced across replicas. A worker may claim on one replica and post
    release to another. In that case, the local registry misses the claim while
    the database still has the authoritative worker ownership.
    """
    try:
        from .database import get_pool

        pool = await get_pool()
        if not pool:
            return False
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT status, worker_id FROM tasks WHERE id = $1',
                task_id,
            )
    except Exception as e:
        logger.warning(
            f'Failed to verify DB claim for release of task {task_id}: {e}'
        )
        return False

    if not row:
        return False

    return row['worker_id'] == worker_id and row['status'] in {
        'running',
        'working',
    }


class CodebaseUpdateRequest(BaseModel):
    """Request to update worker's codebase list."""

    codebases: List[str]
    # Accept extra fields from workers that send full registration payloads
    worker_id: Optional[str] = None
    agent_name: Optional[str] = None
    models: Optional[Any] = None
    capabilities: Optional[List[str]] = None

    model_config = {'extra': 'ignore'}


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
    last_event_id: Optional[str] = Header(None, alias='Last-Event-ID'),
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
        raw_codebases = {c.strip() for c in x_codebases.split(',') if c.strip()}
        codebases = set(raw_codebases)
        # Resolve any filesystem paths to codebase UUIDs so task routing
        # (which uses UUIDs) works correctly.
        path_entries = {c for c in raw_codebases if c.startswith('/')}
        if path_entries:
            try:
                from . import database as _db

                for path in path_entries:
                    matches = await _db.db_list_workspaces_by_path(path)
                    for ws in matches:
                        if ws.get('id'):
                            codebases.add(ws['id'])
            except Exception as _e:
                logger.debug(f'SSE path→UUID resolution failed: {_e}')

    registry = get_worker_registry()

    async def event_generator():
        """Generate SSE events for the connected worker."""
        queue: asyncio.Queue = make_worker_queue()
        worker = None
        seq = registry.sequencer_for(resolved_worker_id)

        try:
            # Register this worker
            worker = await registry.register_worker(
                worker_id=resolved_worker_id,
                agent_name=resolved_agent_name,
                queue=queue,
                capabilities=capabilities,
                codebases=codebases,
            )

            # Honor a reconnecting client's Last-Event-ID against this worker's
            # persistent sequencer: replay the gap (seq, head] when still within
            # the ring, or emit resync-required on epoch mismatch / window
            # overflow. A first-time connect (no id) yields nothing here.
            for frame in resume_frames(last_event_id, seq):
                yield frame

            # Send connection confirmation
            connect_event = {
                'event': 'connected',
                'worker_id': resolved_worker_id,
                'agent_name': resolved_agent_name,
                'message': 'Connected to task stream',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            yield format_event('connected', connect_event, seq)

            # Send any pending tasks to the newly connected worker
            try:
                from .agent_bridge import get_bridge as get_agent_bridge
                from .agent_bridge import AgentTaskStatus

                bridge = get_agent_bridge()
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
                        task_target_agent = getattr(
                            task, 'target_agent_name', None
                        ) or (task.metadata or {}).get('target_agent_name')
                        # Worker can handle task if:
                        # 1. Task has no specific codebase (global/__pending__)
                        # 2. Worker has the task's codebase in their list
                        # NOTE: Workers with no codebases can ONLY handle global/__pending__ tasks
                        # This prevents cross-server task leakage
                        can_handle = (
                            task_codebase in ('__pending__', 'global')
                            or task_codebase in worker_codebases
                            or is_targeted_clone_task(
                                task.agent_type, task_target_agent
                            )
                        )

                        if (
                            task_target_agent
                            and task_target_agent != resolved_agent_name
                        ):
                            continue

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
                                'model_ref': getattr(task, 'model_ref', None)
                                or (task.metadata or {}).get('model_ref'),
                                'target_agent_name': task_target_agent,
                                'created_at': task.created_at.isoformat()
                                if task.created_at
                                else None,
                            }
                            yield format_event('task_available', task_data, seq)
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

                        yield format_event(event_type, event_data, seq)

                    except asyncio.TimeoutError:
                        pass  # No event, check if heartbeat needed

                    # Send heartbeat if interval elapsed
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        heartbeat_data = {
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'worker_id': resolved_worker_id,
                        }
                        yield format_event('heartbeat', heartbeat_data, seq)
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
            'Cache-Control': 'no-cache, no-transform',
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
        logger.info(
            f'Task {claim.task_id} claimed by worker {resolved_worker_id}'
        )
        # Update task status to 'running' in DB so the UI reflects reality
        try:
            from .agent_bridge import get_bridge as get_agent_bridge
            from .agent_bridge import AgentTaskStatus
            from .database import db_update_task_status

            bridge = get_agent_bridge()
            if bridge:
                updated_task = await bridge.update_task_status(
                    task_id=claim.task_id,
                    status=AgentTaskStatus.RUNNING,
                    worker_id=resolved_worker_id,
                )
                if updated_task is None:
                    logger.debug(
                        f'Bridge missed task {claim.task_id}; using DB status update fallback'
                    )

            updated = await db_update_task_status(
                task_id=claim.task_id,
                status=AgentTaskStatus.RUNNING.value,
                worker_id=resolved_worker_id,
            )
            if not updated:
                logger.warning(
                    f'Claimed task {claim.task_id} but could not persist running status'
                )
        except Exception as e:
            logger.warning(
                f'Failed to update task {claim.task_id} to running: {e}'
            )

        run_claim = await _claim_task_run_for_worker(
            claim.task_id,
            resolved_worker_id,
        )

        response = {
            'success': True,
            'task_id': claim.task_id,
            'worker_id': resolved_worker_id,
            'message': 'Task claimed successfully',
        }
        response.update(run_claim)
        return response
    else:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Task {claim.task_id} cannot be claimed by worker {resolved_worker_id} '
                '(already claimed, worker not connected, or worker not eligible for this task)'
            ),
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
    if not success and await _db_claim_allows_release(
        release.task_id,
        resolved_worker_id,
    ):
        logger.warning(
            f'Task {release.task_id} release accepted from DB claim after '
            f'local registry miss (worker={resolved_worker_id})'
        )
        success = True

    if success:
        # Persist status/result/error to in-memory cache AND database
        try:
            from .agent_bridge import get_bridge as get_agent_bridge

            bridge = get_agent_bridge()
            updated_task = None
            if bridge:
                from .agent_bridge import AgentTaskStatus

                status_enum = AgentTaskStatus(release.status)
                updated_task = await bridge.update_task_status(
                    task_id=release.task_id,
                    status=status_enum,
                    result=release.result,
                    error=release.error,
                    worker_id=resolved_worker_id,
                )
                if updated_task:
                    logger.info(
                        f'Task {release.task_id} status updated to {release.status} via bridge'
                    )
                else:
                    logger.warning(
                        f'Bridge missed released task {release.task_id}; using DB status update fallback'
                    )
                if release.status == 'completed':
                    try:
                        from .post_clone_followup import (
                            enqueue_post_clone_followup,
                        )

                        await enqueue_post_clone_followup(
                            bridge, release.task_id
                        )
                    except Exception as e:
                        logger.error(
                            f'Failed to enqueue post-clone follow-up for {release.task_id}: {e}'
                        )
            if not updated_task:
                # Fallback: direct DB update if bridge is unavailable or missed
                # a task created through the DB-backed worker polling path.
                from .database import db_update_task_status

                updated = await db_update_task_status(
                    task_id=release.task_id,
                    status=release.status,
                    worker_id=resolved_worker_id,
                    result=release.result,
                    error=release.error,
                )
                if updated:
                    logger.info(
                        f'Task {release.task_id} status updated to {release.status} via DB fallback'
                    )
                else:
                    logger.warning(
                        f'Released task {release.task_id} but could not persist {release.status} status'
                    )
        except Exception as e:
            logger.error(f'Failed to update task {release.task_id} status: {e}')
        await _mirror_release_to_task_run(
            release.task_id,
            resolved_worker_id,
            release.status,
            release.result,
            release.error,
        )
        if release.status in {'completed', 'failed', 'cancelled'}:
            try:
                from .github_app.task_status_hook import (
                    handle_github_app_terminal_task,
                )

                await handle_github_app_terminal_task(
                    release.task_id,
                    resolved_worker_id,
                )
            except Exception as e:
                logger.exception(
                    'GitHub App terminal task hook failed for %s: %s',
                    release.task_id,
                    e,
                )

        # Record result for perpetual loop iterations (if applicable)
        try:
            from .perpetual_loop import handle_task_completion_for_loops

            await handle_task_completion_for_loops(
                task_id=release.task_id,
                status=release.status,
                result=release.result,
            )
        except Exception as e:
            logger.debug(f'Loop completion check for {release.task_id}: {e}')

        # Send email notification on task completion/failure
        if release.status in ('completed', 'failed'):
            try:
                from .database import get_pool

                pool = await get_pool()
                if pool:
                    async with pool.acquire() as conn:
                        task_row = await conn.fetchrow(
                            'SELECT title, metadata FROM tasks WHERE id = $1',
                            release.task_id,
                        )
                    if task_row:
                        metadata = task_row['metadata']
                        if isinstance(metadata, str):
                            import json as _json

                            metadata = _json.loads(metadata)
                        notify_email = (metadata or {}).get('notify_email')
                        if notify_email:
                            from .email_notifications import (
                                is_configured,
                                send_task_completion_email,
                            )

                            if is_configured():
                                email_sent = await send_task_completion_email(
                                    to_email=notify_email,
                                    task_id=release.task_id,
                                    title=task_row['title'] or 'Task',
                                    status=release.status,
                                    result=release.result,
                                    error=release.error
                                    if release.status == 'failed'
                                    else None,
                                    worker_name=resolved_worker_id,
                                )
                                if email_sent:
                                    logger.info(
                                        f'Completion email sent to {notify_email} '
                                        f'for task {release.task_id}'
                                    )
                                else:
                                    logger.warning(
                                        f'Failed to send completion email for '
                                        f'task {release.task_id}'
                                    )
                            else:
                                logger.debug(
                                    'Email notifications not configured '
                                    '(missing SENDGRID_API_KEY or SENDGRID_FROM_EMAIL)'
                                )
            except Exception as e:
                logger.error(
                    f'Error sending completion email for task '
                    f'{release.task_id}: {e}'
                )

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

    resolved_worker_id = worker_id or x_worker_id or update.worker_id
    if not resolved_worker_id:
        raise HTTPException(
            status_code=400,
            detail='worker_id is required (query param, X-Worker-ID header, or in body)',
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
    target_worker_id = task.get('target_worker_id')
    required_capabilities = task.get('required_capabilities')
    if required_capabilities is None and isinstance(task.get('metadata'), dict):
        required_capabilities = task['metadata'].get('required_capabilities')
    if not target_worker_id and isinstance(task.get('metadata'), dict):
        target_worker_id = task['metadata'].get('target_worker_id')

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
        target_worker_id=target_worker_id,
        required_capabilities=required_capabilities,
    )


def setup_task_creation_hook(agent_bridge) -> None:
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

