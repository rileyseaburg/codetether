"""
MCP Server implementation providing tools for A2A agents.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import math
import sys
import os

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

logger = logging.getLogger(__name__)


class MCPToolServer:
    """MCP server providing tools for A2A agents."""

    def __init__(self, host: str = "localhost", port: int = 9000):
        self.host = host
        self.port = port
        self.server = Server("a2a-tools")
        self._setup_tools()

    def _setup_tools(self):
        """Set up available tools."""

        @self.server.tool()
        async def calculator(
            operation: str,
            a: float,
            b: Optional[float] = None
        ) -> str:
            """
            Perform mathematical calculations.

            Args:
                operation: The operation to perform (add, subtract, multiply, divide, square, sqrt)
                a: First number
                b: Second number (optional for unary operations)
            """
            try:
                if operation == "add":
                    if b is None:
                        return json.dumps({"error": "Addition requires two numbers"})
                    result = a + b
                elif operation == "subtract":
                    if b is None:
                        return json.dumps({"error": "Subtraction requires two numbers"})
                    result = a - b
                elif operation == "multiply":
                    if b is None:
                        return json.dumps({"error": "Multiplication requires two numbers"})
                    result = a * b
                elif operation == "divide":
                    if b is None:
                        return json.dumps({"error": "Division requires two numbers"})
                    if b == 0:
                        return json.dumps({"error": "Cannot divide by zero"})
                    result = a / b
                elif operation == "square":
                    result = a ** 2
                elif operation == "sqrt":
                    if a < 0:
                        return json.dumps({"error": "Cannot take square root of negative number"})
                    result = math.sqrt(a)
                else:
                    return json.dumps({"error": f"Unknown operation: {operation}"})

                return json.dumps({"result": result, "operation": operation, "inputs": {"a": a, "b": b}})

            except Exception as e:
                return json.dumps({"error": f"Calculation error: {str(e)}"})

        @self.server.tool()
        async def weather_info(location: str) -> str:
            """
            Get weather information for a location.
            Requires WEATHER_API_KEY environment variable to be set.

            Args:
                location: The location to get weather for
            """
            api_key = os.environ.get('WEATHER_API_KEY')
            if not api_key:
                return json.dumps({"error": "Weather service not configured. Set WEATHER_API_KEY environment variable."})
            return json.dumps({"error": "Weather API integration not yet implemented. Configure a weather provider."})

        @self.server.tool()
        async def text_analyzer(text: str) -> str:
            """
            Analyze text and provide statistics.

            Args:
                text: The text to analyze
            """
            words = text.split()
            sentences = text.split('.')
            chars = len(text)
            chars_no_spaces = len(text.replace(' ', ''))

            analysis = {
                "text": text,
                "word_count": len(words),
                "sentence_count": len([s for s in sentences if s.strip()]),
                "character_count": chars,
                "character_count_no_spaces": chars_no_spaces,
                "average_word_length": sum(len(word) for word in words) / len(words) if words else 0,
                "timestamp": datetime.now().isoformat()
            }
            return json.dumps(analysis)

        @self.server.tool()
        async def memory_store(
            action: str,
            key: Optional[str] = None,
            value: Optional[str] = None
        ) -> str:
            """
            Simple key-value memory store for agents.

            Args:
                action: Action to perform (store, retrieve, list, delete)
                key: Key for store/retrieve/delete operations
                value: Value for store operation
            """
            if not hasattr(self, '_memory'):
                self._memory = {}

            try:
                if action == "store":
                    if key is None or value is None:
                        return json.dumps({"error": "Store action requires both key and value"})
                    self._memory[key] = value
                    return json.dumps({"action": "store", "key": key, "value": value, "success": True})

                elif action == "retrieve":
                    if key is None:
                        return json.dumps({"error": "Retrieve action requires a key"})
                    value = self._memory.get(key)
                    if value is None:
                        return json.dumps({"action": "retrieve", "key": key, "found": False})
                    return json.dumps({"action": "retrieve", "key": key, "value": value, "found": True})

                elif action == "list":
                    keys = list(self._memory.keys())
                    return json.dumps({"action": "list", "keys": keys, "count": len(keys)})

                elif action == "delete":
                    if key is None:
                        return json.dumps({"error": "Delete action requires a key"})
                    if key in self._memory:
                        del self._memory[key]
                        return json.dumps({"action": "delete", "key": key, "success": True})
                    return json.dumps({"action": "delete", "key": key, "success": False, "error": "Key not found"})

                else:
                    return json.dumps({"error": f"Unknown action: {action}"})

            except Exception as e:
                return json.dumps({"error": f"Memory operation error: {str(e)}"})

    async def run(self):
        """Run the MCP server."""
        logger.info(f"Starting MCP tool server")

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)


async def run_mcp_server():
    """Run the MCP server."""
    server = MCPToolServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(run_mcp_server())
