"""
Example demonstrating agent-to-agent messaging capabilities.

This example shows how agents can:
1. Send messages directly to other agents
2. Publish events that other agents can subscribe to
3. Subscribe to events from specific agents
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path so we can import a2a_server
sys.path.insert(0, str(Path(__file__).parent.parent))

from a2a_server.enhanced_agents import EnhancedAgent, initialize_agent_registry
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import Message, Part

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoordinatorAgent(EnhancedAgent):
    """Agent that coordinates work between other agents."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Coordinator",
            description="Coordinates work between multiple agents",
            message_broker=message_broker
        )
        self.task_results = {}

    async def process_message(self, message: Message) -> Message:
        """Process coordination requests."""
        text = self._extract_text_content(message)

        if "coordinate task" in text.lower():
            # Publish a task coordination event
            await self.publish_event("task.assigned", {
                "task_description": text,
                "timestamp": "now",
                "assigned_to": ["Calculator Agent", "Analysis Agent"]
            })

            # Send direct messages to specific agents
            calc_msg = Message(parts=[Part(type="text", content="Calculate 10 + 5")])
            await self.send_message_to_agent("Calculator Agent", calc_msg)

            analysis_msg = Message(parts=[Part(type="text", content="Analyze this coordination task")])
            await self.send_message_to_agent("Analysis Agent", analysis_msg)

            return Message(parts=[Part(
                type="text",
                content="Task coordination initiated. Sent work to Calculator and Analysis agents."
            )])

        return Message(parts=[Part(type="text", content=f"Coordinator received: {text}")])


class DataCollectorAgent(EnhancedAgent):
    """Agent that collects and aggregates data from other agents."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Data Collector",
            description="Collects and aggregates data from multiple agents",
            message_broker=message_broker
        )
        self.collected_data = []

    async def initialize(self, message_broker=None):
        """Initialize and subscribe to events from other agents."""
        await super().initialize(message_broker)

        # Subscribe to calculation results
        await self.subscribe_to_agent_events(
            "Calculator Agent",
            "calculation.complete",
            self.handle_calculation_result
        )

        # Subscribe to analysis results
        await self.subscribe_to_agent_events(
            "Analysis Agent",
            "analysis.complete",
            self.handle_analysis_result
        )

    async def handle_calculation_result(self, event_type: str, data: Dict[str, Any]):
        """Handle calculation results from Calculator Agent."""
        logger.info(f"Data Collector received calculation result: {data}")
        self.collected_data.append({
            "type": "calculation",
            "data": data,
            "source": "Calculator Agent"
        })

        # Publish aggregated data event
        await self.publish_event("data.collected", {
            "count": len(self.collected_data),
            "latest": data
        })

    async def handle_analysis_result(self, event_type: str, data: Dict[str, Any]):
        """Handle analysis results from Analysis Agent."""
        logger.info(f"Data Collector received analysis result: {data}")
        self.collected_data.append({
            "type": "analysis",
            "data": data,
            "source": "Analysis Agent"
        })

        # Publish aggregated data event
        await self.publish_event("data.collected", {
            "count": len(self.collected_data),
            "latest": data
        })

    async def process_message(self, message: Message) -> Message:
        """Process data collection requests."""
        text = self._extract_text_content(message)

        if "show collected data" in text.lower():
            data_summary = f"Collected {len(self.collected_data)} data points:\n"
            for item in self.collected_data[-5:]:  # Show last 5
                data_summary += f"- {item['type']} from {item['source']}\n"

            return Message(parts=[Part(type="text", content=data_summary)])

        return Message(parts=[Part(type="text", content=f"Data Collector received: {text}")])


class NotificationAgent(EnhancedAgent):
    """Agent that monitors and sends notifications based on events."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Notification Agent",
            description="Monitors events and sends notifications",
            message_broker=message_broker
        )
        self.notification_count = 0

    async def initialize(self, message_broker=None):
        """Initialize and subscribe to various agent events."""
        await super().initialize(message_broker)

        # Subscribe to task assignments from coordinator
        await self.subscribe_to_agent_events(
            "Coordinator",
            "task.assigned",
            self.handle_task_assigned
        )

        # Subscribe to data collection events
        await self.subscribe_to_agent_events(
            "Data Collector",
            "data.collected",
            self.handle_data_collected
        )

    async def handle_task_assigned(self, event_type: str, data: Dict[str, Any]):
        """Handle task assignment notifications."""
        logger.info(f"📬 NOTIFICATION: Task assigned - {data.get('task_description')}")
        self.notification_count += 1

        # Publish notification sent event
        await self.publish_event("notification.sent", {
            "type": "task_assignment",
            "count": self.notification_count
        })

    async def handle_data_collected(self, event_type: str, data: Dict[str, Any]):
        """Handle data collection notifications."""
        logger.info(f"📊 NOTIFICATION: Data collected - {data.get('count')} total items")
        self.notification_count += 1

        # Publish notification sent event
        await self.publish_event("notification.sent", {
            "type": "data_collection",
            "count": self.notification_count
        })

    async def process_message(self, message: Message) -> Message:
        """Process notification requests."""
        text = self._extract_text_content(message)

        if "notification count" in text.lower():
            return Message(parts=[Part(
                type="text",
                content=f"Sent {self.notification_count} notifications so far."
            )])

        return Message(parts=[Part(type="text", content=f"Notification Agent received: {text}")])


async def demo_agent_messaging():
    """Demonstrate agent-to-agent messaging capabilities."""
    logger.info("=" * 60)
    logger.info("Starting Agent-to-Agent Messaging Demo")
    logger.info("=" * 60)

    # Create message broker
    message_broker = InMemoryMessageBroker()
    await message_broker.start()
    logger.info("✓ Message broker started")

    # Initialize the standard agent registry
    initialize_agent_registry(message_broker)
    logger.info("✓ Standard agent registry initialized")

    # Create custom agents for this demo
    coordinator = CoordinatorAgent(message_broker)
    data_collector = DataCollectorAgent(message_broker)
    notification_agent = NotificationAgent(message_broker)

    # Initialize all agents
    await coordinator.initialize(message_broker)
    await data_collector.initialize(message_broker)
    await notification_agent.initialize(message_broker)
    logger.info("✓ Custom agents initialized and subscribed to events")

    logger.info("\n" + "=" * 60)
    logger.info("Demo 1: Coordinator sends messages to other agents")
    logger.info("=" * 60)

    # Send a coordination task
    coord_msg = Message(parts=[Part(type="text", content="Coordinate task: Process data pipeline")])
    response = await coordinator.process_message(coord_msg)
    logger.info(f"Coordinator response: {response.parts[0].content}")

    # Give time for messages to be processed
    await asyncio.sleep(0.5)

    logger.info("\n" + "=" * 60)
    logger.info("Demo 2: Calculator publishes an event")
    logger.info("=" * 60)

    # Get Calculator agent from registry
    from a2a_server.enhanced_agents import ENHANCED_AGENTS
    calculator = ENHANCED_AGENTS.get("calculator")

    if calculator:
        # Publish a calculation complete event
        await calculator.publish_event("calculation.complete", {
            "expression": "10 + 5",
            "result": 15,
            "timestamp": "now"
        })
        logger.info("Calculator published calculation.complete event")

        await asyncio.sleep(0.5)

    logger.info("\n" + "=" * 60)
    logger.info("Demo 3: Analysis agent publishes an event")
    logger.info("=" * 60)

    # Get Analysis agent from registry
    analysis = ENHANCED_AGENTS.get("analysis")

    if analysis:
        # Publish an analysis complete event
        await analysis.publish_event("analysis.complete", {
            "text": "Sample text analysis",
            "word_count": 42,
            "sentiment": "neutral"
        })
        logger.info("Analysis published analysis.complete event")

        await asyncio.sleep(0.5)

    logger.info("\n" + "=" * 60)
    logger.info("Demo 4: Check collected data")
    logger.info("=" * 60)

    # Query data collector
    query_msg = Message(parts=[Part(type="text", content="Show collected data")])
    data_response = await data_collector.process_message(query_msg)
    logger.info(f"Data Collector response:\n{data_response.parts[0].content}")

    logger.info("\n" + "=" * 60)
    logger.info("Demo 5: Check notification count")
    logger.info("=" * 60)

    # Query notification agent
    notif_msg = Message(parts=[Part(type="text", content="What's the notification count?")])
    notif_response = await notification_agent.process_message(notif_msg)
    logger.info(f"Notification Agent response: {notif_response.parts[0].content}")

    logger.info("\n" + "=" * 60)
    logger.info("Demo 6: Direct agent-to-agent messaging")
    logger.info("=" * 60)

    # Send a direct message from coordinator to memory agent
    memory = ENHANCED_AGENTS.get("memory")
    if memory:
        store_msg = Message(parts=[Part(type="text", content="Store 'Important Data' as demo_key")])
        await coordinator.send_message_to_agent("Memory Agent", store_msg)
        logger.info("Coordinator sent message to Memory Agent")

        await asyncio.sleep(0.5)

        # Retrieve the stored data
        retrieve_msg = Message(parts=[Part(type="text", content="Retrieve demo_key")])
        retrieve_response = await memory.process_message(retrieve_msg)
        logger.info(f"Memory Agent response: {retrieve_response.parts[0].content}")

    # Cleanup
    await message_broker.stop()
    logger.info("\n✓ Demo completed successfully")
    logger.info("=" * 60)


async def demo_pubsub_pattern():
    """Demonstrate publish-subscribe pattern between agents."""
    logger.info("\n" + "=" * 60)
    logger.info("Publish-Subscribe Pattern Demo")
    logger.info("=" * 60)

    # Create message broker
    message_broker = InMemoryMessageBroker()
    await message_broker.start()

    # Initialize agent registry
    initialize_agent_registry(message_broker)

    from a2a_server.enhanced_agents import ENHANCED_AGENTS

    # Create a custom event handler
    received_events = []

    async def custom_handler(event_type: str, data: Dict[str, Any]):
        logger.info(f"📡 Custom handler received: {event_type} - {data}")
        received_events.append({"event_type": event_type, "data": data})

    # Get calculator agent
    calculator = ENHANCED_AGENTS.get("calculator")

    if calculator:
        # Subscribe calculator to analysis agent's events
        await calculator.subscribe_to_agent_events(
            "Analysis Agent",
            "result.ready",
            custom_handler
        )
        logger.info("Calculator subscribed to Analysis Agent's result.ready events")

        # Get analysis agent and publish event
        analysis = ENHANCED_AGENTS.get("analysis")
        if analysis:
            await analysis.publish_event("result.ready", {
                "analysis_type": "sentiment",
                "confidence": 0.95,
                "result": "positive"
            })
            logger.info("Analysis Agent published result.ready event")

            await asyncio.sleep(0.5)

            logger.info(f"Calculator received {len(received_events)} event(s)")

    await message_broker.stop()
    logger.info("✓ Publish-Subscribe demo completed")
    logger.info("=" * 60)


if __name__ == "__main__":
    async def main():
        # Run the main messaging demo
        await demo_agent_messaging()

        # Run the pub-sub pattern demo
        await demo_pubsub_pattern()

    asyncio.run(main())
