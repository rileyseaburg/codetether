"""
Enhanced A2A agents that use MCP tools to perform complex tasks.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from .mock_mcp import get_mock_mcp_client, MockMCPClient, cleanup_mock_mcp_client
from .models import Part, Message, Task, TaskStatus
from .livekit_bridge import create_livekit_bridge, LiveKitBridge

logger = logging.getLogger(__name__)


class EnhancedAgent:
    """Base class for agents that can use MCP tools and communicate with other agents."""

    def __init__(self, name: str, description: str, message_broker=None):
        self.name = name
        self.description = description
        self.mcp_client: Optional[MockMCPClient] = None
        self.message_broker = message_broker
        self._message_handlers: Dict[str, List[callable]] = {}

    async def initialize(self, message_broker=None):
        """Initialize the agent with MCP client and message broker."""
        try:
            self.mcp_client = await get_mock_mcp_client()
            logger.info(f"Agent {self.name} initialized with mock MCP tools")
        except Exception as e:
            logger.error(f"Failed to initialize mock MCP client for {self.name}: {e}")

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
    """Agent that performs mathematical calculations using MCP tools."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Calculator Agent",
            description="Performs mathematical calculations and data analysis",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        """Process calculation requests."""
        text = self._extract_text_content(message)

        if not self.mcp_client:
            await self.initialize()

        # Parse mathematical expressions
        result_text = await self._handle_calculation_request(text)

        return Message(parts=[Part(type="text", content=result_text)])

    async def _handle_calculation_request(self, text: str) -> str:
        """Handle various types of calculation requests."""
        text_lower = text.lower()

        try:
            # Simple arithmetic patterns
            if "add" in text_lower or "+" in text:
                return await self._handle_arithmetic(text, "add")
            elif "subtract" in text_lower or "-" in text:
                return await self._handle_arithmetic(text, "subtract")
            elif "multiply" in text_lower or "*" in text or "times" in text_lower:
                return await self._handle_arithmetic(text, "multiply")
            elif "divide" in text_lower or "/" in text:
                return await self._handle_arithmetic(text, "divide")
            elif "square root" in text_lower or "sqrt" in text_lower:
                return await self._handle_square_root(text)
            elif "square" in text_lower:
                return await self._handle_square(text)
            else:
                # Try to detect numbers and suggest operations
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

    async def _handle_arithmetic(self, text: str, operation: str) -> str:
        """Handle basic arithmetic operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)

        if len(numbers) < 2:
            return f"I need two numbers to perform {operation}. Please provide both numbers."

        try:
            a = float(numbers[0])
            b = float(numbers[1])

            if self.mcp_client:
                result = await self.mcp_client.calculator(operation, a, b)
                if result.get("success"):
                    calc_result = result["result"]
                    if "error" in calc_result:
                        return f"Calculation error: {calc_result['error']}"
                    return f"Calculation: {a} {operation} {b} = {calc_result['result']}"
                else:
                    return f"Error calling calculator tool: {result.get('error', 'Unknown error')}"
            else:
                return "Calculator tools are not available. Please try again."

        except ValueError:
            return "Please provide valid numbers for the calculation."

    async def _handle_square_root(self, text: str) -> str:
        """Handle square root operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)

        if len(numbers) < 1:
            return "I need a number to find its square root."

        try:
            a = float(numbers[0])

            if self.mcp_client:
                result = await self.mcp_client.calculator("sqrt", a)
                if result.get("success"):
                    calc_result = result["result"]
                    if "error" in calc_result:
                        return f"Calculation error: {calc_result['error']}"
                    return f"Square root of {a} = {calc_result['result']}"
                else:
                    return f"Error calling calculator tool: {result.get('error', 'Unknown error')}"
            else:
                return "Calculator tools are not available. Please try again."

        except ValueError:
            return "Please provide a valid number for the square root calculation."

    async def _handle_square(self, text: str) -> str:
        """Handle square operations."""
        numbers = re.findall(r'-?\d+\.?\d*', text)

        if len(numbers) < 1:
            return "I need a number to square it."

        try:
            a = float(numbers[0])

            if self.mcp_client:
                result = await self.mcp_client.calculator("square", a)
                if result.get("success"):
                    calc_result = result["result"]
                    if "error" in calc_result:
                        return f"Calculation error: {calc_result['error']}"
                    return f"{a} squared = {calc_result['result']}"
                else:
                    return f"Error calling calculator tool: {result.get('error', 'Unknown error')}"
            else:
                return "Calculator tools are not available. Please try again."

        except ValueError:
            return "Please provide a valid number for the square calculation."


class AnalysisAgent(EnhancedAgent):
    """Agent that analyzes text and provides weather information using MCP tools."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Analysis Agent",
            description="Analyzes text and provides weather information",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        """Process analysis requests."""
        text = self._extract_text_content(message)

        if not self.mcp_client:
            await self.initialize()

        result_text = await self._handle_analysis_request(text)

        return Message(parts=[Part(type="text", content=result_text)])

    async def _handle_analysis_request(self, text: str) -> str:
        """Handle various types of analysis requests."""
        text_lower = text.lower()

        try:
            if "weather" in text_lower:
                return await self._handle_weather_request(text)
            elif "analyze" in text_lower or "analysis" in text_lower:
                return await self._handle_text_analysis(text)
            else:
                # Default to text analysis
                return await self._handle_text_analysis(text)

        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"

    async def _handle_weather_request(self, text: str) -> str:
        """Handle weather information requests."""
        # Extract location from text (simple pattern matching)
        location_patterns = [
            r"weather in (.+)",
            r"weather for (.+)",
            r"weather at (.+)",
        ]

        location = None
        for pattern in location_patterns:
            match = re.search(pattern, text.lower())
            if match:
                location = match.group(1).strip()
                break

        if not location:
            location = "unknown location"

        if self.mcp_client:
            result = await self.mcp_client.get_weather(location)
            if result.get("success"):
                weather_data = result["result"]
                return f"Weather for {weather_data['location']}: {weather_data['temperature']}, {weather_data['condition']}. Humidity: {weather_data['humidity']}, Wind: {weather_data['wind']}"
            else:
                return f"Error getting weather information: {result.get('error', 'Unknown error')}"
        else:
            return "Weather tools are not available. Please try again."

    async def _handle_text_analysis(self, text: str) -> str:
        """Handle text analysis requests."""
        if self.mcp_client:
            result = await self.mcp_client.analyze_text(text)
            if result.get("success"):
                analysis = result["result"]
                return f"Text Analysis: {analysis['word_count']} words, {analysis['sentence_count']} sentences, {analysis['character_count']} characters. Average word length: {analysis['average_word_length']:.1f} characters."
            else:
                return f"Error analyzing text: {result.get('error', 'Unknown error')}"
        else:
            return "Text analysis tools are not available. Please try again."


class MemoryAgent(EnhancedAgent):
    """Agent that manages memory and data storage using MCP tools."""

    def __init__(self, message_broker=None):
        super().__init__(
            name="Memory Agent",
            description="Manages memory and data storage for other agents",
            message_broker=message_broker
        )

    async def process_message(self, message: Message) -> Message:
        """Process memory management requests."""
        text = self._extract_text_content(message)

        if not self.mcp_client:
            await self.initialize()

        result_text = await self._handle_memory_request(text)

        return Message(parts=[Part(type="text", content=result_text)])

    async def _handle_memory_request(self, text: str) -> str:
        """Handle various types of memory requests."""
        text_lower = text.lower()

        try:
            if "store" in text_lower or "save" in text_lower or "remember" in text_lower:
                return await self._handle_store_request(text)
            elif "retrieve" in text_lower or "get" in text_lower or "recall" in text_lower:
                return await self._handle_retrieve_request(text)
            elif "list" in text_lower or "show" in text_lower:
                return await self._handle_list_request()
            elif "delete" in text_lower or "remove" in text_lower or "forget" in text_lower:
                return await self._handle_delete_request(text)
            else:
                return "I can help you store, retrieve, list, or delete information. Please specify what you'd like me to do."

        except Exception as e:
            logger.error(f"Error in memory operation: {e}")
            return f"Sorry, I encountered an error while processing your memory request: {str(e)}"

    async def _handle_store_request(self, text: str) -> str:
        """Handle store requests."""
        # Simple pattern matching for key-value pairs
        store_patterns = [
            r"store (.+) as (.+)",
            r"save (.+) as (.+)",
            r"remember (.+) as (.+)",
        ]

        for pattern in store_patterns:
            match = re.search(pattern, text.lower())
            if match:
                value = match.group(1).strip()
                key = match.group(2).strip()

                if self.mcp_client:
                    result = await self.mcp_client.memory_operation("store", key, value)
                    if result.get("success"):
                        mem_result = result["result"]
                        if mem_result.get("success"):
                            return f"Stored '{value}' with key '{key}'"
                        else:
                            return f"Error storing data: {mem_result.get('error', 'Unknown error')}"
                    else:
                        return f"Error calling memory tool: {result.get('error', 'Unknown error')}"
                else:
                    return "Memory tools are not available. Please try again."

        return "Please use the format: 'store [value] as [key]' or 'save [value] as [key]'"

    async def _handle_retrieve_request(self, text: str) -> str:
        """Handle retrieve requests."""
        # Extract key from text
        retrieve_patterns = [
            r"retrieve (.+)",
            r"get (.+)",
            r"recall (.+)",
        ]

        for pattern in retrieve_patterns:
            match = re.search(pattern, text.lower())
            if match:
                key = match.group(1).strip()

                if self.mcp_client:
                    result = await self.mcp_client.memory_operation("retrieve", key)
                    if result.get("success"):
                        mem_result = result["result"]
                        if mem_result.get("found"):
                            return f"Retrieved '{key}': {mem_result['value']}"
                        else:
                            return f"No data found for key '{key}'"
                    else:
                        return f"Error calling memory tool: {result.get('error', 'Unknown error')}"
                else:
                    return "Memory tools are not available. Please try again."

        return "Please specify what you'd like to retrieve: 'retrieve [key]' or 'get [key]'"

    async def _handle_list_request(self) -> str:
        """Handle list requests."""
        if self.mcp_client:
            result = await self.mcp_client.memory_operation("list")
            if result.get("success"):
                mem_result = result["result"]
                keys = mem_result.get("keys", [])
                if keys:
                    return f"Stored keys ({len(keys)}): {', '.join(keys)}"
                else:
                    return "No data stored in memory"
            else:
                return f"Error calling memory tool: {result.get('error', 'Unknown error')}"
        else:
            return "Memory tools are not available. Please try again."

    async def _handle_delete_request(self, text: str) -> str:
        """Handle delete requests."""
        # Extract key from text
        delete_patterns = [
            r"delete (.+)",
            r"remove (.+)",
            r"forget (.+)",
        ]

        for pattern in delete_patterns:
            match = re.search(pattern, text.lower())
            if match:
                key = match.group(1).strip()

                if self.mcp_client:
                    result = await self.mcp_client.memory_operation("delete", key)
                    if result.get("success"):
                        mem_result = result["result"]
                        if mem_result.get("success"):
                            return f"Deleted key '{key}'"
                        else:
                            return f"Key '{key}' not found"
                    else:
                        return f"Error calling memory tool: {result.get('error', 'Unknown error')}"
                else:
                    return "Memory tools are not available. Please try again."

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
    if agent and not agent.mcp_client:
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
    await cleanup_mock_mcp_client()
