"""
Redis-backed Task Manager for A2A Server.

Provides persistent task storage using Redis, ensuring tasks survive server restarts.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, List, Callable
from asyncio import Lock
import asyncio

from .models import Task, TaskStatus, TaskStatusUpdateEvent, Message
from .task_manager import TaskManager

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed. Install with: pip install redis")


class RedisTaskManager(TaskManager):
    """
    Redis-backed task manager with persistent storage.

    Tasks are stored as Redis hashes with the key pattern: task:{task_id}
    Task IDs by status are indexed in Redis sets: tasks:status:{status}
    All task IDs are tracked in a set: tasks:all
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize Redis task manager.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        super().__init__()

        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for RedisTaskManager. "
                "Install with: pip install redis"
            )

        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False

        # Key prefixes
        self.TASK_PREFIX = "task:"
        self.STATUS_SET_PREFIX = "tasks:status:"
        self.ALL_TASKS_SET = "tasks:all"

    async def connect(self):
        """Establish connection to Redis."""
        if self._connected and self.redis:
            return

        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    def _task_key(self, task_id: str) -> str:
        """Generate Redis key for a task."""
        return f"{self.TASK_PREFIX}{task_id}"

    def _status_set_key(self, status: TaskStatus) -> str:
        """Generate Redis set key for tasks with a specific status."""
        return f"{self.STATUS_SET_PREFIX}{status.value}"

    def _serialize_task(self, task: Task) -> Dict[str, str]:
        """Serialize task to Redis hash format."""
        return {
            "id": task.id,
            "status": task.status.value,
            "title": task.title or "",
            "description": task.description or "",
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "progress": str(task.progress or 0.0),
            # Store messages as JSON if present
            "messages": json.dumps([
                msg.model_dump(mode='json') for msg in (task.messages or [])
            ])
        }

    def _deserialize_task(self, data: Dict[str, str]) -> Task:
        """Deserialize task from Redis hash format."""
        messages_json = data.get("messages", "[]")
        messages = []
        try:
            messages_data = json.loads(messages_json)
            messages = [Message.model_validate(msg) for msg in messages_data]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to deserialize messages: {e}")

        # Get fields, preserving empty strings as valid values
        title = data.get("title")
        description = data.get("description")

        return Task(
            id=data["id"],
            status=TaskStatus(data["status"]),
            title=title if title else None,
            description=description if description else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            progress=float(data.get("progress", 0.0)),
            messages=messages if messages else None
        )

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Task:
        """Create a new task and store it in Redis."""
        if not self._connected:
            await self.connect()

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
            # Store task in Redis
            task_data = self._serialize_task(task)
            await self.redis.hset(self._task_key(task_id), mapping=task_data)

            # Add to status index
            await self.redis.sadd(self._status_set_key(TaskStatus.PENDING), task_id)

            # Add to all tasks index
            await self.redis.sadd(self.ALL_TASKS_SET, task_id)

        logger.info(f"Created task {task_id}: {title}")
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task from Redis by ID."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            task_data = await self.redis.hgetall(self._task_key(task_id))

            if not task_data:
                return None

            return self._deserialize_task(task_data)

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: Optional[Message] = None,
        progress: Optional[float] = None,
        final: bool = False
    ) -> Optional[Task]:
        """Update a task's status in Redis and notify handlers."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            # Get existing task
            task_data = await self.redis.hgetall(self._task_key(task_id))
            if not task_data:
                return None

            task = self._deserialize_task(task_data)
            old_status = task.status

            # Update task
            task.status = status
            task.updated_at = datetime.utcnow()
            if progress is not None:
                task.progress = progress

            if message:
                if task.messages is None:
                    task.messages = []
                task.messages.append(message)

            # Store updated task
            updated_data = self._serialize_task(task)
            await self.redis.hset(self._task_key(task_id), mapping=updated_data)

            # Update status indices if status changed
            if old_status != status:
                await self.redis.srem(self._status_set_key(old_status), task_id)
                await self.redis.sadd(self._status_set_key(status), task_id)

            # Create update event
            event = TaskStatusUpdateEvent(
                task=task,
                message=message,
                final=final
            )

        # Notify handlers
        await self._notify_handlers(task_id, event)

        logger.info(f"Updated task {task_id} status: {old_status.value} -> {status.value}")
        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        return await self.update_task_status(task_id, TaskStatus.CANCELLED, final=True)

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from Redis storage."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            # Get task to find its status
            task_data = await self.redis.hgetall(self._task_key(task_id))
            if not task_data:
                return False

            status = TaskStatus(task_data["status"])

            # Remove from all indices
            await self.redis.srem(self._status_set_key(status), task_id)
            await self.redis.srem(self.ALL_TASKS_SET, task_id)

            # Delete the task hash
            await self.redis.delete(self._task_key(task_id))

        logger.info(f"Deleted task {task_id}")
        return True

    async def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            # Get task IDs
            if status is not None:
                task_ids = await self.redis.smembers(self._status_set_key(status))
            else:
                task_ids = await self.redis.smembers(self.ALL_TASKS_SET)

            # Fetch all tasks
            tasks = []
            for task_id in task_ids:
                task_data = await self.redis.hgetall(self._task_key(task_id))
                if task_data:
                    tasks.append(self._deserialize_task(task_data))

        return tasks

    async def cleanup(self):
        """Clean up Redis connections."""
        await self.disconnect()
