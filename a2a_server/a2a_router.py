"""
A2A Protocol Router Integration for FastAPI.

Provides a factory function to create an A2A protocol router using the official
A2A SDK's FastAPI integration. This router handles JSON-RPC and REST bindings
for the A2A protocol.

Endpoints:
    POST /a2a/jsonrpc       - JSON-RPC 2.0 endpoint
    POST /a2a/rest/message:send    - REST binding for sending messages
    POST /a2a/rest/message:stream  - REST binding for streaming messages
    GET  /a2a/rest/tasks/{id}      - REST binding for getting task status
    GET  /a2a/.well-known/agent.json - Agent card discovery
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .agent_card import AgentCard
from .keycloak_auth import (
    UserSession,
    get_current_user,
    keycloak_auth,
    require_auth,
)
from .models import Message, Part, Task, TaskStatus

logger = logging.getLogger(__name__)

# Security scheme for Bearer token authentication
security = HTTPBearer(auto_error=False)


# =============================================================================
# A2A SDK Compatible Types
# =============================================================================


class TaskState(str, Enum):
    """Task states as defined by A2A protocol."""

    PENDING = 'pending'
    WORKING = 'working'
    INPUT_REQUIRED = 'input-required'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'


class A2AMessage(BaseModel):
    """A2A protocol message."""

    role: str = Field(..., description='Message role (user/assistant)')
    parts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class A2ATask(BaseModel):
    """A2A protocol task representation."""

    id: str
    contextId: Optional[str] = None
    status: Dict[str, Any]
    artifacts: Optional[List[Dict[str, Any]]] = None
    history: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class SendMessageParams(BaseModel):
    """Parameters for message/send method."""

    message: A2AMessage
    configuration: Optional[Dict[str, Any]] = None


class GetTaskParams(BaseModel):
    """Parameters for tasks/get method."""

    id: str
    historyLength: Optional[int] = None


class CancelTaskParams(BaseModel):
    """Parameters for tasks/cancel method."""

    id: str


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: str = '2.0'
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: str = '2.0'
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error."""

    code: int
    message: str
    data: Optional[Any] = None


# =============================================================================
# Task Store Abstraction
# =============================================================================


class TaskStore(ABC):
    """Abstract base class for task storage."""

    @abstractmethod
    async def create_task(
        self,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> A2ATask:
        """Create a new task."""
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[A2ATask]:
        """Get a task by ID."""
        pass

    @abstractmethod
    async def update_task(
        self,
        task_id: str,
        status: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[A2ATask]:
        """Update a task."""
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> Optional[A2ATask]:
        """Cancel a task."""
        pass


class InMemoryTaskStore(TaskStore):
    """In-memory task store implementation."""

    def __init__(self):
        self._tasks: Dict[str, A2ATask] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> A2ATask:
        """Create a new task."""
        if task_id is None:
            task_id = str(uuid.uuid4())

        task = A2ATask(
            id=task_id,
            status={'state': TaskState.PENDING.value},
            artifacts=[],
            history=[],
            metadata={'title': title, 'prompt': prompt},
        )

        async with self._lock:
            self._tasks[task_id] = task

        return task

    async def get_task(self, task_id: str) -> Optional[A2ATask]:
        """Get a task by ID."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        status: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[A2ATask]:
        """Update a task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            if status:
                task.status = status
            if artifacts is not None:
                task.artifacts = artifacts

            return task

    async def cancel_task(self, task_id: str) -> Optional[A2ATask]:
        """Cancel a task."""
        return await self.update_task(
            task_id, status={'state': TaskState.CANCELLED.value}
        )


class DatabaseTaskStore(TaskStore):
    """Database-backed task store using the existing database module."""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure database connection is ready."""
        if self._initialized:
            return

        from . import database as db

        await db.get_pool()
        self._initialized = True

    async def create_task(
        self,
        task_id: Optional[str] = None,
        title: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> A2ATask:
        """Create a new task in the database."""
        await self._ensure_initialized()
        from . import database as db

        if task_id is None:
            task_id = str(uuid.uuid4())

        if title is None:
            title = f'A2A Task {task_id[:8]}'

        if prompt is None:
            prompt = 'A2A Protocol message'

        now = datetime.utcnow()
        pool = await db.get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tasks (id, title, prompt, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    task_id,
                    title,
                    prompt,
                    TaskState.PENDING.value,
                    now,
                    now,
                )

        return A2ATask(
            id=task_id,
            status={'state': TaskState.PENDING.value},
            artifacts=[],
            history=[],
            metadata={'title': title},
        )

    async def get_task(self, task_id: str) -> Optional[A2ATask]:
        """Get a task from the database."""
        await self._ensure_initialized()
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM tasks WHERE id = $1', task_id
            )

        if not row:
            return None

        return A2ATask(
            id=row['id'],
            status={'state': row.get('status', TaskState.PENDING.value)},
            artifacts=[],
            history=[],
            metadata={
                'title': row.get('title'),
                'description': row.get('description'),
            },
        )

    async def update_task(
        self,
        task_id: str,
        status: Optional[Dict[str, Any]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[A2ATask]:
        """Update a task in the database."""
        await self._ensure_initialized()
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return None

        now = datetime.utcnow()
        async with pool.acquire() as conn:
            if status:
                await conn.execute(
                    """
                    UPDATE tasks SET status = $1, updated_at = $2 WHERE id = $3
                    """,
                    status.get('state', TaskState.WORKING.value),
                    now,
                    task_id,
                )

        return await self.get_task(task_id)

    async def cancel_task(self, task_id: str) -> Optional[A2ATask]:
        """Cancel a task in the database."""
        return await self.update_task(
            task_id, status={'state': TaskState.CANCELLED.value}
        )


# =============================================================================
# Agent Executor Abstraction
# =============================================================================


class RequestContext:
    """Context for an A2A request."""

    def __init__(
        self,
        task_id: Optional[str] = None,
        message: Optional[A2AMessage] = None,
        configuration: Optional[Dict[str, Any]] = None,
        user: Optional[UserSession] = None,
    ):
        self.task_id = task_id
        self.message = message
        self.configuration = configuration or {}
        self.user = user
        self.metadata: Dict[str, Any] = {}


class EventQueue:
    """Queue for streaming events back to the client."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

    async def put(self, event: Dict[str, Any]):
        """Put an event on the queue."""
        if not self._closed:
            await self._queue.put(event)

    async def get(self) -> Optional[Dict[str, Any]]:
        """Get an event from the queue."""
        if self._closed:
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            return {'type': 'keepalive'}

    def close(self):
        """Close the queue."""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class AgentExecutor(ABC):
    """
    Abstract base class for agent execution logic.

    Implement this interface to bridge your agent's logic with the A2A protocol.
    The executor receives context about the request and uses an event queue to
    communicate results or updates back.
    """

    @abstractmethod
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute agent logic for a request.

        Args:
            context: Request context containing the message and configuration
            event_queue: Queue to push events (status updates, artifacts, etc.)
        """
        pass

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel an in-progress task.

        Args:
            task_id: The ID of the task to cancel

        Returns:
            True if cancellation was successful, False otherwise
        """
        return True


class DefaultAgentExecutor(AgentExecutor):
    """Default agent executor that echoes messages back."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute default echo behavior."""
        # Send working status
        await event_queue.put(
            {
                'type': 'status',
                'status': {'state': TaskState.WORKING.value},
            }
        )

        # Echo the message content
        response_text = 'Echo: '
        if context.message:
            for part in context.message.parts:
                if part.get('type') == 'text':
                    response_text += part.get('text', '')

        # Send artifact with response
        await event_queue.put(
            {
                'type': 'artifact',
                'artifact': {
                    'parts': [{'type': 'text', 'text': response_text}],
                },
            }
        )

        # Send completed status
        await event_queue.put(
            {
                'type': 'status',
                'status': {'state': TaskState.COMPLETED.value},
                'final': True,
            }
        )


# =============================================================================
# Request Handler
# =============================================================================


class DefaultRequestHandler:
    """
    Default request handler that bridges the A2A protocol with agent executors.

    Handles JSON-RPC methods and delegates to the appropriate executor methods.
    """

    def __init__(
        self,
        executor: AgentExecutor,
        task_store: TaskStore,
    ):
        self.executor = executor
        self.task_store = task_store
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def handle_send_message(
        self,
        params: Dict[str, Any],
        user: Optional[UserSession] = None,
    ) -> Dict[str, Any]:
        """Handle message/send method."""
        message_data = params.get('message', {})
        message = A2AMessage(
            role=message_data.get('role', 'user'),
            parts=message_data.get('parts', []),
            metadata=message_data.get('metadata'),
        )

        # Extract text from message parts for prompt
        prompt_text = ''
        for part in message.parts:
            if isinstance(part, dict) and part.get('text'):
                prompt_text += part.get('text', '')

        # Create task with message as prompt
        task = await self.task_store.create_task(
            prompt=prompt_text or 'A2A message'
        )

        # Create context and event queue
        context = RequestContext(
            task_id=task.id,
            message=message,
            configuration=params.get('configuration'),
            user=user,
        )
        event_queue = EventQueue()

        # Execute in background and collect final result
        final_result = {'task': task.model_dump()}

        async def run_executor():
            try:
                await self.executor.execute(context, event_queue)
            except Exception as e:
                logger.error(f'Executor error: {e}')
                await event_queue.put(
                    {
                        'type': 'status',
                        'status': {
                            'state': TaskState.FAILED.value,
                            'message': str(e),
                        },
                        'final': True,
                    }
                )
            finally:
                event_queue.close()

        # Run executor
        exec_task = asyncio.create_task(run_executor())
        self._active_tasks[task.id] = exec_task

        # Collect events until final
        artifacts = []
        final_status = {'state': TaskState.PENDING.value}

        try:
            while not event_queue.is_closed:
                event = await event_queue.get()
                if event is None:
                    break

                event_type = event.get('type')
                if event_type == 'status':
                    final_status = event.get('status', final_status)
                    await self.task_store.update_task(
                        task.id, status=final_status
                    )
                elif event_type == 'artifact':
                    artifacts.append(event.get('artifact', {}))

                if event.get('final'):
                    break
        finally:
            self._active_tasks.pop(task.id, None)

        # Update final task state
        updated_task = await self.task_store.update_task(
            task.id, status=final_status, artifacts=artifacts
        )

        return {
            'task': (updated_task or task).model_dump(),
        }

    async def handle_stream_message(
        self,
        params: Dict[str, Any],
        user: Optional[UserSession] = None,
    ) -> AsyncGenerator[str, None]:
        """Handle message/stream method with SSE."""
        message_data = params.get('message', {})
        message = A2AMessage(
            role=message_data.get('role', 'user'),
            parts=message_data.get('parts', []),
            metadata=message_data.get('metadata'),
        )

        # Create task
        task = await self.task_store.create_task()

        # Create context and event queue
        context = RequestContext(
            task_id=task.id,
            message=message,
            configuration=params.get('configuration'),
            user=user,
        )
        event_queue = EventQueue()

        # Execute in background
        async def run_executor():
            try:
                await self.executor.execute(context, event_queue)
            except Exception as e:
                logger.error(f'Executor error: {e}')
                await event_queue.put(
                    {
                        'type': 'status',
                        'status': {
                            'state': TaskState.FAILED.value,
                            'message': str(e),
                        },
                        'final': True,
                    }
                )
            finally:
                event_queue.close()

        exec_task = asyncio.create_task(run_executor())
        self._active_tasks[task.id] = exec_task

        try:
            # Yield initial task event
            yield f'data: {json.dumps({"type": "task", "task": task.model_dump()})}\n\n'

            while not event_queue.is_closed:
                event = await event_queue.get()
                if event is None:
                    break

                if event.get('type') == 'keepalive':
                    yield ':\n\n'  # SSE comment for keepalive
                    continue

                yield f'data: {json.dumps(event)}\n\n'

                if event.get('final'):
                    break

        finally:
            self._active_tasks.pop(task.id, None)

    async def handle_get_task(
        self,
        params: Dict[str, Any],
        user: Optional[UserSession] = None,
    ) -> Dict[str, Any]:
        """Handle tasks/get method."""
        task_id = params.get('id')
        if not task_id:
            raise ValueError('Task ID is required')

        task = await self.task_store.get_task(task_id)
        if not task:
            raise ValueError(f'Task not found: {task_id}')

        return {'task': task.model_dump()}

    async def handle_cancel_task(
        self,
        params: Dict[str, Any],
        user: Optional[UserSession] = None,
    ) -> Dict[str, Any]:
        """Handle tasks/cancel method."""
        task_id = params.get('id')
        if not task_id:
            raise ValueError('Task ID is required')

        # Cancel the executor if running
        exec_task = self._active_tasks.get(task_id)
        if exec_task:
            exec_task.cancel()
            self._active_tasks.pop(task_id, None)

        # Try to cancel via executor
        await self.executor.cancel(task_id)

        # Update task status
        task = await self.task_store.cancel_task(task_id)
        if not task:
            raise ValueError(f'Task not found: {task_id}')

        return {'task': task.model_dump()}


# =============================================================================
# Router Factory
# =============================================================================


def create_a2a_router(
    executor: Optional[AgentExecutor] = None,
    task_store: Optional[TaskStore] = None,
    agent_card: Optional[AgentCard] = None,
    database_url: Optional[str] = None,
    require_authentication: bool = False,
    auth_callback: Optional[Callable[[str], bool]] = None,
) -> APIRouter:
    """
    Create an A2A protocol router with the provided executor.

    Args:
        executor: AgentExecutor implementation for handling requests.
                 Defaults to DefaultAgentExecutor.
        task_store: TaskStore implementation for persisting tasks.
                   Defaults to InMemoryTaskStore or DatabaseTaskStore if database_url is provided.
        agent_card: AgentCard for discovery. Optional.
        database_url: Database URL for DatabaseTaskStore. Optional.
        require_authentication: Whether to require authentication for all endpoints.
        auth_callback: Custom authentication callback (token) -> bool.

    Returns:
        FastAPI APIRouter with A2A protocol endpoints.
    """
    # Initialize executor
    if executor is None:
        executor = DefaultAgentExecutor()

    # Initialize task store
    if task_store is None:
        if database_url:
            task_store = DatabaseTaskStore(database_url)
        else:
            task_store = InMemoryTaskStore()

    # Create request handler
    handler = DefaultRequestHandler(executor, task_store)

    # Create router
    router = APIRouter(prefix='/a2a', tags=['a2a'])

    # Authentication dependency
    async def get_authenticated_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> Optional[UserSession]:
        """Get authenticated user if credentials provided."""
        if not credentials:
            if require_authentication:
                raise HTTPException(
                    status_code=401, detail='Authentication required'
                )
            return None

        token = credentials.credentials

        # Try custom auth callback first
        if auth_callback:
            if not auth_callback(token):
                raise HTTPException(status_code=401, detail='Invalid token')
            return None  # Custom auth doesn't provide user session

        # Try Keycloak auth
        try:
            user = await get_current_user(credentials)
            if user:
                return user
        except HTTPException:
            if require_authentication:
                raise

        if require_authentication:
            raise HTTPException(status_code=401, detail='Invalid token')

        return None

    # JSON-RPC endpoint
    @router.post('/jsonrpc')
    async def handle_jsonrpc(
        request: Request,
        user: Optional[UserSession] = Depends(get_authenticated_user),
    ) -> Response:
        """Handle JSON-RPC 2.0 requests."""
        try:
            body = await request.body()
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return JSONResponse(
                    content=JSONRPCResponse(
                        id=None,
                        error={'code': -32700, 'message': 'Parse error'},
                    ).model_dump(exclude_none=True),
                    status_code=400,
                )

            # Validate JSON-RPC structure
            try:
                rpc_request = JSONRPCRequest.model_validate(request_data)
            except Exception:
                return JSONResponse(
                    content=JSONRPCResponse(
                        id=request_data.get('id'),
                        error={'code': -32600, 'message': 'Invalid Request'},
                    ).model_dump(exclude_none=True),
                    status_code=400,
                )

            # Route methods
            method = rpc_request.method
            params = rpc_request.params or {}

            try:
                if method == 'message/send':
                    result = await handler.handle_send_message(params, user)
                elif method == 'message/stream':
                    # Return streaming response
                    return StreamingResponse(
                        handler.handle_stream_message(params, user),
                        media_type='text/event-stream',
                        headers={
                            'Cache-Control': 'no-cache',
                            'Connection': 'keep-alive',
                            'X-Accel-Buffering': 'no',
                        },
                    )
                elif method == 'tasks/get':
                    result = await handler.handle_get_task(params, user)
                elif method == 'tasks/cancel':
                    result = await handler.handle_cancel_task(params, user)
                else:
                    return JSONResponse(
                        content=JSONRPCResponse(
                            id=rpc_request.id,
                            error={
                                'code': -32601,
                                'message': 'Method not found',
                            },
                        ).model_dump(exclude_none=True),
                        status_code=400,
                    )

                return JSONResponse(
                    content=JSONRPCResponse(
                        id=rpc_request.id,
                        result=result,
                    ).model_dump(exclude_none=True),
                )

            except ValueError as e:
                return JSONResponse(
                    content=JSONRPCResponse(
                        id=rpc_request.id,
                        error={'code': -32602, 'message': str(e)},
                    ).model_dump(exclude_none=True),
                    status_code=400,
                )
            except Exception as e:
                logger.error(f'Error handling method {method}: {e}')
                return JSONResponse(
                    content=JSONRPCResponse(
                        id=rpc_request.id,
                        error={
                            'code': -32603,
                            'message': f'Internal error: {str(e)}',
                        },
                    ).model_dump(exclude_none=True),
                    status_code=500,
                )

        except Exception as e:
            logger.error(f'Error processing JSON-RPC request: {e}')
            return JSONResponse(
                content=JSONRPCResponse(
                    id=None,
                    error={'code': -32603, 'message': 'Internal error'},
                ).model_dump(exclude_none=True),
                status_code=500,
            )

    # REST binding: Send message
    @router.post('/rest/message:send')
    async def rest_send_message(
        request: Request,
        user: Optional[UserSession] = Depends(get_authenticated_user),
    ) -> JSONResponse:
        """REST binding for sending messages."""
        try:
            body = await request.json()
            result = await handler.handle_send_message(body, user)
            return JSONResponse(content=result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f'Error in REST send message: {e}')
            raise HTTPException(status_code=500, detail='Internal server error')

    # REST binding: Stream message
    @router.post('/rest/message:stream')
    async def rest_stream_message(
        request: Request,
        user: Optional[UserSession] = Depends(get_authenticated_user),
    ) -> StreamingResponse:
        """REST binding for streaming messages."""
        try:
            body = await request.json()
            return StreamingResponse(
                handler.handle_stream_message(body, user),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                },
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f'Error in REST stream message: {e}')
            raise HTTPException(status_code=500, detail='Internal server error')

    # REST binding: Get task
    @router.get('/rest/tasks/{task_id}')
    async def rest_get_task(
        task_id: str,
        user: Optional[UserSession] = Depends(get_authenticated_user),
    ) -> JSONResponse:
        """REST binding for getting task status."""
        try:
            result = await handler.handle_get_task({'id': task_id}, user)
            return JSONResponse(content=result)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error in REST get task: {e}')
            raise HTTPException(status_code=500, detail='Internal server error')

    # REST binding: Cancel task
    @router.post('/rest/tasks/{task_id}:cancel')
    async def rest_cancel_task(
        task_id: str,
        user: Optional[UserSession] = Depends(get_authenticated_user),
    ) -> JSONResponse:
        """REST binding for cancelling a task."""
        try:
            result = await handler.handle_cancel_task({'id': task_id}, user)
            return JSONResponse(content=result)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f'Error in REST cancel task: {e}')
            raise HTTPException(status_code=500, detail='Internal server error')

    # Agent card discovery endpoint
    if agent_card:

        @router.get('/.well-known/agent.json')
        async def get_agent_card_endpoint() -> JSONResponse:
            """Get the agent card for discovery."""
            return JSONResponse(content=agent_card.to_dict())

    return router


# =============================================================================
# Convenience function for quick setup
# =============================================================================


def setup_a2a_routes(
    app,
    executor: Optional[AgentExecutor] = None,
    agent_card: Optional[AgentCard] = None,
    database_url: Optional[str] = None,
    require_authentication: bool = False,
) -> None:
    """
    Convenience function to setup A2A routes on a FastAPI app.

    Args:
        app: FastAPI application instance
        executor: AgentExecutor implementation
        agent_card: AgentCard for discovery
        database_url: Database URL for task persistence
        require_authentication: Whether to require auth for all endpoints
    """
    router = create_a2a_router(
        executor=executor,
        agent_card=agent_card,
        database_url=database_url,
        require_authentication=require_authentication,
    )
    app.include_router(router)
    logger.info('A2A protocol routes mounted at /a2a')


# =============================================================================
# Export public API
# =============================================================================

__all__ = [
    # Core types
    'TaskState',
    'A2AMessage',
    'A2ATask',
    'JSONRPCRequest',
    'JSONRPCResponse',
    'JSONRPCError',
    # Task stores
    'TaskStore',
    'InMemoryTaskStore',
    'DatabaseTaskStore',
    # Executor
    'AgentExecutor',
    'DefaultAgentExecutor',
    'RequestContext',
    'EventQueue',
    # Request handler
    'DefaultRequestHandler',
    # Router factory
    'create_a2a_router',
    'setup_a2a_routes',
]
