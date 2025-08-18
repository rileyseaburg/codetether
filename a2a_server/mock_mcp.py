"""
Mock MCP implementation for demonstration purposes.
This simulates MCP tool integration without requiring complex MCP infrastructure.
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class MockMCPTool:
    """Base class for mock MCP tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call the tool with given arguments."""
        raise NotImplementedError


class CalculatorTool(MockMCPTool):
    """Mock calculator tool."""
    
    def __init__(self):
        super().__init__("calculator", "Performs mathematical calculations")
    
    async def call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform calculation."""
        try:
            operation = arguments.get("operation")
            a = float(arguments.get("a", 0))
            b = arguments.get("b")
            
            if b is not None:
                b = float(b)
            
            if operation == "add":
                if b is None:
                    return {"error": "Addition requires two numbers"}
                result = a + b
            elif operation == "subtract":
                if b is None:
                    return {"error": "Subtraction requires two numbers"}
                result = a - b
            elif operation == "multiply":
                if b is None:
                    return {"error": "Multiplication requires two numbers"}
                result = a * b
            elif operation == "divide":
                if b is None:
                    return {"error": "Division requires two numbers"}
                if b == 0:
                    return {"error": "Cannot divide by zero"}
                result = a / b
            elif operation == "square":
                result = a ** 2
            elif operation == "sqrt":
                if a < 0:
                    return {"error": "Cannot take square root of negative number"}
                result = math.sqrt(a)
            else:
                return {"error": f"Unknown operation: {operation}"}
            
            return {"result": result, "operation": operation, "inputs": {"a": a, "b": b}}
            
        except Exception as e:
            return {"error": f"Calculation error: {str(e)}"}


class WeatherTool(MockMCPTool):
    """Mock weather tool."""
    
    def __init__(self):
        super().__init__("weather_info", "Provides weather information")
    
    async def call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather information."""
        location = arguments.get("location", "unknown location")
        
        # Mock weather data
        return {
            "location": location,
            "temperature": "22°C",
            "condition": "Partly cloudy",
            "humidity": "65%",
            "wind": "10 km/h SW",
            "timestamp": datetime.now().isoformat()
        }


class TextAnalyzerTool(MockMCPTool):
    """Mock text analyzer tool."""
    
    def __init__(self):
        super().__init__("text_analyzer", "Analyzes text and provides statistics")
    
    async def call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze text."""
        text = arguments.get("text", "")
        
        words = text.split()
        sentences = text.split('.')
        chars = len(text)
        chars_no_spaces = len(text.replace(' ', ''))
        
        return {
            "text": text,
            "word_count": len(words),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "character_count": chars,
            "character_count_no_spaces": chars_no_spaces,
            "average_word_length": sum(len(word) for word in words) / len(words) if words else 0,
            "timestamp": datetime.now().isoformat()
        }


class MemoryTool(MockMCPTool):
    """Mock memory/storage tool."""
    
    def __init__(self):
        super().__init__("memory_store", "Simple key-value memory store")
        self._memory = {}
    
    async def call(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Perform memory operation."""
        try:
            action = arguments.get("action")
            key = arguments.get("key")
            value = arguments.get("value")
            
            if action == "store":
                if key is None or value is None:
                    return {"error": "Store action requires both key and value"}
                self._memory[key] = value
                return {"action": "store", "key": key, "value": value, "success": True}
            
            elif action == "retrieve":
                if key is None:
                    return {"error": "Retrieve action requires a key"}
                value = self._memory.get(key)
                if value is None:
                    return {"action": "retrieve", "key": key, "found": False}
                return {"action": "retrieve", "key": key, "value": value, "found": True}
            
            elif action == "list":
                keys = list(self._memory.keys())
                return {"action": "list", "keys": keys, "count": len(keys)}
            
            elif action == "delete":
                if key is None:
                    return {"error": "Delete action requires a key"}
                if key in self._memory:
                    del self._memory[key]
                    return {"action": "delete", "key": key, "success": True}
                return {"action": "delete", "key": key, "success": False, "error": "Key not found"}
            
            else:
                return {"error": f"Unknown action: {action}"}
                
        except Exception as e:
            return {"error": f"Memory operation error: {str(e)}"}


class MockMCPClient:
    """Mock MCP client that simulates MCP tool interactions."""
    
    def __init__(self):
        self.tools = {
            "calculator": CalculatorTool(),
            "weather_info": WeatherTool(),
            "text_analyzer": TextAnalyzerTool(),
            "memory_store": MemoryTool()
        }
        self.connected = False
    
    async def connect(self) -> bool:
        """Simulate connecting to MCP server."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self.connected = True
        logger.info(f"Mock MCP client connected with {len(self.tools)} tools")
        return True
    
    async def disconnect(self):
        """Simulate disconnecting from MCP server."""
        self.connected = False
        logger.info("Mock MCP client disconnected")
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return [
            {"name": name, "description": tool.description}
            for name, tool in self.tools.items()
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with the given arguments."""
        if not self.connected:
            return {"error": "Not connected to MCP server"}
        
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}
        
        try:
            result = await tool.call(arguments)
            return {
                "success": True,
                "tool": tool_name,
                "arguments": arguments,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "error": f"Tool call failed: {str(e)}",
                "tool": tool_name,
                "arguments": arguments
            }
    
    async def calculator(self, operation: str, a: float, b: Optional[float] = None) -> Dict[str, Any]:
        """Convenience method for calculator tool."""
        args = {"operation": operation, "a": a}
        if b is not None:
            args["b"] = b
        return await self.call_tool("calculator", args)
    
    async def get_weather(self, location: str) -> Dict[str, Any]:
        """Convenience method for weather tool."""
        return await self.call_tool("weather_info", {"location": location})
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Convenience method for text analyzer tool."""
        return await self.call_tool("text_analyzer", {"text": text})
    
    async def memory_operation(self, action: str, key: Optional[str] = None, value: Optional[str] = None) -> Dict[str, Any]:
        """Convenience method for memory store tool."""
        args = {"action": action}
        if key is not None:
            args["key"] = key
        if value is not None:
            args["value"] = value
        return await self.call_tool("memory_store", args)


# Global mock MCP client instance
_mock_mcp_client: Optional[MockMCPClient] = None


async def get_mock_mcp_client() -> MockMCPClient:
    """Get or create the global mock MCP client instance."""
    global _mock_mcp_client
    
    if _mock_mcp_client is None:
        _mock_mcp_client = MockMCPClient()
        await _mock_mcp_client.connect()
    
    return _mock_mcp_client


async def cleanup_mock_mcp_client():
    """Clean up the global mock MCP client instance."""
    global _mock_mcp_client
    
    if _mock_mcp_client:
        await _mock_mcp_client.disconnect()
        _mock_mcp_client = None