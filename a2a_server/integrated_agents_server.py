"""
Integrated A2A + OpenAI Agents SDK Server
Combines A2A protocol with OpenAI Agents SDK for better tool handling
"""
import asyncio
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from agents import Agent, Runner, function_tool
from agents.memory import SQLiteSession

from .server import A2AServer
from .models import Message, Part, AgentCard as A2AAgentCard
from .message_broker import MessageBroker
from .task_manager import TaskManager
from .agent_card import AgentCard

logger = logging.getLogger(__name__)


# Define tools using OpenAI Agents SDK decorators
@function_tool
def calculator(operation: str, a: float, b: float = 0.0) -> str:
    """
    Perform mathematical calculations.

    Args:
        operation: The operation to perform (add, subtract, multiply, divide, square, sqrt)
        a: First number
        b: Second number (optional for unary operations)

    Returns:
        The result of the calculation
    """
    try:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero"
            result = a / b
        elif operation == "square":
            result = a ** 2
        elif operation == "sqrt":
            if a < 0:
                return "Error: Cannot take square root of negative number"
            result = a ** 0.5
        else:
            return f"Error: Unknown operation '{operation}'"

        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
def get_weather(city: str) -> str:
    """
    Get weather information for a city.

    Args:
        city: The name of the city

    Returns:
        Weather information
    """
    return f"The weather in {city} is sunny with a temperature of 72°F (22°C)."


@function_tool
def analyze_text(text: str, analysis_type: str = "sentiment") -> str:
    """
    Analyze text for various properties.

    Args:
        text: The text to analyze
        analysis_type: Type of analysis (sentiment, keywords, summary)

    Returns:
        Analysis results
    """
    if analysis_type == "sentiment":
        return f"Text sentiment: Positive (based on analysis of: '{text[:50]}...')"
    elif analysis_type == "keywords":
        words = text.split()[:5]
        return f"Key terms: {', '.join(words)}"
    elif analysis_type == "summary":
        return f"Summary: {text[:100]}..."
    return f"Analysis type '{analysis_type}' not supported"


@function_tool
def remember_fact(key: str, value: str) -> str:
    """
    Store a fact in memory.

    Args:
        key: The key to store the fact under
        value: The value to remember

    Returns:
        Confirmation message
    """
    # This will be handled by session memory automatically
    return f"Remembered: {key} = {value}"


class IntegratedAgentsServer(A2AServer):
    """
    Enhanced A2A Server using OpenAI Agents SDK.
    Provides A2A protocol compatibility with advanced agent capabilities.
    """

    def __init__(
        self,
        agent_card: AgentCard,
        task_manager: TaskManager,
        message_broker: MessageBroker,
        auth_callback=None,
        sessions_db: str = None
    ):
        super().__init__(agent_card, task_manager, message_broker, auth_callback)

        # Use SESSIONS_DB_PATH from env, fallback to /tmp for ephemeral storage
        if sessions_db is None:
            sessions_db = os.environ.get('SESSIONS_DB_PATH')
            if not sessions_db:
                import tempfile
                sessions_db = os.path.join(tempfile.gettempdir(), "a2a_sessions.db")

        self.sessions_db = sessions_db
        self._agents_initialized = False

        # Ensure the database directory exists and is writable
        db_dir = os.path.dirname(self.sessions_db)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Create OpenAI Agents SDK agents
        self.agents = {
            "assistant": Agent(
                name="Assistant",
                instructions="You are a helpful assistant with access to various tools. Be concise and helpful.",
                tools=[calculator, get_weather, analyze_text, remember_fact]
            ),
            "calculator": Agent(
                name="Calculator Agent",
                instructions="You specialize in mathematical calculations. Always use the calculator tool for math operations.",
                tools=[calculator]
            ),
            "analyst": Agent(
                name="Analysis Agent",
                instructions="You specialize in text analysis. Use the analyze_text tool to provide insights.",
                tools=[analyze_text]
            ),
            "memory": Agent(
                name="Memory Agent",
                instructions="You help users remember and recall information. Use the remember_fact tool.",
                tools=[remember_fact]
            )
        }

        # Session cache for conversation history
        self.session_cache: Dict[str, SQLiteSession] = {}

        logger.info("Initialized IntegratedAgentsServer with OpenAI Agents SDK")

    def _get_session(self, conversation_id: str) -> SQLiteSession:
        """Get or create a session for conversation history."""
        if conversation_id not in self.session_cache:
            self.session_cache[conversation_id] = SQLiteSession(
                conversation_id,
                self.sessions_db
            )
        return self.session_cache[conversation_id]

    def _select_agent(self, message_text: str) -> Agent:
        """Select the most appropriate agent based on message content."""
        text_lower = message_text.lower()

        # Simple keyword-based routing
        if any(word in text_lower for word in ['calculate', 'math', 'add', 'subtract', 'multiply', 'divide']):
            return self.agents["calculator"]
        elif any(word in text_lower for word in ['analyze', 'sentiment', 'keywords', 'summary']):
            return self.agents["analyst"]
        elif any(word in text_lower for word in ['remember', 'recall', 'store', 'memory']):
            return self.agents["memory"]
        else:
            return self.agents["assistant"]

    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """
        Process message using OpenAI Agents SDK.
        Maintains A2A protocol compatibility while using advanced agent features.
        """
        try:
            # Extract text from message parts
            text_parts = [part.text for part in message.parts if part.kind == "text" and part.text]
            input_text = " ".join(text_parts)

            # Get or create session for this conversation
            # Use message ID or generate one
            conversation_id = getattr(message, 'conversation_id', 'default')
            session = self._get_session(conversation_id)

            # Select appropriate agent
            agent = self._select_agent(input_text)

            logger.info(f"Processing message with {agent.name}: {input_text[:50]}...")

            # Publish to message broker for UI monitoring
            await self.message_broker.publish(
                "agent.message.received",
                {
                    "agent": agent.name,
                    "message": input_text[:100],
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id
                }
            )

            # Run the agent with session memory
            result = await Runner.run(
                agent,
                input=input_text,
                session=session
            )

            # Publish response to message broker for UI monitoring
            await self.message_broker.publish(
                "agent.message.sent",
                {
                    "agent": agent.name,
                    "response": result.final_output[:100],
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id
                }
            )

            logger.info(f"Agent {agent.name} response: {result.final_output[:50]}...")

            # Convert back to A2A Message format
            response_parts = [
                Part(
                    type="text",
                    content=result.final_output
                )
            ]

            return Message(parts=response_parts)

        except Exception as e:
            logger.error(f"Error processing message with Agents SDK: {e}", exc_info=True)

            # Fallback response
            return Message(parts=[
                Part(
                    type="text",
                    content=f"I encountered an error processing your message: {str(e)}"
                )
            ])

    async def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the integrated A2A + Agents SDK server."""
        # Start message broker
        await self.message_broker.start()
        logger.info("Message broker started for agent communication")

        self._agents_initialized = True

        # Call parent start method to run A2A server
        await super().start(host=host, port=port)

    async def cleanup(self):
        """Clean up server resources."""
        if self._agents_initialized:
            # Clear session cache
            self.session_cache.clear()

            if self.message_broker:
                await self.message_broker.stop()

            self._agents_initialized = False

        logger.info("Integrated Agents server cleanup completed")


def create_integrated_agent_card() -> AgentCard:
    """Create an agent card for the integrated server."""
    from .models import AgentProvider

    provider = AgentProvider(
        organization="A2A Protocol Server",
        url="https://github.com/rileyseaburg/codetether"
    )

    card = AgentCard(
        name="A2A Coordination Server",
        description="Agent-to-Agent communication hub enabling distributed task delegation and inter-agent collaboration",
        url=os.environ.get("A2A_AGENT_URL", "http://localhost:8000"),
        provider=provider
    )

    # Core A2A capabilities
    card.add_skill(
        skill_id="task_delegation",
        name="Task Delegation",
        description="Create and delegate tasks to other agents in the network",
        input_modes=["text", "structured"],
        output_modes=["text", "structured"]
    )

    card.add_skill(
        skill_id="agent_discovery",
        name="Agent Discovery",
        description="Discover and query available agents and their capabilities",
        input_modes=["text"],
        output_modes=["structured"]
    )

    card.add_skill(
        skill_id="message_routing",
        name="Message Routing",
        description="Route messages between agents for asynchronous communication",
        input_modes=["text", "structured"],
        output_modes=["text", "structured"]
    )

    card.add_skill(
        skill_id="task_monitoring",
        name="Task Monitoring",
        description="Monitor task status and receive updates from executing agents",
        input_modes=["structured"],
        output_modes=["structured"]
    )

    # Enable A2A capabilities
    card.enable_streaming()
    card.enable_push_notifications()

    return card
