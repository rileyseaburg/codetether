"""
Task management for A2A protocol.

Handles the lifecycle of tasks including creation, updates, and state management.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, List, Callable, Any
from asyncio import Lock
import asyncio

from .models import Task, TaskStatus, TaskStatusUpdateEvent, Message


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
    """Task manager with persistent storage (placeholder for future implementation)."""
    
    def __init__(self, storage_path: str):
        super().__init__()
        self.storage_path = storage_path
        # TODO: Implement persistent storage using SQLite or similar