"""
Tests for agent-to-agent messaging functionality.
"""

import asyncio
import pytest
from a2a_server.enhanced_agents import EnhancedAgent, initialize_agent_registry, ENHANCED_AGENTS
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import Message, Part


class TestAgent(EnhancedAgent):
    """Test agent for messaging tests."""

    def __init__(self, name: str, message_broker=None):
        super().__init__(
            name=name,
            description=f"Test agent {name}",
            message_broker=message_broker
        )
        self.received_messages = []
        self.received_events = []

    async def process_message(self, message: Message) -> Message:
        """Store received messages and echo back."""
        text = self._extract_text_content(message)
        self.received_messages.append(text)
        return Message(parts=[Part(type="text", content=f"{self.name} received: {text}")])

    async def handle_event(self, event_type: str, data: dict):
        """Store received events."""
        self.received_events.append({"event_type": event_type, "data": data})


@pytest.mark.asyncio
async def test_direct_messaging():
    """Test direct agent-to-agent messaging."""
    broker = InMemoryMessageBroker()
    await broker.start()

    # Create two agents
    agent_a = TestAgent("Agent A", message_broker=broker)
    agent_b = TestAgent("Agent B", message_broker=broker)

    await agent_a.initialize(broker)
    await agent_b.initialize(broker)

    # Send message from A to B
    message = Message(parts=[Part(type="text", content="Hello from A")])
    await agent_a.send_message_to_agent("Agent B", message)

    # Give time for message to be processed
    await asyncio.sleep(0.1)

    # Verify B received the message
    assert len(agent_b.received_messages) == 1
    assert "Hello from A" in agent_b.received_messages[0]

    await broker.stop()


@pytest.mark.asyncio
async def test_event_publishing():
    """Test event publishing and subscription."""
    broker = InMemoryMessageBroker()
    await broker.start()

    # Create publisher and subscriber agents
    publisher = TestAgent("Publisher", message_broker=broker)
    subscriber = TestAgent("Subscriber", message_broker=broker)

    await publisher.initialize(broker)
    await subscriber.initialize(broker)

    # Subscribe to publisher's events
    await subscriber.subscribe_to_agent_events(
        "Publisher",
        "test.event",
        subscriber.handle_event
    )

    # Publish an event
    test_data = {"key": "value", "number": 42}
    await publisher.publish_event("test.event", test_data)

    # Give time for event to be processed
    await asyncio.sleep(0.1)

    # Verify subscriber received the event
    assert len(subscriber.received_events) == 1
    assert subscriber.received_events[0]["data"]["key"] == "value"
    assert subscriber.received_events[0]["data"]["number"] == 42

    await broker.stop()


@pytest.mark.asyncio
async def test_multi_agent_coordination():
    """Test coordination between multiple agents."""
    broker = InMemoryMessageBroker()
    await broker.start()

    # Create coordinator and worker agents
    coordinator = TestAgent("Coordinator", message_broker=broker)
    worker1 = TestAgent("Worker 1", message_broker=broker)
    worker2 = TestAgent("Worker 2", message_broker=broker)

    await coordinator.initialize(broker)
    await worker1.initialize(broker)
    await worker2.initialize(broker)

    # Coordinator sends tasks to both workers
    task1 = Message(parts=[Part(type="text", content="Task 1")])
    task2 = Message(parts=[Part(type="text", content="Task 2")])

    await coordinator.send_message_to_agent("Worker 1", task1)
    await coordinator.send_message_to_agent("Worker 2", task2)

    # Give time for messages to be processed
    await asyncio.sleep(0.1)

    # Verify both workers received their tasks
    assert len(worker1.received_messages) == 1
    assert "Task 1" in worker1.received_messages[0]

    assert len(worker2.received_messages) == 1
    assert "Task 2" in worker2.received_messages[0]

    await broker.stop()


@pytest.mark.asyncio
async def test_event_aggregation():
    """Test aggregating events from multiple sources."""
    broker = InMemoryMessageBroker()
    await broker.start()

    # Create multiple publishers and one aggregator
    publisher1 = TestAgent("Publisher 1", message_broker=broker)
    publisher2 = TestAgent("Publisher 2", message_broker=broker)
    aggregator = TestAgent("Aggregator", message_broker=broker)

    await publisher1.initialize(broker)
    await publisher2.initialize(broker)
    await aggregator.initialize(broker)

    # Aggregator subscribes to both publishers
    await aggregator.subscribe_to_agent_events(
        "Publisher 1",
        "data.ready",
        aggregator.handle_event
    )
    await aggregator.subscribe_to_agent_events(
        "Publisher 2",
        "data.ready",
        aggregator.handle_event
    )

    # Both publishers emit events
    await publisher1.publish_event("data.ready", {"source": "p1", "value": 10})
    await publisher2.publish_event("data.ready", {"source": "p2", "value": 20})

    # Give time for events to be processed
    await asyncio.sleep(0.1)

    # Verify aggregator received both events
    assert len(aggregator.received_events) == 2
    sources = [e["data"]["source"] for e in aggregator.received_events]
    assert "p1" in sources
    assert "p2" in sources

    await broker.stop()


@pytest.mark.asyncio
async def test_built_in_agents_messaging():
    """Test messaging with built-in enhanced agents."""
    broker = InMemoryMessageBroker()
    await broker.start()

    # Initialize built-in agents
    initialize_agent_registry(broker)

    calculator = ENHANCED_AGENTS.get("calculator")
    memory = ENHANCED_AGENTS.get("memory")

    await calculator.initialize(broker)
    await memory.initialize(broker)

    # Create a test agent to receive responses
    test_agent = TestAgent("Test Agent", message_broker=broker)
    await test_agent.initialize(broker)

    # Send a calculation message
    calc_msg = Message(parts=[Part(type="text", content="add 5 and 3")])
    response = await calculator.process_message(calc_msg)

    # Verify response
    assert response is not None
    assert len(response.parts) > 0

    # Send a memory storage message
    store_msg = Message(parts=[Part(type="text", content="store 'test value' as test_key")])
    store_response = await memory.process_message(store_msg)

    # Verify storage response
    assert store_response is not None
    assert len(store_response.parts) > 0

    await broker.stop()


@pytest.mark.asyncio
async def test_unsubscribe_from_events():
    """Test unsubscribing from agent events."""
    broker = InMemoryMessageBroker()
    await broker.start()

    publisher = TestAgent("Publisher", message_broker=broker)
    subscriber = TestAgent("Subscriber", message_broker=broker)

    await publisher.initialize(broker)
    await subscriber.initialize(broker)

    # Subscribe
    await subscriber.subscribe_to_agent_events(
        "Publisher",
        "test.event",
        subscriber.handle_event
    )

    # Publish event - should be received
    await publisher.publish_event("test.event", {"count": 1})
    await asyncio.sleep(0.1)
    assert len(subscriber.received_events) == 1

    # Unsubscribe
    await subscriber.unsubscribe_from_agent_events(
        "Publisher",
        "test.event",
        subscriber.handle_event
    )

    # Publish again - should NOT be received
    await publisher.publish_event("test.event", {"count": 2})
    await asyncio.sleep(0.1)
    assert len(subscriber.received_events) == 1  # Still just 1

    await broker.stop()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
