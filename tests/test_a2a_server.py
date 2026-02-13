"""
Basic tests for A2A Server implementation.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime

from a2a_server.models import (
    AgentCard, AgentProvider, AgentCapabilities, AgentSkill,
    Task, TaskStatus, Message, Part, JSONRPCRequest
)
from a2a_server.task_manager import InMemoryTaskManager
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.agent_card import create_agent_card


class TestModels:
    """Test Pydantic models."""

    def test_agent_card_creation(self):
        """Test creating an agent card."""
        provider = AgentProvider(
            organization="Test Org",
            url="https://test.com"
        )

        card = AgentCard(
            name="Test Agent",
            description="A test agent",
            url="http://localhost:8000",
            provider=provider
        )

        assert card.name == "Test Agent"
        assert card.provider.organization == "Test Org"

    def test_task_model(self):
        """Test task model."""
        task = Task(
            id="test-task",
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        assert task.id == "test-task"
        assert task.status == TaskStatus.PENDING

    def test_message_model(self):
        """Test message model."""
        # Legacy format still accepted via validator
        message = Message(parts=[
            Part(type="text", content="Hello world")
        ])

        assert len(message.parts) == 1
        assert message.parts[0].kind == "text"
        assert message.parts[0].text == "Hello world"


class TestTaskManager:
    """Test task manager functionality."""

    @pytest_asyncio.fixture
    async def task_manager(self):
        """Create a task manager instance."""
        return InMemoryTaskManager()

    @pytest.mark.asyncio
    async def test_create_task(self, task_manager):
        """Test creating a task."""
        task = await task_manager.create_task(
            title="Test Task",
            description="A test task"
        )

        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.id is not None

    @pytest.mark.asyncio
    async def test_get_task(self, task_manager):
        """Test retrieving a task."""
        created_task = await task_manager.create_task(title="Test")
        retrieved_task = await task_manager.get_task(created_task.id)

        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id
        assert retrieved_task.title == "Test"

    @pytest.mark.asyncio
    async def test_update_task_status(self, task_manager):
        """Test updating task status."""
        import asyncio
        task = await task_manager.create_task(title="Test")

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.01)

        updated_task = await task_manager.update_task_status(
            task.id, TaskStatus.WORKING
        )

        assert updated_task is not None
        assert updated_task.status == TaskStatus.WORKING
        assert updated_task.updated_at >= task.updated_at

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_manager):
        """Test cancelling a task."""
        task = await task_manager.create_task(title="Test")
        cancelled_task = await task_manager.cancel_task(task.id)

        assert cancelled_task is not None
        assert cancelled_task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_list_tasks(self, task_manager):
        """Test listing tasks."""
        await task_manager.create_task(title="Task 1")
        await task_manager.create_task(title="Task 2")

        tasks = await task_manager.list_tasks()
        assert len(tasks) == 2

        # Test filtering by status
        pending_tasks = await task_manager.list_tasks(TaskStatus.PENDING)
        assert len(pending_tasks) == 2


class TestMessageBroker:
    """Test message broker functionality."""

    @pytest_asyncio.fixture
    async def message_broker(self):
        """Create a message broker instance."""
        broker = InMemoryMessageBroker()
        await broker.start()
        yield broker
        await broker.stop()

    @pytest.mark.asyncio
    async def test_register_agent(self, message_broker):
        """Test registering an agent."""
        agent_card = create_agent_card(
            name="Test Agent",
            description="A test agent",
            url="http://localhost:8000",
            organization="Test Org",
            organization_url="https://test.com"
        ).build()

        await message_broker.register_agent(agent_card.card)

        # Check if agent was registered
        agents = await message_broker.discover_agents()
        assert len(agents) == 1
        assert agents[0]['name'] == "Test Agent"

    @pytest.mark.asyncio
    async def test_discover_agents(self, message_broker):
        """Test discovering agents."""
        # Register multiple agents
        for i in range(3):
            agent_card = create_agent_card(
                name=f"Agent {i}",
                description=f"Test agent {i}",
                url=f"http://localhost:800{i}",
                organization="Test Org",
                organization_url="https://test.com"
            ).build()

            await message_broker.register_agent(agent_card.card)

        agents = await message_broker.discover_agents()
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_get_agent(self, message_broker):
        """Test getting a specific agent."""
        agent_card = create_agent_card(
            name="Specific Agent",
            description="A specific test agent",
            url="http://localhost:8000",
            organization="Test Org",
            organization_url="https://test.com"
        ).build()

        await message_broker.register_agent(agent_card.card)

        retrieved_agent = await message_broker.get_agent("Specific Agent")
        assert retrieved_agent is not None
        assert retrieved_agent.name == "Specific Agent"

        # Test non-existent agent
        missing_agent = await message_broker.get_agent("Missing Agent")
        assert missing_agent is None

    @pytest.mark.asyncio
    async def test_event_subscription(self, message_broker):
        """Test event subscription and publishing."""
        received_events = []

        async def event_handler(event_type: str, data):
            received_events.append((event_type, data))

        # Subscribe to events
        await message_broker.subscribe_to_events("test.event", event_handler)

        # Publish an event
        await message_broker.publish_event("test.event", {"message": "Hello"})

        # Give some time for event processing
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0][0] == "test.event"
        assert received_events[0][1]["message"] == "Hello"


class TestAgentCard:
    """Test agent card functionality."""

    def test_create_agent_card(self):
        """Test creating an agent card with builder."""
        card = (create_agent_card(
            name="Test Agent",
            description="A test agent for testing",
            url="http://localhost:8000",
            organization="Test Organization",
            organization_url="https://test-org.com"
        )
        .with_streaming()
        .with_push_notifications()
        .with_skill(
            skill_id="test-skill",
            name="Test Skill",
            description="A test skill",
            input_modes=["text"],
            output_modes=["text"]
        )
        .build())

        assert card.card.name == "Test Agent"
        assert card.card.capabilities.streaming is True
        assert card.card.capabilities.push_notifications is True
        assert len(card.card.skills) == 1
        assert card.card.skills[0].id == "test-skill"

    def test_agent_card_serialization(self):
        """Test agent card JSON serialization."""
        card = create_agent_card(
            name="Test Agent",
            description="A test agent",
            url="http://localhost:8000",
            organization="Test Org",
            organization_url="https://test.com"
        ).build()

        # Test JSON serialization
        json_str = card.to_json()
        assert "Test Agent" in json_str

        # Test round-trip
        from a2a_server.agent_card import AgentCard
        restored_card = AgentCard.from_json(json_str)
        assert restored_card.card.name == "Test Agent"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
