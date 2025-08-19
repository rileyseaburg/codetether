"""
Enhanced A2A agents that use MCP tools to perform complex tasks.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from .mock_mcp import get_mock_mcp_client, MockMCPClient, cleanup_mock_mcp_client
from .models import Part, Message

logger = logging.getLogger(__name__)


class EnhancedAgent:
    """Base class for agents that can use MCP tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.mcp_client: Optional[MockMCPClient] = None
    
    async def initialize(self):
        """Initialize the agent with MCP client."""
        try:
            self.mcp_client = await get_mock_mcp_client()
            logger.info(f"Agent {self.name} initialized with mock MCP tools")
        except Exception as e:
            logger.error(f"Failed to initialize mock MCP client for {self.name}: {e}")
    
    async def process_message(self, message: Message) -> Message:
        """Process a message and return a response."""
        raise NotImplementedError
    
    def _extract_text_content(self, message: Message) -> str:
        """Extract text content from message parts."""
        text_parts = []
        for part in message.parts:
            if part.type == "text":
                text_parts.append(part.content)
        return " ".join(text_parts)


class CalculatorAgent(EnhancedAgent):
    """Agent that performs mathematical calculations using MCP tools."""
    
    def __init__(self):
        super().__init__(
            name="Calculator Agent",
            description="Performs mathematical calculations and data analysis"
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
    
    def __init__(self):
        super().__init__(
            name="Analysis Agent",
            description="Analyzes text and provides weather information"
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
    
    def __init__(self):
        super().__init__(
            name="Memory Agent",
            description="Manages memory and data storage for other agents"
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


# Agent registry
ENHANCED_AGENTS = {
    "calculator": CalculatorAgent(),
    "analysis": AnalysisAgent(),
    "memory": MemoryAgent(),
}


async def get_agent(agent_type: str) -> Optional[EnhancedAgent]:
    """Get an agent by type."""
    agent = ENHANCED_AGENTS.get(agent_type)
    if agent and not agent.mcp_client:
        await agent.initialize()
    return agent


async def route_message_to_agent(message: Message) -> Message:
    """Route a message to the appropriate agent based on content."""
    text = " ".join(part.content for part in message.parts if part.type == "text").lower()
    
    # Route based on content keywords
    if any(word in text for word in ["add", "subtract", "multiply", "divide", "calculate", "math", "square", "sqrt", "+", "-", "*", "/"]):
        agent = await get_agent("calculator")
        if agent:
            return await agent.process_message(message)
    
    elif any(word in text for word in ["weather", "analyze", "analysis"]):
        agent = await get_agent("analysis")
        if agent:
            return await agent.process_message(message)
    
    elif any(word in text for word in ["store", "save", "remember", "retrieve", "get", "recall", "list", "delete", "remove", "forget", "memory"]):
        agent = await get_agent("memory")
        if agent:
            return await agent.process_message(message)
    
    # Default to echo behavior
    return Message(parts=[Part(type="text", content=f"Echo: {' '.join(part.content for part in message.parts if part.type == 'text')}")])


async def initialize_all_agents():
    """Initialize all agents with MCP connections."""
    for agent in ENHANCED_AGENTS.values():
        await agent.initialize()


async def cleanup_all_agents():
    """Clean up all agent resources."""
    await cleanup_mock_mcp_client()