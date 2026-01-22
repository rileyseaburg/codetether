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
from .monitor_api import (
    monitor_router,
    nextauth_router,
    opencode_router,
    voice_router,
    log_agent_message,
    get_opencode_bridge,
)
from .worker_sse import (
    worker_sse_router,
    get_worker_registry,
    notify_workers_of_new_task,
    setup_task_creation_hook,
)

# Import marketing tools
try:
    from .marketing_tools import (
        get_marketing_tools,
        MARKETING_TOOL_HANDLERS,
    )

    MARKETING_TOOLS_AVAILABLE = True
except ImportError:
    MARKETING_TOOLS_AVAILABLE = False
    get_marketing_tools = lambda: []
    MARKETING_TOOL_HANDLERS = {}

# Import user authentication router for self-service signups
try:
    from .user_auth import router as user_auth_router

    USER_AUTH_AVAILABLE = True
except ImportError:
    USER_AUTH_AVAILABLE = False
    user_auth_router = None

# Import queue status API router
try:
    from .queue_api import router as queue_api_router

    QUEUE_API_AVAILABLE = True
except ImportError:
    QUEUE_API_AVAILABLE = False
    queue_api_router = None

# Import task queue for hosted workers
try:
    from .task_queue import enqueue_task, get_task_queue

    TASK_QUEUE_AVAILABLE = True
except ImportError:
    TASK_QUEUE_AVAILABLE = False
    enqueue_task = None
    get_task_queue = None

# Import billing webhook router for Stripe
try:
    from .billing_webhooks import billing_webhook_router

    BILLING_WEBHOOKS_AVAILABLE = True
except ImportError:
    BILLING_WEBHOOKS_AVAILABLE = False
    billing_webhook_router = None

# Import automation API router for Zapier/n8n/Make integrations
try:
    from .automation_api import router as automation_router

    AUTOMATION_API_AVAILABLE = True
except ImportError:
    AUTOMATION_API_AVAILABLE = False
    automation_router = None

logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""

    jsonrpc: str = '2.0'
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""

    jsonrpc: str = '2.0'
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPHTTPServer:
    """HTTP-based MCP server that exposes A2A agent capabilities as MCP tools."""

    def __init__(
        self, host: str = '0.0.0.0', port: int = 9000, a2a_server=None
    ):
        self.host = host
        self.port = port
        self.a2a_server = a2a_server  # Reference to A2A server
        self.app = FastAPI(title='MCP HTTP Server', version='1.0.0')

        # Include the monitor router for UI and monitoring endpoints
        self.app.include_router(monitor_router)

        # Include OpenCode router for worker task management API
        self.app.include_router(opencode_router)

        # Include voice router for voice session management
        self.app.include_router(voice_router)

        # Include NextAuth compatibility routes for Cypress
        self.app.include_router(nextauth_router)

        # Include Worker SSE router for push-based task distribution
        self.app.include_router(worker_sse_router)

        # Include User Auth router for self-service registration (mid-market)
        if USER_AUTH_AVAILABLE and user_auth_router:
            self.app.include_router(user_auth_router)

        # Include Queue API router for operational visibility
        if QUEUE_API_AVAILABLE and queue_api_router:
            self.app.include_router(queue_api_router)

        # Include Billing Webhooks router for Stripe
        if BILLING_WEBHOOKS_AVAILABLE and billing_webhook_router:
            self.app.include_router(billing_webhook_router)

        # Include Automation API router for Zapier/n8n/Make
        if AUTOMATION_API_AVAILABLE and automation_router:
            self.app.include_router(automation_router)

        self._setup_routes()

    def _get_tools_from_a2a_server(self) -> List[Dict[str, Any]]:
        """Extract MCP tools from A2A server capabilities."""
        if not self.a2a_server:
            return self._get_fallback_tools()

        tools = [
            # Core A2A operations exposed as MCP tools
            {
                'name': 'send_message',
                'description': 'Send a message to the A2A agent for processing and receive a response. Returns: success, response text, conversation_id (for threading follow-up messages), and timestamp. Use conversation_id in subsequent calls to maintain context.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'The message to send to the agent',
                        },
                        'conversation_id': {
                            'type': 'string',
                            'description': 'Optional conversation ID for message threading',
                        },
                    },
                    'required': ['message'],
                },
            },
            {
                'name': 'send_message_async',
                'description': 'Send a message asynchronously by creating a task that workers will pick up. Unlike send_message (synchronous), this immediately returns a task_id and run_id, allowing you to poll for results later. Use for long-running operations or when you want fire-and-forget semantics. Returns: task_id, run_id, status, conversation_id.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'The message/prompt for the agent to process',
                        },
                        'conversation_id': {
                            'type': 'string',
                            'description': 'Optional conversation ID for message threading',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Target codebase ID (default: global)',
                        },
                        'priority': {
                            'type': 'integer',
                            'description': 'Priority level (higher = more urgent, default: 0)',
                        },
                        'notify_email': {
                            'type': 'string',
                            'description': 'Email to notify when task completes',
                        },
                        'model_ref': {
                            'type': 'string',
                            'description': 'Normalized model identifier (provider:model format, e.g., "openai:gpt-4.1", "anthropic:claude-3.5-sonnet"). If set, only workers supporting this model can claim the task.',
                        },
                    },
                    'required': ['message'],
                },
            },
            {
                'name': 'send_to_agent',
                'description': 'Send a message to a specific named agent. The task will be queued until that agent is available to claim it. If the agent is offline, the task queues indefinitely (unless deadline_seconds is set). Use discover_agents to find available agent names. Returns: task_id, run_id, target_agent_name, status.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'agent_name': {
                            'type': 'string',
                            'description': 'Name of the target agent (must match agent_name used during worker registration)',
                        },
                        'message': {
                            'type': 'string',
                            'description': 'The message/prompt for the agent to process',
                        },
                        'conversation_id': {
                            'type': 'string',
                            'description': 'Optional conversation ID for message threading',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Target codebase ID (default: global)',
                        },
                        'priority': {
                            'type': 'integer',
                            'description': 'Priority level (higher = more urgent, default: 0)',
                        },
                        'deadline_seconds': {
                            'type': 'integer',
                            'description': 'Optional: fail if not claimed within this many seconds. If not set, task queues indefinitely.',
                        },
                        'notify_email': {
                            'type': 'string',
                            'description': 'Email to notify when task completes',
                        },
                        'model_ref': {
                            'type': 'string',
                            'description': 'Normalized model identifier (provider:model format). If set, only workers supporting this model can claim the task.',
                        },
                    },
                    'required': ['agent_name', 'message'],
                },
            },
            {
                'name': 'create_task',
                'description': "Create a new task in the task queue. Tasks start with 'pending' status and can be picked up by worker agents. Returns: task_id (use with get_task/cancel_task), title, description, status, and created_at timestamp. Task lifecycle: pending → working → completed/failed/cancelled.",
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'title': {
                            'type': 'string',
                            'description': 'Task title',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Detailed task description',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Target codebase ID (default: global)',
                        },
                        'agent_type': {
                            'type': 'string',
                            'enum': ['build', 'plan', 'general', 'explore'],
                            'description': 'Agent type (default: build)',
                        },
                        'model': {
                            'type': 'string',
                            'enum': [
                                'default',
                                'claude-sonnet',
                                'claude-sonnet-4',
                                'sonnet',
                                'claude-opus',
                                'opus',
                                'claude-haiku',
                                'haiku',
                                'minimax',
                                'minimax-m2',
                                'minimax-m2.1',
                                'm2.1',
                                'gpt-4',
                                'gpt-4o',
                                'gpt-4-turbo',
                                'gpt-4.1',
                                'o1',
                                'o1-mini',
                                'o3',
                                'o3-mini',
                                'gemini',
                                'gemini-pro',
                                'gemini-2.5-pro',
                                'gemini-flash',
                                'gemini-2.5-flash',
                                'grok',
                                'grok-3',
                            ],
                            'description': 'Model to use for this task. Use friendly names like "minimax", "claude-sonnet", "gemini" - they are automatically mapped to the correct provider/model-id format.',
                        },
                        'priority': {
                            'type': 'integer',
                            'description': 'Priority level (higher = more urgent, default: 0)',
                        },
                    },
                    'required': ['title'],
                },
            },
            {
                'name': 'get_task',
                'description': 'Get the current status and details of a specific task by its ID. Returns: task_id, title, description, status (pending/working/completed/failed/cancelled), created_at, and updated_at timestamps.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'The ID of the task to retrieve',
                        }
                    },
                    'required': ['task_id'],
                },
            },
            {
                'name': 'list_tasks',
                'description': 'List all tasks in the queue, optionally filtered by status. Returns an array of tasks with their IDs, titles, statuses, and timestamps. Use to monitor queue state or find pending tasks to work on.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'status': {
                            'type': 'string',
                            'enum': [
                                'pending',
                                'working',
                                'completed',
                                'failed',
                                'cancelled',
                            ],
                            'description': 'Filter tasks by status',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Filter by codebase ID',
                        },
                    },
                },
            },
            {
                'name': 'cancel_task',
                'description': "Cancel a task by its ID. Only pending or working tasks can be cancelled. Returns the updated task with status set to 'cancelled'.",
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'task_id': {
                            'type': 'string',
                            'description': 'The ID of the task to cancel',
                        }
                    },
                    'required': ['task_id'],
                },
            },
            {
                'name': 'discover_agents',
                'description': 'List all registered worker agents in the network. Agents must call register_agent to appear here. Returns an array of agents with their name, description, and URL. Use to find available agents before delegating work.',
                'inputSchema': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'get_agent',
                'description': 'Get detailed information about a specific registered agent by name. Returns: name, description, URL, and capabilities (streaming, push_notifications). Use after discover_agents to get full details.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'agent_name': {
                            'type': 'string',
                            'description': 'Name of the agent to retrieve',
                        }
                    },
                    'required': ['agent_name'],
                },
            },
            {
                'name': 'register_agent',
                'description': "Register this agent as a worker in the network so it can be discovered by other agents and receive tasks. Call once on startup. Requires: name (unique identifier), description, url (agent's endpoint). Optional: capabilities object, models_supported list. After registering, the agent will appear in discover_agents results.",
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                            'description': 'Unique name/identifier for this agent',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Human-readable description of what this agent does',
                        },
                        'url': {
                            'type': 'string',
                            'description': 'Base URL where this agent can be reached',
                        },
                        'capabilities': {
                            'type': 'object',
                            'description': 'Optional capabilities: {streaming: boolean, push_notifications: boolean}',
                            'properties': {
                                'streaming': {'type': 'boolean'},
                                'push_notifications': {'type': 'boolean'},
                            },
                        },
                        'models_supported': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'List of model identifiers this agent supports (normalized format: provider:model, e.g., ["anthropic:claude-3.5-sonnet", "openai:gpt-4.1"]). Tasks with model_ref will only route to agents supporting that model.',
                        },
                    },
                    'required': ['name', 'description', 'url'],
                },
            },
            {
                'name': 'get_agent_card',
                'description': "Get this server's agent card containing its identity, capabilities, and skills. Returns: name, description, URL, provider info, capabilities, and list of skills. Useful for understanding what this agent can do.",
                'inputSchema': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'refresh_agent_heartbeat',
                'description': 'Refresh the last_seen timestamp for a registered agent. Call periodically (every 30-60s) to keep the agent visible in discovery. Agents not seen within 120s are filtered from discover_agents results.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'agent_name': {
                            'type': 'string',
                            'description': 'Name of the agent to refresh (must match name used in register_agent)',
                        },
                    },
                    'required': ['agent_name'],
                },
            },
            {
                'name': 'get_messages',
                'description': 'Retrieve conversation history from the monitoring system. Filter by conversation_id to get a specific thread. Returns messages with: id, timestamp, type (human/agent), agent_name, content, and metadata. Use to review past interactions.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'conversation_id': {
                            'type': 'string',
                            'description': 'Filter messages by conversation ID',
                        },
                        'limit': {
                            'type': 'number',
                            'description': 'Maximum number of messages to retrieve (default: 50)',
                        },
                    },
                },
            },
            {
                'name': 'get_task_updates',
                'description': 'Poll for recent task status changes. Filter by since_timestamp (ISO format) to get only new updates, or by specific task_ids. Returns tasks sorted by updated_at descending. Use for monitoring task progress without repeatedly calling get_task.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'since_timestamp': {
                            'type': 'string',
                            'description': 'ISO timestamp to get updates since (optional)',
                        },
                        'task_ids': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'Specific task IDs to check (optional)',
                        },
                    },
                },
            },
            {
                'name': 'search_tools',
                'description': "Search for available tools by keyword or category. Use this FIRST to discover what tools are available without loading all definitions. Returns tool names and brief descriptions matching your query. Categories: 'messaging' (send_message, get_messages), 'tasks' (create_task, get_task, list_tasks, cancel_task, get_task_updates), 'agents' (discover_agents, get_agent, register_agent, get_agent_card). Example: search_tools({query: 'task'}) returns all task-related tools.",
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': "Search keyword (e.g., 'task', 'agent', 'message') or category name",
                        },
                        'detail_level': {
                            'type': 'string',
                            'enum': ['name_only', 'summary', 'full'],
                            'description': "Level of detail: 'name_only' (just names), 'summary' (name + description), 'full' (complete schema). Default: summary",
                        },
                    },
                    'required': ['query'],
                },
            },
            {
                'name': 'get_tool_schema',
                'description': "Get the complete schema for a specific tool by name. Use after search_tools to get full parameter details for a tool you want to use. Returns the tool's inputSchema with all properties, types, and requirements.",
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'tool_name': {
                            'type': 'string',
                            'description': "Exact name of the tool (e.g., 'create_task', 'send_message')",
                        }
                    },
                    'required': ['tool_name'],
                },
            },
        ]

        # Add marketing tools if available
        if MARKETING_TOOLS_AVAILABLE:
            tools.extend(get_marketing_tools())
            logger.info(f'Added {len(get_marketing_tools())} marketing tools')

        return tools

    def _get_fallback_tools(self) -> List[Dict[str, Any]]:
        """Fallback tools when no A2A server is available."""
        fallback = [
            {
                'name': 'echo',
                'description': 'Echo back a message',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'Message to echo',
                        }
                    },
                    'required': ['message'],
                },
            }
        ]

        # Still include marketing tools even without A2A server
        if MARKETING_TOOLS_AVAILABLE:
            fallback.extend(get_marketing_tools())

        return fallback

    def _setup_routes(self):
        """Set up HTTP routes for MCP."""

        @self.app.get('/')
        async def root():
            """Health check endpoint."""
            return {
                'status': 'ok',
                'server': 'MCP HTTP Server',
                'version': '1.0.0',
                'endpoints': {
                    'rpc': '/mcp/v1/rpc',
                    'sse': '/mcp/v1/sse',
                    'message': '/mcp/v1/message',
                    'tools': '/mcp/v1/tools',
                    'health': '/',
                },
            }

        @self.app.get('/mcp/v1/sse')
        async def handle_sse(request: Request):
            """Handle SSE connections for MCP."""

            async def event_generator():
                """Generate SSE events."""
                try:
                    # Send initial connection event with the message endpoint URL
                    # The MCP SDK SSEClientTransport expects the endpoint event data
                    # to be a URL path that it will POST messages to
                    yield f'event: endpoint\ndata: /mcp/v1/message\n\n'

                    # Keep connection alive
                    while True:
                        # Send periodic ping to keep connection alive
                        await asyncio.sleep(30)
                        yield f'event: ping\ndata: {json.dumps({"timestamp": datetime.now().isoformat()})}\n\n'

                except asyncio.CancelledError:
                    logger.info('SSE connection closed')
                    raise
                except Exception as e:
                    logger.error(f'Error in SSE stream: {e}')
                    raise

            return StreamingResponse(
                event_generator(),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                },
            )

        @self.app.get('/mcp')
        async def mcp_root(request: Request):
            """MCP SSE endpoint root - redirects to SSE endpoint."""
            # Check if client accepts SSE
            accept = request.headers.get('accept', '')
            if 'text/event-stream' in accept:
                # Forward to SSE handler
                return await handle_sse(request)
            else:
                # Return info about available endpoints
                return {
                    'jsonrpc': '2.0',
                    'protocol': 'mcp',
                    'version': '1.0.0',
                    'capabilities': {'tools': True, 'sse': True},
                    'endpoints': {
                        'sse': '/mcp/v1/sse',
                        'message': '/mcp/v1/message',
                        'rpc': '/mcp/v1/rpc',
                        'tools': '/mcp/v1/tools',
                    },
                }

        @self.app.post('/mcp')
        async def mcp_post(request: Request):
            """Handle POST messages to /mcp for SSE transport."""
            # Forward to the RPC handler
            return await handle_rpc(request)

        @self.app.get('/mcp/v1/tools')
        async def list_tools():
            """List available MCP tools - exposes A2A agents as tools."""
            # Get tools dynamically from connected A2A server
            tools = self._get_tools_from_a2a_server()
            return {'tools': tools}

        @self.app.post('/mcp/v1/message')
        async def handle_message(request: Request):
            """Handle POST messages from SSE clients."""
            # This handles the same requests as RPC but for SSE clients
            return await handle_rpc(request)

        @self.app.post('/mcp/v1/rpc')
        async def handle_rpc(request: Request):
            """Handle MCP JSON-RPC requests with Streamable HTTP support.

            - Accepts JSON-RPC notifications (no id) -> returns 202 Accepted
            - Accepts JSON-RPC requests -> returns JSON or SSE stream depending on Accept header
            - Basic protocol version header and Origin validation
            """
            try:
                # Validate MCP Protocol header if present
                protocol_version = request.headers.get('mcp-protocol-version')
                if protocol_version and protocol_version not in (
                    '2025-06-18',
                    '2024-11-05',
                    '2025-03-26',
                ):
                    return JSONResponse(
                        {'error': 'Unsupported MCP-Protocol-Version'},
                        status_code=400,
                    )

                # Basic Origin check - allow localhost by default
                origin = request.headers.get('origin')
                if origin and origin not in (
                    'http://localhost',
                    'http://127.0.0.1',
                ):
                    logger.warning(
                        f'Received request from unusual Origin: {origin}'
                    )

                # GET requests: return SSE stream (legacy behavior / convenience)
                if request.method == 'GET':
                    return await handle_sse(request)

                # Read request body and parse JSON-RPC payload
                body_bytes = await request.body()
                if not body_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail='Empty request body - expected JSON-RPC payload',
                    )

                try:
                    payload = json.loads(body_bytes.decode('utf-8'))
                except Exception:
                    raise HTTPException(
                        status_code=400, detail='Invalid JSON in request body'
                    )

                # Detect if client mistakenly sent JSON in URL path
                if (
                    '%7B' in request.url.path
                    or '{"jsonrpc"' in request.url.path
                ):
                    return JSONResponse(
                        {
                            'error': 'Invalid request: JSON appears to be URL-encoded in the path. Use POST with JSON body.'
                        },
                        status_code=400,
                    )

                method = payload.get('method')
                request_id = payload.get('id')
                params = payload.get('params', {}) or {}

                # Notification (no id): process in background and return 202 Accepted
                if request_id is None:
                    asyncio.create_task(
                        self._call_tool_from_payload(method, params)
                    )
                    return JSONResponse(status_code=202, content=None)

                # Handle some predefined MCP methods
                if method == 'initialize':
                    # Return initialization result and prefer new protocol version
                    init_result = {
                        'protocolVersion': '2025-06-18',
                        'capabilities': {'tools': {}},
                        'serverInfo': {
                            'name': 'a2a-server',
                            'version': '0.1.0',
                        },
                    }
                    return JSONResponse(
                        content={
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': init_result,
                        }
                    )

                if method == 'tools/list':
                    tools_response = await list_tools()
                    return JSONResponse(
                        content={
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': tools_response,
                        }
                    )

                # Build JSON-RPC response helper
                # Per JSON-RPC 2.0 spec: response MUST have either result OR error, not both
                def make_response(id_val, result=None, error=None):
                    response = {
                        'jsonrpc': '2.0',
                        'id': id_val,
                    }
                    if error is not None:
                        response['error'] = error
                    else:
                        response['result'] = result
                    return response

                # Per MCP spec: server can choose to respond with JSON or SSE
                # We prefer JSON for simple request/response (more compatible)
                # SSE is only used when client explicitly requests it via query param
                # or when streaming long-running operations
                use_sse = (
                    request.query_params.get('stream', '').lower() == 'true'
                )

                if use_sse:

                    async def event_generator():
                        # Open stream for this request
                        yield f'data: {json.dumps({"type": "connected", "id": request_id})}\n\n'
                        try:
                            if method == 'tools/call':
                                result = await self._call_tool(
                                    params.get('name'),
                                    params.get('arguments', {}),
                                )
                            else:
                                response = make_response(
                                    request_id,
                                    error={
                                        'code': -32601,
                                        'message': f'Method not found: {method}',
                                    },
                                )
                                yield f'data: {json.dumps(response)}\n\n'
                                return
                            response = make_response(request_id, result=result)
                            yield f'data: {json.dumps(response)}\n\n'
                        except Exception as e:
                            response = make_response(
                                request_id,
                                error={'code': -32603, 'message': str(e)},
                            )
                            yield f'data: {json.dumps(response)}\n\n'

                    return StreamingResponse(
                        event_generator(),
                        media_type='text/event-stream',
                        headers={
                            'Cache-Control': 'no-cache',
                            'Connection': 'keep-alive',
                            'X-Accel-Buffering': 'no',
                        },
                    )

                # Default: return single JSON response
                try:
                    if method == 'tools/call':
                        result = await self._call_tool(
                            params.get('name'), params.get('arguments', {})
                        )
                    else:
                        response = make_response(
                            request_id,
                            error={
                                'code': -32601,
                                'message': f'Method not found: {method}',
                            },
                        )
                        return JSONResponse(content=response, status_code=400)
                    response = make_response(request_id, result=result)
                    return JSONResponse(content=response)
                except Exception as e:
                    response = make_response(
                        request_id, error={'code': -32603, 'message': str(e)}
                    )
                    return JSONResponse(content=response, status_code=500)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f'Error handling RPC: {e}')
                return JSONResponse(
                    {
                        'jsonrpc': '2.0',
                        'error': {'code': -32603, 'message': str(e)},
                    },
                    status_code=500,
                )

        # REST API endpoints for task queue (used by monitor UI)
        @self.app.get('/mcp/v1/tasks')
        async def list_tasks_rest(status: Optional[str] = None):
            """REST endpoint to list tasks."""
            try:
                result = await self._list_tasks(
                    {'status': status} if status else {}
                )
                return result
            except Exception as e:
                logger.error(f'Error listing tasks: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post('/mcp/v1/tasks')
        async def create_task_rest(request: Request):
            """REST endpoint to create a task."""
            try:
                body = await request.json()
                result = await self._create_task(body)
                return result
            except Exception as e:
                logger.error(f'Error creating task: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get('/mcp/v1/tasks/{task_id}')
        async def get_task_rest(task_id: str):
            """REST endpoint to get a specific task."""
            try:
                result = await self._get_task({'task_id': task_id})
                if 'error' in result:
                    raise HTTPException(status_code=404, detail=result['error'])
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f'Error getting task: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.put('/mcp/v1/tasks/{task_id}')
        async def update_task_rest(task_id: str, request: Request):
            """REST endpoint to update task status."""
            try:
                body = await request.json()
                new_status = body.get('status')

                if not hasattr(self.a2a_server, 'task_manager'):
                    raise HTTPException(
                        status_code=503, detail='Task manager not available'
                    )

                from .models import TaskStatus

                task = await self.a2a_server.task_manager.update_task_status(
                    task_id, TaskStatus(new_status)
                )

                if not task:
                    raise HTTPException(
                        status_code=404, detail=f'Task {task_id} not found'
                    )

                return {
                    'success': True,
                    'task_id': task.id,
                    'status': task.status.value,
                    'updated_at': task.updated_at.isoformat(),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f'Error updating task: {e}')
                raise HTTPException(status_code=500, detail=str(e))

    async def _call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute A2A operations based on tool name."""
        if not self.a2a_server:
            return {'error': 'No A2A server connected'}

        try:
            if tool_name == 'send_message':
                return await self._send_message(arguments)

            elif tool_name == 'send_message_async':
                return await self._send_message_async(arguments)

            elif tool_name == 'send_to_agent':
                return await self._send_to_agent(arguments)

            elif tool_name == 'create_task':
                return await self._create_task(arguments)

            elif tool_name == 'get_task':
                return await self._get_task(arguments)

            elif tool_name == 'list_tasks':
                return await self._list_tasks(arguments)

            elif tool_name == 'cancel_task':
                return await self._cancel_task(arguments)

            elif tool_name == 'discover_agents':
                return await self._discover_agents()

            elif tool_name == 'get_agent':
                return await self._get_agent(arguments)

            elif tool_name == 'register_agent':
                return await self._register_agent(arguments)

            elif tool_name == 'get_agent_card':
                return await self._get_agent_card()

            elif tool_name == 'refresh_agent_heartbeat':
                return await self._refresh_agent_heartbeat(arguments)

            elif tool_name == 'get_messages':
                return await self._get_messages(arguments)

            elif tool_name == 'get_task_updates':
                return await self._get_task_updates(arguments)

            elif tool_name == 'search_tools':
                return await self._search_tools(arguments)

            elif tool_name == 'get_tool_schema':
                return await self._get_tool_schema(arguments)

            elif tool_name == 'get_queue_stats':
                return await self._get_queue_stats()

            elif tool_name == 'list_task_runs':
                return await self._list_task_runs(arguments)

            # Check if it's a marketing tool
            elif (
                MARKETING_TOOLS_AVAILABLE
                and tool_name in MARKETING_TOOL_HANDLERS
            ):
                handler = MARKETING_TOOL_HANDLERS[tool_name]
                return await handler(arguments)

            else:
                return {'error': f'Unknown tool: {tool_name}'}

        except Exception as e:
            logger.error(f'Error calling tool {tool_name}: {e}', exc_info=True)
            return {'error': f'Tool execution error: {str(e)}'}

    async def _call_tool_from_payload(
        self, method: str, params: Dict[str, Any]
    ) -> None:
        """Execute a tool call-style request from a JSON-RPC payload (used for notifications)."""
        try:
            if not method:
                return
            if method == 'tools/call':
                tool_name = params.get('name')
                arguments = params.get('arguments', {})
                await self._call_tool(tool_name, arguments)
            else:
                # No-op for other MCP methods at this time
                return
        except Exception as exc:
            logger.error(f'Error processing notification {method}: {exc}')

    async def _send_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to the A2A agent."""
        message_text = args.get('message', '')
        conversation_id = args.get('conversation_id') or str(uuid.uuid4())

        # Log to monitoring UI
        await log_agent_message(
            agent_name='MCP Client',
            content=message_text,
            message_type='human',
            metadata={'conversation_id': conversation_id, 'source': 'mcp'},
        )

        # Publish to message broker for UI monitoring
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                'mcp.message.received',
                {
                    'source': 'MCP Client',
                    'message': message_text[:100],
                    'timestamp': datetime.now().isoformat(),
                    'conversation_id': conversation_id,
                },
            )

        # Check if message is asking about tasks
        if any(
            keyword in message_text.lower()
            for keyword in ['task', 'queue', 'status', 'update']
        ):
            # Include task queue information in the response
            if hasattr(self.a2a_server, 'task_manager'):
                tasks = await self.a2a_server.task_manager.list_tasks()
                pending_tasks = [
                    t for t in tasks if t.status.value == 'pending'
                ]
                working_tasks = [
                    t for t in tasks if t.status.value == 'working'
                ]

                task_summary = f'\n\n📋 Task Queue Status:\n'
                task_summary += f'• Pending: {len(pending_tasks)} tasks\n'
                task_summary += f'• Working: {len(working_tasks)} tasks\n'

                if pending_tasks:
                    task_summary += f'\nPending tasks:\n'
                    for task in pending_tasks[:3]:  # Show first 3
                        task_summary += f'  - {task.title} (ID: {task.id})\n'

                if working_tasks:
                    task_summary += f'\nActive tasks:\n'
                    for task in working_tasks[:3]:  # Show first 3
                        task_summary += f'  - {task.title} (ID: {task.id})\n'

                message_text += task_summary

        message = Message(parts=[Part(type='text', content=message_text)])
        response = await self.a2a_server._process_message(message)

        response_text = ' '.join(
            [part.content for part in response.parts if part.type == 'text']
        )

        # Log response to monitoring UI
        await log_agent_message(
            agent_name=self.a2a_server.agent_card.card.name
            if hasattr(self.a2a_server, 'agent_card')
            else 'A2A Agent',
            content=response_text,
            message_type='agent',
            metadata={'conversation_id': conversation_id, 'source': 'a2a'},
        )

        # Publish response to message broker
        if hasattr(self.a2a_server, 'message_broker'):
            await self.a2a_server.message_broker.publish_event(
                'mcp.message.sent',
                {
                    'source': 'A2A Agent',
                    'response': response_text[:100],
                    'timestamp': datetime.now().isoformat(),
                    'conversation_id': conversation_id,
                },
            )

        return {
            'success': True,
            'response': response_text,
            'conversation_id': conversation_id,
            'timestamp': datetime.now().isoformat(),
        }

    async def _send_message_async(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message asynchronously by creating a task and enqueuing it.

        Unlike _send_message (synchronous), this immediately returns a task_id
        and run_id, allowing callers to poll for results later.

        This is the primary entry point for the "fire and forget" flow.
        """
        from .monitor_api import get_opencode_bridge

        message = args.get('message', '')
        conversation_id = args.get('conversation_id') or str(uuid.uuid4())
        codebase_id = args.get('codebase_id', 'global')
        priority = args.get('priority', 0)
        notify_email = args.get('notify_email')
        model_ref = args.get('model_ref')  # Normalized provider:model format

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        # Create a task with the message as the prompt
        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=f'Async message: {message[:50]}...'
            if len(message) > 50
            else f'Async message: {message}',
            prompt=message,
            agent_type='general',
            priority=priority,
            metadata={
                'conversation_id': conversation_id,
                'source': 'send_message_async',
            },
        )

        if task is None:
            return {'error': 'Failed to create task'}

        # Build task data for SSE notification
        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.prompt,
            'codebase_id': task.codebase_id,
            'agent_type': task.agent_type,
            'priority': task.priority,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
        }

        # Notify SSE-connected workers
        try:
            notified = await notify_workers_of_new_task(task_data)
            logger.info(
                f'Async message task {task.id} created, notified {len(notified)} SSE workers'
            )
        except Exception as e:
            logger.warning(
                f'Failed to notify SSE workers of task {task.id}: {e}'
            )

        # Enqueue for hosted workers
        run_id = None
        if TASK_QUEUE_AVAILABLE and enqueue_task:
            try:
                user_id = args.get('_user_id')
                task_run = await enqueue_task(
                    task_id=task.id,
                    user_id=user_id,
                    priority=priority,
                    notify_email=notify_email,
                    model_ref=model_ref,
                )
                if task_run:
                    run_id = task_run.id
                    logger.info(
                        f'Async message task {task.id} enqueued as run {run_id}'
                        + (f' (model_ref={model_ref})' if model_ref else '')
                    )
            except Exception as e:
                logger.warning(f'Failed to enqueue task {task.id}: {e}')

        return {
            'success': True,
            'task_id': task.id,
            'run_id': run_id,
            'status': 'queued',
            'conversation_id': conversation_id,
            'model_ref': model_ref,
            'timestamp': datetime.now().isoformat(),
        }

    async def _send_to_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to a specific named agent.

        The task will be queued until that agent is available to claim it.
        If the agent is offline, the task queues indefinitely unless
        deadline_seconds is set.

        This enables explicit agent-to-agent communication where the caller
        needs work done by a specific agent (not just any available worker).
        """
        from .monitor_api import get_opencode_bridge
        from datetime import timedelta

        agent_name = args.get('agent_name')
        if not agent_name:
            return {'error': 'agent_name is required'}

        message = args.get('message', '')
        conversation_id = args.get('conversation_id') or str(uuid.uuid4())
        codebase_id = args.get('codebase_id', 'global')
        priority = args.get('priority', 0)
        deadline_seconds = args.get('deadline_seconds')
        notify_email = args.get('notify_email')
        model_ref = args.get('model_ref')  # Normalized provider:model format

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        # Create a task with the message as the prompt
        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=f'To {agent_name}: {message[:40]}...'
            if len(message) > 40
            else f'To {agent_name}: {message}',
            prompt=message,
            agent_type='general',
            priority=priority,
            metadata={
                'conversation_id': conversation_id,
                'source': 'send_to_agent',
                'target_agent_name': agent_name,
            },
        )

        if task is None:
            return {'error': 'Failed to create task'}

        # Calculate deadline if specified
        deadline_at = None
        if deadline_seconds:
            from datetime import timezone

            deadline_at = datetime.now(timezone.utc) + timedelta(
                seconds=deadline_seconds
            )

        # Build task data for SSE notification (include routing fields)
        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.prompt,
            'codebase_id': task.codebase_id,
            'agent_type': task.agent_type,
            'priority': task.priority,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
            # Routing fields for notify-time filtering
            'target_agent_name': agent_name,
        }

        # Notify SSE-connected workers (only the targeted agent will be notified)
        try:
            notified = await notify_workers_of_new_task(task_data)
            if notified:
                logger.info(
                    f'Targeted task {task.id} for agent {agent_name}, '
                    f'notified {len(notified)} workers'
                )
            else:
                logger.info(
                    f'Targeted task {task.id} for agent {agent_name}, '
                    f'no matching workers online (will queue)'
                )
        except Exception as e:
            logger.warning(f'Failed to notify workers of task {task.id}: {e}')

        # Enqueue for hosted workers with routing fields
        run_id = None
        if TASK_QUEUE_AVAILABLE and enqueue_task:
            try:
                user_id = args.get('_user_id')
                task_run = await enqueue_task(
                    task_id=task.id,
                    user_id=user_id,
                    priority=priority,
                    notify_email=notify_email,
                    # Agent routing fields
                    target_agent_name=agent_name,
                    deadline_at=deadline_at,
                    # Model routing
                    model_ref=model_ref,
                )
                if task_run:
                    run_id = task_run.id
                    logger.info(
                        f'Targeted task {task.id} enqueued as run {run_id} '
                        f'(target={agent_name}, deadline={deadline_at}'
                        + (f', model_ref={model_ref}' if model_ref else '')
                        + ')'
                    )
            except Exception as e:
                logger.warning(f'Failed to enqueue task {task.id}: {e}')

        # Build routing info for debugging/UX
        routing_info = {
            'target_agent_name': agent_name,
            'required_capabilities': None,  # Not used in send_to_agent currently
            'deadline_at': deadline_at.isoformat() if deadline_at else None,
            'model_ref': model_ref,
        }

        result = {
            'success': True,
            'task_id': task.id,
            'run_id': run_id,
            'status': 'queued',
            'conversation_id': conversation_id,
            'timestamp': datetime.now().isoformat(),
            # Routing info for debugging "why is my job stuck?"
            'routing': routing_info,
        }

        return result

    async def _create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task."""
        from .monitor_api import get_opencode_bridge
        from .opencode_bridge import AgentTaskStatus, resolve_model

        title = args.get('title')
        description = args.get('description', '')
        codebase_id = args.get('codebase_id', 'global')
        agent_type = args.get('agent_type', 'build')
        priority = args.get('priority', 0)
        # Resolve user-friendly model name to full provider/model-id
        model_input = args.get('model')
        model = resolve_model(model_input) if model_input else None

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=title,
            prompt=description,
            agent_type=agent_type,
            priority=priority,
            model=model,
        )

        if task is None:
            return {'error': 'Failed to create task'}

        # Notify SSE-connected workers of the new task
        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.prompt,
            'codebase_id': task.codebase_id,
            'agent_type': task.agent_type,
            'model': task.model,
            'priority': task.priority,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
        }
        try:
            notified = await notify_workers_of_new_task(task_data)
            logger.info(
                f'Task {task.id} created, notified {len(notified)} SSE workers'
            )
        except Exception as e:
            logger.warning(
                f'Failed to notify SSE workers of task {task.id}: {e}'
            )

        # Enqueue for hosted workers (if task queue is available)
        # This enables the mid-market "submit and get email" flow
        run_id = None
        if TASK_QUEUE_AVAILABLE and enqueue_task:
            try:
                # Extract user_id from args if available (set by auth middleware)
                user_id = args.get('_user_id')
                notify_email = args.get('notify_email')
                template_id = args.get('template_id')
                automation_id = args.get('automation_id')

                task_run = await enqueue_task(
                    task_id=task.id,
                    user_id=user_id,
                    template_id=template_id,
                    automation_id=automation_id,
                    priority=priority,
                    notify_email=notify_email,
                )
                if task_run:
                    run_id = task_run.id
                    logger.info(f'Task {task.id} enqueued as run {run_id}')
            except Exception as e:
                logger.warning(f'Failed to enqueue task {task.id}: {e}')

        return {
            'success': True,
            'task_id': task.id,
            'run_id': run_id,  # Include run_id if enqueued
            'title': task.title,
            'description': task.prompt,
            'codebase_id': task.codebase_id,
            'model': task.model,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
        }

    async def _get_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get task details."""
        from .monitor_api import get_opencode_bridge
        from .opencode_bridge import AgentTaskStatus

        task_id = args.get('task_id')

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        task = await bridge.get_task(task_id)

        if not task:
            return {'error': f'Task {task_id} not found'}

        status_value = (
            task.status.value
            if hasattr(task.status, 'value')
            else str(task.status)
        )
        if status_value == 'running':
            status_value = 'working'

        return {
            'task_id': task.id,
            'title': task.title,
            'description': task.prompt or '',
            'codebase_id': task.codebase_id,
            'agent_type': task.agent_type,
            'priority': task.priority,
            'status': status_value,
            'created_at': task.created_at.isoformat()
            if task.created_at
            else None,
            'updated_at': task.created_at.isoformat()
            if task.created_at
            else None,
            'started_at': task.started_at.isoformat()
            if task.started_at
            else None,
            'completed_at': task.completed_at.isoformat()
            if task.completed_at
            else None,
            'result': task.result,
            'error': task.error,
        }

    async def _list_tasks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all tasks."""
        from .monitor_api import get_opencode_bridge
        from .opencode_bridge import AgentTaskStatus

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        codebase_id = args.get('codebase_id')
        status_filter = args.get('status')

        status_map = {
            'pending': AgentTaskStatus.PENDING,
            'working': AgentTaskStatus.RUNNING,
            'completed': AgentTaskStatus.COMPLETED,
            'failed': AgentTaskStatus.FAILED,
            'cancelled': AgentTaskStatus.CANCELLED,
        }
        status_enum = status_map.get(status_filter) if status_filter else None

        tasks = await bridge.list_tasks(
            codebase_id=codebase_id, status=status_enum
        )

        return {
            'tasks': [
                {
                    'task_id': task.id,
                    'title': task.title,
                    'description': task.prompt or '',
                    'status': task.status.value
                    if hasattr(task.status, 'value')
                    else str(task.status),
                    'created_at': task.created_at.isoformat()
                    if task.created_at
                    else None,
                    'updated_at': task.created_at.isoformat()
                    if task.created_at
                    else None,
                }
                for task in tasks
            ],
            'count': len(tasks),
        }

    async def _cancel_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a task."""
        task_id = args.get('task_id')

        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        success = await bridge.cancel_task(task_id)
        if not success:
            return {'error': f'Task {task_id} not found or cannot be cancelled'}

        task = await bridge.get_task(task_id)
        return {
            'success': True,
            'task_id': task_id,
            'status': 'cancelled',
        }

    async def _get_queue_stats(self) -> Dict[str, Any]:
        """Get task queue statistics for hosted workers."""
        if not TASK_QUEUE_AVAILABLE or not get_task_queue:
            return {'error': 'Task queue not available'}

        queue = get_task_queue()
        if not queue:
            return {'error': 'Task queue not initialized'}

        try:
            stats = await queue.get_queue_stats()
            return {
                'success': True,
                'stats': stats,
            }
        except Exception as e:
            return {'error': f'Failed to get queue stats: {str(e)}'}

    async def _list_task_runs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List task runs from the queue."""
        if not TASK_QUEUE_AVAILABLE or not get_task_queue:
            return {'error': 'Task queue not available'}

        queue = get_task_queue()
        if not queue:
            return {'error': 'Task queue not initialized'}

        try:
            user_id = args.get('user_id') or args.get('_user_id')
            status = args.get('status')
            limit = args.get('limit', 100)

            # Convert status string to enum if provided
            status_enum = None
            if status:
                from .task_queue import TaskRunStatus

                try:
                    status_enum = TaskRunStatus(status)
                except ValueError:
                    return {'error': f'Invalid status: {status}'}

            runs = await queue.list_runs(
                user_id=user_id,
                status=status_enum,
                limit=limit,
            )

            return {
                'success': True,
                'runs': [
                    {
                        'id': run.id,
                        'task_id': run.task_id,
                        'user_id': run.user_id,
                        'status': run.status.value,
                        'priority': run.priority,
                        'attempts': run.attempts,
                        'started_at': run.started_at.isoformat()
                        if run.started_at
                        else None,
                        'completed_at': run.completed_at.isoformat()
                        if run.completed_at
                        else None,
                        'runtime_seconds': run.runtime_seconds,
                        'result_summary': run.result_summary,
                        'created_at': run.created_at.isoformat(),
                    }
                    for run in runs
                ],
                'count': len(runs),
            }
        except Exception as e:
            return {'error': f'Failed to list task runs: {str(e)}'}

    async def _discover_agents(self) -> Dict[str, Any]:
        """
        Discover available agents.

        Returns agents with:
        - name: Unique discovery identity (e.g., "code-reviewer:dev-vm:abc123")
        - role: Routing identity for send_to_agent (e.g., "code-reviewer")
        - instance_id: Unique instance identifier
        - description, url, capabilities, last_seen

        Note: Use 'role' with send_to_agent for routing, not 'name'.
        """
        import os

        if not self.a2a_server or not hasattr(
            self.a2a_server, 'message_broker'
        ):
            return {'error': 'Message broker not available'}

        broker = self.a2a_server.message_broker
        if broker is None:
            return {'error': 'Message broker not configured'}

        # Check if broker is started (Redis broker requires this)
        if hasattr(broker, '_running') and not broker._running:
            return {
                'error': 'Message broker not started. Ensure the server is fully initialized.'
            }

        # Get max_age from environment (default 120s)
        max_age_seconds = int(
            os.environ.get('A2A_AGENT_DISCOVERY_MAX_AGE', '120')
        )

        try:
            agents = await broker.discover_agents(
                max_age_seconds=max_age_seconds
            )
        except RuntimeError as e:
            return {'error': f'Message broker error: {str(e)}'}

        # Handle both old (AgentCard) and new (dict) return formats
        agent_list = []
        for agent in agents:
            if isinstance(agent, dict):
                # New enriched format with role/instance_id
                agent_list.append(
                    {
                        'name': agent.get('name'),
                        'role': agent.get(
                            'role'
                        ),  # Use this for send_to_agent routing
                        'instance_id': agent.get('instance_id'),
                        'description': agent.get('description'),
                        'url': agent.get('url'),
                        'capabilities': agent.get('capabilities'),
                        'last_seen': agent.get('last_seen'),
                    }
                )
            else:
                # Legacy AgentCard format (backward compat)
                agent_list.append(
                    {
                        'name': agent.name,
                        'role': agent.name.split(':')[0]
                        if ':' in agent.name
                        else agent.name,
                        'description': agent.description,
                        'url': agent.url,
                    }
                )

        return {
            'agents': agent_list,
            'count': len(agent_list),
            'routing_note': (
                "IMPORTANT: Use 'role' with send_to_agent for routing. "
                "'name' is a unique instance identity and will NOT route tasks. "
                "Example: send_to_agent(agent_name='code-reviewer') routes by role."
            ),
        }

    async def _get_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get specific agent information."""
        agent_name = args.get('agent_name')

        if not self.a2a_server or not hasattr(
            self.a2a_server, 'message_broker'
        ):
            return {'error': 'Message broker not available'}

        broker = self.a2a_server.message_broker
        if broker is None:
            return {'error': 'Message broker not configured'}

        # Check if broker is started (Redis broker requires this)
        if hasattr(broker, '_running') and not broker._running:
            return {
                'error': 'Message broker not started. Ensure the server is fully initialized.'
            }

        try:
            agent = await broker.get_agent(agent_name)
        except RuntimeError as e:
            return {'error': f'Message broker error: {str(e)}'}

        if not agent:
            return {'error': f"Agent '{agent_name}' not found"}

        return {
            'name': agent.name,
            'description': agent.description,
            'url': agent.url,
            'capabilities': {
                'streaming': agent.capabilities.streaming
                if hasattr(agent, 'capabilities')
                else False,
                'push_notifications': agent.capabilities.push_notifications
                if hasattr(agent, 'capabilities')
                else False,
            },
        }

    async def _get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card for this server."""
        if not hasattr(self.a2a_server, 'agent_card'):
            return {'error': 'Agent card not available'}

        card = self.a2a_server.agent_card.card

        return {
            'name': card.name,
            'description': card.description,
            'url': card.url,
            'provider': {
                'organization': card.provider.organization,
                'url': card.provider.url,
            },
            'capabilities': {
                'streaming': card.capabilities.streaming
                if hasattr(card, 'capabilities')
                else False,
                'push_notifications': card.capabilities.push_notifications
                if hasattr(card, 'capabilities')
                else False,
            },
            'skills': [
                {
                    'id': skill.id,
                    'name': skill.name,
                    'description': skill.description,
                }
                for skill in (card.skills if hasattr(card, 'skills') else [])
            ],
        }

    async def _register_agent(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new agent in the network."""
        name = args.get('name')
        description = args.get('description')
        url = args.get('url')
        capabilities = args.get('capabilities', {})
        models_supported = args.get(
            'models_supported'
        )  # List of model identifiers

        if not name:
            return {'error': 'Agent name is required'}
        if not description:
            return {'error': 'Agent description is required'}
        if not url:
            return {'error': 'Agent URL is required'}

        if not self.a2a_server or not hasattr(
            self.a2a_server, 'message_broker'
        ):
            return {'error': 'Message broker not available'}

        broker = self.a2a_server.message_broker
        if broker is None:
            return {'error': 'Message broker not configured'}

        # Check if broker is started (Redis broker requires this)
        if hasattr(broker, '_running') and not broker._running:
            return {
                'error': 'Message broker not started. Ensure the server is fully initialized.'
            }

        from .models import AgentCard, AgentProvider, AgentCapabilities

        # Create agent card
        agent_card = AgentCard(
            name=name,
            description=description,
            url=url,
            provider=AgentProvider(organization='External Agent', url=url),
            capabilities=AgentCapabilities(
                streaming=capabilities.get('streaming', False),
                push_notifications=capabilities.get(
                    'push_notifications', False
                ),
            ),
        )

        try:
            await broker.register_agent(
                agent_card, models_supported=models_supported
            )
        except RuntimeError as e:
            return {'error': f'Message broker error: {str(e)}'}

        # Register with monitoring service for UI tracking
        from .monitor_api import monitoring_service

        agent_id = f'external_{name}'
        await monitoring_service.register_agent(agent_id, name)

        # Log to monitoring
        await log_agent_message(
            agent_name=name,
            content=f"Agent '{name}' registered at {url}",
            message_type='system',
            metadata={'event': 'agent_registered', 'url': url},
        )

        # Publish event (broker is already validated above)
        try:
            await broker.publish_event(
                'mcp.agent.registered',
                {
                    'name': name,
                    'url': url,
                    'timestamp': datetime.now().isoformat(),
                },
            )
        except RuntimeError:
            pass  # Non-critical, continue with registration success

        return {
            'success': True,
            'name': name,
            'description': description,
            'url': url,
            'message': f"Agent '{name}' successfully registered and is now discoverable",
        }

    async def _refresh_agent_heartbeat(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Refresh the last_seen timestamp for an agent to keep it visible in discovery."""
        agent_name = args.get('agent_name')

        if not agent_name:
            return {'error': 'agent_name is required'}

        if not self.a2a_server or not hasattr(
            self.a2a_server, 'message_broker'
        ):
            return {'error': 'Message broker not available'}

        broker = self.a2a_server.message_broker
        if broker is None:
            return {'error': 'Message broker not configured'}

        # Check if broker supports heartbeat refresh
        if not hasattr(broker, 'refresh_agent_heartbeat'):
            return {
                'error': 'Message broker does not support heartbeat refresh'
            }

        try:
            success = await broker.refresh_agent_heartbeat(agent_name)
            if success:
                return {
                    'success': True,
                    'agent_name': agent_name,
                    'message': f"Heartbeat refreshed for agent '{agent_name}'",
                }
            else:
                return {
                    'success': False,
                    'agent_name': agent_name,
                    'message': f"Agent '{agent_name}' not found in registry (register first)",
                }
        except Exception as e:
            return {'error': f'Heartbeat refresh failed: {str(e)}'}

    async def _get_messages(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get messages from the monitoring system."""
        from .monitor_api import monitoring_service

        conversation_id = args.get('conversation_id')
        limit_param = args.get('limit', 50)

        # Ensure limit is an integer with robust conversion
        logger.info(
            f'get_messages called with limit_param: {limit_param} (type: {type(limit_param)})'
        )
        try:
            limit = int(limit_param)
            logger.info(f'Converted limit to: {limit} (type: {type(limit)})')
        except (TypeError, ValueError) as e:
            logger.warning(
                f'Invalid limit parameter: {limit_param}, error: {e}, using default 50'
            )
            limit = 50

        # Get messages from monitoring service
        all_messages = monitoring_service.messages
        logger.info(
            f'Total messages in monitoring service: {len(all_messages)} (type: {type(all_messages)})'
        )

        # Filter by conversation_id if provided
        if conversation_id:
            filtered_messages = [
                msg
                for msg in all_messages
                if msg.metadata.get('conversation_id') == conversation_id
            ]
        else:
            filtered_messages = list(all_messages)  # Convert to list explicitly

        logger.info(
            f'Filtered messages: {len(filtered_messages)} (type: {type(filtered_messages)})'
        )

        # Limit results (ensure limit is positive)
        if limit > 0:
            recent_messages = filtered_messages[-limit:]
            logger.info(f'Recent messages sliced: {len(recent_messages)}')
        else:
            recent_messages = filtered_messages

        return {
            'success': True,
            'messages': [
                {
                    'id': msg.id,
                    'timestamp': msg.timestamp.isoformat(),
                    'type': msg.type,
                    'agent_name': msg.agent_name,
                    'content': msg.content,
                    'metadata': msg.metadata,
                }
                for msg in recent_messages
            ],
            'total': len(recent_messages),
        }

    async def _get_task_updates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent task updates."""
        bridge = get_opencode_bridge()
        if bridge is None:
            return {'error': 'OpenCode bridge not available'}

        since_timestamp = args.get('since_timestamp')
        task_ids = args.get('task_ids', [])

        all_tasks = await bridge.list_tasks()

        if task_ids:
            tasks = [t for t in all_tasks if t.id in task_ids]
        else:
            tasks = all_tasks

        if since_timestamp:
            from datetime import datetime

            cutoff = datetime.fromisoformat(
                since_timestamp.replace('Z', '+00:00')
            )
            tasks = [
                t
                for t in tasks
                if t.created_at > cutoff
                or (t.started_at and t.started_at > cutoff)
                or (t.completed_at and t.completed_at > cutoff)
            ]

        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return {
            'success': True,
            'updates': [
                {
                    'task_id': task.id,
                    'title': task.title,
                    'description': task.prompt,
                    'status': 'working'
                    if task.status.value == 'running'
                    else task.status.value,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.created_at.isoformat(),
                    'codebase_id': task.codebase_id,
                    'agent_type': task.agent_type,
                    'priority': task.priority,
                }
                for task in tasks
            ],
            'total': len(tasks),
        }

    async def _search_tools(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for tools by keyword or category for progressive disclosure.

        This enables LLMs to discover tools on-demand instead of loading all
        definitions upfront, following Anthropic's MCP efficiency recommendations.
        """
        query = args.get('query', '').lower()
        detail_level = args.get('detail_level', 'summary')

        # Define tool categories for efficient discovery
        tool_categories = {
            'messaging': ['send_message', 'get_messages'],
            'tasks': [
                'create_task',
                'get_task',
                'list_tasks',
                'cancel_task',
                'get_task_updates',
            ],
            'agents': [
                'discover_agents',
                'get_agent',
                'register_agent',
                'get_agent_card',
            ],
            'discovery': ['search_tools', 'get_tool_schema'],
            # Spotlessbinco marketing tool categories
            'creative': [
                'spotless_generate_creative',
                'spotless_batch_generate_creatives',
                'spotless_get_top_creatives',
                'spotless_analyze_creative_performance',
            ],
            'campaigns': [
                'spotless_create_campaign',
                'spotless_update_campaign_status',
                'spotless_update_campaign_budget',
                'spotless_get_campaign_metrics',
                'spotless_list_campaigns',
            ],
            'automations': [
                'spotless_create_automation',
                'spotless_trigger_automation',
                'spotless_list_automations',
                'spotless_update_automation_status',
            ],
            'audiences': [
                'spotless_create_geo_audience',
                'spotless_create_lookalike_audience',
                'spotless_create_custom_audience',
                'spotless_get_trash_zone_zips',
            ],
            'analytics': [
                'spotless_get_unified_metrics',
                'spotless_get_roi_metrics',
                'spotless_get_channel_performance',
                'spotless_thompson_sample_budget',
                'spotless_get_conversion_attribution',
            ],
            'platform_sync': [
                'spotless_sync_facebook_metrics',
                'spotless_sync_tiktok_metrics',
                'spotless_sync_google_metrics',
                'spotless_send_facebook_conversion',
                'spotless_send_tiktok_event',
            ],
            # Convenience aliases
            'marketing': [
                'spotless_create_campaign',
                'spotless_generate_creative',
                'spotless_create_automation',
                'spotless_get_unified_metrics',
                'spotless_thompson_sample_budget',
            ],
            'spotless': [
                'spotless_generate_creative',
                'spotless_create_campaign',
                'spotless_create_automation',
                'spotless_create_geo_audience',
                'spotless_get_unified_metrics',
            ],
        }

        # Get all tools
        all_tools = self._get_tools_from_a2a_server()
        tools_by_name = {t['name']: t for t in all_tools}

        matching_tools = []

        # Check if query matches a category
        if query in tool_categories:
            tool_names = tool_categories[query]
            matching_tools = [
                tools_by_name[name]
                for name in tool_names
                if name in tools_by_name
            ]
        else:
            # Search by keyword in name or description
            for tool in all_tools:
                if (
                    query in tool['name'].lower()
                    or query in tool['description'].lower()
                ):
                    matching_tools.append(tool)

        # Format results based on detail level
        if detail_level == 'name_only':
            results = [{'name': t['name']} for t in matching_tools]
        elif detail_level == 'full':
            results = matching_tools
        else:  # summary (default)
            results = [
                {
                    'name': t['name'],
                    'description': t['description'][:200] + '...'
                    if len(t['description']) > 200
                    else t['description'],
                }
                for t in matching_tools
            ]

        return {
            'success': True,
            'tools': results,
            'count': len(results),
            'categories': list(tool_categories.keys()),
            'hint': 'Use get_tool_schema(tool_name) to get full parameter details for a specific tool',
        }

    async def _get_tool_schema(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get the complete schema for a specific tool.

        Enables LLMs to load tool definitions on-demand rather than all upfront,
        reducing context window usage per Anthropic's MCP efficiency recommendations.
        """
        tool_name = args.get('tool_name')

        if not tool_name:
            return {'error': 'tool_name is required'}

        # Get all tools and find the requested one
        all_tools = self._get_tools_from_a2a_server()

        for tool in all_tools:
            if tool['name'] == tool_name:
                # Add usage examples for common workflows
                examples = self._get_tool_examples(tool_name)

                return {
                    'success': True,
                    'tool': tool,
                    'examples': examples,
                    'hint': f'Call this tool with: {tool_name}({{...params}})',
                }

        return {'error': f"Tool '{tool_name}' not found"}

    def _get_tool_examples(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get code examples for efficient tool chaining.

        Provides examples showing how to chain tools efficiently,
        keeping intermediate results in code rather than context.
        """
        examples = {
            'create_task': [
                {
                    'description': 'Create a task and monitor until complete',
                    'code': """
# Create task and poll for completion
result = await create_task(title="Process data", description="Analyze sales data")
task_id = result["task_id"]

# Poll for updates (efficient - only checks changed tasks)
while True:
    updates = await get_task_updates(task_ids=[task_id])
    if updates["updates"][0]["status"] in ["completed", "failed"]:
        break
    await asyncio.sleep(5)
""",
                }
            ],
            'send_message': [
                {
                    'description': 'Send message and continue conversation',
                    'code': """
# Start conversation
resp = await send_message(message="Hello, analyze this data")
conv_id = resp["conversation_id"]

# Continue same conversation thread
resp2 = await send_message(message="Now summarize the results", conversation_id=conv_id)
""",
                }
            ],
            'discover_agents': [
                {
                    'description': 'Find and delegate to a specialized agent',
                    'code': """
# Discover available agents
agents = await discover_agents()

# Find agent with specific capability
for agent in agents["agents"]:
    if "analysis" in agent["description"].lower():
        details = await get_agent(agent_name=agent["name"])
        # Delegate work to this agent...
        break
""",
                }
            ],
            'register_agent': [
                {
                    'description': 'Register as a worker agent on startup',
                    'code': """
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
""",
                }
            ],
            'list_tasks': [
                {
                    'description': 'Process all pending tasks efficiently',
                    'code': """
# Get pending tasks in one call
pending = await list_tasks(status="pending")

# Process in code without returning to model each iteration
for task in pending["tasks"]:
    task_id = task["task_id"]
    # Process task...
    # Update status when done
""",
                }
            ],
        }

        return examples.get(tool_name, [])

    async def start(self):
        """Start the HTTP MCP server."""
        logger.info(f'Starting MCP HTTP server on {self.host}:{self.port}')
        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level='info'
        )
        server = uvicorn.Server(config)
        await server.serve()


async def run_mcp_http_server(
    host: str = '0.0.0.0', port: int = 9000, a2a_server=None
):
    """Run the MCP HTTP server connected to an A2A server."""
    server = MCPHTTPServer(host=host, port=port, a2a_server=a2a_server)
    await server.start()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='MCP HTTP Server')
    parser.add_argument(
        '--port', '-p', type=int, default=9000, help='Port to run on'
    )
    parser.add_argument(
        '--host', '-H', type=str, default='0.0.0.0', help='Host to bind to'
    )
    args = parser.parse_args()
    asyncio.run(run_mcp_http_server(host=args.host, port=args.port))
