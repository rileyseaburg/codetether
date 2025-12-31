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
    logger.warning(
        'redis package not installed. Install with: pip install redis'
    )


class RedisTaskManager(TaskManager):
    """
    Redis-backed task manager with persistent storage.

    Tasks are stored as Redis hashes with the key pattern: task:{task_id}
    Task IDs by status are indexed in Redis sets: tasks:status:{status}
    All task IDs are tracked in a set: tasks:all
    """

    def __init__(self, redis_url: str = 'redis://localhost:6379'):
        """
        Initialize Redis task manager.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        super().__init__()

        if not REDIS_AVAILABLE:
            raise ImportError(
                'redis package is required for RedisTaskManager. '
                'Install with: pip install redis'
            )

        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self._connected = False

        # Key prefixes
        self.TASK_PREFIX = 'task:'
        self.STATUS_SET_PREFIX = 'tasks:status:'
        self.ALL_TASKS_SET = 'tasks:all'

        # Lua scripts for atomic operations
        self._claim_script = None
        self._release_script = None

    async def connect(self):
        """Establish connection to Redis."""
        if self._connected and self.redis:
            return

        try:
            self.redis = await aioredis.from_url(
                self.redis_url, encoding='utf-8', decode_responses=True
            )
            # Test connection
            await self.redis.ping()
            self._connected = True
            logger.info(f'Connected to Redis at {self.redis_url}')
        except Exception as e:
            logger.error(f'Failed to connect to Redis: {e}')
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self._connected = False
            logger.info('Disconnected from Redis')

    def _task_key(self, task_id: str) -> str:
        """Generate Redis key for a task."""
        return f'{self.TASK_PREFIX}{task_id}'

    def _status_set_key(self, status: TaskStatus) -> str:
        """Generate Redis set key for tasks with a specific status."""
        return f'{self.STATUS_SET_PREFIX}{status.value}'

    def _serialize_task(self, task: Task) -> Dict[str, str]:
        """Serialize task to Redis hash format."""
        return {
            'id': task.id,
            'status': task.status.value,
            'title': task.title or '',
            'description': task.description or '',
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
            'progress': str(task.progress or 0.0),
            # Store messages as JSON if present
            'messages': json.dumps(
                [msg.model_dump(mode='json') for msg in (task.messages or [])]
            ),
            'worker_id': task.worker_id or '',
            'claimed_at': task.claimed_at.isoformat()
            if task.claimed_at
            else '',
        }

    def _deserialize_task(self, data: Dict[str, str]) -> Task:
        """Deserialize task from Redis hash format."""
        messages_json = data.get('messages', '[]')
        messages = []
        try:
            messages_data = json.loads(messages_json)
            messages = [Message.model_validate(msg) for msg in messages_data]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f'Failed to deserialize messages: {e}')

        # Get fields, preserving empty strings as valid values
        title = data.get('title')
        description = data.get('description')
        worker_id = data.get('worker_id')
        claimed_at_str = data.get('claimed_at')

        return Task(
            id=data['id'],
            status=TaskStatus(data['status']),
            title=title if title else None,
            description=description if description else None,
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            progress=float(data.get('progress', 0.0)),
            messages=messages if messages else None,
            worker_id=worker_id if worker_id else None,
            claimed_at=datetime.fromisoformat(claimed_at_str)
            if claimed_at_str
            else None,
        )

    async def create_task(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        task_id: Optional[str] = None,
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
            description=description,
        )

        async with self._task_lock:
            # Store task in Redis
            task_data = self._serialize_task(task)
            await self.redis.hset(self._task_key(task_id), mapping=task_data)

            # Add to status index
            await self.redis.sadd(
                self._status_set_key(TaskStatus.PENDING), task_id
            )

            # Add to all tasks index
            await self.redis.sadd(self.ALL_TASKS_SET, task_id)

        logger.info(f'Created task {task_id}: {title}')
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
        final: bool = False,
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
                task=task, message=message, final=final
            )

        # Notify handlers
        await self._notify_handlers(task_id, event)

        logger.info(
            f'Updated task {task_id} status: {old_status.value} -> {status.value}'
        )
        return task

    async def cancel_task(self, task_id: str) -> Optional[Task]:
        """Cancel a task."""
        return await self.update_task_status(
            task_id, TaskStatus.CANCELLED, final=True
        )

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task from Redis storage."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            # Get task to find its status
            task_data = await self.redis.hgetall(self._task_key(task_id))
            if not task_data:
                return False

            status = TaskStatus(task_data['status'])

            # Remove from all indices
            await self.redis.srem(self._status_set_key(status), task_id)
            await self.redis.srem(self.ALL_TASKS_SET, task_id)

            # Delete the task hash
            await self.redis.delete(self._task_key(task_id))

        logger.info(f'Deleted task {task_id}')
        return True

    async def list_tasks(
        self, status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        if not self._connected:
            await self.connect()

        async with self._task_lock:
            # Get task IDs
            if status is not None:
                task_ids = await self.redis.smembers(
                    self._status_set_key(status)
                )
            else:
                task_ids = await self.redis.smembers(self.ALL_TASKS_SET)

            # Fetch all tasks
            tasks = []
            for task_id in task_ids:
                task_data = await self.redis.hgetall(self._task_key(task_id))
                if task_data:
                    tasks.append(self._deserialize_task(task_data))

        return tasks

    async def _get_claim_script(self):
        """Get or create the Lua script for atomic task claiming."""
        if self._claim_script is None:
            # Lua script for atomic task claiming
            # KEYS[1] = task key (task:{task_id})
            # KEYS[2] = pending status set key
            # KEYS[3] = working status set key
            # ARGV[1] = worker_id
            # ARGV[2] = updated_at timestamp (ISO format)
            # ARGV[3] = pending status value
            # ARGV[4] = working status value
            script = """
                -- Get current task data
                local task_data = redis.call('HGETALL', KEYS[1])
                if #task_data == 0 then
                    return nil
                end
                
                -- Parse task data into a table
                local task = {}
                for i = 1, #task_data, 2 do
                    task[task_data[i]] = task_data[i + 1]
                end
                
                -- Check if task is in pending status
                if task['status'] ~= ARGV[3] then
                    return nil
                end
                
                -- Update task fields atomically
                redis.call('HSET', KEYS[1],
                    'status', ARGV[4],
                    'worker_id', ARGV[1],
                    'claimed_at', ARGV[2],
                    'updated_at', ARGV[2]
                )
                
                -- Update status indices
                redis.call('SREM', KEYS[2], task['id'])
                redis.call('SADD', KEYS[3], task['id'])
                
                -- Return success indicator
                return 1
            """
            self._claim_script = self.redis.register_script(script)
        return self._claim_script

    async def _get_release_script(self):
        """Get or create the Lua script for atomic task release."""
        if self._release_script is None:
            # Lua script for atomic task release
            # KEYS[1] = task key (task:{task_id})
            # KEYS[2] = working status set key
            # KEYS[3] = pending status set key
            # ARGV[1] = worker_id (must match current owner)
            # ARGV[2] = updated_at timestamp (ISO format)
            # ARGV[3] = working status value
            # ARGV[4] = pending status value
            script = """
                -- Get current task data
                local task_data = redis.call('HGETALL', KEYS[1])
                if #task_data == 0 then
                    return nil
                end
                
                -- Parse task data into a table
                local task = {}
                for i = 1, #task_data, 2 do
                    task[task_data[i]] = task_data[i + 1]
                end
                
                -- Check if worker owns this task
                if task['worker_id'] ~= ARGV[1] then
                    return nil
                end
                
                -- Check if task is in working status
                if task['status'] ~= ARGV[3] then
                    return nil
                end
                
                -- Update task fields atomically
                redis.call('HSET', KEYS[1],
                    'status', ARGV[4],
                    'worker_id', '',
                    'claimed_at', '',
                    'updated_at', ARGV[2]
                )
                
                -- Update status indices
                redis.call('SREM', KEYS[2], task['id'])
                redis.call('SADD', KEYS[3], task['id'])
                
                -- Return success indicator
                return 1
            """
            self._release_script = self.redis.register_script(script)
        return self._release_script

    async def claim_task(self, task_id: str, worker_id: str) -> Optional[Task]:
        """
        Atomically claim a task for a worker using a Lua script.

        This method uses a Lua script to ensure atomicity of the check-and-update
        operation in Redis, preventing race conditions between multiple workers.

        Args:
            task_id: The ID of the task to claim
            worker_id: The ID of the worker claiming the task

        Returns:
            The claimed Task if successful, None if the task doesn't exist,
            is not in pending status, or was already claimed by another worker.
        """
        if not self._connected:
            await self.connect()

        now = datetime.utcnow()
        claim_script = await self._get_claim_script()

        # Execute the Lua script
        result = await claim_script(
            keys=[
                self._task_key(task_id),
                self._status_set_key(TaskStatus.PENDING),
                self._status_set_key(TaskStatus.WORKING),
            ],
            args=[
                worker_id,
                now.isoformat(),
                TaskStatus.PENDING.value,
                TaskStatus.WORKING.value,
            ],
        )

        if result is None:
            logger.debug(
                f'Task {task_id} could not be claimed by worker {worker_id}'
            )
            return None

        # Fetch and return the updated task
        task = await self.get_task(task_id)
        if task:
            # Notify handlers
            event = TaskStatusUpdateEvent(task=task, message=None, final=False)
            await self._notify_handlers(task_id, event)
            logger.info(f'Task {task_id} claimed by worker {worker_id}')

        return task

    async def release_task(
        self, task_id: str, worker_id: str
    ) -> Optional[Task]:
        """
        Release a claimed task back to pending status using a Lua script.

        This method uses a Lua script to ensure atomicity of the check-and-update
        operation in Redis, preventing race conditions.

        Args:
            task_id: The ID of the task to release
            worker_id: The ID of the worker releasing the task

        Returns:
            The released Task if successful, None if the task doesn't exist
            or the worker_id doesn't match the claiming worker.
        """
        if not self._connected:
            await self.connect()

        now = datetime.utcnow()
        release_script = await self._get_release_script()

        # Execute the Lua script
        result = await release_script(
            keys=[
                self._task_key(task_id),
                self._status_set_key(TaskStatus.WORKING),
                self._status_set_key(TaskStatus.PENDING),
            ],
            args=[
                worker_id,
                now.isoformat(),
                TaskStatus.WORKING.value,
                TaskStatus.PENDING.value,
            ],
        )

        if result is None:
            logger.debug(
                f'Task {task_id} could not be released by worker {worker_id}'
            )
            return None

        # Fetch and return the updated task
        task = await self.get_task(task_id)
        if task:
            # Notify handlers
            event = TaskStatusUpdateEvent(task=task, message=None, final=False)
            await self._notify_handlers(task_id, event)
            logger.info(f'Task {task_id} released by worker {worker_id}')

        return task

    async def cleanup(self):
        """Clean up Redis connections."""
        await self.disconnect()
