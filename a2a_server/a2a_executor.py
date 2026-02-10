"""
CodeTether A2A Executor - Bridges official A2A SDK to our task queue system.

This module implements the A2A SDK's AgentExecutor interface to bridge standard
A2A protocol requests to CodeTether's internal task queue and worker system.

The executor allows CodeTether to:
1. Receive requests via the standard A2A protocol (JSON-RPC over HTTP/SSE)
2. Route them through our existing task queue with leasing and concurrency control
3. Distribute work to workers via our SSE push system
4. Stream results back through the A2A protocol's event system

Note: This module uses conditional imports to support both:
- Full A2A SDK installation (a2a-sdk package)
- Standalone operation with Protocol-based type stubs
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

# Try to import from the official A2A SDK, fall back to local stubs
try:
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue
    from a2a.types import (
        Artifact,
        DataPart,
        FilePart,
        InternalError,
        InvalidParamsError,
        Message,
        Part,
        Task,
        TaskArtifactUpdateEvent,
        TaskState,
        TaskStatus,
        TaskStatusUpdateEvent,
        TextPart,
        UnsupportedOperationError,
    )

    A2A_SDK_AVAILABLE = True
except ImportError:
    # A2A SDK not installed - define Protocol-based stubs for type checking
    # These allow the code to be imported and type-checked even without the SDK
    A2A_SDK_AVAILABLE = False

    class TaskStatus(str, Enum):
        """A2A Task status enum (stub)."""

        submitted = 'submitted'
        working = 'working'
        input_required = 'input-required'
        completed = 'completed'
        failed = 'failed'
        canceled = 'canceled'

    @dataclass
    class TaskState:
        """A2A Task state (stub)."""

        state: TaskStatus
        message: Optional[str] = None
        timestamp: Optional[str] = None

    @dataclass
    class TextPart:
        """A2A Text part (stub)."""

        text: str
        type: str = 'text'

    @dataclass
    class FilePart:
        """A2A File part (stub)."""

        file: Dict[str, Any]
        type: str = 'file'

    @dataclass
    class DataPart:
        """A2A Data part (stub)."""

        data: Any
        mimeType: str = 'application/json'
        type: str = 'data'

    # Union type for all part types
    Part = Union[TextPart, FilePart, DataPart]

    @dataclass
    class Message:
        """A2A Message (stub)."""

        role: str
        parts: List[Part]
        metadata: Optional[Dict[str, Any]] = None

    @dataclass
    class Task:
        """A2A Task (stub)."""

        id: str
        status: TaskStatus
        artifacts: Optional[List[Any]] = None
        history: Optional[List[Any]] = None
        metadata: Optional[Dict[str, Any]] = None

    @dataclass
    class Artifact:
        """A2A Artifact (stub)."""

        artifactId: str
        name: str
        parts: List[Part]
        metadata: Optional[Dict[str, Any]] = None

    @dataclass
    class TaskStatusUpdateEvent:
        """A2A Task status update event (stub)."""

        taskId: str
        status: TaskState
        message: Optional[Message] = None
        final: bool = False

    @dataclass
    class TaskArtifactUpdateEvent:
        """A2A Task artifact update event (stub)."""

        taskId: str
        artifact: Artifact

    @runtime_checkable
    class RequestContext(Protocol):
        """Protocol for A2A request context."""

        @property
        def task_id(self) -> str:
            """The task ID."""
            ...

        @property
        def message(self) -> Message:
            """The request message."""
            ...

        @property
        def metadata(self) -> Optional[Dict[str, Any]]:
            """Optional metadata."""
            ...

    @runtime_checkable
    class EventQueue(Protocol):
        """Protocol for A2A event queue."""

        async def enqueue_event(self, event: Any) -> None:
            """Enqueue an event to be sent to the client."""
            ...

    class AgentExecutor(ABC):
        """Abstract base class for A2A agent executors (stub)."""

        @abstractmethod
        async def execute(
            self, context: RequestContext, event_queue: EventQueue
        ) -> None:
            """Execute agent logic."""
            ...

        @abstractmethod
        async def cancel(
            self, context: RequestContext, event_queue: EventQueue
        ) -> None:
            """Cancel a running task."""
            ...

    class InvalidParamsError(Exception):
        """A2A Invalid params error (stub)."""

        def __init__(self, message: str, data: Any = None):
            self.message = message
            self.data = data
            super().__init__(message)

    class InternalError(Exception):
        """A2A Internal error (stub)."""

        def __init__(self, message: str, data: Any = None):
            self.message = message
            self.data = data
            super().__init__(message)

    class UnsupportedOperationError(Exception):
        """A2A Unsupported operation error (stub)."""

        def __init__(self, message: str, data: Any = None):
            self.message = message
            self.data = data
            super().__init__(message)


# When A2A SDK is available, its error types are Pydantic BaseModel subclasses,
# NOT Exception subclasses. Python's except clause requires BaseException subclasses.
# Create proper Exception wrappers for use in try/except blocks.
class _InvalidParamsException(Exception):
    """Exception wrapper for A2A InvalidParamsError."""
    def __init__(self, message: str, data: Any = None):
        self.message = message
        self.data = data
        super().__init__(message)

class _InternalException(Exception):
    """Exception wrapper for A2A InternalError."""
    def __init__(self, message: str, data: Any = None):
        self.message = message
        self.data = data
        super().__init__(message)

class _UnsupportedOperationException(Exception):
    """Exception wrapper for A2A UnsupportedOperationError."""
    def __init__(self, message: str, data: Any = None):
        self.message = message
        self.data = data
        super().__init__(message)


# Internal imports
from .task_queue import TaskQueue, TaskRun, TaskRunStatus, TaskLimitExceeded, get_task_queue
from .database import get_pool as get_db_pool
from .models import TaskStatus as InternalTaskStatus
from .worker_sse import notify_workers_of_new_task

logger = logging.getLogger(__name__)

# Polling configuration
DEFAULT_POLL_INTERVAL = 1.0  # seconds
MAX_POLL_DURATION = 120  # 2 minutes max wait


# A2A Task status constants as plain strings.
# The A2A SDK's TaskStatus is a Pydantic model (not an Enum),
# and the router uses its own TaskState enum. Use raw strings
# to stay compatible with both.
class A2AStatus:
    """A2A task status string constants."""
    SUBMITTED = 'submitted'
    PENDING = 'pending'
    WORKING = 'working'
    INPUT_REQUIRED = 'input-required'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELED = 'cancelled'


class CodetetherExecutionError(Exception):
    """Base exception for CodeTether executor errors."""

    def __init__(self, message: str, code: int = -32000, data: Any = None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(message)


class CodetetherExecutor(AgentExecutor):
    """
    Bridges A2A protocol requests to CodeTether's task queue and worker system.

    This allows us to:
    1. Receive requests via standard A2A protocol
    2. Route them through our existing task queue with leasing
    3. Distribute to workers via our SSE push system
    4. Return results back through A2A streaming

    The executor converts between A2A's Message/Task types and our internal
    TaskRun system, maintaining full compatibility with both protocols.
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        worker_manager: Optional[Any] = None,
        database: Optional[Any] = None,
        default_user_id: Optional[str] = None,
        default_priority: int = 0,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_poll_duration: float = MAX_POLL_DURATION,
    ):
        """
        Initialize the CodeTether executor.

        Args:
            task_queue: The TaskQueue instance for enqueuing and tracking tasks
            worker_manager: Optional worker manager for direct worker communication
            database: Optional database connection for task persistence
            default_user_id: Default user ID for tasks without explicit user context
            default_priority: Default priority for new tasks
            poll_interval: How often to poll for task updates (seconds)
            max_poll_duration: Maximum time to wait for task completion (seconds)
        """
        self._task_queue = task_queue
        self.worker_manager = worker_manager
        self.database = database
        self.default_user_id = default_user_id
        self.default_priority = default_priority
        self.poll_interval = poll_interval
        self.max_poll_duration = max_poll_duration

    @property
    def task_queue(self) -> TaskQueue:
        """Lazily resolve the task queue from global state if not set directly."""
        if self._task_queue is None:
            self._task_queue = get_task_queue()
        if self._task_queue is None:
            raise RuntimeError('Task queue is not initialized. Database may not be connected.')
        return self._task_queue

    @task_queue.setter
    def task_queue(self, value):
        self._task_queue = value

    async def _get_database(self):
        """Lazily resolve the database pool."""
        if self.database is None:
            self.database = await get_db_pool()
        return self.database

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """
        Execute agent logic by routing to our task queue.

        This method:
        1. Extracts the message content from the A2A request
        2. Creates an internal task in our PostgreSQL database
        3. Enqueues a task_run for worker processing
        4. Polls for results and streams them back via event_queue

        Args:
            context: The A2A request context containing message and task info
            event_queue: Queue for sending events back to the client
        """
        task_id = context.task_id
        message = context.message

        logger.info(f'Executing A2A request for task {task_id}')

        try:
            # Extract text content from the A2A message
            prompt = self._extract_text_from_message(message)
            if not prompt:
                raise _InvalidParamsException(
                    message='Message must contain at least one text part'
                )

            # Extract metadata for routing
            metadata = self._extract_metadata(context)
            user_id = metadata.get('user_id', self.default_user_id)
            priority = metadata.get('priority', self.default_priority)
            target_agent = metadata.get('target_agent_name')
            required_capabilities = metadata.get('required_capabilities')
            model_ref = metadata.get('model_ref')

            # Create the internal task record
            internal_task_id = await self._create_internal_task(
                task_id=task_id,
                prompt=prompt,
                user_id=user_id,
                metadata=metadata,
                model_ref=model_ref,
            )

            # Enqueue the task run
            task_run = await self._enqueue_task_run(
                task_id=internal_task_id,
                user_id=user_id,
                priority=priority,
                target_agent_name=target_agent,
                required_capabilities=required_capabilities,
                model_ref=model_ref,
                prompt=prompt,
            )

            logger.info(
                f'Created task_run {task_run.id} for A2A task {task_id}'
            )

            # Send initial working status
            await self._send_status_update(
                event_queue=event_queue,
                task_id=task_id,
                status=A2AStatus.WORKING,
                message='Task queued for processing',
            )

            # Poll for results and stream back
            await self._poll_and_stream_results(
                event_queue=event_queue,
                task_id=task_id,
                task_run_id=task_run.id,
            )

        except TaskLimitExceeded as e:
            logger.warning(f'Task limit exceeded for task {task_id}: {e}')
            await self._send_error(
                event_queue=event_queue,
                task_id=task_id,
                error_message=str(e),
                error_code=-32002,
                error_data=e.to_dict(),
            )

        except _InvalidParamsException as e:
            logger.warning(f'Invalid params for task {task_id}: {e}')
            await self._send_error(
                event_queue=event_queue,
                task_id=task_id,
                error_message=str(e),
                error_code=-32602,
            )

        except Exception as e:
            logger.exception(f'Error executing task {task_id}: {e}')
            await self._send_error(
                event_queue=event_queue,
                task_id=task_id,
                error_message=f'Internal execution error: {str(e)}',
                error_code=-32000,
            )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """
        Cancel a running task.

        This method:
        1. Finds the task_run associated with the A2A task
        2. Attempts to cancel it in our queue
        3. Sends cancellation confirmation via event_queue

        Args:
            context: The A2A request context containing task info
            event_queue: Queue for sending events back to the client
        """
        task_id = context.task_id

        logger.info(f'Cancelling A2A task {task_id}')

        try:
            # Find the task_run for this A2A task
            task_run = await self._find_task_run_by_external_id(task_id)

            if not task_run:
                raise _InvalidParamsException(
                    message=f'No task found with ID {task_id}'
                )

            # Check if task is in a cancellable state
            if task_run.status in (
                TaskRunStatus.COMPLETED,
                TaskRunStatus.FAILED,
                TaskRunStatus.CANCELLED,
            ):
                logger.info(
                    f'Task {task_id} already in terminal state: {task_run.status}'
                )
                await self._send_status_update(
                    event_queue=event_queue,
                    task_id=task_id,
                    status=self._map_internal_to_a2a_status(task_run.status),
                    message=f'Task already {task_run.status.value}',
                    is_final=True,
                )
                return

            # Attempt cancellation
            cancelled = await self.task_queue.cancel_run(task_run.id)

            if cancelled:
                logger.info(f'Successfully cancelled task {task_id}')
                await self._send_status_update(
                    event_queue=event_queue,
                    task_id=task_id,
                    status=A2AStatus.CANCELED,
                    message='Task cancelled successfully',
                    is_final=True,
                )
            else:
                # Task may have transitioned to running state
                logger.warning(
                    f'Failed to cancel task {task_id} - may be running'
                )
                await self._send_status_update(
                    event_queue=event_queue,
                    task_id=task_id,
                    status=A2AStatus.WORKING,
                    message='Task is currently running and cannot be cancelled',
                )

        except _InvalidParamsException:
            raise

        except Exception as e:
            logger.exception(f'Error cancelling task {task_id}: {e}')
            raise _InternalException(message=f'Failed to cancel task: {str(e)}')

    # -------------------------------------------------------------------------
    # Helper Methods - Message Extraction
    # -------------------------------------------------------------------------

    def _extract_text_from_message(self, message: Message) -> str:
        """
        Extract text content from an A2A Message.

        Concatenates all text parts in the message, preserving order.
        Handles both SDK TextPart objects and plain dict parts from the router.

        Args:
            message: The A2A Message to extract text from

        Returns:
            Concatenated text content from all TextParts
        """
        text_parts = []

        for part in message.parts:
            # Handle plain dict parts (from the router's A2AMessage)
            if isinstance(part, dict):
                text = part.get('text')
                if text:
                    text_parts.append(str(text))
            elif isinstance(part, TextPart):
                text_parts.append(part.text)
            elif hasattr(part, 'text'):
                text_parts.append(str(part.text))

        return '\n'.join(text_parts)

    def _extract_metadata(self, context: RequestContext) -> Dict[str, Any]:
        """
        Extract routing and configuration metadata from the request context.

        Args:
            context: The A2A RequestContext

        Returns:
            Dictionary of metadata for task routing and configuration
        """
        metadata: Dict[str, Any] = {}

        # Extract from context metadata if available
        if hasattr(context, 'metadata') and context.metadata:
            ctx_meta = context.metadata
            if isinstance(ctx_meta, dict):
                metadata.update(ctx_meta)

        # Extract from message metadata
        if context.message and hasattr(context.message, 'metadata'):
            msg_meta = context.message.metadata
            if isinstance(msg_meta, dict):
                metadata.update(msg_meta)

        return metadata

    # -------------------------------------------------------------------------
    # Helper Methods - Task Management
    # -------------------------------------------------------------------------

    async def _create_internal_task(
        self,
        task_id: str,
        prompt: str,
        user_id: Optional[str],
        metadata: Dict[str, Any],
        model_ref: Optional[str] = None,
    ) -> str:
        """
        Create an internal task record in the database.

        Args:
            task_id: The A2A task ID (used as external reference)
            prompt: The task prompt/description
            user_id: Optional user ID
            metadata: Additional task metadata
            model_ref: Optional model reference (provider:model format)

        Returns:
            The internal task ID
        """
        # Resolve model_ref to use
        import os
        if not model_ref:
            model_ref = os.environ.get(
                'A2A_RLM_DEFAULT_SUBCALL_MODEL_REF',
                'zhipuai:glm-4.7',
            )

        db = await self._get_database()
        if db is None:
            # If no database, use the A2A task_id directly
            return task_id

        try:
            import json as _json
            async with db.acquire() as conn:
                # Check if task already exists (idempotency)
                existing = await conn.fetchrow(
                    "SELECT id FROM tasks WHERE id = $1 OR metadata->>'a2a_task_id' = $1",
                    task_id,
                )
                if existing:
                    return existing['id']

                # Create new task
                internal_id = str(uuid.uuid4())
                task_metadata = {
                    **metadata,
                    'a2a_task_id': task_id,
                    'source': 'a2a_executor',
                }

                await conn.execute(
                    """
                    INSERT INTO tasks (id, title, prompt, status, model, metadata, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $7)
                    """,
                    internal_id,
                    f'A2A Task: {task_id[:8]}',
                    prompt,
                    'pending',
                    model_ref,
                    _json.dumps(task_metadata),
                    datetime.now(timezone.utc),
                )

                logger.info(f'Created internal task {internal_id} with model={model_ref}')
                return internal_id

        except Exception as e:
            logger.error(f'Failed to create internal task: {e}')
            # Fall back to using A2A task_id
            return task_id

    async def _enqueue_task_run(
        self,
        task_id: str,
        user_id: Optional[str],
        priority: int,
        target_agent_name: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        model_ref: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> TaskRun:
        """
        Enqueue a task run for worker processing.

        Args:
            task_id: The internal task ID
            user_id: Optional user ID for concurrency limiting
            priority: Task priority (higher = more urgent)
            target_agent_name: Optional specific agent to route to
            required_capabilities: Optional required worker capabilities
            model_ref: Optional model reference (provider:model format)
            prompt: Optional prompt text to include in worker notification

        Returns:
            The created TaskRun
        """
        # Use default model ref from env if not specified
        import os
        if not model_ref:
            model_ref = os.environ.get(
                'A2A_RLM_DEFAULT_SUBCALL_MODEL_REF',
                'zhipuai:glm-4.7',
            )

        task_run = await self.task_queue.enqueue(
            task_id=task_id,
            user_id=user_id,
            priority=priority,
            target_agent_name=target_agent_name,
            required_capabilities=required_capabilities,
            model_ref=model_ref,
        )

        # Store prompt on the task_run for re-notification use
        self._last_prompt = prompt
        self._last_model_ref = model_ref

        # Notify connected workers via SSE so they claim the task
        try:
            task_title = f'A2A Task: {task_id[:8]}'
            task_data = {
                'id': task_id,
                'title': task_title,
                'prompt': prompt or task_title,
                'model': model_ref,
                'model_ref': model_ref,
                'priority': priority,
                'status': 'pending',
                'agent_type': 'a2a',
            }
            if target_agent_name:
                task_data['target_agent_name'] = target_agent_name
            if required_capabilities:
                task_data['required_capabilities'] = required_capabilities
            notified = await notify_workers_of_new_task(task_data)
            logger.info(f'Notified {len(notified)} workers of new task {task_run.id} with model={model_ref}')
        except Exception as e:
            logger.warning(f'Failed to notify workers of new task: {e}')

        return task_run

    async def _find_task_run_by_external_id(
        self, a2a_task_id: str
    ) -> Optional[TaskRun]:
        """
        Find a task_run by its A2A external task ID.

        Args:
            a2a_task_id: The A2A task ID

        Returns:
            The TaskRun if found, None otherwise
        """
        # First try direct lookup (if A2A task_id was used as internal ID)
        task_run = await self.task_queue.get_run_by_task(a2a_task_id)
        if task_run:
            return task_run

        # If we have a database, look up via metadata
        db = await self._get_database()
        if db:
            try:
                async with db.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT tr.* FROM task_runs tr
                        JOIN tasks t ON tr.task_id = t.id
                        WHERE t.metadata->>'a2a_task_id' = $1
                        ORDER BY tr.created_at DESC
                        LIMIT 1
                        """,
                        a2a_task_id,
                    )
                    if row:
                        return self.task_queue._row_to_task_run(row)
            except Exception as e:
                logger.error(f'Error looking up task by A2A ID: {e}')

        return None

    # -------------------------------------------------------------------------
    # Helper Methods - Polling and Streaming
    # -------------------------------------------------------------------------

    async def _poll_and_stream_results(
        self,
        event_queue: EventQueue,
        task_id: str,
        task_run_id: str,
    ) -> None:
        """
        Poll for task completion and stream results back.

        This method polls the task_run status and streams updates
        back to the client via the event_queue until the task
        reaches a terminal state.

        Args:
            event_queue: Queue for sending events
            task_id: The A2A task ID
            task_run_id: The internal task_run ID
        """
        start_time = asyncio.get_event_loop().time()
        last_status = None
        last_renotify_time = start_time
        renotify_interval = 5.0  # Re-notify workers every 5s if still queued

        while True:
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.max_poll_duration:
                logger.warning(f'Task {task_id} timed out after {elapsed:.1f}s')
                await self._send_status_update(
                    event_queue=event_queue,
                    task_id=task_id,
                    status=A2AStatus.FAILED,
                    message=f'Task timed out after {self.max_poll_duration}s',
                    is_final=True,
                )
                return

            # Get current task run status
            task_run = await self.task_queue.get_run(task_run_id)

            if not task_run:
                logger.error(f'Task run {task_run_id} not found')
                await self._send_error(
                    event_queue=event_queue,
                    task_id=task_id,
                    error_message='Task run not found',
                    error_code=-32001,
                )
                return

            # Send status update if changed
            if task_run.status != last_status:
                last_status = task_run.status

                a2a_status = self._map_internal_to_a2a_status(task_run.status)
                is_final = task_run.status in (
                    TaskRunStatus.COMPLETED,
                    TaskRunStatus.FAILED,
                    TaskRunStatus.CANCELLED,
                )

                # Build message based on status
                message = self._build_status_message(task_run)

                await self._send_status_update(
                    event_queue=event_queue,
                    task_id=task_id,
                    status=a2a_status,
                    message=message,
                    is_final=is_final,
                )

                # If we have a result, send it as an artifact
                if is_final and task_run.result_summary:
                    await self._send_result_artifact(
                        event_queue=event_queue,
                        task_id=task_id,
                        result=task_run.result_summary,
                        full_result=task_run.result_full,
                    )

                if is_final:
                    return

            # Re-notify workers if task is still queued (handles claim-release cycles)
            if task_run and task_run.status == TaskRunStatus.QUEUED:
                now = asyncio.get_event_loop().time()
                if now - last_renotify_time >= renotify_interval:
                    last_renotify_time = now
                    try:
                        _model = getattr(self, '_last_model_ref', None) or getattr(task_run, 'model_ref', None)
                        _prompt = getattr(self, '_last_prompt', None) or f'A2A Task: {task_run.task_id[:8]}'
                        task_data = {
                            'id': task_run.task_id,
                            'title': f'A2A Task: {task_run.task_id[:8]}',
                            'prompt': _prompt,
                            'model': _model,
                            'model_ref': _model,
                            'priority': getattr(task_run, 'priority', 0),
                            'status': 'pending',
                            'agent_type': 'a2a',
                        }
                        notified = await notify_workers_of_new_task(task_data)
                        logger.info(f'Re-notified {len(notified)} workers of queued task {task_run_id} with model={_model}')
                    except Exception as e:
                        logger.debug(f'Re-notification failed: {e}')

            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    def _build_status_message(self, task_run: TaskRun) -> str:
        """Build a human-readable status message for a task run."""
        status_messages = {
            TaskRunStatus.QUEUED: 'Task is queued for processing',
            TaskRunStatus.RUNNING: 'Task is being processed by a worker',
            TaskRunStatus.NEEDS_INPUT: 'Task requires additional input',
            TaskRunStatus.COMPLETED: 'Task completed successfully',
            TaskRunStatus.FAILED: task_run.last_error or 'Task failed',
            TaskRunStatus.CANCELLED: 'Task was cancelled',
        }
        return status_messages.get(
            task_run.status, f'Status: {task_run.status.value}'
        )

    # -------------------------------------------------------------------------
    # Helper Methods - Event Sending
    # -------------------------------------------------------------------------

    async def _send_status_update(
        self,
        event_queue: EventQueue,
        task_id: str,
        status: str,
        message: str,
        is_final: bool = False,
    ) -> None:
        """
        Send a task status update event.

        Args:
            event_queue: Queue for sending events
            task_id: The A2A task ID
            status: The new task status
            message: Human-readable status message
            is_final: Whether this is the final update
        """
        # Build event as a plain dict compatible with the router's EventQueue
        status_value = status.value if hasattr(status, 'value') else str(status)
        event = {
            'type': 'status',
            'taskId': task_id,
            'status': {
                'state': status_value,
                'message': message,
            },
            'final': is_final,
        }

        # Support both router EventQueue (put) and SDK EventQueue (enqueue_event)
        if hasattr(event_queue, 'put'):
            await event_queue.put(event)
        elif hasattr(event_queue, 'enqueue_event'):
            await event_queue.enqueue_event(event)
        else:
            logger.error('EventQueue has no put() or enqueue_event() method')

    async def _send_result_artifact(
        self,
        event_queue: EventQueue,
        task_id: str,
        result: str,
        full_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send task result as an artifact.

        Args:
            event_queue: Queue for sending events
            task_id: The A2A task ID
            result: The result summary text
            full_result: Optional full result data
        """
        # Build artifact parts as plain dicts for router compatibility
        parts = [{'type': 'text', 'text': result}]

        if full_result:
            parts.append({
                'type': 'data',
                'data': full_result,
                'mimeType': 'application/json',
            })

        event = {
            'type': 'artifact',
            'taskId': task_id,
            'artifact': {
                'artifactId': str(uuid.uuid4()),
                'name': 'result',
                'parts': parts,
            },
        }

        # Support both router EventQueue (put) and SDK EventQueue (enqueue_event)
        if hasattr(event_queue, 'put'):
            await event_queue.put(event)
        elif hasattr(event_queue, 'enqueue_event'):
            await event_queue.enqueue_event(event)
        else:
            logger.error('EventQueue has no put() or enqueue_event() method')

    async def _send_error(
        self,
        event_queue: EventQueue,
        task_id: str,
        error_message: str,
        error_code: int = -32000,
        error_data: Any = None,
    ) -> None:
        """
        Send an error status update.

        Args:
            event_queue: Queue for sending events
            task_id: The A2A task ID
            error_message: Error description
            error_code: JSON-RPC error code
            error_data: Optional additional error data
        """
        # Build error message with details
        full_message = error_message
        if error_data:
            full_message = f'{error_message}\nDetails: {error_data}'

        try:
            await self._send_status_update(
                event_queue=event_queue,
                task_id=task_id,
                status=A2AStatus.FAILED,
                message=full_message,
                is_final=True,
            )
        except Exception as e:
            logger.error(f'Failed to send error status for task {task_id}: {e}')

    # -------------------------------------------------------------------------
    # Helper Methods - Status Mapping
    # -------------------------------------------------------------------------

    def _map_internal_to_a2a_status(
        self, internal_status: TaskRunStatus
    ) -> str:
        """
        Map internal TaskRunStatus to A2A status string.

        Args:
            internal_status: Our internal status enum

        Returns:
            The corresponding A2A status string
        """
        status_map = {
            TaskRunStatus.QUEUED: A2AStatus.SUBMITTED,
            TaskRunStatus.RUNNING: A2AStatus.WORKING,
            TaskRunStatus.NEEDS_INPUT: A2AStatus.INPUT_REQUIRED,
            TaskRunStatus.COMPLETED: A2AStatus.COMPLETED,
            TaskRunStatus.FAILED: A2AStatus.FAILED,
            TaskRunStatus.CANCELLED: A2AStatus.CANCELED,
        }
        return status_map.get(internal_status, A2AStatus.WORKING)

    def _map_a2a_to_internal_status(
        self, a2a_status: str
    ) -> TaskRunStatus:
        """
        Map A2A status string to internal TaskRunStatus.

        Args:
            a2a_status: The A2A status string

        Returns:
            The corresponding internal TaskRunStatus
        """
        status_map = {
            A2AStatus.SUBMITTED: TaskRunStatus.QUEUED,
            A2AStatus.WORKING: TaskRunStatus.RUNNING,
            A2AStatus.INPUT_REQUIRED: TaskRunStatus.NEEDS_INPUT,
            A2AStatus.COMPLETED: TaskRunStatus.COMPLETED,
            A2AStatus.FAILED: TaskRunStatus.FAILED,
            A2AStatus.CANCELED: TaskRunStatus.CANCELLED,
        }
        return status_map.get(a2a_status, TaskRunStatus.QUEUED)


# Factory function for easy instantiation
def create_codetether_executor(
    task_queue: TaskQueue,
    worker_manager: Optional[Any] = None,
    database: Optional[Any] = None,
    **kwargs,
) -> CodetetherExecutor:
    """
    Factory function to create a CodetetherExecutor instance.

    Args:
        task_queue: The TaskQueue instance
        worker_manager: Optional worker manager
        database: Optional database connection pool
        **kwargs: Additional configuration options

    Returns:
        Configured CodetetherExecutor instance
    """
    return CodetetherExecutor(
        task_queue=task_queue,
        worker_manager=worker_manager,
        database=database,
        **kwargs,
    )
