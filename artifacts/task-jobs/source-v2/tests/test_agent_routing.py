"""
Tests for agent routing functionality.

Tests the new send_to_agent and send_message_async tools, as well as
the underlying routing logic in worker_sse.py and task_queue.py.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Import the modules under test
from a2a_server.worker_sse import (
    WorkerRegistry,
    ConnectedWorker,
    get_worker_registry,
    notify_workers_of_new_task,
)
from a2a_server.task_queue import TaskRun, TaskRunStatus


class TestWorkerRegistryRouting:
    """Test agent-targeted routing in WorkerRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh worker registry for testing."""
        return WorkerRegistry()

    @pytest.fixture
    def worker_queue(self):
        """Create a queue for worker events."""
        return asyncio.Queue()

    @pytest.mark.asyncio
    async def test_get_available_workers_no_targeting(
        self, registry, worker_queue
    ):
        """Workers without target_agent_name should match all available workers."""
        # Register two workers with different agent names
        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=worker_queue,
        )
        await registry.register_worker(
            worker_id='worker2',
            agent_name='agent-beta',
            queue=worker_queue,
        )

        # Without targeting, both workers should be available
        available = await registry.get_available_workers()
        assert len(available) == 2

    @pytest.mark.asyncio
    async def test_get_available_workers_with_targeting(
        self, registry, worker_queue
    ):
        """With target_agent_name set, only matching workers should be returned."""
        # Register two workers with different agent names
        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=worker_queue,
        )
        await registry.register_worker(
            worker_id='worker2',
            agent_name='agent-beta',
            queue=worker_queue,
        )

        # Target agent-alpha specifically
        available = await registry.get_available_workers(
            target_agent_name='agent-alpha'
        )
        assert len(available) == 1
        assert available[0].agent_name == 'agent-alpha'

    @pytest.mark.asyncio
    async def test_get_available_workers_target_not_found(
        self, registry, worker_queue
    ):
        """If target agent is not online, should return empty list."""
        # Register a worker with different agent name
        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=worker_queue,
        )

        # Target non-existent agent
        available = await registry.get_available_workers(
            target_agent_name='agent-gamma'
        )
        assert len(available) == 0

    @pytest.mark.asyncio
    async def test_get_available_workers_busy_excluded(
        self, registry, worker_queue
    ):
        """Busy workers should be excluded even if they match targeting."""
        # Register a worker
        worker = await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=worker_queue,
        )

        # Mark worker as busy
        await registry.claim_task('task-123', 'worker1')

        # Even when targeted, busy workers should be excluded
        available = await registry.get_available_workers(
            target_agent_name='agent-alpha'
        )
        assert len(available) == 0

    @pytest.mark.asyncio
    async def test_broadcast_task_with_targeting(self, registry, worker_queue):
        """broadcast_task should only notify targeted agent."""
        queue1 = asyncio.Queue()
        queue2 = asyncio.Queue()

        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=queue1,
        )
        await registry.register_worker(
            worker_id='worker2',
            agent_name='agent-beta',
            queue=queue2,
        )

        task_data = {
            'id': 'task-123',
            'title': 'Test Task',
            'target_agent_name': 'agent-alpha',
        }

        notified = await registry.broadcast_task(
            task_data,
            target_agent_name='agent-alpha',
        )

        # Only worker1 (agent-alpha) should be notified
        assert len(notified) == 1
        assert 'worker1' in notified

        # Verify queue1 got the notification, queue2 did not
        assert not queue1.empty()
        assert queue2.empty()


class TestNotifyWorkersOfNewTask:
    """Test the notify_workers_of_new_task function with routing fields."""

    @pytest.mark.asyncio
    async def test_notify_extracts_target_agent_name(self):
        """notify_workers_of_new_task should extract and pass target_agent_name."""
        with patch(
            'a2a_server.worker_sse.get_worker_registry'
        ) as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.broadcast_task = AsyncMock(return_value=['worker1'])
            mock_get_registry.return_value = mock_registry

            task_data = {
                'id': 'task-123',
                'codebase_id': 'global',
                'target_agent_name': 'agent-alpha',
                'required_capabilities': ['coding', 'testing'],
            }

            await notify_workers_of_new_task(task_data)

            # Verify broadcast_task was called with routing fields
            mock_registry.broadcast_task.assert_called_once()
            call_args = mock_registry.broadcast_task.call_args
            assert call_args.kwargs.get('target_agent_name') == 'agent-alpha'
            assert call_args.kwargs.get('required_capabilities') == [
                'coding',
                'testing',
            ]


class TestTaskRunRouting:
    """Test TaskRun dataclass with routing fields."""

    def test_task_run_with_routing_fields(self):
        """TaskRun should properly store routing fields."""
        deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

        run = TaskRun(
            id='run-123',
            task_id='task-456',
            target_agent_name='agent-alpha',
            required_capabilities=['coding', 'testing'],
            deadline_at=deadline,
        )

        assert run.target_agent_name == 'agent-alpha'
        assert run.required_capabilities == ['coding', 'testing']
        assert run.deadline_at == deadline
        assert run.routing_failed_at is None
        assert run.routing_failure_reason is None

    def test_task_run_without_routing_fields(self):
        """TaskRun should work without routing fields (backwards compatible)."""
        run = TaskRun(
            id='run-123',
            task_id='task-456',
        )

        assert run.target_agent_name is None
        assert run.required_capabilities is None
        assert run.deadline_at is None


class TestCapabilitiesFiltering:
    """Test capability-based filtering in WorkerRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh worker registry for testing."""
        return WorkerRegistry()

    @pytest.mark.asyncio
    async def test_get_available_workers_with_capabilities(self, registry):
        """Workers should be filtered by required capabilities."""
        queue1 = asyncio.Queue()
        queue2 = asyncio.Queue()

        # Worker 1 has coding and testing capabilities
        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=queue1,
            capabilities=['coding', 'testing', 'review'],
        )

        # Worker 2 only has coding capability
        await registry.register_worker(
            worker_id='worker2',
            agent_name='agent-beta',
            queue=queue2,
            capabilities=['coding'],
        )

        # Require both coding and testing
        available = await registry.get_available_workers(
            required_capabilities=['coding', 'testing']
        )

        # Only worker1 has both capabilities
        assert len(available) == 1
        assert available[0].agent_name == 'agent-alpha'

    @pytest.mark.asyncio
    async def test_combined_targeting_and_capabilities(self, registry):
        """Targeting and capabilities should be combined (AND logic)."""
        queue1 = asyncio.Queue()
        queue2 = asyncio.Queue()

        # Worker 1: agent-alpha with coding capability
        await registry.register_worker(
            worker_id='worker1',
            agent_name='agent-alpha',
            queue=queue1,
            capabilities=['coding'],
        )

        # Worker 2: agent-alpha with testing capability (same agent name)
        await registry.register_worker(
            worker_id='worker2',
            agent_name='agent-alpha',
            queue=queue2,
            capabilities=['testing'],
        )

        # Target agent-alpha but require testing capability
        available = await registry.get_available_workers(
            target_agent_name='agent-alpha',
            required_capabilities=['testing'],
        )

        # Only worker2 matches both criteria
        assert len(available) == 1
        assert available[0].worker_id == 'worker2'
