"""
HTTP/SSE-based MCP Server for external agent connections.

This allows external agents to connect to the MCP server over HTTP
instead of stdio, enabling distributed agent synchronization.

Integrates with the A2A server to expose actual agent capabilities as MCP tools.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from .models import Message, Part
from .monitor_api import monitor_router, nextauth_router, log_agent_message

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
    """HTTP-based MCP server that exposes A2A agent capabilities as MCP tools."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9000, a2a_server=None):
        self.host = host
        self.port = port
        self.a2a_server = a2a_server  # Reference to A2A server
        self.app = FastAPI(title="MCP HTTP Server", version="1.0.0")

        # Include the monitor router for UI and monitoring endpoints
        self.app.include_router(monitor_router)

        # Include NextAuth compatibility routes for Cypress
        self.app.include_router(nextauth_router)

        self._setup_routes()

    def _get_tools_from_a2a_server(self) -> List[Dict[str, Any]]:
        """Extract MCP tools from A2A server capabilities."""
        if not self.a2a_server:
            return self._get_fallback_tools()

        tools = [
            # Core A2A operations exposed as MCP tools
            {
                "name": "send_message",
                "description": "Send a message to the A2A agent for processing and receive a response. Returns: success, response text, conversation_id (for threading follow-up messages), and timestamp. Use conversation_id in subsequent calls to maintain context.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to send to the agent"
                        },
                        "conversation_id": {
                            "type": "string",
                            "description": "Optional conversation ID for message threading"
                        }
                    },
                    "required": ["message"]
                }
            },
            {
                "name": "create_task",
                "description": "Create a new task in the task queue. Tasks start with 'pending' status and can be picked up by worker agents. Returns: task_id (use with get_task/cancel_task), title, description, status, and created_at timestamp. Task lifecycle: pending → working → completed/failed/cancelled.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Task title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed task description"
                        }
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "get_task",
                "description": "Get the current status and details of a specific task by its ID. Returns: task_id, title, description, status (pending/working/completed/failed/cancelled), created_at, and updated_at timestamps.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task to retrieve"
                        }
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "list_tasks",
                "description": "List all tasks in the queue, optionally filtered by status. Returns an array of tasks with their IDs, titles, statuses, and timestamps. Use to monitor queue state or find pending tasks to work on.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "working", "completed", "failed", "cancelled"],
                            "description": "Filter tasks by status"
                        }
                    }
                }
            },
            {
                "name": "cancel_task",
                "description": "Cancel a task by its ID. Only pending or working tasks can be cancelled. Returns the updated task with status set to 'cancelled'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task to cancel"
                        }
                    },
                    "required": ["task_id"]
                }
            },
            {
                "name": "discover_agents",
                "description": "List all registered worker agents in the network. Agents must call register_agent to appear here. Returns an array of agents with their name, description, and URL. Use to find available agents before delegating work.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_agent",
                "description": "Get detailed information about a specific registered agent by name. Returns: name, description, URL, and capabilities (streaming, push_notifications). Use after discover_agents to get full details.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Name of the agent to retrieve"
                        }
                    },
                    "required": ["agent_name"]
                }
            },
            {
                "name": "register_agent",
                "description": "Register this agent as a worker in the network so it can be discovered by other agents and receive tasks. Call once on startup. Requires: name (unique identifier), description, url (agent's endpoint). Optional: capabilities object. After registering, the agent will appear in discover_agents results.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique name/identifier for this agent"
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable description of what this agent does"
                        },
                        "url": {
                            "type": "string",
                            "description": "Base URL where this agent can be reached"
                        },
                        "capabilities": {
                            "type": "object",
                            "description": "Optional capabilities: {streaming: boolean, push_notifications: boolean}",
                            "properties": {
                                "streaming": {"type": "boolean"},
                                "push_notifications": {"type": "boolean"}
                            }
                        }
                    },
                    "required": ["name", "description", "url"]
                }
            },
            {
                "name": "get_agent_card",
                "description": "Get this server's agent card containing its identity, capabilities, and skills. Returns: name, description, URL, provider info, capabilities, and list of skills. Useful for understanding what this agent can do.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_messages",
                "description": "Retrieve conversation history from the monitoring system. Filter by conversation_id to get a specific thread. Returns messages with: id, timestamp, type (human/agent), agent_name, content, and metadata. Use to review past interactions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Filter messages by conversation ID"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of messages to retrieve (default: 50)"
                        }
                    }
                }
            },
            {
                "name": "get_task_updates",
                "description": "Poll for recent task status changes. Filter by since_timestamp (ISO format) to get only new updates, or by specific task_ids. Returns tasks sorted by updated_at descending. Use for monitoring task progress without repeatedly calling get_task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "since_timestamp": {
                            "type": "string",
                            "description": "ISO timestamp to get updates since (optional)"
                        },
                        "task_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific task IDs to check (optional)"
                        }
                    }
                }
            },
            {
                "name": "search_tools",
                "description": "Search for available tools by keyword or category. Use this FIRST to discover what tools are available without loading all definitions. Returns tool names and brief descriptions matching your query. Categories: 'messaging' (send_message, get_messages), 'tasks' (create_task, get_task, list_tasks, cancel_task, get_task_updates), 'agents' (discover_agents, get_agent, register_agent, get_agent_card). Example: search_tools({query: 'task'}) returns all task-related tools.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword (e.g., 'task', 'agent', 'message') or category name"
                        },
                        "detail_level": {
                            "type": "string",
                            "enum": ["name_only", "summary", "full"],
                            "description": "Level of detail: 'name_only' (just names), 'summary' (name + description), 'full' (complete schema). Default: summary"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_tool_schema",
                "description": "Get the complete schema for a specific tool by name. Use after search_tools to get full parameter details for a tool you want to use. Returns the tool's inputSchema with all properties, types, and requirements.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Exact name of the tool (e.g., 'create_task', 'send_message')"
                        }
                    },
                    "required": ["tool_name"]
                }
            }
        ]

        return tools

    def _get_fallback_tools(self) -> List[Dict[str, Any]]:
        """Fallback tools when no A2A server is available."""
        return [
            {
                "name": "echo",
                "description": "Echo back a message",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to echo"
                        }
                    },
                    "required": ["message"]
                }
            }
        ]

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
                    "sse": "/mcp/v1/sse",
                    "message": "/mcp/v1/message",
                    "tools": "/mcp/v1/tools",
                    "health": "/"
                }
            }

        @self.app.get("/mcp/v1/sse")
        async def handle_sse(request: Request):
            """Handle SSE connections for MCP."""
            async def event_generator():
                """Generate SSE events."""
                try:
                    # Send initial connection event
                    yield f"event: endpoint\ndata: {json.dumps({'jsonrpc': '2.0'})}\n\n"

                    # Keep connection alive
                    while True:
                        # Send periodic ping to keep connection alive
                        await asyncio.sleep(30)
                        yield f"event: ping\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"

                except asyncio.CancelledError:
                    logger.info("SSE connection closed")
                    raise
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    raise

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

        @self.app.get("/mcp")
        async def mcp_root(request: Request):
            """MCP SSE endpoint root - redirects to SSE endpoint."""
            # Check if client accepts SSE
            accept = request.headers.get("accept", "")
            if "text/event-stream" in accept:
                # Forward to SSE handler
                return await handle_sse(request)
            else:
                # Return info about available endpoints
                return {
                    "jsonrpc": "2.0",
                    "protocol": "mcp",
                    "version": "1.0.0",
                    "capabilities": {
                        "tools": True,
                        "sse": True
                    },
                    "endpoints": {
                        "sse": "/mcp/v1/sse",
                        "message": "/mcp/v1/message",
                        "rpc": "/mcp/v1/rpc",
                        "tools": "/mcp/v1/tools"
                    }
                }

        @self.app.post("/mcp")
        async def mcp_post(request: Request):
            """Handle POST messages to /mcp for SSE transport."""
            # Forward to the RPC handler
            return await handle_rpc(request)

        @self.app.get("/mcp/v1/tools")
        async def list_tools():
            """List available MCP tools - exposes A2A agents as tools."""
            # Get tools dynamically from connected A2A server
            tools = self._get_tools_from_a2a_server()
            return {"tools": tools}

        @self.app.post("/mcp/v1/message")
        async def handle_message(request: Request):
            """Handle POST messages from SSE clients."""
            # This handles the same requests as RPC but for SSE clients
            return await handle_rpc(request)

        @self.app.post("/mcp/v1/rpc")
        async def handle_rpc(request: Request):
            """Handle MCP JSON-RPC requests with Streamable HTTP support.

            - Accepts JSON-RPC notifications (no id) -> returns 202 Accepted
            - Accepts JSON-RPC requests -> returns JSON or SSE stream depending on Accept header
            - Basic protocol version header and Origin validation
            """
            try:
                # Validate MCP Protocol header if present
                protocol_version = request.headers.get("mcp-protocol-version")
                if protocol_version and protocol_version not in ("2025-06-18", "2024-11-05", "2025-03-26"):
                    return JSONResponse({"error": "Unsupported MCP-Protocol-Version"}, status_code=400)

                # Basic Origin check - allow localhost by default
                origin = request.headers.get("origin")
                if origin and origin not in ("http://localhost", "http://127.0.0.1"):
                    logger.warning(f"Received request from unusual Origin: {origin}")

                # GET requests: return SSE stream (legacy behavior / convenience)
                if request.method == "GET":
                    return await handle_sse(request)

                # Read request body and parse JSON-RPC payload
                body_bytes = await request.body()
                if not body_bytes:
                    raise HTTPException(status_code=400, detail="Empty request body - expected JSON-RPC payload")

                try:
                    payload = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid JSON in request body")

                # Detect if client mistakenly sent JSON in URL path
                if "%7B" in request.url.path or "{\"jsonrpc\"" in request.url.path:
                    return JSONResponse({"error": "Invalid request: JSON appears to be URL-encoded in the path. Use POST with JSON body."}, status_code=400)

                method = payload.get("method")
                request_id = payload.get("id")
                params = payload.get("params", {}) or {}

                # Notification (no id): process in background and return 202 Accepted
                if request_id is None:
                    asyncio.create_task(self._call_tool_from_payload(method, params))
                    return JSONResponse(status_code=202, content=None)

                # Handle some predefined MCP methods
                if method == "initialize":
                    # Return initialization result and prefer new protocol version
                    init_result = {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "a2a-server",
                            "version": "0.1.0"
                        }
                    }
                    return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": init_result})

                if method == "tools/list":
                    tools_response = await list_tools()
                    return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": tools_response})

                # Build JSON-RPC response helper
                def make_response(id_val, result=None, error=None):
                    return {"jsonrpc": "2.0", "id": id_val, "result": result, "error": error}

                # Accept header determines if client wants SSE
                accept = request.headers.get("accept", "")
                wants_sse = "text/event-stream" in accept.lower()

                if wants_sse:
                    async def event_generator():
                        # Open stream for this request
                        yield f"data: {json.dumps({'type': 'connected', 'id': request_id})}\n\n"
                        try:
                            if method == "tools/call":
                                result = await self._call_tool(params.get("name"), params.get("arguments", {}))
                            else:
                                response = make_response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
                                yield f"data: {json.dumps(response)}\n\n"
                                return
                            response = make_response(request_id, result=result)
                            yield f"data: {json.dumps(response)}\n\n"
                        except Exception as e:
                            response = make_response(request_id, error={"code": -32603, "message": str(e)})
                            yield f"data: {json.dumps(response)}\n\n"

                    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

                # Default: return single JSON response
                try:
                    if method == "tools/call":
                        result = await self._call_tool(params.get("name"), params.get("arguments", {}))
                    else:
                        response = make_response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
                        return JSONResponse(content=response, status_code=400)
                    response = make_response(request_id, result=result)
                    return JSONResponse(content=response)
                except Exception as e:
                    response = make_response(request_id, error={"code": -32603, "message": str(e)})
                    return JSONResponse(content=response, status_code=500)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error handling RPC: {e}")
                return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}, status_code=500)

        # REST API endpoints for task queue (used by monitor UI)
        @self.app.get("/mcp/v1/tasks")
        async def list_tasks_rest(status: Optional[str] = None):
            """REST endpoint to list tasks."""
            try:
                result = await self._list_tasks({"status": status} if status else {})
                return result
            except Exception as e:
                logger.error(f"Error listing tasks: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/v1/tasks")
        async def create_task_rest(request: Request):
            """REST endpoint to create a task."""
            try:
                body = await request.json()
                result = await self._create_task(body)
                return result
            except Exception as e:
                logger.error(f"Error creating task: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/v1/tasks/{task_id}")
        async def get_task_rest(task_id: str):
            """REST endpoint to get a specific task."""
            try:
                result = await self._get_task({"task_id": task_id})
                if "error" in result:
                    raise HTTPException(status_code=404, detail=result["error"])
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting task: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.put("/mcp/v1/tasks/{task_id}")
        async def update_task_rest(task_id: str, request: Request):
            """REST endpoint to update task status."""
            try:
                body = await request.json()
                new_status = body.get("status")

                if not hasattr(self.a2a_server, 'task_manager'):
                    raise HTTPException(status_code=503, detail="Task manager not available")

                from .models import TaskStatus
                task = await self.a2a_server.task_manager.update_task_status(
                    task_id, TaskStatus(new_status)
                )

                if not task:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

                return {
                    "success": True,
                    "task_id": task.id,
                    "status": task.status.value,
                    "updated_at": task.updated_at.isoformat()
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error updating task: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute A2A operations based on tool name."""
        if not self.a2a_server:
            return {"error": "No A2A server connected"}

        try:
            if tool_name == "send_message":
                return await self._send_message(arguments)

            elif tool_name == "create_task":
                return await self._create_task(arguments)

            elif tool_name == "get_task":
                return await self._get_task(arguments)

            elif tool_name == "list_tasks":
                return await self._list_tasks(arguments)

            elif tool_name == "cancel_task":
                return await self._cancel_task(arguments)

            elif tool_name == "discover_agents":
                return await self._discover_agents()

            elif tool_name == "get_agent":
                return await self._get_agent(arguments)

            elif tool_name == "register_agent":
                return await self._register_agent(arguments)

            elif tool_name == "get_agent_card":
                return await self._get_agent_card()

            elif tool_name == "get_messages":
                return await self._get_messages(arguments)

            elif tool_name == "get_task_updates":
                return await self._get_task_updates(arguments)

            elif tool_name == "search_tools":
                return await self._search_tools(arguments)

            elif tool_name == "get_tool_schema":
                return await self._get_tool_schema(arguments)

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            return {"error": f"Tool execution error: {str(e)}"}

    async def _call_tool_from_payload(self, method: str, params: Dict[str, Any]) -> None:
        """Execute a tool call-style request from a JSON-RPC payload (used for notifications)."""
        try:
            if not method:
                return
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                await self._call_tool(tool_name, arguments)
            else:
                # No-op for other MCP methods at this time
                return
        except Exception as exc:
            logger.error(f"Error processing notification {method}: {exc}")

    async def _send_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to the A2A agent."""
        message_text = args.get("message", "")
        conversation_id = args.get("conversation_id") or str(uuid.uuid4())

        # Log to monitoring UI
        await log_agent_message(
            agent_name="MCP Client",
            content=message_text,
            message_type="human",
            metadata={
                "conversation_id": conversation_id,
                "source": "mcp"
            }
        )

        # Publish to message broker for UI monitoring
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                "mcp.message.received",
                {
                    "source": "MCP Client",
                    "message": message_text[:100],
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id
                }
            )

        # Check if message is asking about tasks
        if any(keyword in message_text.lower() for keyword in ['task', 'queue', 'status', 'update']):
            # Include task queue information in the response
            if hasattr(self.a2a_server, 'task_manager'):
                tasks = await self.a2a_server.task_manager.list_tasks()
                pending_tasks = [t for t in tasks if t.status.value == 'pending']
                working_tasks = [t for t in tasks if t.status.value == 'working']

                task_summary = f"\n\n📋 Task Queue Status:\n"
                task_summary += f"• Pending: {len(pending_tasks)} tasks\n"
                task_summary += f"• Working: {len(working_tasks)} tasks\n"

                if pending_tasks:
                    task_summary += f"\nPending tasks:\n"
                    for task in pending_tasks[:3]:  # Show first 3
                        task_summary += f"  - {task.title} (ID: {task.id})\n"

                if working_tasks:
                    task_summary += f"\nActive tasks:\n"
                    for task in working_tasks[:3]:  # Show first 3
                        task_summary += f"  - {task.title} (ID: {task.id})\n"

                message_text += task_summary

        message = Message(parts=[Part(type="text", content=message_text)])
        response = await self.a2a_server._process_message(message)

        response_text = " ".join([
            part.content for part in response.parts if part.type == "text"
        ])

        # Log response to monitoring UI
        await log_agent_message(
            agent_name=self.a2a_server.agent_card.card.name if hasattr(self.a2a_server, 'agent_card') else "A2A Agent",
            content=response_text,
            message_type="agent",
            metadata={
                "conversation_id": conversation_id,
                "source": "a2a"
            }
        )

        # Publish response to message broker
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                "mcp.message.sent",
                {
                    "source": "A2A Agent",
                    "response": response_text[:100],
                    "timestamp": datetime.now().isoformat(),
                    "conversation_id": conversation_id
                }
            )

        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat()
        }

    async def _create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task."""
        title = args.get("title")
        description = args.get("description", "")

        if not hasattr(self.a2a_server, 'task_manager'):
            return {"error": "Task manager not available"}

        task = await self.a2a_server.task_manager.create_task(
            title=title,
            description=description
        )

        # Publish to message broker for UI monitoring
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                "mcp.task.created",
                {
                    "task_id": task.id,
                    "title": title,
                    "status": task.status.value,
                    "timestamp": datetime.now().isoformat()
                }
            )

        return {
            "success": True,
            "task_id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "created_at": task.created_at.isoformat()
        }

    async def _get_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get task details."""
        task_id = args.get("task_id")

        if not hasattr(self.a2a_server, 'task_manager'):
            return {"error": "Task manager not available"}

        task = await self.a2a_server.task_manager.get_task(task_id)

        if not task:
            return {"error": f"Task {task_id} not found"}

        return {
            "task_id": task.id,
            "title": task.title,
            "description": task.description or "",
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }

    async def _list_tasks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all tasks."""
        if not hasattr(self.a2a_server, 'task_manager'):
            return {"error": "Task manager not available"}

        status_filter = args.get("status")
        from .models import TaskStatus

        status = TaskStatus(status_filter) if status_filter else None
        tasks = await self.a2a_server.task_manager.list_tasks(status)

        return {
            "tasks": [
                {
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description or "",
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                }
                for task in tasks
            ],
            "count": len(tasks)
        }

    async def _cancel_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a task."""
        task_id = args.get("task_id")

        if not hasattr(self.a2a_server, 'task_manager'):
            return {"error": "Task manager not available"}

        task = await self.a2a_server.task_manager.cancel_task(task_id)

        if not task:
            return {"error": f"Task {task_id} not found"}

        return {
            "success": True,
            "task_id": task.id,
            "status": task.status.value
        }

    async def _discover_agents(self) -> Dict[str, Any]:
        """Discover available agents."""
        if not hasattr(self.a2a_server, 'message_broker'):
            return {"error": "Message broker not available"}

        agents = await self.a2a_server.message_broker.discover_agents()

        return {
            "agents": [
                {
                    "name": agent.name,
                    "description": agent.description,
                    "url": agent.url
                }
                for agent in agents
            ],
            "count": len(agents)
        }

    async def _get_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific agent information."""
        agent_name = args.get("agent_name")

        if not hasattr(self.a2a_server, 'message_broker'):
            return {"error": "Message broker not available"}

        agent = await self.a2a_server.message_broker.get_agent(agent_name)

        if not agent:
            return {"error": f"Agent '{agent_name}' not found"}

        return {
            "name": agent.name,
            "description": agent.description,
            "url": agent.url,
            "capabilities": {
                "streaming": agent.capabilities.streaming if hasattr(agent, 'capabilities') else False,
                "push_notifications": agent.capabilities.push_notifications if hasattr(agent, 'capabilities') else False
            }
        }

    async def _get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card for this server."""
        if not hasattr(self.a2a_server, 'agent_card'):
            return {"error": "Agent card not available"}

        card = self.a2a_server.agent_card.card

        return {
            "name": card.name,
            "description": card.description,
            "url": card.url,
            "provider": {
                "organization": card.provider.organization,
                "url": card.provider.url
            },
            "capabilities": {
                "streaming": card.capabilities.streaming if hasattr(card, 'capabilities') else False,
                "push_notifications": card.capabilities.push_notifications if hasattr(card, 'capabilities') else False
            },
            "skills": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description
                }
                for skill in (card.skills if hasattr(card, 'skills') else [])
            ]
        }

    async def _register_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new agent in the network."""
        name = args.get("name")
        description = args.get("description")
        url = args.get("url")
        capabilities = args.get("capabilities", {})

        if not name:
            return {"error": "Agent name is required"}
        if not description:
            return {"error": "Agent description is required"}
        if not url:
            return {"error": "Agent URL is required"}

        if not hasattr(self.a2a_server, 'message_broker'):
            return {"error": "Message broker not available"}

        from .models import AgentCard, AgentProvider, AgentCapabilities

        # Create agent card
        agent_card = AgentCard(
            name=name,
            description=description,
            url=url,
            provider=AgentProvider(
                organization="External Agent",
                url=url
            ),
            capabilities=AgentCapabilities(
                streaming=capabilities.get("streaming", False),
                push_notifications=capabilities.get("push_notifications", False)
            )
        )

        await self.a2a_server.message_broker.register_agent(agent_card)

        # Register with monitoring service for UI tracking
        from .monitor_api import monitoring_service
        agent_id = f"external_{name}"
        await monitoring_service.register_agent(agent_id, name)

        # Log to monitoring
        await log_agent_message(
            agent_name=name,
            content=f"Agent '{name}' registered at {url}",
            message_type="system",
            metadata={"event": "agent_registered", "url": url}
        )

        # Publish event
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                "mcp.agent.registered",
                {
                    "name": name,
                    "url": url,
                    "timestamp": datetime.now().isoformat()
                }
            )

        return {
            "success": True,
            "name": name,
            "description": description,
            "url": url,
            "message": f"Agent '{name}' successfully registered and is now discoverable"
        }

    async def _get_messages(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get messages from the monitoring system."""
        from .monitor_api import monitoring_service

        conversation_id = args.get("conversation_id")
        limit_param = args.get("limit", 50)

        # Ensure limit is an integer with robust conversion
        logger.info(f"get_messages called with limit_param: {limit_param} (type: {type(limit_param)})")
        try:
            limit = int(limit_param)
            logger.info(f"Converted limit to: {limit} (type: {type(limit)})")
        except (TypeError, ValueError) as e:
            logger.warning(f"Invalid limit parameter: {limit_param}, error: {e}, using default 50")
            limit = 50

        # Get messages from monitoring service
        all_messages = monitoring_service.messages
        logger.info(f"Total messages in monitoring service: {len(all_messages)} (type: {type(all_messages)})")

        # Filter by conversation_id if provided
        if conversation_id:
            filtered_messages = [
                msg for msg in all_messages
                if msg.metadata.get("conversation_id") == conversation_id
            ]
        else:
            filtered_messages = list(all_messages)  # Convert to list explicitly

        logger.info(f"Filtered messages: {len(filtered_messages)} (type: {type(filtered_messages)})")

        # Limit results (ensure limit is positive)
        if limit > 0:
            recent_messages = filtered_messages[-limit:]
            logger.info(f"Recent messages sliced: {len(recent_messages)}")
        else:
            recent_messages = filtered_messages

        return {
            "success": True,
            "messages": [
                {
                    "id": msg.id,
                    "timestamp": msg.timestamp.isoformat(),
                    "type": msg.type,
                    "agent_name": msg.agent_name,
                    "content": msg.content,
                    "metadata": msg.metadata
                }
                for msg in recent_messages
            ],
            "total": len(recent_messages)
        }

    async def _get_task_updates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent task updates."""
        if not hasattr(self.a2a_server, 'task_manager'):
            return {"error": "Task manager not available"}

        since_timestamp = args.get("since_timestamp")
        task_ids = args.get("task_ids", [])

        # Get all tasks
        all_tasks = await self.a2a_server.task_manager.list_tasks()

        # Filter by task_ids if provided
        if task_ids:
            tasks = [t for t in all_tasks if t.id in task_ids]
        else:
            tasks = all_tasks

        # Filter by timestamp if provided
        if since_timestamp:
            from datetime import datetime
            cutoff = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
            tasks = [t for t in tasks if t.updated_at > cutoff]

        # Sort by updated_at descending
        tasks.sort(key=lambda t: t.updated_at, reverse=True)

        return {
            "success": True,
            "updates": [
                {
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description or "",
                    "status": task.status.value,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                }
                for task in tasks
            ],
            "total": len(tasks)
        }

    async def _search_tools(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for tools by keyword or category for progressive disclosure.

        This enables LLMs to discover tools on-demand instead of loading all
        definitions upfront, following Anthropic's MCP efficiency recommendations.
        """
        query = args.get("query", "").lower()
        detail_level = args.get("detail_level", "summary")

        # Define tool categories for efficient discovery
        tool_categories = {
            "messaging": ["send_message", "get_messages"],
            "tasks": ["create_task", "get_task", "list_tasks", "cancel_task", "get_task_updates"],
            "agents": ["discover_agents", "get_agent", "register_agent", "get_agent_card"],
            "discovery": ["search_tools", "get_tool_schema"]
        }

        # Get all tools
        all_tools = self._get_tools_from_a2a_server()
        tools_by_name = {t["name"]: t for t in all_tools}

        matching_tools = []

        # Check if query matches a category
        if query in tool_categories:
            tool_names = tool_categories[query]
            matching_tools = [tools_by_name[name] for name in tool_names if name in tools_by_name]
        else:
            # Search by keyword in name or description
            for tool in all_tools:
                if query in tool["name"].lower() or query in tool["description"].lower():
                    matching_tools.append(tool)

        # Format results based on detail level
        if detail_level == "name_only":
            results = [{"name": t["name"]} for t in matching_tools]
        elif detail_level == "full":
            results = matching_tools
        else:  # summary (default)
            results = [
                {
                    "name": t["name"],
                    "description": t["description"][:200] + "..." if len(t["description"]) > 200 else t["description"]
                }
                for t in matching_tools
            ]

        return {
            "success": True,
            "tools": results,
            "count": len(results),
            "categories": list(tool_categories.keys()),
            "hint": "Use get_tool_schema(tool_name) to get full parameter details for a specific tool"
        }

    async def _get_tool_schema(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get the complete schema for a specific tool.

        Enables LLMs to load tool definitions on-demand rather than all upfront,
        reducing context window usage per Anthropic's MCP efficiency recommendations.
        """
        tool_name = args.get("tool_name")

        if not tool_name:
            return {"error": "tool_name is required"}

        # Get all tools and find the requested one
        all_tools = self._get_tools_from_a2a_server()

        for tool in all_tools:
            if tool["name"] == tool_name:
                # Add usage examples for common workflows
                examples = self._get_tool_examples(tool_name)

                return {
                    "success": True,
                    "tool": tool,
                    "examples": examples,
                    "hint": f"Call this tool with: {tool_name}({{...params}})"
                }

        return {"error": f"Tool '{tool_name}' not found"}

    def _get_tool_examples(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get code examples for efficient tool chaining.

        Provides examples showing how to chain tools efficiently,
        keeping intermediate results in code rather than context.
        """
        examples = {
            "create_task": [
                {
                    "description": "Create a task and monitor until complete",
                    "code": """
# Create task and poll for completion
result = await create_task(title="Process data", description="Analyze sales data")
task_id = result["task_id"]

# Poll for updates (efficient - only checks changed tasks)
while True:
    updates = await get_task_updates(task_ids=[task_id])
    if updates["updates"][0]["status"] in ["completed", "failed"]:
        break
    await asyncio.sleep(5)
"""
                }
            ],
            "send_message": [
                {
                    "description": "Send message and continue conversation",
                    "code": """
# Start conversation
resp = await send_message(message="Hello, analyze this data")
conv_id = resp["conversation_id"]

# Continue same conversation thread
resp2 = await send_message(message="Now summarize the results", conversation_id=conv_id)
"""
                }
            ],
            "discover_agents": [
                {
                    "description": "Find and delegate to a specialized agent",
                    "code": """
# Discover available agents
agents = await discover_agents()

# Find agent with specific capability
for agent in agents["agents"]:
    if "analysis" in agent["description"].lower():
        details = await get_agent(agent_name=agent["name"])
        # Delegate work to this agent...
        break
"""
                }
            ],
            "register_agent": [
                {
                    "description": "Register as a worker agent on startup",
                    "code": """
# Register this agent to receive tasks
await register_agent(
    name="data-processor",
    description="Processes and analyzes data files",
    url="http://localhost:8001"
)

# Now poll for pending tasks
while True:
    tasks = await list_tasks(status="pending")
    if tasks["count"] > 0:
        # Claim and process first task...
        break
    await asyncio.sleep(5)
"""
                }
            ],
            "list_tasks": [
                {
                    "description": "Process all pending tasks efficiently",
                    "code": """
# Get pending tasks in one call
pending = await list_tasks(status="pending")

# Process in code without returning to model each iteration
for task in pending["tasks"]:
    task_id = task["task_id"]
    # Process task...
    # Update status when done
"""
                }
            ]
        }

        return examples.get(tool_name, [])

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


async def run_mcp_http_server(host: str = "0.0.0.0", port: int = 9000, a2a_server=None):
    """Run the MCP HTTP server connected to an A2A server."""
    server = MCPHTTPServer(host=host, port=port, a2a_server=a2a_server)
    await server.start()


if __name__ == "__main__":
    asyncio.run(run_mcp_http_server())
