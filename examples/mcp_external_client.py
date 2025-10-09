"""
External MCP Client for connecting to deployed A2A Server.

This client allows external agents to synchronize with and use tools
from a deployed A2A server's MCP HTTP interface.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class A2AMCPClient:
    """HTTP-based MCP client for external agent synchronization."""
    
    def __init__(self, endpoint: str, timeout: float = 30.0):
        """
        Initialize MCP client.
        
        Args:
            endpoint: MCP JSON-RPC endpoint (e.g., http://a2a.example.com:9000/mcp/v1/rpc)
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._request_id = 0
        
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        self._request_id += 1
        
        request_body = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {}
        }
        
        logger.debug(f"Sending request: {json.dumps(request_body, indent=2)}")
        
        try:
            response = await self.client.post(
                self.endpoint,
                json=request_body,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Received response: {json.dumps(data, indent=2)}")
            
            if "error" in data:
                raise Exception(f"MCP error: {data['error']}")
            
            return data.get("result", {})
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling MCP: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling MCP: {e}")
            raise
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        result = await self._send_request("tools/list")
        return result.get("tools", [])
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        result = await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            }
        )
        
        # Extract text content from response
        content = result.get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "{}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"result": text}
        
        return result
    
    async def calculator(
        self,
        operation: str,
        a: float,
        b: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Perform a calculation.
        
        Args:
            operation: add, subtract, multiply, divide, square, sqrt
            a: First number
            b: Second number (optional for unary operations)
        """
        args = {"operation": operation, "a": a}
        if b is not None:
            args["b"] = b
        return await self.call_tool("calculator", args)
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze text and get statistics."""
        return await self.call_tool("text_analyzer", {"text": text})
    
    async def get_weather(self, location: str) -> Dict[str, Any]:
        """Get weather information for a location."""
        return await self.call_tool("weather_info", {"location": location})
    
    async def memory_store(
        self,
        action: str,
        key: Optional[str] = None,
        value: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Interact with shared memory.
        
        Args:
            action: store, retrieve, list, delete
            key: Key for store/retrieve/delete
            value: Value for store
        """
        args = {"action": action}
        if key:
            args["key"] = key
        if value:
            args["value"] = value
        return await self.call_tool("memory_store", args)


async def example_usage():
    """Example usage of the MCP client."""
    
    # Connect to deployed A2A server
    # Update this endpoint to match your deployment
    endpoint = "http://localhost:9000/mcp/v1/rpc"
    
    client = A2AMCPClient(endpoint=endpoint)
    
    try:
        print("=" * 60)
        print("A2A Server MCP Client - Example Usage")
        print("=" * 60)
        print()
        
        # List available tools
        print("📋 Listing available MCP tools...")
        tools = await client.list_tools()
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print()
        
        # Calculator examples
        print("🧮 Calculator Examples:")
        result = await client.calculator("add", 10, 5)
        print(f"  10 + 5 = {result.get('result')}")
        
        result = await client.calculator("multiply", 7, 6)
        print(f"  7 × 6 = {result.get('result')}")
        
        result = await client.calculator("sqrt", 144)
        print(f"  √144 = {result.get('result')}")
        print()
        
        # Text analysis
        print("📝 Text Analysis:")
        text = "The quick brown fox jumps over the lazy dog."
        result = await client.analyze_text(text)
        print(f"  Text: '{text}'")
        print(f"  Words: {result.get('word_count')}")
        print(f"  Characters: {result.get('character_count')}")
        print(f"  Avg word length: {result.get('average_word_length', 0):.2f}")
        print()
        
        # Weather info
        print("🌤️  Weather Information:")
        result = await client.get_weather("San Francisco")
        print(f"  Location: {result.get('location')}")
        print(f"  Temperature: {result.get('temperature')}")
        print(f"  Condition: {result.get('condition')}")
        print()
        
        # Memory operations
        print("💾 Shared Memory Operations:")
        
        # Store data
        result = await client.memory_store("store", "agent_status", "active")
        print(f"  Stored: {result}")
        
        result = await client.memory_store("store", "coordination_mode", "distributed")
        print(f"  Stored: {result}")
        
        # List keys
        result = await client.memory_store("list")
        print(f"  Keys in memory: {result.get('keys')}")
        
        # Retrieve data
        result = await client.memory_store("retrieve", "agent_status")
        print(f"  Retrieved: key='{result.get('key')}', value='{result.get('value')}'")
        
        # Delete data
        result = await client.memory_store("delete", "coordination_mode")
        print(f"  Deleted: {result}")
        print()
        
        print("=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


async def agent_coordination_example():
    """Example of multiple agents coordinating via MCP."""
    
    endpoint = "http://localhost:9000/mcp/v1/rpc"
    
    print("=" * 60)
    print("Multi-Agent Coordination Example")
    print("=" * 60)
    print()
    
    # Simulate Agent 1
    agent1 = A2AMCPClient(endpoint=endpoint)
    
    # Simulate Agent 2
    agent2 = A2AMCPClient(endpoint=endpoint)
    
    try:
        # Agent 1 stores task information
        print("🤖 Agent 1: Storing task in shared memory...")
        result = await agent1.memory_store(
            "store",
            "task_123",
            json.dumps({
                "type": "calculation",
                "status": "pending",
                "assigned_to": "agent_2"
            })
        )
        print(f"  ✓ Task stored: {result}")
        print()
        
        # Agent 2 retrieves the task
        print("🤖 Agent 2: Retrieving task from shared memory...")
        result = await agent2.memory_store("retrieve", "task_123")
        task_data = json.loads(result.get("value", "{}"))
        print(f"  ✓ Task retrieved: {task_data}")
        print()
        
        # Agent 2 performs the calculation
        if task_data.get("type") == "calculation":
            print("🤖 Agent 2: Executing calculation task...")
            calc_result = await agent2.calculator("add", 42, 8)
            print(f"  ✓ Calculation result: {calc_result.get('result')}")
            print()
            
            # Agent 2 updates task status
            task_data["status"] = "completed"
            task_data["result"] = calc_result.get('result')
            await agent2.memory_store(
                "store",
                "task_123",
                json.dumps(task_data)
            )
            print("  ✓ Task status updated to 'completed'")
            print()
        
        # Agent 1 checks the result
        print("🤖 Agent 1: Checking task completion...")
        result = await agent1.memory_store("retrieve", "task_123")
        final_task = json.loads(result.get("value", "{}"))
        print(f"  ✓ Final task state: {final_task}")
        print()
        
        print("=" * 60)
        print("✅ Agent coordination completed successfully!")
        print("=" * 60)
        
    finally:
        await agent1.close()
        await agent2.close()


async def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "coordinate":
        await agent_coordination_example()
    else:
        await example_usage()


if __name__ == "__main__":
    asyncio.run(main())
