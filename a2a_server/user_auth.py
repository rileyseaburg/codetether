"""
Self-service user authentication for mid-market/consumer users.

This module provides email/password authentication that bypasses Keycloak,
designed for self-service signups from the Zapier/ClickFunnels market.

Features:
- Email/password registration with verification
- JWT token-based sessions
- Password reset flow
- API key generation
- Usage tracking/limits
"""

import os
import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import bcrypt
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
    OAuth2PasswordRequestForm,
)

from .database import get_pool

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_urlsafe(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))

# Security
security = HTTPBearer(auto_error=False)

router = APIRouter(prefix='/v1/users', tags=['User Authentication'])


# ========================================
# Request/Response Models
# ========================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    referral_source: Optional[str] = None


class RegisterResponse(BaseModel):
    """Registration response."""

    user_id: str
    email: str
    message: str


class LoginRequest(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT tokens."""

    access_token: str
    token_type: str = 'bearer'
    expires_at: str
    user: Dict[str, Any]


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    status: str
    email_verified: bool
    tasks_used_this_month: int
    tasks_limit: int
    created_at: str


class PasswordResetRequest(BaseModel):
    """Request password reset."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token."""

    token: str
    new_password: str = Field(..., min_length=8)


class CreateApiKeyRequest(BaseModel):
    """Create API key request."""

    name: str
    scopes: Optional[List[str]] = None
    expires_in_days: Optional[int] = None  # None = never expires


class ApiKeyResponse(BaseModel):
    """API key response (key only shown once!)."""

    id: str
    name: str
    key: str  # Only returned on creation
    key_prefix: str
    scopes: List[str]
    created_at: str
    expires_at: Optional[str]


# ========================================
# Password Hashing
# ========================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode(
        'utf-8'
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        password.encode('utf-8'), password_hash.encode('utf-8')
    )


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA256."""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


# ========================================
# JWT Token Management
# ========================================


def create_access_token(
    user_id: str, email: str, expires_delta: Optional[timedelta] = None
) -> tuple[str, datetime]:
    """Create a JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(hours=JWT_EXPIRATION_HOURS)

    expires_at = datetime.utcnow() + expires_delta

    payload = {
        'sub': user_id,
        'email': email,
        'type': 'access',
        'exp': expires_at,
        'iat': datetime.utcnow(),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'access':
            raise HTTPException(status_code=401, detail='Invalid token type')
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {str(e)}')


# ========================================
# Current User Dependency
# ========================================


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Get current authenticated user from JWT or API key."""
    if not credentials:
        return None

    token = credentials.credentials

    # Check if it's an API key (starts with 'ct_')
    if token.startswith('ct_'):
        return await _get_user_from_api_key(token)

    # Otherwise treat as JWT
    try:
        payload = decode_access_token(token)
        user = await get_user_by_id(payload['sub'])
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        if user['status'] != 'active':
            raise HTTPException(status_code=401, detail='Account is not active')
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Token validation error: {e}')
        raise HTTPException(status_code=401, detail='Invalid token')


async def require_user(
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Require authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    return user


async def _get_user_from_api_key(api_key: str) -> Dict[str, Any]:
    """Validate API key and return associated user."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    key_hash = hash_api_key(api_key)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ak.*, u.*
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.key_hash = $1 AND ak.status = 'active'
        """,
            key_hash,
        )

        if not row:
            raise HTTPException(status_code=401, detail='Invalid API key')

        # Check expiration
        if row['expires_at'] and row['expires_at'] < datetime.utcnow():
            raise HTTPException(status_code=401, detail='API key expired')

        # Update last used
        await conn.execute(
            'UPDATE api_keys SET last_used_at = NOW() WHERE id = $1', row['id']
        )

        return {
            'id': row['user_id'],
            'email': row['email'],
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'status': row['status'],
            'tasks_used_this_month': row['tasks_used_this_month'],
            'tasks_limit': row['tasks_limit'],
            'api_key_scopes': row['scopes'],
        }


# ========================================
# Database Operations
# ========================================


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email."""
    pool = await get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM users WHERE email = $1', email.lower()
        )
        return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    pool = await get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM users WHERE id = $1', user_id)
        return dict(row) if row else None


async def create_user(
    email: str,
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    referral_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new user."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    user_id = f'user_{uuid.uuid4().hex[:16]}'
    password_hash = hash_password(password)
    verification_token = secrets.token_urlsafe(32)
    verification_expires = datetime.utcnow() + timedelta(hours=24)

    async with pool.acquire() as conn:
        # Check if email exists
        existing = await conn.fetchval(
            'SELECT id FROM users WHERE email = $1', email.lower()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail='Email already registered'
            )

        # Create user
        await conn.execute(
            """
            INSERT INTO users (
                id, email, password_hash, first_name, last_name,
                status, email_verified, email_verification_token, email_verification_expires,
                referral_source, tasks_limit
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            user_id,
            email.lower(),
            password_hash,
            first_name,
            last_name,
            'active',  # Skip email verification for MVP - activate immediately
            True,  # Mark as verified for MVP
            verification_token,
            verification_expires,
            referral_source,
            10,  # Free tier: 10 tasks/month
        )

        return {
            'id': user_id,
            'email': email.lower(),
            'first_name': first_name,
            'last_name': last_name,
            'verification_token': verification_token,
        }


async def update_user_login(user_id: str) -> None:
    """Update user's last login timestamp."""
    pool = await get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE users SET last_login_at = NOW() WHERE id = $1', user_id
        )


async def increment_task_usage(user_id: str) -> bool:
    """Increment user's task usage. Returns True if within limit."""
    pool = await get_pool()
    if not pool:
        return False

    async with pool.acquire() as conn:
        # Atomic increment and check
        result = await conn.fetchrow(
            """
            UPDATE users
            SET tasks_used_this_month = tasks_used_this_month + 1,
                updated_at = NOW()
            WHERE id = $1
            RETURNING tasks_used_this_month, tasks_limit
        """,
            user_id,
        )

        if result:
            return result['tasks_used_this_month'] <= result['tasks_limit']
        return False


# ========================================
# API Endpoints
# ========================================


@router.post('/register', response_model=RegisterResponse)
async def register(request: RegisterRequest, background_tasks: BackgroundTasks):
    """
    Register a new user account.

    Creates a new user with email/password authentication.
    For MVP, accounts are activated immediately without email verification.
    """
    try:
        user = await create_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            referral_source=request.referral_source,
        )

        # TODO: Send welcome email in background
        # background_tasks.add_task(send_welcome_email, user['email'], user['first_name'])

        logger.info(f'New user registered: {user["email"]}')

        return RegisterResponse(
            user_id=user['id'],
            email=user['email'],
            message='Account created successfully. You can now log in.',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Registration error: {e}')
        raise HTTPException(status_code=500, detail='Registration failed')


@router.post('/login', response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.

    Returns a JWT access token for subsequent API calls.
    """
    user = await get_user_by_email(request.email)

    if not user:
        raise HTTPException(status_code=401, detail='Invalid email or password')

    if not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid email or password')

    if user['status'] != 'active':
        if user['status'] == 'pending_verification':
            raise HTTPException(
                status_code=401, detail='Please verify your email first'
            )
        raise HTTPException(status_code=401, detail='Account is not active')

    # Create access token
    access_token, expires_at = create_access_token(user['id'], user['email'])

    # Update last login
    await update_user_login(user['id'])

    logger.info(f'User logged in: {user["email"]}')

    return LoginResponse(
        access_token=access_token,
        expires_at=expires_at.isoformat(),
        user={
            'id': user['id'],
            'email': user['email'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'tasks_used_this_month': user['tasks_used_this_month'],
            'tasks_limit': user['tasks_limit'],
        },
    )


@router.get('/me', response_model=UserResponse)
async def get_me(user: Dict[str, Any] = Depends(require_user)):
    """Get current user profile."""
    return UserResponse(
        id=user['id'],
        email=user['email'],
        first_name=user.get('first_name'),
        last_name=user.get('last_name'),
        status=user['status'],
        email_verified=user.get('email_verified', False),
        tasks_used_this_month=user['tasks_used_this_month'],
        tasks_limit=user['tasks_limit'],
        created_at=user['created_at'].isoformat()
        if user.get('created_at')
        else '',
    )


@router.post('/password-reset/request')
async def request_password_reset(
    request: PasswordResetRequest, background_tasks: BackgroundTasks
):
    """
    Request a password reset email.

    Always returns success to prevent email enumeration.
    """
    user = await get_user_by_email(request.email)

    if user:
        pool = await get_pool()
        if pool:
            reset_token = secrets.token_urlsafe(32)
            reset_expires = datetime.utcnow() + timedelta(hours=1)

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE users
                    SET password_reset_token = $1, password_reset_expires = $2
                    WHERE id = $3
                """,
                    reset_token,
                    reset_expires,
                    user['id'],
                )

            # TODO: Send password reset email
            # background_tasks.add_task(send_password_reset_email, user['email'], reset_token)
            logger.info(f'Password reset requested for: {user["email"]}')

    return {
        'message': 'If that email exists, a password reset link has been sent.'
    }


@router.post('/password-reset/confirm')
async def confirm_password_reset(request: PasswordResetConfirm):
    """Confirm password reset with token."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id FROM users
            WHERE password_reset_token = $1
            AND password_reset_expires > NOW()
        """,
            request.token,
        )

        if not user:
            raise HTTPException(
                status_code=400, detail='Invalid or expired reset token'
            )

        # Update password
        new_hash = hash_password(request.new_password)
        await conn.execute(
            """
            UPDATE users
            SET password_hash = $1,
                password_reset_token = NULL,
                password_reset_expires = NULL,
                updated_at = NOW()
            WHERE id = $2
        """,
            new_hash,
            user['id'],
        )

    return {'message': 'Password updated successfully'}


@router.post('/api-keys', response_model=ApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    user: Dict[str, Any] = Depends(require_user),
):
    """
    Create a new API key for programmatic access.

    The full key is only shown once! Store it securely.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    # Generate API key
    key_id = f'key_{uuid.uuid4().hex[:12]}'
    raw_key = f'ct_{secrets.token_urlsafe(32)}'
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:11]  # 'ct_' + 8 chars

    scopes = request.scopes or ['tasks:read', 'tasks:write']
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO api_keys (id, user_id, name, key_hash, key_prefix, scopes, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
            key_id,
            user['id'],
            request.name,
            key_hash,
            key_prefix,
            scopes,
            expires_at,
        )

    logger.info(f'API key created for user {user["id"]}: {key_prefix}...')

    return ApiKeyResponse(
        id=key_id,
        name=request.name,
        key=raw_key,  # Only time the full key is shown!
        key_prefix=key_prefix,
        scopes=scopes,
        created_at=datetime.utcnow().isoformat(),
        expires_at=expires_at.isoformat() if expires_at else None,
    )


@router.get('/api-keys')
async def list_api_keys(user: Dict[str, Any] = Depends(require_user)):
    """List all API keys for the current user."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, key_prefix, scopes, status, created_at, expires_at, last_used_at
            FROM api_keys
            WHERE user_id = $1
            ORDER BY created_at DESC
        """,
            user['id'],
        )

    return [
        {
            'id': row['id'],
            'name': row['name'],
            'key_prefix': row['key_prefix'],
            'scopes': row['scopes'],
            'status': row['status'],
            'created_at': row['created_at'].isoformat()
            if row['created_at']
            else None,
            'expires_at': row['expires_at'].isoformat()
            if row['expires_at']
            else None,
            'last_used_at': row['last_used_at'].isoformat()
            if row['last_used_at']
            else None,
        }
        for row in rows
    ]


@router.delete('/api-keys/{key_id}')
async def revoke_api_key(
    key_id: str, user: Dict[str, Any] = Depends(require_user)
):
    """Revoke an API key."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_keys
            SET status = 'revoked'
            WHERE id = $1 AND user_id = $2
        """,
            key_id,
            user['id'],
        )

        if 'UPDATE 0' in result:
            raise HTTPException(status_code=404, detail='API key not found')

    return {'message': 'API key revoked'}


# ========================================
# Usage Tracking Middleware
# ========================================


async def check_usage_limit(
    user: Dict[str, Any] = Depends(require_user),
) -> Dict[str, Any]:
    """Check if user is within their usage limit."""
    if user['tasks_used_this_month'] >= user['tasks_limit']:
        raise HTTPException(
            status_code=429,
            detail={
                'error': 'Usage limit exceeded',
                'used': user['tasks_used_this_month'],
                'limit': user['tasks_limit'],
                'message': 'Upgrade to Pro for unlimited tasks',
            },
        )
    return user
