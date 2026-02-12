"""
A2A Protocol Server Implementation

Main server implementation providing JSON-RPC 2.0 over HTTP(S) with support for
streaming, task management, and agent discovery.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
import uuid

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
import uvicorn

from .models import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    SendMessageRequest,
    SendMessageResponse,
    GetTaskRequest,
    GetTaskResponse,
    CancelTaskRequest,
    CancelTaskResponse,
    StreamMessageRequest,
    TaskStatusUpdateEvent,
    Task,
    TaskStatus,
    Message,
    Part,
    LiveKitTokenRequest,
    LiveKitTokenResponse,
    PushNotificationConfig,
    TaskPushNotificationConfig,
    SetPushNotificationConfigRequest,
    GetPushNotificationConfigRequest,
    ListPushNotificationConfigsRequest,
    DeletePushNotificationConfigRequest,
)
from .task_manager import TaskManager, PersistentTaskManager
from .database import DATABASE_URL
from .message_broker import MessageBroker, InMemoryMessageBroker
from .agent_card import AgentCard
from .monitor_api import (
    monitor_router,
    agent_router,
    opencode_router,  # backward-compat alias (same object as agent_router) — kept for redirect
    voice_router,
    auth_router,
    nextauth_router,
    monitoring_service,
    log_agent_message,
)
from .worker_sse import worker_sse_router
from .email_inbound import email_router
from .email_api import email_api_router
from .tenant_middleware import TenantContextMiddleware
from .policy_middleware import PolicyAuthorizationMiddleware
from .tenant_api import router as tenant_router
from .billing_api import router as billing_router
from .billing_webhooks import billing_webhook_router
from .user_auth import router as user_auth_router
from .token_billing_api import router as token_billing_router
from .finops_api import router as finops_router
from .a2a_agent_card import a2a_agent_card_router
from .ralph_api import ralph_router

# Import policy engine for centralized authorization
try:
    from .policy import close_policy_client, opa_health, require_permission

    POLICY_ENGINE_AVAILABLE = True
except ImportError:
    POLICY_ENGINE_AVAILABLE = False
    close_policy_client = None
    opa_health = None
    require_permission = None

# Import MCP router for unified MCP protocol support on same port
try:
    from .mcp_router import create_mcp_router, MCPToolHandler

    MCP_ROUTER_AVAILABLE = True
except ImportError:
    MCP_ROUTER_AVAILABLE = False
    create_mcp_router = None
    MCPToolHandler = None

# Import admin API for system overview
try:
    from .admin_api import router as admin_router

    ADMIN_API_AVAILABLE = True
except ImportError:
    ADMIN_API_AVAILABLE = False
    admin_router = None

# Import automation API for third-party platforms
try:
    from .automation_api import router as automation_api_router

    AUTOMATION_API_AVAILABLE = True
except ImportError:
    AUTOMATION_API_AVAILABLE = False
    automation_api_router = None

# Import analytics API for first-party event tracking
try:
    from .analytics_api import router as analytics_api_router

    ANALYTICS_API_AVAILABLE = True
except ImportError:
    ANALYTICS_API_AVAILABLE = False
    analytics_api_router = None

# OAuth is handled by Keycloak - no custom OAuth server needed

# Import A2A protocol router for standards-compliant agent communication
try:
    from .a2a_router import create_a2a_router
    from .a2a_executor import CodetetherExecutor, create_codetether_executor

    A2A_ROUTER_AVAILABLE = True
except ImportError as e:
    A2A_ROUTER_AVAILABLE = False
    create_a2a_router = None
    CodetetherExecutor = None
    create_codetether_executor = None
    logger.warning(f'A2A router not available: {e}')

# Import queue API router for operational visibility (mid-market)
try:
    from .queue_api import router as queue_api_router

    QUEUE_API_AVAILABLE = True
except ImportError:
    QUEUE_API_AVAILABLE = False
    queue_api_router = None

try:
    from .livekit_bridge import create_livekit_bridge, LiveKitBridge

    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    create_livekit_bridge = None
    LiveKitBridge = None


logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class A2AServer:
    """Main A2A Protocol Server implementation."""

    def __init__(
        self,
        agent_card: AgentCard,
        task_manager: Optional[TaskManager] = None,
        message_broker: Optional[MessageBroker] = None,
        auth_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.agent_card = agent_card
        self.task_manager = task_manager or PersistentTaskManager(DATABASE_URL)
        self.message_broker = message_broker or InMemoryMessageBroker()
        self.auth_callback = auth_callback

        # Initialize LiveKit bridge if available
        self.livekit_bridge = None
        if LIVEKIT_AVAILABLE and create_livekit_bridge:
            try:
                self.livekit_bridge = create_livekit_bridge()
                if self.livekit_bridge:
                    logger.info('LiveKit bridge initialized successfully')
                else:
                    logger.info(
                        'LiveKit bridge not configured - media features disabled'
                    )
            except Exception as e:
                logger.warning(f'Failed to initialize LiveKit bridge: {e}')
        else:
            logger.info('LiveKit not available - media features disabled')

        # Create FastAPI app
        self.app = FastAPI(
            title=f'A2A Server - {agent_card.card.name}',
            description=agent_card.card.description,
            version=agent_card.card.version,
        )

        # Middleware execution order is reverse of registration order in
        # Starlette.  Register inner middleware first, outermost last.

        # Add policy authorization middleware (OPA enforcement)
        # Runs after tenant extraction in the request lifecycle.
        self.app.add_middleware(PolicyAuthorizationMiddleware)

        # Add budget enforcement middleware (checks token budgets before AI ops)
        # Runs after tenant extraction.
        try:
            from .budget_middleware import BudgetEnforcementMiddleware
            self.app.add_middleware(BudgetEnforcementMiddleware)
        except Exception as e:
            logger.warning(f'Budget enforcement middleware not loaded: {e}')

        # Add tenant context middleware (extracts tenant from JWT)
        self.app.add_middleware(TenantContextMiddleware)

        # Add CORS middleware — registered last so it is the outermost layer.
        # This ensures CORS headers are present on ALL responses, including
        # 401/403 errors from auth middleware.
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                'https://codetether.run',
                'https://api.codetether.run',
                'https://docs.codetether.run',
                'http://localhost:3000',
                'http://localhost:8000',
            ],
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )

        # Method handlers
        self._method_handlers: Dict[str, Callable] = {
            'message/send': self._handle_send_message,
            'message/stream': self._handle_stream_message,
            'tasks/get': self._handle_get_task,
            'tasks/cancel': self._handle_cancel_task,
            'tasks/resubscribe': self._handle_resubscribe_task,
            'tasks/pushNotificationConfig/set': self._handle_set_push_notification_config,
            'tasks/pushNotificationConfig/get': self._handle_get_push_notification_config,
            'tasks/pushNotificationConfig/list': self._handle_list_push_notification_configs,
            'tasks/pushNotificationConfig/delete': self._handle_delete_push_notification_config,
        }

        # Active streaming connections
        self._streaming_connections: Dict[str, List[asyncio.Queue]] = {}

        # Store agent info for deferred registration
        self.agent_id = str(uuid.uuid4())
        self._agent_name = agent_card.card.name

        self._setup_routes()

        # Register agent on startup (async)
        @self.app.on_event('startup')
        async def register_with_monitoring():
            await monitoring_service.register_agent(
                self.agent_id, self._agent_name
            )

        # Start background task reaper for stuck task recovery
        @self.app.on_event('startup')
        async def start_reaper():
            try:
                from .task_reaper import start_task_reaper

                await start_task_reaper()
            except Exception as e:
                logger.warning(f'Failed to start task reaper: {e}')

        @self.app.on_event('shutdown')
        async def stop_reaper():
            try:
                from .task_reaper import stop_task_reaper

                await stop_task_reaper()
            except Exception:
                pass

        # Start cron scheduler for scheduled tasks
        @self.app.on_event('startup')
        async def start_cron_scheduler():
            try:
                from .cron_scheduler import start_cron_scheduler

                await start_cron_scheduler()
            except Exception as e:
                logger.warning(f'Failed to start cron scheduler: {e}')

        @self.app.on_event('shutdown')
        async def stop_cron_scheduler():
            try:
                from .cron_scheduler import stop_cron_scheduler

                await stop_cron_scheduler()
            except Exception:
                pass

        # Start Knative garbage collector for idle session workers
        @self.app.on_event('startup')
        async def start_knative_gc():
            try:
                from .knative_gc import start_background_gc, GC_ENABLED

                if GC_ENABLED:
                    start_background_gc()
                    logger.info('Knative GC started')
            except Exception as e:
                logger.warning(f'Failed to start Knative GC: {e}')

        @self.app.on_event('shutdown')
        async def stop_knative_gc():
            try:
                from .knative_gc import stop_background_gc

                stop_background_gc()
            except Exception:
                pass

        # Start proactive rule engine for event-driven/scheduled agent triggers
        @self.app.on_event('startup')
        async def start_rule_engine():
            try:
                from .rule_engine import start_rule_engine

                await start_rule_engine()
            except Exception as e:
                logger.warning(f'Failed to start proactive rule engine: {e}')

        @self.app.on_event('shutdown')
        async def stop_rule_engine():
            try:
                from .rule_engine import stop_rule_engine

                await stop_rule_engine()
            except Exception:
                pass

        # Start health monitor for proactive health checks
        @self.app.on_event('startup')
        async def start_health_monitor():
            try:
                from .health_monitor import start_health_monitor

                await start_health_monitor()
            except Exception as e:
                logger.warning(f'Failed to start health monitor: {e}')

        @self.app.on_event('shutdown')
        async def stop_health_monitor():
            try:
                from .health_monitor import stop_health_monitor

                await stop_health_monitor()
            except Exception:
                pass

        # Start perpetual cognition manager for persistent thought loops
        @self.app.on_event('startup')
        async def start_perpetual_manager():
            try:
                from .perpetual_loop import start_perpetual_loop_manager

                await start_perpetual_loop_manager()
            except Exception as e:
                logger.warning(f'Failed to start perpetual cognition manager: {e}')

        @self.app.on_event('shutdown')
        async def stop_perpetual_manager():
            try:
                from .perpetual_loop import stop_perpetual_loop_manager

                await stop_perpetual_loop_manager()
            except Exception:
                pass

        # Start shared HTTP client (must start before marketing services)
        @self.app.on_event('startup')
        async def start_shared_http_client():
            try:
                from .http_client import start_http_client

                await start_http_client()
            except Exception as e:
                logger.warning(f'Failed to start shared HTTP client: {e}')

        @self.app.on_event('shutdown')
        async def stop_shared_http_client():
            try:
                from .http_client import stop_http_client

                await stop_http_client()
            except Exception:
                pass

        # Start marketing automation service
        @self.app.on_event('startup')
        async def start_marketing():
            try:
                from .marketing_automation import start_marketing_automation

                await start_marketing_automation()
            except Exception as e:
                logger.warning(f'Failed to start marketing automation: {e}')

        @self.app.on_event('shutdown')
        async def stop_marketing():
            try:
                from .marketing_automation import stop_marketing_automation

                await stop_marketing_automation()
            except Exception:
                pass

        # Start conversion tracker + orchestrator + marketing loop
        @self.app.on_event('startup')
        async def start_conversion_and_orchestration():
            try:
                from .conversion_tracker import start_conversion_tracker
                await start_conversion_tracker()
            except Exception as e:
                logger.warning(f'Failed to start conversion tracker: {e}')
            try:
                from .marketing_orchestrator import start_orchestrator
                await start_orchestrator()
            except Exception as e:
                logger.warning(f'Failed to start marketing orchestrator: {e}')
            try:
                from .marketing_loop import ensure_marketing_loop
                await ensure_marketing_loop()
            except Exception as e:
                logger.warning(f'Failed to ensure marketing loop: {e}')

        @self.app.on_event('shutdown')
        async def stop_conversion_and_orchestration():
            try:
                from .conversion_tracker import stop_conversion_tracker
                await stop_conversion_tracker()
            except Exception:
                pass
            try:
                from .marketing_orchestrator import stop_orchestrator
                await stop_orchestrator()
            except Exception:
                pass

        # Shutdown policy engine HTTP client
        if POLICY_ENGINE_AVAILABLE and close_policy_client:

            @self.app.on_event('shutdown')
            async def shutdown_policy_client():
                try:
                    await close_policy_client()
                except Exception:
                    pass

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        @self.app.get('/.well-known/agent-card.json')
        async def get_agent_card():
            """Serve the agent card for discovery."""
            return JSONResponse(content=self.agent_card.to_dict())

        @self.app.post('/')
        async def handle_jsonrpc(
            request: Request,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(
                security
            ),
        ):
            """Handle JSON-RPC 2.0 requests."""
            return await self._handle_jsonrpc_request(request, credentials)

        # Backwards/Docs compatibility: accept JSON-RPC at a versioned path.
        # Historically, docs and clients used /v1/a2a.
        @self.app.post('/v1/a2a')
        async def handle_jsonrpc_v1(
            request: Request,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(
                security
            ),
        ):
            """Handle JSON-RPC 2.0 requests (alias for `/`)."""
            return await self._handle_jsonrpc_request(request, credentials)

        @self.app.get('/health')
        async def health_check():
            """Health check endpoint."""
            result = {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
            }
            if POLICY_ENGINE_AVAILABLE and opa_health:
                result['policy_engine'] = await opa_health()
            return result

        @self.app.get('/agents')
        async def discover_agents():
            """Discover other agents through the message broker."""
            agents = await self.message_broker.discover_agents()
            return [agent.model_dump() for agent in agents]

        @self.app.post('/v1/livekit/token', response_model=LiveKitTokenResponse)
        async def get_livekit_token(
            token_request: LiveKitTokenRequest,
            credentials: Optional[HTTPAuthorizationCredentials] = Depends(
                security
            ),
        ):
            """Get a LiveKit access token for media sessions."""
            return await self._handle_livekit_token_request(
                token_request, credentials
            )

        # Include monitoring API routes
        self.app.include_router(monitor_router)

        # Include agent integration routes (/v1/agent/*)
        # NOTE: agent_router IS opencode_router (alias) so this single
        # include_router call serves both /v1/agent/* paths.
        self.app.include_router(agent_router)
        logger.info('Agent API router mounted at /v1/agent')

        # Legacy backward-compat: redirect /v1/opencode/* → /v1/agent/*
        # This allows old clients/workers to keep functioning during migration.
        from fastapi import APIRouter as _Router
        from fastapi.responses import RedirectResponse as _Redirect

        _legacy_router = _Router(prefix='/v1/opencode', tags=['opencode-legacy'], deprecated=True)

        @_legacy_router.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
        async def _opencode_to_agent_redirect(path: str, request: Request):
            # Build redirect preserving the original scheme (handles TLS termination)
            scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
            new_path = request.url.path.replace('/v1/opencode/', '/v1/agent/', 1)
            query = f'?{request.url.query}' if request.url.query else ''
            new_url = f'{scheme}://{request.url.netloc}{new_path}{query}'
            return _Redirect(url=new_url, status_code=307)

        self.app.include_router(_legacy_router)
        logger.info('Legacy /v1/opencode/* redirect router mounted')

        # Include Ralph autonomous development routes
        self.app.include_router(ralph_router)

        # Include authentication routes
        self.app.include_router(auth_router)

        # Include NextAuth compatibility routes for Cypress
        self.app.include_router(nextauth_router)

        # Include voice session routes
        self.app.include_router(voice_router)

        # Include worker SSE routes for push-based task distribution
        self.app.include_router(worker_sse_router)

        # Include email inbound webhook routes for reply-based task continuation
        self.app.include_router(email_router)

        # Include email debugging and testing routes
        self.app.include_router(email_api_router)

        # Include tenant management routes
        self.app.include_router(tenant_router)

        # Include billing API routes for subscription management
        self.app.include_router(billing_router)

        # Include billing webhook routes for Stripe
        self.app.include_router(billing_webhook_router)

        # Include token billing API routes for per-token usage tracking
        self.app.include_router(token_billing_router)
        logger.info('Token billing API router mounted at /v1/token-billing')

        # Include FinOps API routes for cost analytics, anomalies, and optimization
        self.app.include_router(finops_router)
        logger.info('FinOps API router mounted at /v1/finops')

        # Include user authentication and billing routes (mid-market individual users)
        self.app.include_router(user_auth_router)
        logger.info('User auth API router mounted at /v1/users')

        # Include queue API routes for operational visibility (mid-market)
        if QUEUE_API_AVAILABLE and queue_api_router:
            self.app.include_router(queue_api_router)

        # Include A2A protocol compliant agent card endpoint
        # This serves the standard /.well-known/agent-card.json for discovery
        self.app.include_router(a2a_agent_card_router)

        # Include admin API for system overview dashboard
        if ADMIN_API_AVAILABLE and admin_router:
            self.app.include_router(admin_router)
            logger.info('Admin API router mounted at /v1/admin')

        # Include automation API for third-party platforms
        if AUTOMATION_API_AVAILABLE and automation_api_router:
            self.app.include_router(automation_api_router)
            logger.info('Automation API router mounted at /v1/automation')

        # Include analytics API for first-party event tracking
        if ANALYTICS_API_AVAILABLE and analytics_api_router:
            self.app.include_router(analytics_api_router)
            logger.info('Analytics API router mounted at /v1/analytics')

        # Include crash report ingestion API
        try:
            from .crash_reports_api import router as crash_reports_router

            self.app.include_router(crash_reports_router)
            logger.info('Crash reports API router mounted at /v1/crash-reports')
        except Exception as e:
            logger.warning(f'Failed to mount crash reports router: {e}')

        # Include cronjobs API for scheduled task management
        try:
            from .cronjobs_api import router as cronjobs_router

            self.app.include_router(cronjobs_router)
            logger.info('Cronjobs API router mounted at /v1/cronjobs')
        except Exception as e:
            logger.warning(f'Failed to mount cronjobs router: {e}')

        # Include proactive API for rules, health checks, and perpetual loops
        try:
            from .proactive_api import router as proactive_router

            self.app.include_router(proactive_router)
            logger.info('Proactive API router mounted at /v1/proactive')
        except Exception as e:
            logger.warning(f'Failed to mount proactive router: {e}')

        # Mount static files for analytics.js and other assets
        import os

        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        if os.path.exists(static_dir):
            self.app.mount(
                '/static', StaticFiles(directory=static_dir), name='static'
            )
            logger.info(f'Static files mounted at /static from {static_dir}')

        # Include A2A protocol router for standards-compliant agent communication
        # This provides JSON-RPC and REST bindings at /a2a/*
        if A2A_ROUTER_AVAILABLE and create_a2a_router:
            try:
                a2a_router = create_a2a_router(
                    executor=create_codetether_executor(
                        task_queue=None,  # Will be initialized lazily
                        database=None,
                    )
                    if create_codetether_executor
                    else None,
                    database_url=DATABASE_URL,
                    require_authentication=False,  # Allow public access, auth per-endpoint
                )
                self.app.include_router(a2a_router)
                logger.info('A2A protocol router mounted at /a2a')
            except Exception as e:
                logger.warning(f'Failed to mount A2A router: {e}')

        # Include MCP protocol router for unified MCP support on same port
        # This eliminates the need for a separate MCP server on port 9000
        if MCP_ROUTER_AVAILABLE and create_mcp_router and MCPToolHandler:
            try:
                mcp_handler = MCPToolHandler(a2a_server=self)
                mcp_router = create_mcp_router(mcp_handler)
                self.app.include_router(mcp_router)
                logger.info('MCP protocol router mounted at /mcp')
            except Exception as e:
                logger.warning(f'Failed to mount MCP router: {e}')

    async def _handle_jsonrpc_request(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials],
    ) -> Response:
        """Handle incoming JSON-RPC request."""
        try:
            # Parse request body
            body = await request.body()
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return self._create_error_response(None, -32700, 'Parse error')

            # Validate JSON-RPC structure
            try:
                rpc_request = JSONRPCRequest.model_validate(request_data)
            except Exception:
                return self._create_error_response(
                    request_data.get('id'), -32600, 'Invalid Request'
                )

            # Check authentication if required
            if self.agent_card.card.authentication and self.auth_callback:
                if not credentials or not self.auth_callback(
                    credentials.credentials
                ):
                    return self._create_error_response(
                        rpc_request.id, -32001, 'Authentication failed'
                    )

            # Handle method
            method_handler = self._method_handlers.get(rpc_request.method)
            if not method_handler:
                return self._create_error_response(
                    rpc_request.id, -32601, 'Method not found'
                )

            try:
                result = await method_handler(rpc_request.params or {})

                # Check if this is a streaming response
                if isinstance(result, StreamingResponse):
                    return result

                return self._create_success_response(rpc_request.id, result)

            except Exception as e:
                logger.error(f'Error handling method {rpc_request.method}: {e}')
                return self._create_error_response(
                    rpc_request.id, -32603, f'Internal error: {str(e)}'
                )

        except Exception as e:
            logger.error(f'Error processing JSON-RPC request: {e}')
            return self._create_error_response(None, -32603, 'Internal error')

    def _create_success_response(
        self, request_id: Any, result: Any
    ) -> JSONResponse:
        """Create a successful JSON-RPC response."""
        response = JSONRPCResponse(id=request_id, result=result)
        return JSONResponse(content=response.model_dump(exclude_none=True))

    def _create_error_response(
        self, request_id: Any, code: int, message: str
    ) -> JSONResponse:
        """Create an error JSON-RPC response."""
        error = JSONRPCError(code=code, message=message)
        response = JSONRPCResponse(id=request_id, error=error.model_dump())
        return JSONResponse(
            content=response.model_dump(exclude_none=True),
            status_code=400 if code != -32603 else 500,
        )

    async def _handle_send_message(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle message/send method."""
        start_time = datetime.now()

        try:
            request = SendMessageRequest.model_validate(params)
        except Exception as e:
            raise ValueError(f'Invalid parameters: {e}')

        # Log incoming message to monitoring
        message_text = ' '.join(
            [p.text for p in request.message.parts if p.kind == 'text' and p.text]
        )
        await log_agent_message(
            agent_name='External Client',
            content=message_text,
            message_type='human',
            metadata={'task_id': request.task_id, 'skill_id': request.skill_id},
        )

        # Create or get task
        if request.task_id:
            task = await self.task_manager.get_task(request.task_id)
            if not task:
                raise ValueError(f'Task not found: {request.task_id}')
        else:
            task = await self.task_manager.create_task(
                title='Message processing',
                description='Processing incoming message',
            )

        # Update task status
        await self.task_manager.update_task_status(
            task.id, TaskStatus.WORKING, request.message
        )

        # Process the message (this would be implemented by specific agents)
        response_message = await self._process_message(
            request.message, request.skill_id
        )

        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds() * 1000

        # Log agent response to monitoring
        response_text = ' '.join(
            [p.text for p in response_message.parts if p.kind == 'text' and p.text]
        )
        await log_agent_message(
            agent_name=self.agent_card.card.name,
            content=response_text,
            message_type='agent',
            metadata={'task_id': task.id, 'skill_id': request.skill_id},
            response_time=response_time,
        )

        # Update task as completed
        await self.task_manager.update_task_status(
            task.id, TaskStatus.COMPLETED, response_message, final=True
        )

        # Publish message event
        await self.message_broker.publish_message(
            'external', self.agent_card.card.name, request.message
        )

        response = SendMessageResponse(task=task, message=response_message)
        return response.model_dump(mode='json')

    async def _handle_stream_message(
        self, params: Dict[str, Any]
    ) -> StreamingResponse:
        """Handle message/stream method."""
        try:
            request = StreamMessageRequest.model_validate(params)
        except Exception as e:
            raise ValueError(f'Invalid parameters: {e}')

        # Check if streaming is supported
        if not (
            self.agent_card.card.capabilities
            and self.agent_card.card.capabilities.streaming
        ):
            raise ValueError('Streaming not supported')

        # Create task
        task = await self.task_manager.create_task(
            title='Streaming message processing',
            description='Processing streaming message',
        )

        # Create event queue for this connection
        event_queue = asyncio.Queue()
        task_id = task.id
        if task_id not in self._streaming_connections:
            self._streaming_connections[task_id] = []
        self._streaming_connections[task_id].append(event_queue)

        # Register task update handler
        async def task_update_handler(event: TaskStatusUpdateEvent):
            await event_queue.put(event)

        await self.task_manager.register_update_handler(
            task_id, task_update_handler
        )

        # Start processing in background
        asyncio.create_task(self._process_streaming_message(request, task))

        # Return streaming response
        async def generate_events():
            try:
                while True:
                    try:
                        # Wait for next event with timeout
                        event = await asyncio.wait_for(
                            event_queue.get(), timeout=30.0
                        )

                        # Format as Server-Sent Event
                        event_data = {
                            'jsonrpc': '2.0',
                            'id': task_id,
                            'result': {'event': event.model_dump(mode='json')},
                        }

                        yield f'data: {json.dumps(event_data)}\n\n'

                        # Break if this is the final event
                        if event.final:
                            break

                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield 'data: {}\n\n'

            finally:
                # Cleanup
                if task_id in self._streaming_connections:
                    try:
                        self._streaming_connections[task_id].remove(event_queue)
                        if not self._streaming_connections[task_id]:
                            del self._streaming_connections[task_id]
                    except ValueError:
                        pass

                await self.task_manager.unregister_update_handler(
                    task_id, task_update_handler
                )

        return StreamingResponse(
            generate_events(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        )

    async def _handle_get_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/get method."""
        try:
            request = GetTaskRequest.model_validate(params)
        except Exception as e:
            raise ValueError(f'Invalid parameters: {e}')

        task = await self.task_manager.get_task(request.task_id)
        if not task:
            raise ValueError(f'Task not found: {request.task_id}')

        response = GetTaskResponse(task=task)
        return response.model_dump(mode='json')

    async def _handle_cancel_task(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tasks/cancel method."""
        try:
            request = CancelTaskRequest.model_validate(params)
        except Exception as e:
            raise ValueError(f'Invalid parameters: {e}')

        task = await self.task_manager.cancel_task(request.task_id)
        if not task:
            raise ValueError(f'Task not found: {request.task_id}')

        response = CancelTaskResponse(task=task)
        return response.model_dump(mode='json')

    async def _handle_resubscribe_task(
        self, params: Dict[str, Any]
    ) -> StreamingResponse:
        """Handle tasks/resubscribe method."""
        task_id = params.get('task_id')
        if not task_id:
            raise ValueError('task_id is required')

        task = await self.task_manager.get_task(task_id)
        if not task:
            raise ValueError(f'Task not found: {task_id}')

        # This is a simplified implementation - in a real system you'd
        # need to handle reconnection to existing streams
        return await self._handle_stream_message(params)

    # ─── Push Notification Config CRUD handlers ──────────────────────────

    async def _handle_set_push_notification_config(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tasks/pushNotificationConfig/set method."""
        request = SetPushNotificationConfigRequest.model_validate(params)
        if not hasattr(self.task_manager, 'set_push_notification_config'):
            raise ValueError('Push notifications not supported by this task manager')

        task = await self.task_manager.get_task(request.task_id)
        if not task:
            raise ValueError(f'Task not found: {request.task_id}')

        result = await self.task_manager.set_push_notification_config(
            request.task_id, request.push_notification_config
        )
        return result.model_dump(by_alias=True, exclude_none=True)

    async def _handle_get_push_notification_config(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tasks/pushNotificationConfig/get method."""
        request = GetPushNotificationConfigRequest.model_validate(params)
        if not hasattr(self.task_manager, 'get_push_notification_config'):
            raise ValueError('Push notifications not supported by this task manager')

        result = await self.task_manager.get_push_notification_config(
            request.task_id, request.config_id
        )
        if not result:
            raise ValueError(f'Push notification config not found for task: {request.task_id}')
        return result.model_dump(by_alias=True, exclude_none=True)

    async def _handle_list_push_notification_configs(
        self, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Handle tasks/pushNotificationConfig/list method."""
        request = ListPushNotificationConfigsRequest.model_validate(params)
        if not hasattr(self.task_manager, 'list_push_notification_configs'):
            raise ValueError('Push notifications not supported by this task manager')

        results = await self.task_manager.list_push_notification_configs(
            request.task_id
        )
        return [r.model_dump(by_alias=True, exclude_none=True) for r in results]

    async def _handle_delete_push_notification_config(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tasks/pushNotificationConfig/delete method."""
        request = DeletePushNotificationConfigRequest.model_validate(params)
        if not hasattr(self.task_manager, 'delete_push_notification_config'):
            raise ValueError('Push notifications not supported by this task manager')

        deleted = await self.task_manager.delete_push_notification_config(
            request.task_id, request.config_id
        )
        return {'success': deleted}

    async def _process_message(
        self, message: Message, skill_id: Optional[str] = None
    ) -> Message:
        """Process an incoming message. Override this in subclasses."""
        # Default implementation - echo the message back
        response_parts = []
        for part in message.parts:
            if part.kind == 'text':
                response_parts.append(
                    Part(kind='text', text=f'Received: {part.text}')
                )
            else:
                response_parts.append(part)

        return Message(parts=response_parts)

    async def _process_streaming_message(
        self, request: StreamMessageRequest, task: Task
    ) -> None:
        """Process a streaming message with periodic updates."""
        try:
            # Update task status to working
            await self.task_manager.update_task_status(
                task.id, TaskStatus.WORKING, request.message
            )

            # Simulate processing with progress updates
            for i in range(5):
                await asyncio.sleep(1)  # Simulate work
                progress = (i + 1) / 5
                await self.task_manager.update_task_status(
                    task.id, TaskStatus.WORKING, progress=progress
                )

            # Generate final response
            response_message = await self._process_message(
                request.message, request.skill_id
            )

            # Complete the task
            await self.task_manager.update_task_status(
                task.id, TaskStatus.COMPLETED, response_message, final=True
            )

        except Exception as e:
            logger.error(f'Error processing streaming message: {e}')
            await self.task_manager.update_task_status(
                task.id, TaskStatus.FAILED, final=True
            )

    def _validate_auth(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> bool:
        """Validate authentication credentials."""
        if self.agent_card.card.authentication and self.auth_callback:
            if not credentials or not self.auth_callback(
                credentials.credentials
            ):
                return False
        return True

    async def _handle_livekit_token_request(
        self,
        token_request: LiveKitTokenRequest,
        credentials: Optional[HTTPAuthorizationCredentials],
    ) -> LiveKitTokenResponse:
        """Handle LiveKit token request with A2A authentication."""
        # Validate authentication
        if not self._validate_auth(credentials):
            raise HTTPException(
                status_code=401, detail='Authentication required'
            )

        # Check if LiveKit bridge is available
        if not self.livekit_bridge:
            raise HTTPException(
                status_code=503,
                detail='LiveKit functionality not available - bridge not configured',
            )

        try:
            # Mint access token using LiveKit bridge
            access_token = self.livekit_bridge.mint_access_token(
                identity=token_request.identity,
                room_name=token_request.room_name,
                a2a_role=token_request.role,
                metadata=token_request.metadata,
                ttl_minutes=token_request.ttl_minutes,
            )

            # Generate join URL
            join_url = self.livekit_bridge.generate_join_url(
                token_request.room_name, access_token
            )

            # Calculate expiration time
            expires_at = datetime.now() + timedelta(
                minutes=token_request.ttl_minutes
            )

            logger.info(
                f'Minted LiveKit token for {token_request.identity} in room {token_request.room_name}'
            )

            return LiveKitTokenResponse(
                access_token=access_token,
                join_url=join_url,
                expires_at=expires_at,
            )

        except Exception as e:
            logger.error(f'Failed to mint LiveKit token: {e}')
            raise HTTPException(
                status_code=500, detail=f'Failed to generate token: {str(e)}'
            )

    async def start(self, host: str = '0.0.0.0', port: int = 8000) -> None:
        """Start the A2A server."""
        # Start message broker
        await self.message_broker.start()

        # Register this agent
        await self.message_broker.register_agent(self.agent_card.card)

        logger.info(f'Starting A2A server for {self.agent_card.card.name}')
        logger.info(
            f'Agent card available at: http://{host}:{port}/.well-known/agent-card.json'
        )

        # Start the server
        config = uvicorn.Config(
            self.app, host=host, port=port, log_level='info',
            proxy_headers=True, forwarded_allow_ips='*',
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self) -> None:
        """Stop the A2A server."""
        # Unregister this agent
        await self.message_broker.unregister_agent(self.agent_card.card.name)

        # Stop message broker
        await self.message_broker.stop()

        logger.info(f'Stopped A2A server for {self.agent_card.card.name}')


# Custom agent implementations would inherit from this
class CustomA2AAgent(A2AServer):
    """Base class for custom A2A agent implementations."""

    async def _process_message(
        self, message: Message, skill_id: Optional[str] = None
    ) -> Message:
        """Override this method to implement custom message processing logic."""
        raise NotImplementedError('Subclasses must implement _process_message')
