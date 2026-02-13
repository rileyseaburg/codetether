"""
HTTP/SSE-based MCP Server for external agent connections.

This allows external agents to connect to the MCP server over HTTP
instead of stdio, enabling distributed agent synchronization.

Integrates with the A2A server to expose actual agent capabilities as MCP tools.
"""

import asyncio
import json
import logging
import os
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
    agent_router,
    opencode_router,  # backward-compat alias
    voice_router,
    log_agent_message,
    get_agent_bridge,
    get_opencode_bridge,  # backward-compat alias → same as get_agent_bridge
)
from .worker_sse import (
    worker_sse_router,
    get_worker_registry,
    notify_workers_of_new_task,
    setup_task_creation_hook,
)
from .task_orchestration import orchestrate_task_route

logger = logging.getLogger(__name__)

# Import marketing tools (disabled by default - these call external Spotless Bin Co APIs)
# Enable with MARKETING_TOOLS_ENABLED=true if running the Spotless backend
MARKETING_TOOLS_ENABLED = (
    os.environ.get('MARKETING_TOOLS_ENABLED', 'false').lower() == 'true'
)

if MARKETING_TOOLS_ENABLED:
    try:
        from .marketing_tools import (
            get_marketing_tools,
            MARKETING_TOOL_HANDLERS,
        )

        MARKETING_TOOLS_AVAILABLE = True
        logger.info('Marketing tools enabled (MARKETING_TOOLS_ENABLED=true)')
    except ImportError:
        MARKETING_TOOLS_AVAILABLE = False
        get_marketing_tools = lambda: []
        MARKETING_TOOL_HANDLERS = {}
        logger.warning('Marketing tools requested but import failed')
else:
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

# Import OAuth 2.1 provider for MCP protocol compliance
try:
    from .oauth_provider import router as oauth_router

    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False
    oauth_router = None

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

    # Session state storage for active codebase per session
    _session_codebases: Dict[str, str] = {}  # session_id -> codebase_id
    _default_codebase_id: Optional[str] = None  # Global default if no session

    def __init__(
        self, host: str = '0.0.0.0', port: int = 9000, a2a_server=None
    ):
        self.host = host
        self.port = port
        self.a2a_server = a2a_server  # Reference to A2A server
        self.app = FastAPI(title='MCP HTTP Server', version='1.0.0')

        # Include the monitor router for UI and monitoring endpoints
        self.app.include_router(monitor_router)

        # Include agent router for worker task management API (/v1/agent/*)
        self.app.include_router(agent_router)

        # Include voice router for voice session management
        self.app.include_router(voice_router)

        # Include NextAuth compatibility routes for Cypress
        self.app.include_router(nextauth_router)

        # Include Worker SSE router for push-based task distribution
        self.app.include_router(worker_sse_router)

        # Include User Auth router for self-service registration (mid-market)
        if USER_AUTH_AVAILABLE and user_auth_router:
            self.app.include_router(user_auth_router)

        # Include OAuth 2.1 provider for MCP protocol compliance
        if OAUTH_AVAILABLE and oauth_router:
            self.app.include_router(oauth_router)

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
        """Get MCP tools for A2A operations.

        These tools work regardless of whether an A2A server instance is passed -
        they call the A2A REST API (configured via A2A_SERVER_URL env var).
        """
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
                        'model': {
                            'type': 'string',
                            'description': 'Optional model selector (friendly name or provider/model). If both model and model_ref are provided, model_ref wins.',
                        },
                        'model_ref': {
                            'type': 'string',
                            'description': 'Normalized model identifier (provider:model format, e.g., "openai:gpt-4.1", "anthropic:claude-3.5-sonnet"). If set, only workers supporting this model can claim the task.',
                        },
                        'worker_personality': {
                            'type': 'string',
                            'description': 'Optional worker personality/profile (e.g., "reviewer", "builder"). Routing policy may map this to target agent/model preferences.',
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
                        'model': {
                            'type': 'string',
                            'description': 'Optional model selector (friendly name or provider/model). If both model and model_ref are provided, model_ref wins.',
                        },
                        'model_ref': {
                            'type': 'string',
                            'description': 'Normalized model identifier (provider:model format). If set, only workers supporting this model can claim the task.',
                        },
                        'worker_personality': {
                            'type': 'string',
                            'description': 'Optional worker personality/profile for orchestration policy routing.',
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
                                'claude-opus-4-6',
                                'opus',
                                'claude-haiku',
                                'haiku',
                                'minimax',
                                'minimax-m2',
                                'minimax-m2.1',
                                'm2.1',
                                'gpt-5.2',
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
                                'gemini-3-pro',
                                'gemini-2.5-pro',
                                'gemini-flash',
                                'gemini-2.5-flash',
                                'grok',
                                'grok-3',
                            ],
                            'description': 'Model to use for this task. Use friendly names like "minimax", "claude-sonnet", "gemini" - they are automatically mapped to the correct provider/model-id format.',
                        },
                        'model_ref': {
                            'type': 'string',
                            'description': 'Normalized model identifier (provider:model). Takes precedence over model when both are provided.',
                        },
                        'worker_personality': {
                            'type': 'string',
                            'description': 'Optional worker personality/profile for orchestration policy routing.',
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
            {
                'name': 'get_current_codebase',
                'description': "Get the current codebase context. Returns codebase_id, name, and path for the codebase this MCP server is connected to. Use this to get the correct codebase_id for task creation. If no specific codebase is set, returns the default 'global' codebase info.",
                'inputSchema': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'list_codebases',
                'description': 'List all registered codebases. Returns array of codebases with id, name, path, worker_id, and status. Use this to find valid codebase_id values for targeting tasks.',
                'inputSchema': {'type': 'object', 'properties': {}},
            },
            {
                'name': 'create_codebase',
                'description': 'Register a new codebase for agent work. The codebase path must exist on the worker machine. If worker_id is provided, registration is immediate. Otherwise, a task is created for workers to validate and register.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                            'description': 'Human-readable name for the codebase (e.g., "marketing-site", "api-server")',
                        },
                        'path': {
                            'type': 'string',
                            'description': 'Absolute path to the codebase directory (e.g., "/home/user/projects/my-app")',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Optional description of the codebase',
                        },
                        'worker_id': {
                            'type': 'string',
                            'description': 'Optional worker ID for immediate registration (skip validation task)',
                        },
                    },
                    'required': ['name', 'path'],
                },
            },
            {
                'name': 'get_codebase',
                'description': 'Get detailed information about a specific codebase by ID.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'codebase_id': {
                            'type': 'string',
                            'description': 'The codebase ID to retrieve',
                        },
                    },
                    'required': ['codebase_id'],
                },
            },
            {
                'name': 'delete_codebase',
                'description': 'Unregister a codebase. This removes it from the system but does not delete any files.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'codebase_id': {
                            'type': 'string',
                            'description': 'The codebase ID to delete',
                        },
                    },
                    'required': ['codebase_id'],
                },
            },
            {
                'name': 'set_active_codebase',
                'description': 'Set the active/default codebase for this session. Subsequent ralph_create_run and task operations will use this codebase automatically if no codebase_id is specified.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'codebase_id': {
                            'type': 'string',
                            'description': 'The codebase ID to set as active (use list_codebases to find IDs)',
                        },
                    },
                    'required': ['codebase_id'],
                },
            },
            {
                'name': 'get_active_codebase',
                'description': 'Get the currently active codebase for this session.',
                'inputSchema': {'type': 'object', 'properties': {}},
            },
            # Ralph (PRD-driven development) tools
            {
                'name': 'ralph_create_run',
                'description': 'Start a Ralph run to implement a PRD (Product Requirements Document). Ralph autonomously implements user stories by iterating until all stories are complete. Returns run_id for tracking progress.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project': {
                            'type': 'string',
                            'description': 'Project name (e.g., "User Authentication System")',
                        },
                        'branch_name': {
                            'type': 'string',
                            'description': 'Git branch name for the implementation (e.g., "feature/user-auth")',
                        },
                        'description': {
                            'type': 'string',
                            'description': 'High-level description of what to build',
                        },
                        'user_stories': {
                            'type': 'array',
                            'description': 'List of user stories to implement',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'id': {
                                        'type': 'string',
                                        'description': 'Unique story ID (e.g., "US-001")',
                                    },
                                    'title': {
                                        'type': 'string',
                                        'description': 'Story title',
                                    },
                                    'description': {
                                        'type': 'string',
                                        'description': 'Detailed description',
                                    },
                                    'acceptance_criteria': {
                                        'type': 'array',
                                        'items': {'type': 'string'},
                                        'description': 'List of acceptance criteria',
                                    },
                                },
                                'required': ['id', 'title', 'description'],
                            },
                        },
                        'max_iterations': {
                            'type': 'integer',
                            'description': 'Maximum iterations before stopping (default: 10)',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Target codebase ID (use list_codebases to find valid IDs)',
                        },
                    },
                    'required': ['project', 'branch_name', 'user_stories'],
                },
            },
            {
                'name': 'ralph_get_run',
                'description': 'Get the status and details of a Ralph run. Returns current status, completed stories, and iteration count.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'run_id': {
                            'type': 'string',
                            'description': 'The Ralph run ID to check',
                        },
                    },
                    'required': ['run_id'],
                },
            },
            {
                'name': 'ralph_list_runs',
                'description': 'List all Ralph runs, optionally filtered by status. Returns run summaries with progress information.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'status': {
                            'type': 'string',
                            'enum': [
                                'pending',
                                'running',
                                'completed',
                                'failed',
                                'cancelled',
                            ],
                            'description': 'Filter by status (optional)',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Max number of runs to return (default: 20)',
                        },
                    },
                },
            },
            {
                'name': 'ralph_cancel_run',
                'description': 'Cancel a running Ralph run. The run will stop after the current iteration completes.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'run_id': {
                            'type': 'string',
                            'description': 'The Ralph run ID to cancel',
                        },
                    },
                    'required': ['run_id'],
                },
            },
            # PRD Chat tools
            {
                'name': 'prd_chat',
                'description': 'Chat with AI to generate a PRD (Product Requirements Document). Describe your project and the AI will help create structured user stories. Use conversation_id to continue a conversation.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'message': {
                            'type': 'string',
                            'description': 'Your message describing the project or answering AI questions',
                        },
                        'conversation_id': {
                            'type': 'string',
                            'description': 'Conversation ID to continue an existing PRD chat session',
                        },
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Target codebase ID for the PRD',
                        },
                    },
                    'required': ['message'],
                },
            },
            {
                'name': 'prd_list_sessions',
                'description': 'List PRD chat sessions for a codebase. Use to find and continue previous PRD conversations.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'codebase_id': {
                            'type': 'string',
                            'description': 'Codebase ID to list sessions for',
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Max sessions to return (default: 20)',
                        },
                    },
                },
            },
            # Model discovery tool
            {
                'name': 'list_models',
                'description': 'List all available AI models from registered workers. Returns models grouped by provider with worker availability info. Use this to discover which models you can select for tasks and runs. Each model includes its provider, friendly name, and which workers support it.',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'provider': {
                            'type': 'string',
                            'description': 'Filter models by provider (e.g., "openrouter", "google", "anthropic"). Omit to list all providers.',
                        },
                        'search': {
                            'type': 'string',
                            'description': 'Search/filter models by name (case-insensitive substring match)',
                        },
                    },
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
        """Execute A2A operations based on tool name.

        Tools work by calling the agent bridge or REST APIs directly,
        not requiring an in-process A2A server reference.
        """
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

            elif tool_name == 'get_current_codebase':
                return await self._get_current_codebase()

            elif tool_name == 'list_codebases':
                return await self._list_codebases()

            elif tool_name == 'create_codebase':
                return await self._create_codebase(arguments)

            elif tool_name == 'get_codebase':
                return await self._get_codebase(arguments)

            elif tool_name == 'delete_codebase':
                return await self._delete_codebase(arguments)

            elif tool_name == 'set_active_codebase':
                return await self._set_active_codebase(arguments)

            elif tool_name == 'get_active_codebase':
                return await self._get_active_codebase()

            # Ralph (PRD-driven development) tools
            elif tool_name == 'ralph_create_run':
                return await self._ralph_create_run(arguments)

            elif tool_name == 'ralph_get_run':
                return await self._ralph_get_run(arguments)

            elif tool_name == 'ralph_list_runs':
                return await self._ralph_list_runs(arguments)

            elif tool_name == 'ralph_cancel_run':
                return await self._ralph_cancel_run(arguments)

            # PRD Chat tools
            elif tool_name == 'prd_chat':
                return await self._prd_chat(arguments)

            elif tool_name == 'prd_list_sessions':
                return await self._prd_list_sessions(arguments)

            elif tool_name == 'list_models':
                return await self._list_models(arguments)

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
            [part.text for part in response.parts if part.kind == 'text' and part.text]
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

    def _resolve_codebase_id(self, codebase_id: Optional[str]) -> Optional[str]:
        """
        Resolve a codebase_id, handling the special 'global' case.

        If codebase_id is 'global' (the default), look up the actual codebase
        with name='global' and return its ID. If no 'global' codebase exists,
        return None to allow task creation without a specific codebase.
        """
        if codebase_id is None or codebase_id == 'global':
            # Look up the actual 'global' codebase by name
            bridge = get_agent_bridge()
            if bridge:
                codebases = bridge.list_codebases()
                for cb in codebases:
                    if cb.name == 'global':
                        return cb.id
            # No global codebase found - return None
            return None
        return codebase_id

    async def _get_available_models(self) -> Dict[str, List[str]]:
        """
        Get all available models from registered workers.

        Returns a dict mapping model_id to list of worker_ids that support it.
        """
        from . import database as db

        workers = await db.db_list_workers()
        model_to_workers: Dict[str, List[str]] = {}

        for worker in workers:
            worker_id = worker.get('worker_id', 'unknown')
            models = worker.get('models', [])
            for model in models:
                # Models can be dicts with 'id' key or strings
                if isinstance(model, dict):
                    model_id = model.get('id', '')
                else:
                    model_id = str(model)

                if model_id:
                    if model_id not in model_to_workers:
                        model_to_workers[model_id] = []
                    model_to_workers[model_id].append(worker_id)

        return model_to_workers

    async def _validate_model_ref(
        self, model_ref: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate that the requested model_ref is available from at least one worker.

        Returns None if valid, or an error dict if invalid.
        """
        if not model_ref:
            return None

        available_models = await self._get_available_models()

        # Check exact match first
        if model_ref in available_models:
            return None

        # Check with colon vs slash normalization (provider:model vs provider/model)
        normalized_slash = (
            model_ref.replace(':', '/', 1) if ':' in model_ref else model_ref
        )
        normalized_colon = (
            model_ref.replace('/', ':', 1) if '/' in model_ref else model_ref
        )

        if (
            normalized_slash in available_models
            or normalized_colon in available_models
        ):
            return None

        # Model not found - build helpful error
        # Group models by provider for readability
        providers: Dict[str, List[str]] = {}
        for model_id in available_models.keys():
            if '/' in model_id:
                provider, model_name = model_id.split('/', 1)
            elif ':' in model_id:
                provider, model_name = model_id.split(':', 1)
            else:
                provider, model_name = 'unknown', model_id

            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model_name)

        # Build suggestions - find similar models
        suggestions = []
        search_term = model_ref.lower()
        for model_id in available_models.keys():
            if any(part in model_id.lower() for part in search_term.split('/')):
                suggestions.append(model_id)

        return {
            'error': f"Model '{model_ref}' not available from any registered worker",
            'available_providers': list(providers.keys()),
            'available_models_sample': list(available_models.keys())[:20],
            'suggestions': suggestions[:5] if suggestions else [],
            'hint': 'Use format provider/model (e.g., "google/gemini-2.5-flash", "zai-coding-plan/glm-4.7")',
            'total_models_available': len(available_models),
        }

    async def _list_models(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all available models from registered workers."""
        from . import database as db

        provider_filter = (args.get('provider') or '').strip().lower()
        search_filter = (args.get('search') or '').strip().lower()

        workers = await db.db_list_workers()
        # Build model details with provider grouping
        providers: Dict[str, List[Dict[str, Any]]] = {}
        model_ids_seen: set = set()

        for worker in workers:
            worker_id = worker.get('worker_id', 'unknown')
            worker_name = worker.get('name', worker_id)
            models = worker.get('models', [])

            for model in models:
                if isinstance(model, dict):
                    model_id = model.get('id', '')
                    model_name = model.get('name', model_id)
                    provider = model.get('provider', '')
                    provider_id = model.get('provider_id', provider)
                else:
                    model_id = str(model)
                    model_name = model_id
                    provider = ''
                    provider_id = ''

                if not model_id:
                    continue

                # Apply provider filter
                if provider_filter and provider_filter not in provider.lower() and provider_filter not in provider_id.lower():
                    continue

                # Apply search filter
                if search_filter and search_filter not in model_id.lower() and search_filter not in model_name.lower():
                    continue

                # Determine display provider
                display_provider = provider or provider_id or 'unknown'

                if display_provider not in providers:
                    providers[display_provider] = []

                # Avoid duplicate model entries, but track multiple workers
                if model_id not in model_ids_seen:
                    model_ids_seen.add(model_id)
                    providers[display_provider].append({
                        'id': model_id,
                        'name': model_name,
                        'provider': display_provider,
                        'workers': [worker_name],
                    })
                else:
                    # Add this worker to existing model entry
                    for p_models in providers.values():
                        for m in p_models:
                            if m['id'] == model_id and worker_name not in m['workers']:
                                m['workers'].append(worker_name)

        # Sort models within each provider
        for p in providers:
            providers[p].sort(key=lambda m: m['name'])

        # Build flat list for convenience
        all_models = []
        for p_models in providers.values():
            all_models.extend(p_models)

        return {
            'models': all_models,
            'providers': sorted(providers.keys()),
            'total': len(all_models),
            'by_provider': {p: [m['id'] for m in ms] for p, ms in sorted(providers.items())},
        }

    async def _validate_codebase_worker(
        self, codebase_id: Optional[str], model_ref: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validate that a worker exists for the codebase and supports the model.

        Returns None if valid, or an error dict if invalid.
        """
        from . import database as db

        # Global/None codebase - check if any worker exists with the model
        if not codebase_id or codebase_id == 'global':
            if model_ref:
                return await self._validate_model_ref(model_ref)
            return None

        # Check if codebase exists and has a worker
        codebase = await db.db_get_codebase(codebase_id)
        if not codebase:
            # List available codebases for helpful error
            all_codebases = await db.db_list_codebases()
            return {
                'error': f"Codebase '{codebase_id}' not found",
                'available_codebases': [
                    {
                        'id': cb.get('id'),
                        'name': cb.get('name'),
                        'path': cb.get('path'),
                    }
                    for cb in all_codebases[:10]
                ],
                'hint': 'Use list_codebases to find valid codebase IDs, or omit codebase_id for global tasks.',
            }

        worker_id = codebase.get('worker_id')
        if not worker_id:
            return {
                'error': f"Codebase '{codebase_id}' ({codebase.get('name')}) has no worker assigned",
                'codebase': {
                    'id': codebase.get('id'),
                    'name': codebase.get('name'),
                    'path': codebase.get('path'),
                },
                'hint': 'A worker must register this codebase before tasks can be executed. Start a worker with --codebase flag.',
            }

        # If model_ref specified, check if the worker supports it
        if model_ref:
            worker = await db.db_get_worker(worker_id)
            if not worker:
                return {
                    'error': f"Worker '{worker_id}' for codebase '{codebase_id}' not found in registry",
                    'hint': 'The worker may have gone offline. Check worker status.',
                }

            models = worker.get('models', [])
            model_ids = set()
            for m in models:
                mid = m.get('id', '') if isinstance(m, dict) else str(m)
                if mid:
                    model_ids.add(mid)

            normalized = (
                model_ref.replace(':', '/', 1)
                if ':' in model_ref
                else model_ref
            )
            if model_ref not in model_ids and normalized not in model_ids:
                return {
                    'error': f"Model '{model_ref}' not supported by worker '{worker_id}' for codebase '{codebase_id}'",
                    'worker': {
                        'id': worker_id,
                        'name': worker.get('name'),
                        'hostname': worker.get('hostname'),
                    },
                    'available_models_on_worker': list(model_ids)[:20],
                    'hint': 'Use a model supported by this worker, or omit model_ref to use the worker default.',
                }

        return None

    async def _send_message_async(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message asynchronously by creating a task and enqueuing it.

        Unlike _send_message (synchronous), this immediately returns a task_id
        and run_id, allowing callers to poll for results later.

        This is the primary entry point for the "fire and forget" flow.
        """
        from .monitor_api import get_agent_bridge

        message = args.get('message', '')
        conversation_id = args.get('conversation_id') or str(uuid.uuid4())
        codebase_id = self._resolve_codebase_id(
            args.get('codebase_id', 'global')
        )
        priority = args.get('priority', 0)
        notify_email = args.get('notify_email')

        base_metadata = {
            'conversation_id': conversation_id,
            'source': 'send_message_async',
        }
        if isinstance(args.get('metadata'), dict):
            base_metadata.update(args.get('metadata'))

        routing_decision, routed_metadata = orchestrate_task_route(
            prompt=message,
            agent_type='general',
            metadata=base_metadata,
            model=args.get('model'),
            model_ref=args.get('model_ref'),
            worker_personality=args.get('worker_personality'),
        )
        model_ref = routing_decision.model_ref

        # Validate codebase has a worker and worker supports the model
        validation_error = await self._validate_codebase_worker(
            codebase_id, model_ref
        )
        if validation_error:
            return validation_error

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

        # Create a task with the message as the prompt
        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=f'Async message: {message[:50]}...'
            if len(message) > 50
            else f'Async message: {message}',
            prompt=message,
            agent_type='general',
            priority=priority,
            model=routed_metadata.get('model'),
            metadata=routed_metadata,
            model_ref=model_ref,
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
            'metadata': task.metadata,
            'model': task.model,
            'model_ref': task.metadata.get('model_ref'),
            'target_agent_name': task.target_agent_name,
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
                    target_agent_name=routing_decision.target_agent_name,
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
            'routing': {
                'complexity': routing_decision.complexity,
                'model_tier': routing_decision.model_tier,
                'target_agent_name': routing_decision.target_agent_name,
                'worker_personality': routing_decision.worker_personality,
            },
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
        from .monitor_api import get_agent_bridge
        from datetime import timedelta

        agent_name = args.get('agent_name')
        if not agent_name:
            return {'error': 'agent_name is required'}

        message = args.get('message', '')
        conversation_id = args.get('conversation_id') or str(uuid.uuid4())
        codebase_id = self._resolve_codebase_id(
            args.get('codebase_id', 'global')
        )
        priority = args.get('priority', 0)
        deadline_seconds = args.get('deadline_seconds')
        notify_email = args.get('notify_email')

        base_metadata = {
            'conversation_id': conversation_id,
            'source': 'send_to_agent',
            'target_agent_name': agent_name,
        }
        if isinstance(args.get('metadata'), dict):
            base_metadata.update(args.get('metadata'))

        routing_decision, routed_metadata = orchestrate_task_route(
            prompt=message,
            agent_type='general',
            metadata=base_metadata,
            model=args.get('model'),
            model_ref=args.get('model_ref'),
            target_agent_name=agent_name,
            worker_personality=args.get('worker_personality'),
        )
        model_ref = routing_decision.model_ref

        # Validate codebase has a worker and worker supports the model
        validation_error = await self._validate_codebase_worker(
            codebase_id, model_ref
        )
        if validation_error:
            return validation_error

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

        # Create a task with the message as the prompt
        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=f'To {agent_name}: {message[:40]}...'
            if len(message) > 40
            else f'To {agent_name}: {message}',
            prompt=message,
            agent_type='general',
            priority=priority,
            model=routed_metadata.get('model'),
            metadata=routed_metadata,
            model_ref=model_ref,
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
            'metadata': task.metadata,
            'model': task.model,
            'model_ref': task.metadata.get('model_ref'),
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
            'complexity': routing_decision.complexity,
            'model_tier': routing_decision.model_tier,
            'worker_personality': routing_decision.worker_personality,
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
        from .monitor_api import get_agent_bridge
        from .agent_bridge import AgentTaskStatus, resolve_model

        title = args.get('title')
        description = args.get('description', '')
        codebase_id = self._resolve_codebase_id(
            args.get('codebase_id', 'global')
        )
        agent_type = args.get('agent_type', 'build')
        priority = args.get('priority', 0)
        # Resolve user-friendly model name to full provider/model-id
        model_input = args.get('model')
        model = resolve_model(model_input) if model_input else None
        model_ref_input = args.get('model_ref')

        base_metadata = {
            'source': 'create_task',
        }
        if isinstance(args.get('metadata'), dict):
            base_metadata.update(args.get('metadata'))

        routing_decision, routed_metadata = orchestrate_task_route(
            prompt=description,
            agent_type=agent_type,
            metadata=base_metadata,
            model=model,
            model_ref=model_ref_input,
            worker_personality=args.get('worker_personality'),
        )
        model_ref = routing_decision.model_ref
        effective_model = routed_metadata.get('model') or model

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

        task = await bridge.create_task(
            codebase_id=codebase_id,
            title=title,
            prompt=description,
            agent_type=agent_type,
            priority=priority,
            model=effective_model,
            metadata=routed_metadata,
            model_ref=model_ref,
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
            'model_ref': task.metadata.get('model_ref'),
            'priority': task.priority,
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
            'metadata': task.metadata,
            'target_agent_name': task.target_agent_name,
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
                    target_agent_name=routing_decision.target_agent_name,
                    model_ref=model_ref,
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
            'model_ref': task.metadata.get('model_ref'),
            'routing': {
                'complexity': routing_decision.complexity,
                'model_tier': routing_decision.model_tier,
                'target_agent_name': routing_decision.target_agent_name,
                'worker_personality': routing_decision.worker_personality,
            },
            'status': task.status.value,
            'created_at': task.created_at.isoformat(),
        }

    async def _get_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get task details."""
        from .monitor_api import get_agent_bridge
        from .agent_bridge import AgentTaskStatus

        task_id = args.get('task_id')

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

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
        from .monitor_api import get_agent_bridge
        from .agent_bridge import AgentTaskStatus

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

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

        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

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

    async def _get_current_codebase(self) -> Dict[str, Any]:
        """Get the current codebase context from the bridge."""
        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

        # Get all codebases and find the one we're running in
        codebases = bridge.list_codebases()

        # Try to determine which codebase we're in based on the working directory
        import os

        cwd = os.getcwd()

        # Find the codebase that matches our current working directory
        current_codebase = None
        for cb in codebases:
            if cb.path and cwd.startswith(cb.path):
                # Prefer more specific matches (longer paths)
                if current_codebase is None or len(cb.path) > len(
                    current_codebase.path
                ):
                    current_codebase = cb

        # If no match, look for a codebase named "global" or return the first one
        if current_codebase is None:
            for cb in codebases:
                if cb.name == 'global':
                    current_codebase = cb
                    break

        if current_codebase is None and codebases:
            current_codebase = codebases[0]

        if current_codebase is None:
            return {
                'error': 'No codebase found',
                'hint': 'Register a codebase first or use list_codebases to see available options',
            }

        return {
            'codebase_id': current_codebase.id,
            'name': current_codebase.name,
            'path': current_codebase.path,
            'worker_id': current_codebase.worker_id,
            'status': current_codebase.status,
            'description': current_codebase.description,
        }

    async def _list_codebases(self) -> Dict[str, Any]:
        """List all registered codebases."""
        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

        codebases = bridge.list_codebases()

        return {
            'codebases': [
                {
                    'codebase_id': cb.id,
                    'name': cb.name,
                    'path': cb.path,
                    'worker_id': cb.worker_id,
                    'status': cb.status,
                    'description': cb.description,
                }
                for cb in codebases
            ],
            'count': len(codebases),
        }

    async def _create_codebase(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new codebase for agent work."""
        import aiohttp

        name = args.get('name')
        path = args.get('path')
        description = args.get('description', '')
        worker_id = args.get('worker_id')

        if not name:
            return {'error': 'name is required'}
        if not path:
            return {'error': 'path is required'}

        payload = {
            'name': name,
            'path': path,
            'description': description,
        }
        if worker_id:
            payload['worker_id'] = worker_id

        api_url = 'http://localhost:8001/v1/agent/codebases'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        # If pending (no worker_id), return task info
                        if data.get('pending'):
                            return {
                                'success': True,
                                'pending': True,
                                'task_id': data.get('task_id'),
                                'message': data.get('message')
                                or f'Registration task created for "{name}". A worker will validate the path.',
                            }
                        # Otherwise return codebase info
                        return {
                            'success': True,
                            'pending': False,
                            'codebase_id': data.get('id')
                            or data.get('codebase_id'),
                            'name': data.get('name') or name,
                            'path': data.get('path') or path,
                            'status': data.get('status'),
                            'message': f'Codebase "{name}" registered successfully',
                        }
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to create codebase: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call codebase API: {str(e)}'}

    async def _get_codebase(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a specific codebase."""
        import aiohttp

        codebase_id = args.get('codebase_id')
        if not codebase_id:
            return {'error': 'codebase_id is required'}

        api_url = f'http://localhost:8001/v1/agent/codebases/{codebase_id}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'codebase_id': data.get('id')
                            or data.get('codebase_id'),
                            'name': data.get('name'),
                            'path': data.get('path'),
                            'worker_id': data.get('worker_id'),
                            'status': data.get('status'),
                            'description': data.get('description'),
                            'created_at': data.get('created_at'),
                        }
                    elif resp.status == 404:
                        return {'error': f'Codebase not found: {codebase_id}'}
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to get codebase: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call codebase API: {str(e)}'}

    async def _delete_codebase(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Unregister a codebase."""
        import aiohttp

        codebase_id = args.get('codebase_id')
        if not codebase_id:
            return {'error': 'codebase_id is required'}

        api_url = f'http://localhost:8001/v1/agent/codebases/{codebase_id}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(api_url) as resp:
                    if resp.status in (200, 204):
                        return {
                            'success': True,
                            'codebase_id': codebase_id,
                            'message': f'Codebase {codebase_id} deleted successfully',
                        }
                    elif resp.status == 404:
                        return {'error': f'Codebase not found: {codebase_id}'}
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to delete codebase: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call codebase API: {str(e)}'}

    async def _set_active_codebase(
        self, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set the active codebase for subsequent operations."""
        codebase_id = args.get('codebase_id')
        if not codebase_id:
            return {'error': 'codebase_id is required'}

        # Verify the codebase exists
        result = await self._get_codebase(args)
        if 'error' in result:
            return result

        # Store as the default codebase
        MCPHTTPServer._default_codebase_id = codebase_id

        return {
            'success': True,
            'active_codebase_id': codebase_id,
            'name': result.get('name'),
            'path': result.get('path'),
            'message': f'Active codebase set to "{result.get("name")}" ({codebase_id})',
        }

    async def _get_active_codebase(self) -> Dict[str, Any]:
        """Get the currently active codebase."""
        codebase_id = MCPHTTPServer._default_codebase_id

        if not codebase_id:
            return {
                'active_codebase_id': None,
                'message': 'No active codebase set. Use set_active_codebase or list_codebases to select one.',
            }

        # Get codebase details
        result = await self._get_codebase({'codebase_id': codebase_id})
        if 'error' in result:
            # Codebase was deleted or doesn't exist anymore
            MCPHTTPServer._default_codebase_id = None
            return {
                'active_codebase_id': None,
                'message': 'Previously active codebase no longer exists. Use set_active_codebase to select a new one.',
            }

        return {
            'active_codebase_id': codebase_id,
            'name': result.get('name'),
            'path': result.get('path'),
            'worker_id': result.get('worker_id'),
            'status': result.get('status'),
        }

    # =========================================================================
    # Ralph (PRD-driven development) tool handlers
    # =========================================================================

    async def _ralph_create_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Ralph run to implement a PRD."""
        import aiohttp

        project = args.get('project', '')
        branch_name = args.get('branch_name', '')
        description = args.get('description', '')
        user_stories = args.get('user_stories', [])
        max_iterations = args.get('max_iterations', 10)
        codebase_id = args.get('codebase_id')

        # Use active codebase if none specified
        if not codebase_id and MCPHTTPServer._default_codebase_id:
            codebase_id = MCPHTTPServer._default_codebase_id

        if not project or not branch_name or not user_stories:
            return {
                'error': 'Missing required fields: project, branch_name, and user_stories are required'
            }

        # Build the PRD payload
        prd_payload = {
            'prd': {
                'project': project,
                'branchName': branch_name,
                'description': description,
                'userStories': [
                    {
                        'id': s.get('id', f'US-{i + 1}'),
                        'title': s.get('title', ''),
                        'description': s.get('description', ''),
                        'acceptanceCriteria': s.get('acceptance_criteria', []),
                        'status': 'pending',
                    }
                    for i, s in enumerate(user_stories)
                ],
            },
            'max_iterations': max_iterations,
        }

        if codebase_id:
            prd_payload['codebase_id'] = codebase_id

        # Call the Ralph API
        api_url = f'http://localhost:8001/v1/ralph/runs'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=prd_payload) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        return {
                            'success': True,
                            'run_id': data.get(
                                'id'
                            ),  # API returns 'id' not 'run_id'
                            'status': data.get('status'),
                            'current_iteration': data.get(
                                'current_iteration', 0
                            ),
                            'max_iterations': data.get('max_iterations'),
                            'message': f'Ralph run started for project "{project}"',
                        }
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to create Ralph run: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call Ralph API: {str(e)}'}

    async def _ralph_get_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get the status of a Ralph run."""
        import aiohttp

        run_id = args.get('run_id')
        if not run_id:
            return {'error': 'run_id is required'}

        api_url = f'http://localhost:8001/v1/ralph/runs/{run_id}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    elif resp.status == 404:
                        return {'error': f'Ralph run not found: {run_id}'}
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to get Ralph run: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call Ralph API: {str(e)}'}

    async def _ralph_list_runs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List Ralph runs."""
        import aiohttp

        status = args.get('status')
        limit = args.get('limit', 20)

        api_url = f'http://localhost:8001/v1/ralph/runs?limit={limit}'
        if status:
            api_url += f'&status={status}'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to list Ralph runs: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call Ralph API: {str(e)}'}

    async def _ralph_cancel_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a Ralph run."""
        import aiohttp

        run_id = args.get('run_id')
        if not run_id:
            return {'error': 'run_id is required'}

        api_url = f'http://localhost:8001/v1/ralph/runs/{run_id}/cancel'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'success': True,
                            'run_id': run_id,
                            'status': data.get('status', 'cancelled'),
                            'message': 'Ralph run cancelled',
                        }
                    elif resp.status == 404:
                        return {'error': f'Ralph run not found: {run_id}'}
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to cancel Ralph run: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call Ralph API: {str(e)}'}

    # =========================================================================
    # PRD Chat tool handlers
    # =========================================================================

    async def _prd_chat(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Chat with AI to generate a PRD."""
        import aiohttp

        message = args.get('message')
        if not message:
            return {'error': 'message is required'}

        conversation_id = args.get('conversation_id', 'prd-builder')
        codebase_id = args.get('codebase_id')

        payload = {
            'message': message,
            'conversation_id': conversation_id,
        }
        if codebase_id:
            payload['codebase_id'] = codebase_id

        api_url = 'http://localhost:8001/v1/ralph/chat'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'success': True,
                            'task_id': data.get('task_id'),
                            'status': data.get('status'),
                            'conversation_id': conversation_id,
                            'message': 'PRD chat message submitted. Poll the task for the AI response.',
                        }
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to send PRD chat: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call PRD chat API: {str(e)}'}

    async def _prd_list_sessions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List PRD chat sessions."""
        import aiohttp

        codebase_id = args.get('codebase_id', 'global')
        limit = args.get('limit', 20)

        api_url = f'http://localhost:8001/v1/ralph/chat/sessions/{codebase_id}?limit={limit}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data
                    else:
                        error_text = await resp.text()
                        return {
                            'error': f'Failed to list PRD sessions: {error_text}'
                        }
        except Exception as e:
            return {'error': f'Failed to call PRD sessions API: {str(e)}'}

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
        agent_list: List[Dict[str, Any]] = []
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
                        'source': agent.get('source', 'agent_registry'),
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
                        'source': 'agent_registry',
                    }
                )

        # Also include SSE-connected workers, even if they haven't registered
        # as discoverable agents via register_agent/refresh_agent_heartbeat.
        #
        # This fixes a common UX issue where tasks are being processed (workers
        # are online) but discover_agents appears empty.
        try:
            sse_registry = get_worker_registry()
            connected_workers = await sse_registry.list_workers()
        except Exception as e:
            logger.debug(f'Failed to list SSE workers for discovery: {e}')
            connected_workers = []

        # Deduplicate by (role, instance_id) where possible
        seen_pairs = {
            (a.get('role'), a.get('instance_id'))
            for a in agent_list
            if a.get('role') and a.get('instance_id')
        }

        for w in connected_workers:
            role = w.get('agent_name') or 'worker'
            instance_id = w.get('worker_id')
            if role and instance_id and (role, instance_id) in seen_pairs:
                continue

            # Represent workers using the role:instance pattern so routing can
            # use role (send_to_agent) while still keeping unique identities.
            name = f'{role}:{instance_id}' if instance_id else role

            worker_capabilities = w.get('capabilities') or []
            worker_codebases = w.get('codebases') or []

            agent_list.append(
                {
                    'name': name,
                    'role': role,
                    'instance_id': instance_id,
                    'description': (
                        f"SSE worker connected (busy={bool(w.get('is_busy'))}, "
                        f"codebases={len(worker_codebases)}, "
                        f"capabilities={len(worker_capabilities)})"
                    ),
                    # Workers do not expose a direct A2A URL; they connect
                    # outbound to the server via SSE.
                    'url': None,
                    'capabilities': {
                        'streaming': False,
                        'push_notifications': False,
                        'worker_capabilities': worker_capabilities,
                        'codebases': worker_codebases,
                        'is_busy': bool(w.get('is_busy')),
                        'current_task_id': w.get('current_task_id'),
                    },
                    'last_seen': w.get('last_heartbeat') or w.get('connected_at'),
                    'source': 'sse_worker_registry',
                }
            )
            if role and instance_id:
                seen_pairs.add((role, instance_id))

        # Also include DB-registered workers ("hosted workers") from the
        # workers table. These are real worker pools that can claim/execute
        # tasks, but they are NOT necessarily routable via send_to_agent.
        #
        # Without this, users can have active workers processing tasks while
        # discover_agents appears empty (common confusion).
        try:
            from . import database as db

            db_workers = await db.db_list_workers(status='active')
        except Exception as e:
            logger.debug(f'Failed to list DB workers for discovery: {e}')
            db_workers = []

        # Deduplicate by worker_id vs any previously-added instance_ids.
        seen_worker_ids = {
            a.get('instance_id')
            for a in agent_list
            if isinstance(a, dict) and a.get('instance_id')
        }

        for w in db_workers:
            worker_id = w.get('worker_id')
            if not worker_id or worker_id in seen_worker_ids:
                continue

            # Filter out stale workers when last_seen is available.
            last_seen = w.get('last_seen')
            if last_seen:
                try:
                    from datetime import timezone

                    # last_seen may be naive (no tz). Handle both.
                    parsed = datetime.fromisoformat(
                        str(last_seen).replace('Z', '+00:00')
                    )
                    now = (
                        datetime.now(timezone.utc)
                        if parsed.tzinfo
                        else datetime.now()
                    )
                    age_seconds = (now - parsed).total_seconds()
                    if age_seconds > max_age_seconds:
                        continue
                except Exception:
                    # If parsing fails, keep the entry (better UX than hiding).
                    pass

            worker_name = w.get('name') or worker_id
            hostname = w.get('hostname') or ''
            models = w.get('models') or []
            capabilities = w.get('capabilities') or {}

            agent_list.append(
                {
                    'name': f'worker:{worker_id}',
                    # Intentionally omit/None role to avoid implying these are
                    # routable via send_to_agent (they are execution pools).
                    'role': None,
                    'instance_id': worker_id,
                    'description': (
                        f"Hosted worker pool (name={worker_name}"
                        + (f", host={hostname}" if hostname else '')
                        + f", models={len(models)})"
                    ),
                    'url': None,
                    'capabilities': {
                        'streaming': False,
                        'push_notifications': False,
                        'worker_name': worker_name,
                        'hostname': hostname,
                        'status': w.get('status'),
                        'models_count': len(models),
                        'models_sample': models[:10],
                        'worker_capabilities': capabilities,
                        # Explicitly communicate that this entry is not a
                        # routable A2A agent identity.
                        'routing_supported': False,
                    },
                    'last_seen': last_seen,
                    'source': 'workers_table',
                }
            )
            seen_worker_ids.add(worker_id)

        return {
            'agents': agent_list,
            'count': len(agent_list),
            'routing_note': (
                "IMPORTANT: Use 'role' with send_to_agent for routing. "
                "'name' is a unique instance identity and will NOT route tasks. "
                "Example: send_to_agent(agent_name='code-reviewer') routes by role. "
                "Entries with source=workers_table are execution pools (not routable via send_to_agent)."
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
        bridge = get_agent_bridge()
        if bridge is None:
            return {'error': 'Agent bridge not available'}

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
