"""
Automation API - Simple REST API for automation platforms (Zapier, n8n, Make)

This module provides a simplified REST interface for third-party automation platforms.
It wraps our existing A2A protocol with standard REST endpoints that automation platforms
can easily integrate with.

Key features:
- Simple POST /v1/automation/tasks to create tasks
- GET /v1/automation/tasks/{id} to poll for status
- Async execution with webhook callbacks
- Idempotency support via Idempotency-Key header
- Rate limiting headers
- Webhook signature verification
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, HttpUrl

from .database import get_pool
from .task_queue import enqueue_task, TaskRunStatus
from .keycloak_auth import require_auth, UserSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/automation', tags=['Automation API'])


# ========================================
# Configuration
# ========================================

# Webhook signing secret (set via env var)
WEBHOOK_SECRET = None

# Rate limit defaults
DEFAULT_RATE_LIMIT = 60  # requests per minute


# ========================================
# Enums
# ========================================


class TaskStatus(str, Enum):
    """Task execution status."""

    QUEUED = 'queued'
    RUNNING = 'running'
    NEEDS_INPUT = 'needs_input'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class AgentType(str, Enum):
    """Agent type for execution."""

    BUILD = 'build'
    PLAN = 'plan'
    GENERAL = 'general'
    EXPLORE = 'explore'


class ModelType(str, Enum):
    """Supported model types."""

    DEFAULT = 'default'
    CLAUDE_SONNET = 'claude-sonnet'
    CLAUDE_SONNET_4 = 'claude-sonnet-4'
    SONNET = 'sonnet'
    CLAUDE_OPUS = 'claude-opus'
    OPUS = 'opus'
    CLAUDE_HAIKU = 'haiku'
    HAIKU = 'claude-haiku'
    MINIMAX = 'minimax'
    MINIMAX_M2 = 'minimax-m2'
    MINIMAX_M2_1 = 'minimax-m2.1'
    M2_1 = 'm2.1'
    GPT_4 = 'gpt-4'
    GPT_4O = 'gpt-4o'
    GPT_4_TURBO = 'gpt-4-turbo'
    GPT_4_1 = 'gpt-4.1'
    O1 = 'o1'
    O1_MINI = 'o1-mini'
    O3 = 'o3'
    O3_MINI = 'o3-mini'
    GEMINI = 'gemini'
    GEMINI_PRO = 'gemini-pro'
    GEMINI_2_5_PRO = 'gemini-2.5-pro'
    GEMINI_FLASH = 'gemini-flash'
    GEMINI_2_5_FLASH = 'gemini-2.5-flash'
    GROK = 'grok'
    GROK_3 = 'grok-3'


# ========================================
# Request/Response Models
# ========================================


class CreateTaskRequest(BaseModel):
    """Request to create a new automation task."""

    title: str = Field(
        ..., description='Title of the task', min_length=1, max_length=200
    )
    description: str = Field(
        ...,
        description='Task description/prompt',
        min_length=10,
        max_length=10000,
    )
    agent_type: AgentType = Field(
        default=AgentType.BUILD, description='Type of agent to use'
    )
    model: ModelType = Field(
        default=ModelType.DEFAULT, description='Model to use for execution'
    )
    codebase_id: str = Field(
        default='global', description='Codebase ID to work with'
    )
    priority: int = Field(
        default=0, ge=0, le=100, description='Priority (higher = more urgent)'
    )
    webhook_url: Optional[HttpUrl] = Field(
        default=None, description='Webhook URL to call on task completion'
    )
    notify_email: Optional[EmailStr] = Field(
        default=None, description='Email address to notify on completion'
    )


class TaskResponse(BaseModel):
    """Task response."""

    task_id: str = Field(..., description='Unique task identifier')
    run_id: str = Field(..., description='Task run identifier')
    status: TaskStatus = Field(..., description='Current task status')
    title: str = Field(..., description='Task title')
    description: str = Field(..., description='Task description')
    created_at: str = Field(
        ..., description='ISO timestamp when task was created'
    )
    started_at: Optional[str] = Field(
        None, description='ISO timestamp when task started'
    )
    completed_at: Optional[str] = Field(
        None, description='ISO timestamp when task completed'
    )
    runtime_seconds: Optional[int] = Field(
        None, description='Runtime in seconds (if completed)'
    )
    result_summary: Optional[str] = Field(
        None, description='Summary of the result (if completed)'
    )
    error: Optional[str] = Field(None, description='Error message (if failed)')
    model: Optional[str] = Field(None, description='Model used for execution')


class TaskListResponse(BaseModel):
    """List of tasks response."""

    tasks: List[TaskResponse] = Field(..., description='List of tasks')
    total: int = Field(..., description='Total count')
    limit: int = Field(..., description='Limit applied')
    offset: int = Field(..., description='Offset applied')


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description='Error type')
    message: str = Field(..., description='Human-readable error message')
    details: Optional[Dict[str, Any]] = Field(
        None, description='Additional error details'
    )


# ========================================
# Rate Limiting
# ========================================


@dataclass
class RateLimitInfo:
    """Rate limit tracking info."""

    requests_remaining: int
    limit: int
    reset_at: datetime


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self._requests: Dict[str, List[datetime]] = {}

    async def check(
        self, identifier: str, limit: int = DEFAULT_RATE_LIMIT
    ) -> RateLimitInfo:
        """Check if request is allowed.

        Returns:
            RateLimitInfo with current state
        """
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)

        if identifier not in self._requests:
            self._requests[identifier] = []

        # Clean old requests
        self._requests[identifier] = [
            ts for ts in self._requests[identifier] if ts > minute_ago
        ]

        requests_count = len(self._requests[identifier])
        requests_remaining = max(0, limit - requests_count)

        # Find reset time (oldest request + 1 minute)
        reset_at = now
        if self._requests[identifier]:
            oldest = min(self._requests[identifier])
            reset_at = oldest + timedelta(minutes=1)

        if requests_count >= limit:
            # Rate limit exceeded
            return RateLimitInfo(
                requests_remaining=0, limit=limit, reset_at=reset_at
            )

        # Add this request
        self._requests[identifier].append(now)

        return RateLimitInfo(
            requests_remaining=requests_remaining - 1,
            limit=limit,
            reset_at=reset_at,
        )


# Global rate limiter
_rate_limiter = RateLimiter()


def get_client_identifier(request: Request) -> str:
    """Get a unique identifier for rate limiting."""
    # Try API key first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        api_key = auth_header[7:]
        if api_key.startswith('ct_'):
            return api_key

    # Fall back to IP
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()

    return request.client.host if request.client else 'unknown'


# ========================================
# Idempotency
# ========================================


@dataclass
class IdempotencyKey:
    """Idempotency key storage."""

    task_id: str
    run_id: str
    response: Dict[str, Any]
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class IdempotencyStore:
    """In-memory store for idempotency keys."""

    def __init__(self):
        self._store: Dict[str, IdempotencyKey] = {}

    def get(self, key: str) -> Optional[IdempotencyKey]:
        """Get stored response for key."""
        # Keys expire after 48 hours
        if key in self._store:
            entry = self._store[key]
            if datetime.now(timezone.utc) - entry.created_at < timedelta(
                hours=48
            ):
                return entry
            else:
                del self._store[key]
        return None

    def set(
        self, key: str, task_id: str, run_id: str, response: Dict[str, Any]
    ) -> None:
        """Store response for key."""
        self._store[key] = IdempotencyKey(
            task_id=task_id, run_id=run_id, response=response
        )


_global_idempotency_store = IdempotencyStore()


# ========================================
# Webhook Signature
# ========================================


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return (
        'sha256='
        + hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
    )


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature."""
    expected = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(signature, expected)


# ========================================
# API Endpoints
# ========================================


@router.post(
    '/tasks',
    response_model=TaskResponse,
    status_code=201,
    responses={429: {'model': ErrorResponse}, 409: {'model': ErrorResponse}},
)
async def create_task(
    request: CreateTaskRequest,
    http_request: Request,
    user: UserSession = Depends(require_auth),
    idempotency_key: Optional[str] = Header(None, alias='Idempotency-Key'),
):
    """Create a new automation task.

    This endpoint creates a task for async execution. The task will be queued
    and executed by available workers.

    Use the `webhook_url` parameter to receive a callback when the task completes.
    Alternatively, poll the `/tasks/{task_id}` endpoint for status updates.

    **Idempotency**: To avoid duplicate tasks on retries, include an
    `Idempotency-Key` header with a unique value (e.g., a UUID). Requests
    with the same key will return the same task id.

    **Rate Limiting**: 60 requests per minute per API key/IP.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    # Get client identifier for rate limiting
    client_id = get_client_identifier(http_request)
    rate_info = await _rate_limiter.check(client_id)

    if rate_info.requests_remaining <= 0:
        headers = {
            'X-RateLimit-Limit': str(rate_info.limit),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': str(int(rate_info.reset_at.timestamp())),
            'Retry-After': str(
                int(
                    (
                        rate_info.reset_at - datetime.now(timezone.utc)
                    ).total_seconds()
                )
            ),
        }
        raise HTTPException(
            status_code=429,
            detail={
                'error': 'rate_limit_exceeded',
                'message': 'Too many requests. Please retry later.',
            },
            headers=headers,
        )

    # Check idempotency key
    if idempotency_key:
        existing = _global_idempotency_store.get(idempotency_key)
        if existing:
            headers = {
                'X-RateLimit-Limit': str(rate_info.limit),
                'X-RateLimit-Remaining': str(rate_info.requests_remaining),
                'X-RateLimit-Reset': str(int(rate_info.reset_at.timestamp())),
            }
            return JSONResponse(
                status_code=200,
                headers=headers,
                content={
                    **existing.response,
                    '_idempotent_replay': 'true',
                },
            )

    # Generate task ID
    task_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    # Create task in database
    # Use NULL for codebase_id if it's 'global' (no codebase context)
    codebase_id = (
        request.codebase_id if request.codebase_id != 'global' else None
    )

    # Get tenant_id from authenticated user
    tenant_id = user.tenant_id
    user_id = user.user_id

    async with pool.acquire() as conn:
        # Set tenant context for RLS
        if tenant_id:
            await conn.execute(
                f"SET LOCAL app.current_tenant_id = '{tenant_id}'"
            )

        await conn.execute(
            """
            INSERT INTO tasks (id, title, prompt, agent_type, codebase_id, status, metadata, tenant_id, model, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6::jsonb, $7, $8, NOW(), NOW())
            """,
            task_id,
            request.title,
            request.description,
            request.agent_type.value,
            codebase_id,
            json.dumps(
                {'model': request.model.value}
            ),  # Store model in metadata as JSON string
            tenant_id,
            request.model.value,
        )

    # Enqueue task for execution
    task_run = await enqueue_task(
        task_id=task_id,
        user_id=user_id,
        tenant_id=tenant_id,
        priority=request.priority,
        notify_email=request.notify_email or user.email,
        notify_webhook_url=str(request.webhook_url)
        if request.webhook_url
        else None,
    )

    if not task_run:
        logger.warning(f'Failed to enqueue task {task_id}')
        raise HTTPException(status_code=503, detail='Failed to queue task')

    # Store idempotency key
    response_data = {
        'task_id': task_id,
        'run_id': task_run.id,
        'status': TaskStatus.QUEUED.value,
        'title': request.title,
        'description': request.description,
        'created_at': task_run.created_at.isoformat(),
        'model': request.model.value,
    }

    if idempotency_key:
        _global_idempotency_store.set(
            idempotency_key, task_id, task_run.id, response_data
        )

    headers = {
        'X-RateLimit-Limit': str(rate_info.limit),
        'X-RateLimit-Remaining': str(rate_info.requests_remaining),
        'X-RateLimit-Reset': str(int(rate_info.reset_at.timestamp())),
    }

    return JSONResponse(status_code=201, headers=headers, content=response_data)


@router.get(
    '/tasks/{task_id}',
    response_model=TaskResponse,
    responses={404: {'model': ErrorResponse}},
)
async def get_task(
    task_id: str,
    http_request: Request,
    user: UserSession = Depends(require_auth),
):
    """Get the current status of a task.

    Use this endpoint to poll for task status when you didn't provide a webhook URL.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    # Get client identifier for rate limiting
    client_id = get_client_identifier(http_request)
    rate_info = await _rate_limiter.check(client_id)

    # Get task and run info (filtered by tenant)
    tenant_id = user.tenant_id
    async with pool.acquire() as conn:
        # Set tenant context for RLS
        if tenant_id:
            await conn.execute(
                f"SET LOCAL app.current_tenant_id = '{tenant_id}'"
            )

        row = await conn.fetchrow(
            """
            SELECT 
                t.id as task_id,
                t.title,
                t.prompt as description,
                t.status,
                t.created_at,
                tr.id as run_id,
                tr.status as run_status,
                tr.started_at,
                tr.completed_at,
                tr.runtime_seconds,
                tr.result_summary,
                tr.last_error as error,
                t.model
            FROM tasks t
            LEFT JOIN task_runs tr ON tr.task_id = t.id
            WHERE t.id = $1
              AND (t.tenant_id = $2 OR t.tenant_id IS NULL)
            ORDER BY tr.created_at DESC
            LIMIT 1
            """,
            task_id,
            tenant_id,
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail={'error': 'not_found', 'message': 'Task not found'},
        )

    # Map run_status to TaskStatus
    status_map = {
        'queued': TaskStatus.QUEUED,
        'running': TaskStatus.RUNNING,
        'needs_input': TaskStatus.NEEDS_INPUT,
        'completed': TaskStatus.COMPLETED,
        'failed': TaskStatus.FAILED,
        'cancelled': TaskStatus.CANCELLED,
    }

    task_status = status_map.get(
        row['run_status'] or row['status'], TaskStatus.QUEUED
    )

    response_data = {
        'task_id': row['task_id'],
        'run_id': row['run_id'] or '',
        'status': task_status.value,
        'title': row['title'],
        'description': row['description'],
        'created_at': row['created_at'].isoformat(),
        'started_at': row['started_at'].isoformat()
        if row['started_at']
        else None,
        'completed_at': row['completed_at'].isoformat()
        if row['completed_at']
        else None,
        'runtime_seconds': row['runtime_seconds'],
        'result_summary': row['result_summary'],
        'error': row['error'],
        'model': row['model'],
    }

    headers = {
        'X-RateLimit-Limit': str(rate_info.limit),
        'X-RateLimit-Remaining': str(rate_info.requests_remaining),
        'X-RateLimit-Reset': str(int(rate_info.reset_at.timestamp())),
    }

    return JSONResponse(headers=headers, content=response_data)


@router.get('/tasks', response_model=TaskListResponse)
async def list_tasks(
    http_request: Request,
    user: UserSession = Depends(require_auth),
    status: Optional[TaskStatus] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List tasks with optional filtering.

    **Note:** This endpoint is primarily for historical reference.
    For newly created tasks, use the webhook callback pattern.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    # Get client identifier for rate limiting
    client_id = get_client_identifier(http_request)
    rate_info = await _rate_limiter.check(client_id)

    # Get tenant_id from user for filtering
    tenant_id = user.tenant_id

    # Build query with tenant isolation
    conditions = ['(tr.tenant_id = $1 OR tr.tenant_id IS NULL)']
    params = [tenant_id]
    param_idx = 2

    if status:
        conditions.append(f'tr.status = ${param_idx}')
        params.append(status.value)
        param_idx += 1

    where_clause = ' AND '.join(conditions)

    # Get count
    async with pool.acquire() as conn:
        # Set tenant context for RLS
        if tenant_id:
            await conn.execute(
                f"SET LOCAL app.current_tenant_id = '{tenant_id}'"
            )

        count = await conn.fetchval(
            f"""
            SELECT COUNT(*)
            FROM task_runs tr
            LEFT JOIN tasks t ON t.id = tr.task_id
            WHERE {where_clause}
            """,
            *params,
        )

        # Get tasks
        rows = await conn.fetch(
            f"""
            SELECT 
                t.id as task_id,
                t.title,
                t.prompt as description,
                tr.id as run_id,
                tr.status as run_status,
                tr.created_at,
                tr.started_at,
                tr.completed_at,
                tr.runtime_seconds,
                tr.result_summary,
                tr.last_error as error
            FROM task_runs tr
            LEFT JOIN tasks t ON t.id = tr.task_id
            WHERE {where_clause}
            ORDER BY tr.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    status_map = {
        'queued': TaskStatus.QUEUED,
        'running': TaskStatus.RUNNING,
        'needs_input': TaskStatus.NEEDS_INPUT,
        'completed': TaskStatus.COMPLETED,
        'failed': TaskStatus.FAILED,
        'cancelled': TaskStatus.CANCELLED,
    }

    tasks = []
    for row in rows:
        task_status = status_map.get(row['run_status'], TaskStatus.QUEUED)
        tasks.append(
            {
                'task_id': row['task_id'],
                'run_id': row['run_id'],
                'status': task_status.value,
                'title': row['title'],
                'description': row['description'],
                'created_at': row['created_at'].isoformat(),
                'started_at': row['started_at'].isoformat()
                if row['started_at']
                else None,
                'completed_at': row['completed_at'].isoformat()
                if row['completed_at']
                else None,
                'runtime_seconds': row['runtime_seconds'],
                'result_summary': row['result_summary'],
                'error': row['error'],
                'model': None,
            }
        )

    headers = {
        'X-RateLimit-Limit': str(rate_info.limit),
        'X-RateLimit-Remaining': str(rate_info.requests_remaining),
        'X-RateLimit-Reset': str(int(rate_info.reset_at.timestamp())),
    }

    return JSONResponse(
        headers=headers,
        content={
            'tasks': tasks,
            'total': count,
            'limit': limit,
            'offset': offset,
        },
    )


@router.get('/')
async def api_info():
    """Get API information and capabilities.

    Returns information about available endpoints, rate limits,
    and webhook events supported.
    """
    return {
        'name': 'CodeTether Automation API',
        'version': '1.0.0',
        'description': 'Simple REST API for AI-powered task automation',
        'base_url': '/v1/automation',
        'endpoints': {
            'POST /tasks': 'Create a new automation task',
            'GET /tasks/{task_id}': 'Get task status by ID',
            'GET /tasks': 'List tasks with filtering',
        },
        'rate_limits': {
            'default': f'{DEFAULT_RATE_LIMIT} requests per minute',
            'headers': [
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset',
            ],
        },
        'webhook': {
            'description': 'Optional webhook callback on task completion',
            'webhook_url_parameter': 'Provide in POST /tasks request',
            'signature': 'HMAC-SHA256 signature in X-CodeTether-Signature header',
            'events': [
                'task_started',
                'task_progress',
                'task_completed',
                'task_failed',
                'task_needs_input',
            ],
        },
        'idempotency': {
            'description': 'Prevent duplicate task creation on retries',
            'header': 'Idempotency-Key',
            'example': 'Idempotency-Key: <uuid>',
        },
        'authentication': {
            'description': 'Optional API key or OAuth 2.0 token',
            'header': 'Authorization: Bearer <token>',
            'oauth_flows': ['authorization_code'],
        },
        'models': [m.value for m in ModelType],
        'agent_types': [t.value for t in AgentType],
    }


# ========================================
# User Info Endpoint (for Zapier OAuth test)
# ========================================


class UserInfoResponse(BaseModel):
    """User info response for OAuth test."""

    id: str = Field(..., description='User ID')
    email: Optional[str] = Field(None, description='User email')
    name: Optional[str] = Field(None, description='User display name')
    authenticated: bool = Field(
        ..., description='Whether user is authenticated'
    )


@router.get(
    '/me',
    response_model=UserInfoResponse,
    summary='Get current user info',
    description='Returns information about the authenticated user. Used by Zapier to test OAuth connection.',
    responses={
        200: {'description': 'User info retrieved successfully'},
        401: {'description': 'Not authenticated'},
    },
)
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """
    Get current user information.

    This endpoint is used by Zapier and other OAuth clients to verify
    that authentication is working and to get basic user info.
    """
    # Extract token from Authorization header
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'unauthorized',
                'message': 'Missing Authorization header',
            },
        )

    if not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'unauthorized',
                'message': 'Invalid Authorization header format',
            },
        )

    token = authorization[7:]  # Remove 'Bearer ' prefix

    # Validate token with Keycloak
    try:
        import os
        import httpx

        keycloak_url = os.environ.get(
            'KEYCLOAK_URL', 'https://auth.quantum-forge.io'
        )
        realm = os.environ.get('KEYCLOAK_REALM', 'quantum-forge')

        # Call Keycloak userinfo endpoint to validate token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'{keycloak_url}/realms/{realm}/protocol/openid-connect/userinfo',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10,
            )

            if response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail={
                        'error': 'unauthorized',
                        'message': 'Invalid or expired token',
                    },
                )

            if response.status_code != 200:
                logger.error(
                    f'Keycloak userinfo failed: {response.status_code} - {response.text}'
                )
                raise HTTPException(
                    status_code=500,
                    detail={
                        'error': 'server_error',
                        'message': 'Failed to validate token',
                    },
                )

            user_info = response.json()

            return UserInfoResponse(
                id=user_info.get('sub', 'unknown'),
                email=user_info.get('email'),
                name=user_info.get('name')
                or user_info.get('preferred_username'),
                authenticated=True,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error validating token: {e}')
        raise HTTPException(
            status_code=500,
            detail={
                'error': 'server_error',
                'message': 'Failed to validate authentication',
            },
        )


# Additional import needed for timedelta
from datetime import timedelta
