"""
HTTP/SSE-based MCP Server for external agent connections.

This allows external agents to connect to the MCP server over HTTP
instead of stdio, enabling distributed agent synchronization.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPHTTPServer:
    """HTTP-based MCP server for external agent connections."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 9000):
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP HTTP Server", version="1.0.0")
        self._memory: Dict[str, str] = {}
        self._setup_routes()
        
    def _setup_routes(self):
        """Set up HTTP routes for MCP."""
        
        @self.app.get("/")
        async def root():
            """Health check endpoint."""
            return {
                "status": "ok",
                "server": "MCP HTTP Server",
                "version": "1.0.0",
                "endpoints": {
                    "rpc": "/mcp/v1/rpc",
                    "tools": "/mcp/v1/tools",
                    "health": "/"
                }
            }
        
        @self.app.get("/mcp/v1/tools")
        async def list_tools():
            """List available MCP tools."""
            tools = [
                {
                    "name": "calculator",
                    "description": "Perform mathematical calculations",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["add", "subtract", "multiply", "divide", "square", "sqrt"],
                                "description": "The operation to perform"
                            },
                            "a": {
                                "type": "number",
                                "description": "First number"
                            },
                            "b": {
                                "type": "number",
                                "description": "Second number (optional for unary operations)"
                            }
                        },
                        "required": ["operation", "a"]
                    }
                },
                {
                    "name": "weather_info",
                    "description": "Get weather information for a location (mock implementation)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The location to get weather for"
                            }
                        },
                        "required": ["location"]
                    }
                },
                {
                    "name": "text_analyzer",
                    "description": "Analyze text and provide statistics",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The text to analyze"
                            }
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "memory_store",
                    "description": "Simple key-value memory store for agents",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["store", "retrieve", "list", "delete"],
                                "description": "Action to perform"
                            },
                            "key": {
                                "type": "string",
                                "description": "Key for store/retrieve/delete operations"
                            },
                            "value": {
                                "type": "string",
                                "description": "Value for store operation"
                            }
                        },
                        "required": ["action"]
                    }
                }
            ]
            return {"tools": tools}
        
        @self.app.post("/mcp/v1/rpc")
        async def handle_rpc(request: MCPRequest):
            """Handle MCP JSON-RPC requests."""
            try:
                if request.method == "tools/list":
                    tools_response = await list_tools()
                    return MCPResponse(
                        id=request.id,
                        result=tools_response
                    )
                
                elif request.method == "tools/call":
                    if not request.params:
                        raise HTTPException(status_code=400, detail="Missing params")
                    
                    tool_name = request.params.get("name")
                    arguments = request.params.get("arguments", {})
                    
                    result = await self._call_tool(tool_name, arguments)
                    
                    return MCPResponse(
                        id=request.id,
                        result={
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result)
                                }
                            ]
                        }
                    )
                
                else:
                    return MCPResponse(
                        id=request.id,
                        error={
                            "code": -32601,
                            "message": f"Method not found: {request.method}"
                        }
                    )
                    
            except Exception as e:
                logger.error(f"Error handling RPC: {e}")
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                )
    
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with the given arguments."""
        
        if tool_name == "calculator":
            return await self._calculator(arguments)
        elif tool_name == "weather_info":
            return await self._weather_info(arguments)
        elif tool_name == "text_analyzer":
            return await self._text_analyzer(arguments)
        elif tool_name == "memory_store":
            return await self._memory_store(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _calculator(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Calculator tool implementation."""
        operation = args.get("operation")
        a = args.get("a")
        b = args.get("b")
        
        try:
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
            
            return {
                "result": result,
                "operation": operation,
                "inputs": {"a": a, "b": b}
            }
            
        except Exception as e:
            return {"error": f"Calculation error: {str(e)}"}
    
    async def _weather_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Weather info tool implementation."""
        location = args.get("location")
        
        return {
            "location": location,
            "temperature": "22°C",
            "condition": "Partly cloudy",
            "humidity": "65%",
            "wind": "10 km/h SW",
            "timestamp": datetime.now().isoformat()
        }
    
    async def _text_analyzer(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Text analyzer tool implementation."""
        text = args.get("text", "")
        
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
    
    async def _memory_store(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Memory store tool implementation."""
        action = args.get("action")
        key = args.get("key")
        value = args.get("value")
        
        try:
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
    
    async def start(self):
        """Start the HTTP MCP server."""
        logger.info(f"Starting MCP HTTP server on {self.host}:{self.port}")
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def run_mcp_http_server(host: str = "0.0.0.0", port: int = 9000):
    """Run the MCP HTTP server."""
    server = MCPHTTPServer(host=host, port=port)
    await server.start()


if __name__ == "__main__":
    asyncio.run(run_mcp_http_server())
