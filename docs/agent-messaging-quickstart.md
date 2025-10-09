# Agent-to-Agent Messaging Quick Start Guide

This guide will help you quickly get started with agent-to-agent messaging in the A2A Server.

## Prerequisites

- Python 3.12+
- A2A Server installed (`pip install -r requirements.txt`)
- Optional: Redis for production deployments

## 1. Basic Setup

### Create Your First Agent

```python
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.models import Message, Part

class MyAgent(EnhancedAgent):
    def __init__(self, message_broker=None):
        super().__init__(
            name="My Agent",
            description="My first agent with messaging",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        text = self._extract_text_content(message)
        return Message(parts=[Part(
            type="text",
            content=f"My Agent received: {text}"
        )])
```

### Initialize with Message Broker

```python
from a2a_server.message_broker import InMemoryMessageBroker

# Create message broker
broker = InMemoryMessageBroker()
await broker.start()

# Create agent with broker
my_agent = MyAgent(message_broker=broker)
await my_agent.initialize(broker)
```

## 2. Send Messages Between Agents

### Direct Messaging

```python
# Agent A sends to Agent B
from a2a_server.models import Message, Part

message = Message(parts=[Part(type="text", content="Hello Agent B!")])
await agent_a.send_message_to_agent("Agent B", message)
```

Agent B automatically receives and processes the message through its `process_message` method.

## 3. Publish and Subscribe to Events

### Publishing Events

```python
class DataAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Do some work
        data = {"result": 42, "status": "success"}

        # Publish event
        await self.publish_event("data.ready", data)

        return Message(parts=[Part(type="text", content="Data published")])
```

### Subscribing to Events

```python
class ListenerAgent(EnhancedAgent):
    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)

        # Subscribe to events from DataAgent
        await self.subscribe_to_agent_events(
            "Data Agent",
            "data.ready",
            self.handle_data_ready
        )

    async def handle_data_ready(self, event_type: str, data: dict):
        print(f"Received data: {data}")
```

## 4. Multi-Agent Patterns

### Pattern: Coordinator-Worker

```python
class CoordinatorAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Distribute work to multiple workers
        for i, worker in enumerate(["Worker 1", "Worker 2", "Worker 3"]):
            task_msg = Message(parts=[Part(
                type="text",
                content=f"Process task {i}"
            )])
            await self.send_message_to_agent(worker, task_msg)

        return Message(parts=[Part(
            type="text",
            content="Work distributed to 3 workers"
        )])
```

### Pattern: Event Aggregator

```python
class AggregatorAgent(EnhancedAgent):
    def __init__(self, message_broker=None):
        super().__init__(
            name="Aggregator",
            description="Aggregates events from multiple sources",
            message_broker=message_broker
        )
        self.events = []

    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)

        # Subscribe to multiple agents
        for agent_name in ["Agent A", "Agent B", "Agent C"]:
            await self.subscribe_to_agent_events(
                agent_name,
                "task.complete",
                self.handle_task_complete
            )

    async def handle_task_complete(self, event_type: str, data: dict):
        self.events.append(data)
        print(f"Total events collected: {len(self.events)}")
```

### Pattern: Pipeline Processing

```python
class Stage1Agent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Process stage 1
        result = self.stage1_processing(message)

        # Send to next stage
        next_msg = Message(parts=[Part(type="text", content=result)])
        await self.send_message_to_agent("Stage 2 Agent", next_msg)

        return Message(parts=[Part(type="text", content="Stage 1 complete")])

class Stage2Agent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Process stage 2
        result = self.stage2_processing(message)

        # Send to next stage
        next_msg = Message(parts=[Part(type="text", content=result)])
        await self.send_message_to_agent("Stage 3 Agent", next_msg)

        return Message(parts=[Part(type="text", content="Stage 2 complete")])
```

## 5. Running the Examples

### Run Built-in Demo

```bash
python examples/agent_to_agent_messaging.py
```

This demonstrates:
- ✅ Direct agent-to-agent messaging
- ✅ Event publishing and subscribing
- ✅ Multi-agent coordination
- ✅ Data aggregation patterns

### Create Your Own Demo

```python
import asyncio
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.enhanced_agents import initialize_agent_registry, ENHANCED_AGENTS

async def main():
    # Start message broker
    broker = InMemoryMessageBroker()
    await broker.start()

    # Initialize built-in agents
    initialize_agent_registry(broker)

    # Get agents
    calculator = ENHANCED_AGENTS["calculator"]
    memory = ENHANCED_AGENTS["memory"]

    # Initialize them
    await calculator.initialize(broker)
    await memory.initialize(broker)

    # Send messages between agents
    from a2a_server.models import Message, Part

    calc_msg = Message(parts=[Part(type="text", content="Calculate 5 + 3")])
    await calculator.send_message_to_agent("Memory Agent", calc_msg)

    # Give time for processing
    await asyncio.sleep(0.5)

    # Cleanup
    await broker.stop()

asyncio.run(main())
```

## 6. Production Setup with Redis

### Install Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install locally
# macOS: brew install redis
# Ubuntu: sudo apt-get install redis-server
# Windows: Use Docker or WSL
```

### Configure Redis Broker

```python
from a2a_server.message_broker import MessageBroker

# Create Redis broker
broker = MessageBroker(redis_url="redis://localhost:6379/0")
await broker.start()

# Use with agents
agent = MyAgent(message_broker=broker)
await agent.initialize(broker)
```

### Environment Configuration

```bash
# .env file
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0
```

## 7. Debugging and Troubleshooting

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("a2a_server")
logger.setLevel(logging.DEBUG)
```

### Check Message Broker Status

```python
# Verify broker is running
if broker._running:
    print("✓ Message broker is running")
else:
    print("✗ Message broker is not running")
```

### Verify Agent Subscriptions

```python
# Check what events an agent is subscribed to
print(f"Agent subscriptions: {agent._message_handlers.keys()}")
```

### Common Issues

**Issue: Messages not being received**
- ✅ Ensure message broker is started: `await broker.start()`
- ✅ Verify agent is initialized: `await agent.initialize(broker)`
- ✅ Check agent name matches exactly (case-sensitive)

**Issue: Events not triggering handlers**
- ✅ Subscribe before publishing: Initialize subscribers first
- ✅ Verify event type matches exactly
- ✅ Check handler is async if needed

**Issue: Redis connection errors**
- ✅ Verify Redis is running: `redis-cli ping`
- ✅ Check Redis URL is correct
- ✅ Ensure network connectivity

## 8. Next Steps

- 📚 Read the [full documentation](../README.md#agent-to-agent-messaging)
- 🔧 Explore [examples directory](../examples/)
- 🧪 Check [test files](../tests/) for more patterns
- 🚀 Deploy with [Kubernetes](../chart/a2a-server/)

## API Quick Reference

### EnhancedAgent Methods

| Method | Description |
|--------|-------------|
| `send_message_to_agent(target, message)` | Send message to specific agent |
| `publish_event(event_type, data)` | Publish event to all subscribers |
| `subscribe_to_agent_events(agent, event, handler)` | Subscribe to agent events |
| `unsubscribe_from_agent_events(agent, event, handler)` | Unsubscribe from events |

### Message Broker

| Method | Description |
|--------|-------------|
| `start()` | Start the message broker |
| `stop()` | Stop the message broker |
| `publish_event(event_type, data)` | Publish global event |
| `subscribe_to_events(event_type, handler)` | Subscribe to global events |

## Example Project Structure

```
my_agent_system/
├── agents/
│   ├── __init__.py
│   ├── coordinator.py
│   ├── worker.py
│   └── monitor.py
├── config.py
├── main.py
└── requirements.txt
```

Happy agent messaging! 🤖💬
