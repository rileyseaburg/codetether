"""
Task management for A2A protocol.

Handles the lifecycle of tasks including creation, updates, and state management.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List, Callable, Any
from asyncio import Lock
import asyncio

from .models import Task, TaskStatus, TaskStatusUpdateEvent, Message

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages the lifecycle and state of A2A tasks."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._task_lock = Lock()
        self._update_handlers: Dict[str, List[Callable[[TaskStatusUpdateEvent], None]]] = {}
        self._handler_lock = Lock()

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Task:
        """Create a new task."""
        if task_id is None:
            task_id = str(uuid.uuid4())

        now = datetime.utcnow()
        task = Task(
            id=task_id,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            title=title,
            description=description
        )

        async with self._task_lock:
            self._tasks[task_id] = task

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        async with self._task_lock:
            return self._tasks.get(task_id)

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: Optional[Message] = None,
        progress: Optional[float] = None,
        final: bool = False
    ) -> Optional[Task]:
        """Update a task's status and notify handlers."""
        async with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            # Update task
            task.status = status
            task.updated_at = datetime.utcnow()
            if progress is not None:
                task.progress = progress

            # Create update event
            event = TaskStatusUpdateEvent(
                task=task,
                message=message,
                final=final
            )

        # Notify handlers
        await self._notify_handlers(task_id, event)

        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        return await self.update_task_status(task_id, TaskStatus.CANCELLED, final=True)

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from storage."""
        async with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        async with self._task_lock:
            tasks = list(self._tasks.values())

        if status is not None:
            tasks = [task for task in tasks if task.status == status]

        return tasks

    async def register_update_handler(
        self,
        task_id: str,
        handler: Callable[[TaskStatusUpdateEvent], None]
    ) -> None:
        """Register a handler for task updates."""
        async with self._handler_lock:
            if task_id not in self._update_handlers:
                self._update_handlers[task_id] = []
            self._update_handlers[task_id].append(handler)

    async def unregister_update_handler(
        self,
        task_id: str,
        handler: Callable[[TaskStatusUpdateEvent], None]
    ) -> None:
        """Unregister a handler for task updates."""
        async with self._handler_lock:
            if task_id in self._update_handlers:
                try:
                    self._update_handlers[task_id].remove(handler)
                    if not self._update_handlers[task_id]:
                        del self._update_handlers[task_id]
                except ValueError:
                    pass  # Handler wasn't registered

    async def _notify_handlers(self, task_id: str, event: TaskStatusUpdateEvent) -> None:
        """Notify all registered handlers for a task."""
        async with self._handler_lock:
            handlers = self._update_handlers.get(task_id, []).copy()

        # Run handlers concurrently
        if handlers:
            await asyncio.gather(
                *[self._safe_call_handler(handler, event) for handler in handlers],
                return_exceptions=True
            )

    async def _safe_call_handler(
        self,
        handler: Callable[[TaskStatusUpdateEvent], None],
        event: TaskStatusUpdateEvent
    ) -> None:
        """Safely call a handler, catching any exceptions."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            # Log error but don't let it break other handlers
            print(f"Error in task update handler: {e}")


class InMemoryTaskManager(TaskManager):
    """In-memory implementation of TaskManager."""
    pass  # Uses the base class implementation


class PersistentTaskManager(TaskManager):
    """Task manager with PostgreSQL-backed persistent storage."""

    def __init__(self, storage_path: str):
        super().__init__()
        self.storage_path = storage_path
        self._pool = None
        self._pool_lock = Lock()
        self._initialized = False

    async def _get_pool(self):
        if self._pool:
            return self._pool

        async with self._pool_lock:
            if self._pool:
                return self._pool

            try:
                import asyncpg
            except ImportError as exc:
                raise ImportError(
                    "asyncpg is required for PersistentTaskManager. Install with: pip install asyncpg"
                ) from exc

            self._pool = await asyncpg.create_pool(
                self.storage_path,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )

            if not self._initialized:
                await self._init_schema(self._pool)
                self._initialized = True

        return self._pool

    async def _init_schema(self, pool) -> None:
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS a2a_tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    progress REAL,
                    messages JSONB DEFAULT '[]'::jsonb
                )
            """)

            await conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_a2a_tasks_status ON a2a_tasks(status)'
            )
            await conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_a2a_tasks_updated_at ON a2a_tasks(updated_at)'
            )

    def _deserialize_messages(self, value: Any) -> Optional[List[Message]]:
        if not value:
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                logger.warning("Failed to decode task messages: %s", exc)
                return None

        messages: List[Message] = []
        if isinstance(value, list):
            for item in value:
                try:
                    messages.append(Message.model_validate(item))
                except Exception as exc:
                    logger.warning("Failed to parse task message: %s", exc)
        return messages or None

    def _row_to_task(self, row) -> Task:
        return Task(
            id=row['id'],
            status=TaskStatus(row['status']),
            title=row['title'],
            description=row['description'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            progress=row['progress'],
            messages=self._deserialize_messages(row['messages']),
        )

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Task:
        """Create a new task and store it in PostgreSQL."""
        if task_id is None:
            task_id = str(uuid.uuid4())

        now = datetime.utcnow()
        task = Task(
            id=task_id,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            title=title,
            description=description
        )

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO a2a_tasks (id, status, title, description, created_at, updated_at, progress, messages)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                task.id,
                task.status.value,
                task.title,
                task.description,
                task.created_at,
                task.updated_at,
                task.progress,
                json.dumps([]),
            )

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, status, title, description, created_at, updated_at, progress, messages
                FROM a2a_tasks
                WHERE id = $1
                """,
                task_id,
            )
        if not row:
            return None
        return self._row_to_task(row)

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: Optional[Message] = None,
        progress: Optional[float] = None,
        final: bool = False
    ) -> Optional[Task]:
        """Update a task's status in PostgreSQL and notify handlers."""
        updates = ['status = $2', 'updated_at = $3']
        params: List[Any] = [task_id, status.value, datetime.utcnow()]
        param_idx = 4

        if progress is not None:
            updates.append(f'progress = ${param_idx}')
            params.append(progress)
            param_idx += 1

        if message:
            updates.append(
                f"messages = COALESCE(messages, '[]'::jsonb) || ${param_idx}::jsonb"
            )
            params.append(json.dumps([message.model_dump(mode='json')]))
            param_idx += 1

        query = f"""
            UPDATE a2a_tasks
            SET {", ".join(updates)}
            WHERE id = $1
            RETURNING id, status, title, description, created_at, updated_at, progress, messages
        """

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return None

        task = self._row_to_task(row)

        event = TaskStatusUpdateEvent(
            task=task,
            message=message,
            final=final
        )

        await self._notify_handlers(task_id, event)

        return task

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from storage."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                'DELETE FROM a2a_tasks WHERE id = $1', task_id
            )
        return 'DELETE 1' in result

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if status is None:
                rows = await conn.fetch(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages
                    FROM a2a_tasks
                    ORDER BY created_at DESC
                    """
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages
                    FROM a2a_tasks
                    WHERE status = $1
                    ORDER BY created_at DESC
                    """,
                    status.value,
                )

        return [self._row_to_task(row) for row in rows]

    async def cleanup(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
