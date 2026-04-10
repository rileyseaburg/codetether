"""
Enhanced A2A agents that perform tasks and communicate with other agents.
"""

import asyncio
import json
import logging
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from .models import Part, Message, Task, TaskStatus
from .livekit_bridge import create_livekit_bridge, LiveKitBridge

logger = logging.getLogger(__name__)


class EnhancedAgent:
    """Base class for agents that communicate with other agents."""

    def __init__(self, name: str, description: str, message_broker=None):
        self.name = name
        self.description = description
        self.message_broker = message_broker
        self._message_handlers: Dict[str, List[callable]] = {}
        self._initialized = False

    async def initialize(self, message_broker=None):
        """Initialize the agent and message broker."""
        self._initialized = True
        logger.info(f"Agent {self.name} initialized")

        # Set message broker if provided
        if message_broker:
            self.message_broker = message_broker
            # Subscribe to messages for this agent
            await self.subscribe_to_messages()

    async def subscribe_to_messages(self):
        """Subscribe to messages addressed to this agent."""
        if not self.message_broker:
            logger.warning(f"Agent {self.name} has no message broker configured")
            return

        # Subscribe to direct messages
        await self.message_broker.subscribe_to_events(
            f"message.to.{self.name}",
            self._handle_incoming_message
        )
        logger.info(f"Agent {self.name} subscribed to incoming messages")

    async def _handle_incoming_message(self, event_type: str, data: Dict[str, Any]):
        """Handle incoming messages from other agents."""
        try:
            from_agent = data.get("from_agent")
            message_data = data.get("message", {})

            # Convert message data to Message object
            message = Message(**message_data)

            logger.info(f"Agent {self.name} received message from {from_agent}")

            # Process the message
            response = await self.process_message(message)

            # Send response back to sender
            if from_agent:
                await self.send_message_to_agent(from_agent, response)

        except Exception as e:
            logger.error(f"Error handling incoming message in {self.name}: {e}")

    async def send_message_to_agent(self, target_agent: str, message: Message):
        """Send a message to another agent."""
        if not self.message_broker:
            logger.error(f"Agent {self.name} cannot send message: no message broker configured")
            return

        try:
            # Publish message to specific agent's channel
            await self.message_broker.publish_event(
                f"message.to.{target_agent}",
                {
                    "from_agent": self.name,
                    "to_agent": target_agent,
                    "message": message.model_dump(),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Agent {self.name} sent message to {target_agent}")

        except Exception as e:
            logger.error(f"Error sending message from {self.name} to {target_agent}: {e}")

    async def publish_event(self, event_type: str, data: Any):
        """Publish an event that other agents can subscribe to."""
        if not self.message_broker:
            logger.error(f"Agent {self.name} cannot publish event: no message broker configured")
            return

        try:
            await self.message_broker.publish_event(
                f"agent.{self.name}.{event_type}",
                {
                    "agent": self.name,
                    "event_type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Agent {self.name} published event: {event_type}")

        except Exception as e:
            logger.error(f"Error publishing event from {self.name}: {e}")

    async def subscribe_to_agent_events(self, agent_name: str, event_type: str, handler: callable):
        """Subscribe to events from a specific agent."""
        if not self.message_broker:
            logger.error(f"Agent {self.name} cannot subscribe to events: no message broker configured")
            return

        try:
            full_event_type = f"agent.{agent_name}.{event_type}"
            await self.message_broker.subscribe_to_events(full_event_type, handler)

            # Track handler for cleanup
            if full_event_type not in self._message_handlers:
                self._message_handlers[full_event_type] = []
            self._message_handlers[full_event_type].append(handler)

            logger.info(f"Agent {self.name} subscribed to {agent_name}'s {event_type} events")

        except Exception as e:
            logger.error(f"Error subscribing to agent events: {e}")

    async def unsubscribe_from_agent_events(self, agent_name: str, event_type: str, handler: callable):
        """Unsubscribe from events from a specific agent."""
        if not self.message_broker:
            return

        try:
            full_event_type = f"agent.{agent_name}.{event_type}"
            await self.message_broker.unsubscribe_from_events(full_event_type, handler)

            # Remove from tracked handlers
            if full_event_type in self._message_handlers:
                try:
                    self._message_handlers[full_event_type].remove(handler)
                except ValueError:
                    pass

            logger.info(f"Agent {self.name} unsubscribed from {agent_name}'s {event_type} events")

        except Exception as e:
            logger.error(f"Error unsubscribing from agent events: {e}")

    async def process_message(self, message: Message) -> Message:
        """Process a message and return a response."""
        raise NotImplementedError

    def _extract_text_content(self, message: Message) -> str:
        """Extract text content from message parts."""
        text_parts = []
        for part in message.parts:
            if part.kind == "text" and part.text:
                text_parts.append(part.text)
        return " ".join(text_parts)


class CalculatorAgent(EnhancedAgent):
    """Agent that performs mathematical calculations."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Calculator Agent",
            description="Performs mathematical calculations and data analysis",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        """Process calculation requests."""
        text = self._extract_text_content(message)

        if not self._initialized:
            await self.initialize()

        result_text = await self._handle_calculation_request(text)

        return Message(parts=[Part(type="text", content=result_text)])

    async def _handle_calculation_request(self, text: str) -> str:
        """Handle various types of calculation requests."""
        text_lower = text.lower()

        try:
            if "add" in text_lower or "+" in text:
                return self._arithmetic(text, "add")
            elif "subtract" in text_lower or "-" in text:
                return self._arithmetic(text, "subtract")
            elif "multiply" in text_lower or "*" in text or "times" in text_lower:
                return self._arithmetic(text, "multiply")
            elif "divide" in text_lower or "/" in text:
                return self._arithmetic(text, "divide")
            elif "square root" in text_lower or "sqrt" in text_lower:
                return self._square_root(text)
            elif "square" in text_lower:
                return self._square(text)
            else:
                numbers = re.findall(r'-?\d+\.?\d*', text)
                if len(numbers) >= 2:
                    return f"I found numbers {numbers} in your message. Please specify what operation you'd like me to perform (add, subtract, multiply, divide)."
                elif len(numbers) == 1:
                    return f"I found the number {numbers[0]}. I can square it, find its square root, or perform operations with another number."
                else:
                    return "I'm a calculator agent. I can help you with mathematical operations like addition, subtraction, multiplication, division, squares, and square roots. Please provide numbers and specify the operation."

        except Exception as e:
            logger.error(f"Error in calculation: {e}")
            return f"Sorry, I encountered an error while processing your calculation: {str(e)}"

    def _arithmetic(self, text: str, operation: str) -> str:
        """Handle basic arithmetic operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)
        if len(numbers) < 2:
            return f"I need two numbers to perform {operation}. Please provide both numbers."
        a, b = float(numbers[0]), float(numbers[1])
        ops = {"add": a + b, "subtract": a - b, "multiply": a * b}
        if operation == "divide":
            if b == 0:
                return "Cannot divide by zero."
            result = a / b
        else:
            result = ops[operation]
        return f"Calculation: {a} {operation} {b} = {result}"

    def _square_root(self, text: str) -> str:
        """Handle square root operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)
        if not numbers:
            return "I need a number to find its square root."
        a = float(numbers[0])
        if a < 0:
            return "Cannot take square root of a negative number."
        return f"Square root of {a} = {math.sqrt(a)}"

    def _square(self, text: str) -> str:
        """Handle square operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)
        if not numbers:
            return "I need a number to square it."
        a = float(numbers[0])
        return f"{a} squared = {a ** 2}"


class AnalysisAgent(EnhancedAgent):
    """Agent that analyzes text."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Analysis Agent",
            description="Analyzes text and provides statistics",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        """Process analysis requests."""
        text = self._extract_text_content(message)

        if not self._initialized:
            await self.initialize()

        result_text = self._analyze_text(text)
        return Message(parts=[Part(type="text", content=result_text)])

    def _analyze_text(self, text: str) -> str:
        """Analyze text and return statistics."""
        words = text.split()
        sentences = [s for s in text.split('.') if s.strip()]
        chars = len(text)
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        return (
            f"Text Analysis: {len(words)} words, {len(sentences)} sentences, "
            f"{chars} characters. Average word length: {avg_word_len:.1f} characters."
        )


class MemoryAgent(EnhancedAgent):
    """Agent that manages in-memory key-value storage for other agents."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Memory Agent",
            description="Manages key-value storage for other agents",
            message_broker=message_broker
        )
        self._memory: Dict[str, Any] = {}

    async def process_message(self, message: Message) -> Message:
        """Process memory management requests."""
        text = self._extract_text_content(message)

        if not self._initialized:
            await self.initialize()

        result_text = self._handle_memory_request(text)
        return Message(parts=[Part(type="text", content=result_text)])

    def _handle_memory_request(self, text: str) -> str:
        """Handle various types of memory requests."""
        text_lower = text.lower()

        if "store" in text_lower or "save" in text_lower or "remember" in text_lower:
            return self._store(text)
        elif "retrieve" in text_lower or "get" in text_lower or "recall" in text_lower:
            return self._retrieve(text)
        elif "list" in text_lower or "show" in text_lower:
            return self._list_keys()
        elif "delete" in text_lower or "remove" in text_lower or "forget" in text_lower:
            return self._delete(text)
        else:
            return "I can help you store, retrieve, list, or delete information. Please specify what you'd like me to do."

    def _store(self, text: str) -> str:
        """Handle store requests."""
        for pattern in [r"store (.+) as (.+)", r"save (.+) as (.+)", r"remember (.+) as (.+)"]:
            match = re.search(pattern, text.lower())
            if match:
                value, key = match.group(1).strip(), match.group(2).strip()
                self._memory[key] = value
                return f"Stored '{value}' with key '{key}'"
        return "Please use the format: 'store [value] as [key]' or 'save [value] as [key]'"

    def _retrieve(self, text: str) -> str:
        """Handle retrieve requests."""
        for pattern in [r"retrieve (.+)", r"get (.+)", r"recall (.+)"]:
            match = re.search(pattern, text.lower())
            if match:
                key = match.group(1).strip()
                value = self._memory.get(key)
                if value is not None:
                    return f"Retrieved '{key}': {value}"
                return f"No data found for key '{key}'"
        return "Please specify what you'd like to retrieve: 'retrieve [key]' or 'get [key]'"

    def _list_keys(self) -> str:
        """Handle list requests."""
        keys = list(self._memory.keys())
        if keys:
            return f"Stored keys ({len(keys)}): {', '.join(keys)}"
        return "No data stored in memory"

    def _delete(self, text: str) -> str:
        """Handle delete requests."""
        for pattern in [r"delete (.+)", r"remove (.+)", r"forget (.+)"]:
            match = re.search(pattern, text.lower())
            if match:
                key = match.group(1).strip()
                if key in self._memory:
                    del self._memory[key]
                    return f"Deleted key '{key}'"
                return f"Key '{key}' not found"
        return "Please specify what you'd like to delete: 'delete [key]' or 'remove [key]'"


class MediaAgent(EnhancedAgent):
    """Agent that manages real-time media sessions using LiveKit."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Media Agent",
            description="Manages real-time audio/video sessions using LiveKit",
            message_broker=message_broker
        )
        self.livekit_bridge: Optional[LiveKitBridge] = None

    async def initialize(self, message_broker=None):
        """Initialize the agent with LiveKit bridge."""
        try:
            self.livekit_bridge = create_livekit_bridge()
            if self.livekit_bridge:
                logger.info(f"Agent {self.name} initialized with LiveKit bridge")
            else:
                logger.warning(f"Agent {self.name} could not initialize LiveKit bridge - media features disabled")
        except Exception as e:
            logger.error(f"Failed to initialize LiveKit bridge for {self.name}: {e}")
            self.livekit_bridge = None

        # Set message broker if provided
        if message_broker:
            self.message_broker = message_broker
            # Subscribe to messages for this agent
            await self.subscribe_to_messages()

    async def process_message(self, message: Message) -> Message:
        """Process media-related requests."""
        text = self._extract_text_content(message)

        if not self.livekit_bridge:
            return Message(parts=[Part(
                type="text",
                content="Media functionality is not available. LiveKit bridge not configured."
            )])

        # Parse the message to determine action
        action = self._parse_media_action(text, message)

        try:
            if action["type"] == "media-request":
                return await self._handle_media_request(action, message)
            elif action["type"] == "media-join":
                return await self._handle_media_join(action, message)
            elif action["type"] == "list-rooms":
                return await self._handle_list_rooms()
            elif action["type"] == "room-info":
                return await self._handle_room_info(action)
            else:
                return Message(parts=[Part(
                    type="text",
                    content=(
                        "I can help you with media sessions. Available commands:\n"
                        "- 'create media session' or 'start video call' - Create a new media session\n"
                        "- 'join room [room_name]' - Join an existing room\n"
                        "- 'list rooms' - List active rooms\n"
                        "- 'room info [room_name]' - Get information about a room"
                    )
                )])
        except Exception as e:
            logger.error(f"Error processing media request: {e}")
            return Message(parts=[Part(
                type="text",
                content=f"Error processing media request: {str(e)}"
            )])

    def _parse_media_action(self, text: str, message: Message) -> Dict[str, Any]:
        """Parse the message to determine the media action."""
        text_lower = text.lower()

        # Check for media request keywords
        if any(phrase in text_lower for phrase in [
            "create media", "start video", "start audio", "create room",
            "new session", "video call", "audio call"
        ]):
            return {
                "type": "media-request",
                "room_name": self._extract_room_name(text),
                "role": self._extract_role(text),
                "identity": self._extract_identity(text, message)
            }

        # Check for join room keywords
        elif any(phrase in text_lower for phrase in ["join room", "join session", "connect to"]):
            return {
                "type": "media-join",
                "room_name": self._extract_room_name(text, required=True),
                "role": self._extract_role(text),
                "identity": self._extract_identity(text, message)
            }

        # Check for list rooms
        elif "list rooms" in text_lower or "show rooms" in text_lower:
            return {"type": "list-rooms"}

        # Check for room info
        elif "room info" in text_lower or "room details" in text_lower:
            return {
                "type": "room-info",
                "room_name": self._extract_room_name(text, required=True)
            }

        return {"type": "help"}

    def _extract_room_name(self, text: str, required: bool = False) -> Optional[str]:
        """Extract room name from text."""
        # Look for patterns like "room MyRoom" or "session MySession"
        patterns = [
            r"room\s+([a-zA-Z0-9_-]+)",
            r"session\s+([a-zA-Z0-9_-]+)",
            r"called\s+([a-zA-Z0-9_-]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        if required:
            return None

        # Generate a random room name if none specified
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"room-{timestamp}-{uuid.uuid4().hex[:16]}"

    def _extract_role(self, text: str) -> str:
        """Extract role from text."""
        text_lower = text.lower()

        if "admin" in text_lower or "administrator" in text_lower:
            return "admin"
        elif "moderator" in text_lower or "mod" in text_lower:
            return "moderator"
        elif "publisher" in text_lower or "presenter" in text_lower:
            return "publisher"
        elif "viewer" in text_lower or "watch" in text_lower:
            return "viewer"
        else:
            return "participant"

    def _extract_identity(self, text: str, message: Message) -> str:
        """Extract participant identity from text or generate one."""
        # Look for identity patterns
        identity_patterns = [
            r"as\s+([a-zA-Z0-9_-]+)",
            r"identity\s+([a-zA-Z0-9_-]+)",
            r"user\s+([a-zA-Z0-9_-]+)"
        ]

        for pattern in identity_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        # Check message metadata for identity
        if message.metadata and "user_id" in message.metadata:
            return str(message.metadata["user_id"])

        # Generate a random identity
        return f"user-{uuid.uuid4().hex}"

    async def _handle_media_request(self, action: Dict[str, Any], message: Message) -> Message:
        """Handle request to create a new media session."""
        room_name = action["room_name"]
        role = action["role"]
        identity = action["identity"]

        try:
            # Check if room already exists
            existing_room = await self.livekit_bridge.get_room_info(room_name)

            if not existing_room:
                # Create new room
                room_metadata = {
                    "created_by": identity,
                    "created_at": datetime.now().isoformat(),
                    "a2a_agent": "media"
                }

                room_info = await self.livekit_bridge.create_room(
                    room_name=room_name,
                    metadata=room_metadata
                )

                logger.info(f"Created new room: {room_name}")
            else:
                room_info = existing_room
                logger.info(f"Using existing room: {room_name}")

            # Mint access token
            token = self.livekit_bridge.mint_access_token(
                identity=identity,
                room_name=room_name,
                a2a_role=role,
                metadata=f"A2A participant {identity}"
            )

            # Generate join URL
            join_url = self.livekit_bridge.generate_join_url(room_name, token)

            # Create response with detailed information
            response_data = {
                "room_name": room_name,
                "room_sid": room_info.get("sid"),
                "join_url": join_url,
                "participant_identity": identity,
                "role": role,
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "max_participants": room_info.get("max_participants", 50)
            }

            return Message(parts=[
                Part(type="text", content=f"Media session created successfully! Room: {room_name}"),
                Part(type="data", content=response_data, metadata={"content_type": "application/json"})
            ])

        except Exception as e:
            logger.error(f"Failed to create media session: {e}")
            raise

    async def _handle_media_join(self, action: Dict[str, Any], message: Message) -> Message:
        """Handle request to join an existing media session."""
        room_name = action["room_name"]
        role = action["role"]
        identity = action["identity"]

        if not room_name:
            return Message(parts=[Part(
                type="text",
                content="Please specify a room name to join (e.g., 'join room MyRoom')"
            )])

        try:
            # Check if room exists
            room_info = await self.livekit_bridge.get_room_info(room_name)

            if not room_info:
                return Message(parts=[Part(
                    type="text",
                    content=f"Room '{room_name}' not found. You can create it by saying 'create media session room {room_name}'"
                )])

            # Mint access token
            token = self.livekit_bridge.mint_access_token(
                identity=identity,
                room_name=room_name,
                a2a_role=role,
                metadata=f"A2A participant {identity}"
            )

            # Generate join URL
            join_url = self.livekit_bridge.generate_join_url(room_name, token)

            # Create response
            response_data = {
                "room_name": room_name,
                "join_url": join_url,
                "participant_identity": identity,
                "role": role,
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
            }

            return Message(parts=[
                Part(type="text", content=f"Access granted to room '{room_name}' as {role}"),
                Part(type="data", content=response_data, metadata={"content_type": "application/json"})
            ])

        except Exception as e:
            logger.error(f"Failed to join media session: {e}")
            raise

    async def _handle_list_rooms(self) -> Message:
        """Handle request to list active rooms."""
        # Note: This is a simplified implementation.
        # LiveKit's list_rooms API would need to be called here
        return Message(parts=[Part(
            type="text",
            content="Room listing feature coming soon. For now, you can join specific rooms by name."
        )])

    async def _handle_room_info(self, action: Dict[str, Any]) -> Message:
        """Handle request for room information."""
        room_name = action["room_name"]

        if not room_name:
            return Message(parts=[Part(
                type="text",
                content="Please specify a room name (e.g., 'room info MyRoom')"
            )])

        try:
            room_info = await self.livekit_bridge.get_room_info(room_name)

            if not room_info:
                return Message(parts=[Part(
                    type="text",
                    content=f"Room '{room_name}' not found."
                )])

            participants = await self.livekit_bridge.list_participants(room_name)

            info_text = f"""Room Information for '{room_name}':
- Room SID: {room_info.get('sid', 'N/A')}
- Max Participants: {room_info.get('max_participants', 'N/A')}
- Current Participants: {len(participants)}
- Created: {room_info.get('creation_time', 'N/A')}
- Participants: {', '.join([p['identity'] for p in participants]) if participants else 'None'}"""

            return Message(parts=[
                Part(type="text", content=info_text),
                Part(type="data", content=room_info, metadata={"content_type": "application/json"})
            ])

        except Exception as e:
            logger.error(f"Failed to get room info: {e}")
            return Message(parts=[Part(
                type="text",
                content=f"Error getting room information: {str(e)}"
            )])


# Agent registry
ENHANCED_AGENTS = {}


def initialize_agent_registry(message_broker=None):
    """Initialize the agent registry with message broker support."""
    global ENHANCED_AGENTS
    ENHANCED_AGENTS = {
        "calculator": CalculatorAgent(message_broker=message_broker),
        "analysis": AnalysisAgent(message_broker=message_broker),
        "memory": MemoryAgent(message_broker=message_broker),
        "media": MediaAgent(message_broker=message_broker),
    }


async def get_agent(agent_type: str, message_broker=None) -> Optional[EnhancedAgent]:
    """Get an agent by type."""
    if not ENHANCED_AGENTS:
        initialize_agent_registry(message_broker)

    agent = ENHANCED_AGENTS.get(agent_type)
    if agent and not agent._initialized:
        await agent.initialize(message_broker)
    return agent


async def route_message_to_agent(message: Message, message_broker=None) -> Message:
    """Route a message to the appropriate agent based on content.

    For agent-to-agent communication, we simply acknowledge receipt and store the message.
    Agents can retrieve messages using get_messages MCP tool.
    """
    text = " ".join(part.text for part in message.parts if part.kind == "text" and part.text)

    # Simple acknowledgment response for agent communication
    response_text = f"Message received and logged. Agents can retrieve it using get_messages."

    # If message broker is available, publish it for other agents to see
    if message_broker:
        try:
            await message_broker.publish_event("agent.message.broadcast", {
                "content": text,
                "timestamp": datetime.utcnow().isoformat(),
                "message_id": str(uuid.uuid4())
            })
            logger.info(f"Message broadcast to agent network: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to broadcast message: {e}")

    return Message(parts=[Part(type="text", content=response_text)])


async def initialize_all_agents(message_broker=None):
    """Initialize all agents with MCP connections and message broker."""
    if not ENHANCED_AGENTS:
        initialize_agent_registry(message_broker)

    for agent in ENHANCED_AGENTS.values():
        await agent.initialize(message_broker)


async def cleanup_all_agents():
    """Clean up all agent resources."""
    pass
