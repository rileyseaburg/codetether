"""
MCP Client for A2A agents to interact with tools.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
import subprocess
import os
import signal

from mcp.client import ClientSession, StdioServerParameters
from mcp.types import CallToolRequest, ListToolsRequest

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for A2A agents to use tools."""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.tools: List[Dict[str, Any]] = []
        self._server_process: Optional[subprocess.Popen] = None
        
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        try:
            # Start the MCP server as a subprocess
            self._server_process = subprocess.Popen(
                ["python", "-m", "a2a_server.mcp_server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd="/home/runner/work/A2A-Server-MCP/A2A-Server-MCP"
            )
            
            # Create client session
            server_params = StdioServerParameters(
                command="python",
                args=["-m", "a2a_server.mcp_server"],
                cwd="/home/runner/work/A2A-Server-MCP/A2A-Server-MCP"
            )
            
            self.session = ClientSession(server_params)
            await self.session.initialize()
            
            # Get available tools
            await self._load_tools()
            
            logger.info(f"Connected to MCP server with {len(self.tools)} tools")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.close()
            self.session = None
            
        if self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._server_process.kill()
            except Exception as e:
                logger.error(f"Error stopping MCP server process: {e}")
            finally:
                self._server_process = None
    
    async def _load_tools(self):
        """Load available tools from the MCP server."""
        if not self.session:
            return
            
        try:
            tools_response = await self.session.list_tools()
            self.tools = [tool.model_dump() for tool in tools_response.tools]
            logger.info(f"Loaded {len(self.tools)} tools: {[tool['name'] for tool in self.tools]}")
        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            self.tools = []
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return self.tools.copy()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with the given arguments."""
        if not self.session:
            return {"error": "Not connected to MCP server"}
        
        try:
            # Find the tool
            tool = next((t for t in self.tools if t['name'] == tool_name), None)
            if not tool:
                return {"error": f"Tool '{tool_name}' not found"}
            
            # Call the tool
            request = CallToolRequest(name=tool_name, arguments=arguments)
            response = await self.session.call_tool(request)
            
            # Process response
            if response.content:
                # Extract text content
                result_text = ""
                for content in response.content:
                    if hasattr(content, 'text'):
                        result_text += content.text
                    elif hasattr(content, 'content'):
                        result_text += str(content.content)
                    else:
                        result_text += str(content)
                
                # Try to parse as JSON
                try:
                    result = json.loads(result_text)
                except json.JSONDecodeError:
                    result = {"result": result_text}
                
                return {
                    "success": True,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                }
            else:
                return {
                    "success": True,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": "No content returned"
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


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


async def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client instance."""
    global _mcp_client
    
    if _mcp_client is None:
        _mcp_client = MCPClient()
        await _mcp_client.connect()
    
    return _mcp_client


async def cleanup_mcp_client():
    """Clean up the global MCP client instance."""
    global _mcp_client
    
    if _mcp_client:
        await _mcp_client.disconnect()
        _mcp_client = None