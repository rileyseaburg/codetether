"""
Enhanced A2A Server with MCP tool integration.
"""

import asyncio
import logging
import os
from typing import Optional

from .server import A2AServer
from .models import Message, Part
from .enhanced_agents import route_message_to_agent, initialize_all_agents, cleanup_all_agents
from .agent_card import AgentCard
from .message_broker import MessageBroker, InMemoryMessageBroker

logger = logging.getLogger(__name__)


class EnhancedA2AServer(A2AServer):
    """Enhanced A2A Server that uses MCP tools through specialized agents."""

    def __init__(self, *args, use_redis: bool = False, redis_url: str = "redis://localhost:6379", **kwargs):
        super().__init__(*args, **kwargs)
        self._agents_initialized = False
        self._use_redis = use_redis
        self._redis_url = redis_url
        # Note: message_broker is already set by parent class constructor

    async def initialize_agents(self):
        """Initialize all MCP-enabled agents with message broker."""
        if not self._agents_initialized:
            try:
                # Use the message broker from parent class
                await self.message_broker.start()
                logger.info(f"Message broker started ({'Redis' if self._use_redis else 'In-Memory'})")

                # Initialize agents with message broker
                await initialize_all_agents(self.message_broker)
                self._agents_initialized = True
                logger.info("Enhanced agents initialized successfully with message broker")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced agents: {e}")
                raise

    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """Process message using MCP-enabled agents."""
        # Ensure agents are initialized
        if not self._agents_initialized:
            await self.initialize_agents()

        try:
            # Route message to appropriate agent with message broker
            response = await route_message_to_agent(message, self.message_broker)
            logger.info(f"Message processed by enhanced agents")
            return response
        except Exception as e:
            logger.error(f"Error processing message with enhanced agents: {e}")
            # Fallback to echo behavior
            response_parts = []
            for part in message.parts:
                if part.kind == "text":
                    response_parts.append(Part(
                        kind="text",
                        text=f"Echo: {part.text}"
                    ))
                else:
                    response_parts.append(part)

            return Message(parts=response_parts)

    async def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the enhanced A2A server with proper initialization."""
        # Initialize agents and message broker first
        await self.initialize_agents()

        # Now call parent start method
        await super().start(host=host, port=port)

    async def cleanup(self):
        """Clean up server resources."""
        if self._agents_initialized:
            await cleanup_all_agents()
            if self.message_broker:
                await self.message_broker.stop()
            self._agents_initialized = False
        logger.info("Enhanced server cleanup completed")


def create_enhanced_agent_card() -> AgentCard:
    """Create an enhanced agent card with A2A coordination capabilities."""
    from .agent_card import AgentCard
    from .models import AgentProvider

    provider = AgentProvider(
        organization="A2A Protocol Server",
        url="https://github.com/rileyseaburg/codetether"
    )

    card = AgentCard(
        name="A2A Coordination Hub",
        description="Agent-to-Agent communication and task coordination server enabling distributed agent collaboration",
        url=os.environ.get("A2A_AGENT_URL", "http://localhost:8000"),
        provider=provider
    )

    # Core A2A coordination skills
    card.add_skill(
        skill_id="task_delegation",
        name="Task Delegation",
        description="Delegate tasks to other agents in the network with status tracking",
        input_modes=["text", "structured"],
        output_modes=["text", "structured"]
    )

    card.add_skill(
        skill_id="agent_discovery",
        name="Agent Discovery",
        description="Discover available agents and their capabilities for task routing",
        input_modes=["text"],
        output_modes=["structured"]
    )

    card.add_skill(
        skill_id="message_queue",
        name="Inter-Agent Messaging",
        description="Asynchronous message queue for agent-to-agent communication",
        input_modes=["text", "structured"],
        output_modes=["text", "structured"]
    )

    card.add_skill(
        skill_id="task_monitoring",
        name="Task Status Monitoring",
        description="Monitor and track task progress across distributed agents",
        input_modes=["structured"],
        output_modes=["structured", "streaming"]
    )

    card.add_skill(
        skill_id="agent_registration",
        name="Agent Registration",
        description="Register new agents and their capabilities to the network",
        input_modes=["structured"],
        output_modes=["structured"]
    )

    # Enable media capability for real-time agent collaboration
    card.enable_media()
    card.add_livekit_interface(
        token_endpoint="/v1/livekit/token",
        server_managed=True
    )

    # Add MCP interface for external agent synchronization
    card.add_mcp_interface(
        endpoint="http://localhost:9000/mcp/v1/rpc",
        protocol="http",
        description="MCP interface for A2A task delegation, agent discovery, and message routing"
    )

    return card
