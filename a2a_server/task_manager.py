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
        self._update_handlers: Dict[
            str, List[Callable[[TaskStatusUpdateEvent], None]]
        ] = {}
        self._handler_lock = Lock()

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None,
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
            description=description,
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
        final: bool = False,
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
                task=task, message=message, final=final
            )

        # Notify handlers
        await self._notify_handlers(task_id, event)

        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        return await self.update_task_status(
            task_id, TaskStatus.CANCELLED, final=True
        )

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from storage."""
        async with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    async def list_tasks(
        self, status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        async with self._task_lock:
            tasks = list(self._tasks.values())

        if status is not None:
            tasks = [task for task in tasks if task.status == status]

        return tasks

    async def claim_task(self, task_id: str, worker_id: str) -> Optional[Task]:
        """
        Atomically claim a task for a worker.

        This method checks if the task is in 'pending' status and atomically
        sets it to 'working' while recording which worker claimed it.

        Args:
            task_id: The ID of the task to claim
            worker_id: The ID of the worker claiming the task

        Returns:
            The claimed Task if successful, None if the task doesn't exist,
            is not in pending status, or was already claimed by another worker.
        """
        async with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            # Only allow claiming pending tasks
            if task.status != TaskStatus.PENDING:
                logger.debug(
                    f'Task {task_id} cannot be claimed: status is {task.status.value}'
                )
                return None

            # Claim the task
            now = datetime.utcnow()
            task.status = TaskStatus.WORKING
            task.worker_id = worker_id
            task.claimed_at = now
            task.updated_at = now

            # Create update event
            event = TaskStatusUpdateEvent(task=task, message=None, final=False)

        # Notify handlers outside the lock
        await self._notify_handlers(task_id, event)
        logger.info(f'Task {task_id} claimed by worker {worker_id}')

        return task

    async def release_task(
        self, task_id: str, worker_id: str
    ) -> Optional[Task]:
        """
        Release a claimed task back to pending status.

        This is used when a worker fails, disconnects, or wants to give up
        on a task. Only the worker that claimed the task can release it.

        Args:
            task_id: The ID of the task to release
            worker_id: The ID of the worker releasing the task

        Returns:
            The released Task if successful, None if the task doesn't exist
            or the worker_id doesn't match the claiming worker.
        """
        async with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            # Only allow the claiming worker to release the task
            if task.worker_id != worker_id:
                logger.warning(
                    f'Worker {worker_id} attempted to release task {task_id} '
                    f'but it is owned by {task.worker_id}'
                )
                return None

            # Only release tasks that are currently being worked on
            if task.status != TaskStatus.WORKING:
                logger.debug(
                    f'Task {task_id} cannot be released: status is {task.status.value}'
                )
                return None

            # Release the task
            now = datetime.utcnow()
            task.status = TaskStatus.PENDING
            task.worker_id = None
            task.claimed_at = None
            task.updated_at = now

            # Create update event
            event = TaskStatusUpdateEvent(task=task, message=None, final=False)

        # Notify handlers outside the lock
        await self._notify_handlers(task_id, event)
        logger.info(f'Task {task_id} released by worker {worker_id}')

        return task

    async def register_update_handler(
        self, task_id: str, handler: Callable[[TaskStatusUpdateEvent], None]
    ) -> None:
        """Register a handler for task updates."""
        async with self._handler_lock:
            if task_id not in self._update_handlers:
                self._update_handlers[task_id] = []
            self._update_handlers[task_id].append(handler)

    async def unregister_update_handler(
        self, task_id: str, handler: Callable[[TaskStatusUpdateEvent], None]
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

    async def _notify_handlers(
        self, task_id: str, event: TaskStatusUpdateEvent
    ) -> None:
        """Notify all registered handlers for a task."""
        async with self._handler_lock:
            handlers = self._update_handlers.get(task_id, []).copy()

        # Run handlers concurrently
        if handlers:
            await asyncio.gather(
                *[
                    self._safe_call_handler(handler, event)
                    for handler in handlers
                ],
                return_exceptions=True,
            )

    async def _safe_call_handler(
        self,
        handler: Callable[[TaskStatusUpdateEvent], None],
        event: TaskStatusUpdateEvent,
    ) -> None:
        """Safely call a handler, catching any exceptions."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            # Log error but don't let it break other handlers
            print(f'Error in task update handler: {e}')


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
                    'asyncpg is required for PersistentTaskManager. Install with: pip install asyncpg'
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
                    messages JSONB DEFAULT '[]'::jsonb,
                    worker_id TEXT,
                    claimed_at TIMESTAMPTZ
                )
            """)

            await conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_a2a_tasks_status ON a2a_tasks(status)'
            )
            await conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_a2a_tasks_updated_at ON a2a_tasks(updated_at)'
            )
            await conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_a2a_tasks_worker_id ON a2a_tasks(worker_id)'
            )

            # Add columns if they don't exist (for existing databases)
            await conn.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'a2a_tasks' AND column_name = 'worker_id') THEN
                        ALTER TABLE a2a_tasks ADD COLUMN worker_id TEXT;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name = 'a2a_tasks' AND column_name = 'claimed_at') THEN
                        ALTER TABLE a2a_tasks ADD COLUMN claimed_at TIMESTAMPTZ;
                    END IF;
                END $$;
            """)

    def _deserialize_messages(self, value: Any) -> Optional[List[Message]]:
        if not value:
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                logger.warning('Failed to decode task messages: %s', exc)
                return None

        messages: List[Message] = []
        if isinstance(value, list):
            for item in value:
                try:
                    messages.append(Message.model_validate(item))
                except Exception as exc:
                    logger.warning('Failed to parse task message: %s', exc)
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
            worker_id=row.get('worker_id'),
            claimed_at=row.get('claimed_at'),
        )

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None,
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
            description=description,
        )

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO a2a_tasks (id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                task.id,
                task.status.value,
                task.title,
                task.description,
                task.created_at,
                task.updated_at,
                task.progress,
                json.dumps([]),
                None,  # worker_id
                None,  # claimed_at
            )

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
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
        final: bool = False,
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
            SET {', '.join(updates)}
            WHERE id = $1
            RETURNING id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
        """

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return None

        task = self._row_to_task(row)

        event = TaskStatusUpdateEvent(task=task, message=message, final=final)

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

    async def list_tasks(
        self, status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if status is None:
                rows = await conn.fetch(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    FROM a2a_tasks
                    ORDER BY created_at DESC
                    """
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    FROM a2a_tasks
                    WHERE status = $1
                    ORDER BY created_at DESC
                    """,
                    status.value,
                )

        return [self._row_to_task(row) for row in rows]

    async def claim_task(self, task_id: str, worker_id: str) -> Optional[Task]:
        """
        Atomically claim a task for a worker using database transactions.

        Uses SELECT FOR UPDATE to lock the row and ensure atomic claim.

        Args:
            task_id: The ID of the task to claim
            worker_id: The ID of the worker claiming the task

        Returns:
            The claimed Task if successful, None if the task doesn't exist,
            is not in pending status, or was already claimed by another worker.
        """
        pool = await self._get_pool()
        now = datetime.utcnow()

        async with pool.acquire() as conn:
            # Use a transaction with row-level locking for atomicity
            async with conn.transaction():
                # Lock the row and check status atomically
                row = await conn.fetchrow(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    FROM a2a_tasks
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    task_id,
                )

                if not row:
                    return None

                # Check if task is pending
                if row['status'] != TaskStatus.PENDING.value:
                    logger.debug(
                        f'Task {task_id} cannot be claimed: status is {row["status"]}'
                    )
                    return None

                # Claim the task
                updated_row = await conn.fetchrow(
                    """
                    UPDATE a2a_tasks
                    SET status = $2, worker_id = $3, claimed_at = $4, updated_at = $4
                    WHERE id = $1
                    RETURNING id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    """,
                    task_id,
                    TaskStatus.WORKING.value,
                    worker_id,
                    now,
                )

        task = self._row_to_task(updated_row)

        # Notify handlers
        event = TaskStatusUpdateEvent(task=task, message=None, final=False)
        await self._notify_handlers(task_id, event)
        logger.info(f'Task {task_id} claimed by worker {worker_id}')

        return task

    async def release_task(
        self, task_id: str, worker_id: str
    ) -> Optional[Task]:
        """
        Release a claimed task back to pending status using database transactions.

        Uses SELECT FOR UPDATE to lock the row and ensure atomic release.

        Args:
            task_id: The ID of the task to release
            worker_id: The ID of the worker releasing the task

        Returns:
            The released Task if successful, None if the task doesn't exist
            or the worker_id doesn't match the claiming worker.
        """
        pool = await self._get_pool()
        now = datetime.utcnow()

        async with pool.acquire() as conn:
            # Use a transaction with row-level locking for atomicity
            async with conn.transaction():
                # Lock the row and check ownership atomically
                row = await conn.fetchrow(
                    """
                    SELECT id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    FROM a2a_tasks
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    task_id,
                )

                if not row:
                    return None

                # Check if worker owns this task
                if row['worker_id'] != worker_id:
                    logger.warning(
                        f'Worker {worker_id} attempted to release task {task_id} '
                        f'but it is owned by {row["worker_id"]}'
                    )
                    return None

                # Check if task is in working status
                if row['status'] != TaskStatus.WORKING.value:
                    logger.debug(
                        f'Task {task_id} cannot be released: status is {row["status"]}'
                    )
                    return None

                # Release the task
                updated_row = await conn.fetchrow(
                    """
                    UPDATE a2a_tasks
                    SET status = $2, worker_id = NULL, claimed_at = NULL, updated_at = $3
                    WHERE id = $1
                    RETURNING id, status, title, description, created_at, updated_at, progress, messages, worker_id, claimed_at
                    """,
                    task_id,
                    TaskStatus.PENDING.value,
                    now,
                )

        task = self._row_to_task(updated_row)

        # Notify handlers
        event = TaskStatusUpdateEvent(task=task, message=None, final=False)
        await self._notify_handlers(task_id, event)
        logger.info(f'Task {task_id} released by worker {worker_id}')

        return task

    async def cleanup(self) -> None:
        """Close database connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
