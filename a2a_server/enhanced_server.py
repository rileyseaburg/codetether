"""
Enhanced A2A Server with MCP tool integration.
"""

import asyncio
import logging
from typing import Optional

from .server import A2AServer
from .models import Message, Part
from .enhanced_agents import route_message_to_agent, initialize_all_agents, cleanup_all_agents
from .agent_card import AgentCard

logger = logging.getLogger(__name__)


class EnhancedA2AServer(A2AServer):
    """Enhanced A2A Server that uses MCP tools through specialized agents."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._agents_initialized = False
    
    async def initialize_agents(self):
        """Initialize all MCP-enabled agents."""
        if not self._agents_initialized:
            try:
                await initialize_all_agents()
                self._agents_initialized = True
                logger.info("Enhanced agents initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced agents: {e}")
                raise
    
    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """Process message using MCP-enabled agents."""
        # Ensure agents are initialized
        if not self._agents_initialized:
            await self.initialize_agents()
        
        try:
            # Route message to appropriate agent
            response = await route_message_to_agent(message)
            logger.info(f"Message processed by enhanced agents")
            return response
        except Exception as e:
            logger.error(f"Error processing message with enhanced agents: {e}")
            # Fallback to echo behavior
            response_parts = []
            for part in message.parts:
                if part.type == "text":
                    response_parts.append(Part(
                        type="text",
                        content=f"Echo: {part.content}"
                    ))
                else:
                    response_parts.append(part)
            
            return Message(parts=response_parts)
    
    async def cleanup(self):
        """Clean up server resources."""
        if self._agents_initialized:
            await cleanup_all_agents()
            self._agents_initialized = False
        logger.info("Enhanced server cleanup completed")


def create_enhanced_agent_card() -> AgentCard:
    """Create an enhanced agent card with MCP tool capabilities."""
    from .agent_card import AgentCard
    from .models import AgentProvider
    
    provider = AgentProvider(
        organization="A2A Server",
        url="https://github.com/rileyseaburg/A2A-Server-MCP"
    )
    
    card = AgentCard(
        name="Enhanced A2A Agent",
        description="An A2A agent with MCP tool integration for calculations, analysis, and memory management",
        url="http://localhost:8000",
        provider=provider
    )
    
    # Add calculator skills
    card.add_skill(
        skill_id="calculator",
        name="Mathematical Calculator",
        description="Performs mathematical calculations including basic arithmetic, squares, and square roots",
        input_modes=["text"],
        output_modes=["text"]
    )
    
    # Add analysis skills
    card.add_skill(
        skill_id="text_analysis",
        name="Text Analysis",
        description="Analyzes text and provides statistics like word count, character count, and sentence count",
        input_modes=["text"],
        output_modes=["text"]
    )
    
    card.add_skill(
        skill_id="weather",
        name="Weather Information",
        description="Provides weather information for specified locations",
        input_modes=["text"],
        output_modes=["text"]
    )
    
    # Add memory skills
    card.add_skill(
        skill_id="memory",
        name="Memory Management",
        description="Stores, retrieves, and manages information for other agents and users",
        input_modes=["text"],
        output_modes=["text"]
    )
    
    # Add media skills
    card.add_skill(
        skill_id="media",
        name="Real-Time Media Sessions",
        description="Creates and manages real-time audio/video sessions using LiveKit",
        input_modes=["text"],
        output_modes=["text", "data"]
    )
    
    # Keep the original echo skill for compatibility
    card.add_skill(
        skill_id="echo",
        name="Echo Messages",
        description="Echoes back received messages for testing and fallback",
        input_modes=["text"],
        output_modes=["text"]
    )
    
    # Enable media capability and add LiveKit interface
    card.enable_media()
    card.add_livekit_interface(
        token_endpoint="/v1/livekit/token",
        server_managed=True
    )
    
    return card