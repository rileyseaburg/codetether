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
from .provisioning_service import provision_instance_for_new_user

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_urlsafe(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))

# Keycloak Configuration (for validating Keycloak-issued tokens)
KEYCLOAK_ISSUER = os.environ.get(
    'KEYCLOAK_ISSUER', 'https://auth.quantum-forge.io/realms/quantum-forge'
)
KEYCLOAK_JWKS_URL = f'{KEYCLOAK_ISSUER}/protocol/openid-connect/certs'

# Cache for Keycloak JWKS
_keycloak_jwks_client = None

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
    tenant_id: Optional[str] = None
    realm_name: Optional[str] = None
    # Kubernetes instance info
    instance_url: Optional[str] = None
    instance_namespace: Optional[str] = None
    provisioning_status: str = 'pending'


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
    """Decode and validate a JWT access token (HS256 self-issued or RS256 Keycloak)."""
    try:
        # First try HS256 (self-issued tokens)
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'access':
            raise HTTPException(status_code=401, detail='Invalid token type')
        return payload
    except JWTError:
        # Fall back to Keycloak RS256 token validation
        return decode_keycloak_token(token)


def _parse_realm_from_issuer(issuer: Optional[str]) -> Optional[str]:
    """Extract Keycloak realm from issuer URL."""
    if not issuer or '/realms/' not in issuer:
        return None
    realm_part = issuer.split('/realms/', 1)[1]
    realm_name = realm_part.split('/', 1)[0].strip()
    return realm_name or None


def _normalize_keycloak_identity(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Normalize user identity claims from Keycloak payloads.

    Handles common cases where `sub` or `email` are missing from access tokens by
    deriving stable fallbacks.
    """
    subject = (
        payload.get('sub')
        or payload.get('sid')
        or payload.get('jti')
        or payload.get('user_id')
        or payload.get('id')
    )
    email = (
        payload.get('email')
        or payload.get('preferred_username')
        or payload.get('upn')
    )

    # If subject is missing but we have an email/username, derive a stable ID.
    if not subject and email:
        subject = f'keycloak:{hashlib.sha256(email.encode()).hexdigest()[:24]}'

    # If email is missing but we have a subject, provide a deterministic fallback.
    if not email and subject:
        email = f'{subject}@keycloak.local'

    return {
        'sub': subject,
        'email': email,
        'realm_name': _parse_realm_from_issuer(payload.get('iss')),
    }


def _decode_keycloak_token_unverified(token: str) -> Dict[str, Any]:
    """
    Decode a Keycloak token WITHOUT signature verification.

    WARNING: This is INSECURE and should only be used in dev environments
    where the backend cannot reach Keycloak's JWKS endpoint.

    Enable by setting ALLOW_UNVERIFIED_KEYCLOAK_TOKENS=true
    """
    from jose import jwt as jose_jwt

    logger.warning(
        'SECURITY WARNING: Decoding Keycloak token without verification!'
    )

    try:
        # Log token info for debugging
        token_parts = token.split('.')
        logger.warning(f'Token has {len(token_parts)} parts')
        logger.warning(f'Token prefix: {token[:100]}...')

        if len(token_parts) != 3:
            logger.error(
                f'Invalid JWT format: expected 3 parts, got {len(token_parts)}'
            )
            raise HTTPException(
                status_code=401, detail='Invalid token format - not a JWT'
            )

        # Decode without verification
        payload = jose_jwt.get_unverified_claims(token)
        logger.warning(f'Decoded payload keys: {list(payload.keys())}')
        logger.warning(
            f'Payload: sub={payload.get("sub")}, email={payload.get("email")}, iss={payload.get("iss")}'
        )

        identity = _normalize_keycloak_identity(payload)
        subject = identity.get('sub')
        email = identity.get('email')

        if not subject:
            logger.error(
                f'No subject found in token. Available claims: {list(payload.keys())}'
            )
            raise HTTPException(
                status_code=401, detail='Token missing subject claim'
            )
        if not email:
            logger.error(
                f'No email found in token. Available claims: {list(payload.keys())}'
            )
            raise HTTPException(
                status_code=401, detail='Token missing email claim'
            )

        logger.info(f'Token validated for user: {email} (sub: {subject})')

        # Update payload with found values
        payload['sub'] = subject
        payload['email'] = email

        # Check expiration manually (skip in dev mode with unverified tokens)
        exp = payload.get('exp')
        if exp:
            from datetime import datetime

            if datetime.utcnow().timestamp() > exp:
                # In dev mode, just warn about expired tokens but allow them
                logger.warning(
                    f'Token expired at {exp}, but allowing due to ALLOW_UNVERIFIED_KEYCLOAK_TOKENS=true'
                )

        return {
            'sub': subject,
            'email': email,
            'type': 'keycloak',
            'exp': payload.get('exp'),
            'iat': payload.get('iat'),
            'preferred_username': payload.get('preferred_username'),
            'name': payload.get('name'),
            'realm_name': identity.get('realm_name'),
            'roles': _extract_keycloak_roles(payload),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to decode unverified token: {e}')
        raise HTTPException(status_code=401, detail='Invalid token format')


def decode_keycloak_token(token: str) -> Dict[str, Any]:
    """Decode and validate a Keycloak-issued JWT token using JWKS."""
    import httpx
    from jose import jwt as jose_jwt
    from jose.exceptions import JWTError as JoseJWTError

    global _keycloak_jwks_client

    try:
        # Fetch JWKS from Keycloak (with caching)
        if _keycloak_jwks_client is None:
            logger.info(f'Fetching Keycloak JWKS from {KEYCLOAK_JWKS_URL}')
            try:
                response = httpx.get(KEYCLOAK_JWKS_URL, timeout=5.0)
                response.raise_for_status()
                _keycloak_jwks_client = response.json()
                logger.info(
                    f'Successfully fetched JWKS with {len(_keycloak_jwks_client.get("keys", []))} keys'
                )
            except httpx.HTTPError as e:
                logger.warning(
                    f'Failed to fetch Keycloak JWKS: {e}. Trying unverified decode.'
                )
                # Fall back to unverified decode for dev environments
                # This is INSECURE but allows local dev without Keycloak connectivity
                if (
                    os.environ.get(
                        'ALLOW_UNVERIFIED_KEYCLOAK_TOKENS', ''
                    ).lower()
                    == 'true'
                ):
                    return _decode_keycloak_token_unverified(token)
                raise

        # Get the key ID from the token header
        unverified_header = jose_jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')

        # Find the matching key in JWKS
        rsa_key = None
        for key in _keycloak_jwks_client.get('keys', []):
            if key.get('kid') == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(
                status_code=401, detail='Unable to find matching key'
            )

        # Decode and validate the token
        payload = jose_jwt.decode(
            token,
            rsa_key,
            algorithms=['RS256'],
            audience='account',  # Keycloak default audience
            issuer=KEYCLOAK_ISSUER,
            options={
                'verify_aud': False
            },  # Keycloak tokens may not have standard audience
        )

        # Normalize claims because some Keycloak access tokens omit standard claims.
        identity = _normalize_keycloak_identity(payload)
        if not identity.get('sub') or not identity.get('email'):
            raise HTTPException(
                status_code=401,
                detail='Invalid Keycloak token: missing identity claims',
            )

        # Map Keycloak claims to our format
        return {
            'sub': identity.get('sub'),
            'email': identity.get('email'),
            'type': 'keycloak',  # Mark as Keycloak token
            'exp': payload.get('exp'),
            'iat': payload.get('iat'),
            'preferred_username': payload.get('preferred_username'),
            'name': payload.get('name'),
            'realm_name': identity.get('realm_name'),
            'roles': _extract_keycloak_roles(payload),
        }
    except JoseJWTError as e:
        logger.error(f'Keycloak token validation error: {e}')
        raise HTTPException(
            status_code=401, detail=f'Invalid Keycloak token: {str(e)}'
        )
    except httpx.HTTPError as e:
        logger.error(f'Failed to fetch Keycloak JWKS: {e}')
        # Try unverified fallback for dev
        if (
            os.environ.get('ALLOW_UNVERIFIED_KEYCLOAK_TOKENS', '').lower()
            == 'true'
        ):
            logger.warning(
                'Using unverified token decode (ALLOW_UNVERIFIED_KEYCLOAK_TOKENS=true)'
            )
            return _decode_keycloak_token_unverified(token)
        raise HTTPException(status_code=503, detail='Unable to validate token')
    except Exception as e:
        logger.error(f'Unexpected error validating Keycloak token: {e}')
        raise HTTPException(status_code=401, detail='Token validation failed')


def _extract_keycloak_roles(payload: Dict[str, Any]) -> List[str]:
    """Extract roles from Keycloak token payload."""
    roles = []

    # Realm roles
    realm_access = payload.get('realm_access', {})
    roles.extend(realm_access.get('roles', []))

    # Client roles
    resource_access = payload.get('resource_access', {})
    for client in resource_access.values():
        if isinstance(client, dict):
            roles.extend(client.get('roles', []))

    return list(set(roles))  # Dedupe


# ========================================
# Current User Dependency
# ========================================


async def get_current_user(
    request: Request,
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

        # Handle Keycloak tokens (may not have user in our DB)
        if payload.get('type') == 'keycloak':
            # For Keycloak users, create a virtual user object from token claims
            # or look them up / create them in our database
            return await _get_or_create_keycloak_user(payload, request=request)

        # Handle self-issued tokens (user must exist in DB)
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


async def _get_or_create_keycloak_user(
    payload: Dict[str, Any],
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """Resolve a Keycloak-authenticated user for APIs expecting user-shaped dicts."""
    identity = _normalize_keycloak_identity(payload)
    keycloak_sub = identity.get('sub')
    email = identity.get('email')
    realm_name = payload.get('realm_name') or identity.get('realm_name')

    if not keycloak_sub or not email:
        raise HTTPException(
            status_code=401,
            detail='Invalid Keycloak token: missing sub or email',
        )

    tenant_id = payload.get('tenant_id')
    if not tenant_id and request is not None:
        tenant_id = getattr(request.state, 'tenant_id', None) or request.headers.get(
            'X-Tenant-ID'
        )

    if not tenant_id and realm_name:
        try:
            from .database import get_tenant_by_realm

            tenant = await get_tenant_by_realm(realm_name)
            if tenant:
                tenant_id = tenant.get('id') or tenant.get('tenant_id')
        except Exception as e:
            logger.debug(f'Could not resolve tenant from realm {realm_name}: {e}')

    def _build_virtual_user() -> Dict[str, Any]:
        name = payload.get('name') or ''
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else None
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else None
        return {
            'id': keycloak_sub,
            'user_id': keycloak_sub,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'status': 'active',
            'tier': 'free',
            'tier_id': 'free',
            'keycloak_sub': keycloak_sub,
            'roles': payload.get('roles', []),
            'usage_count': 0,
            'usage_limit': 10,
            'tasks_used_this_month': 0,
            'tasks_limit': 10,
            'tenant_id': tenant_id,
            'realm_name': realm_name,
        }

    pool = await get_pool()
    if not pool:
        # If DB is unavailable, return a virtual user from token claims.
        logger.warning('Database unavailable, returning virtual Keycloak user')
        return _build_virtual_user()

    async with pool.acquire() as conn:
        # Link to an existing local account by email when available.
        user = await conn.fetchrow(
            'SELECT * FROM users WHERE lower(email) = lower($1)',
            email,
        )
        if user:
            user_dict = dict(user)
            if tenant_id and not user_dict.get('tenant_id'):
                try:
                    await conn.execute(
                        'UPDATE users SET tenant_id = $1 WHERE id = $2 AND tenant_id IS NULL',
                        tenant_id,
                        user_dict['id'],
                    )
                    user_dict['tenant_id'] = tenant_id
                except Exception as e:
                    logger.debug(
                        f'Failed to backfill tenant_id on user {user_dict.get("id")}: {e}'
                    )
            user_dict['keycloak_sub'] = keycloak_sub
            user_dict['roles'] = payload.get('roles', [])
            user_dict['realm_name'] = realm_name
            return user_dict

        # If no local self-service account exists, expose a virtual user.
        return _build_virtual_user()


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
    Register a new user account and provision their instance.

    Creates a new user with email/password authentication and automatically
    provisions an isolated tenant/instance for the user.

    For MVP, accounts are activated immediately without email verification.
    Instance provisioning happens synchronously to ensure the user has
    immediate access to their workspace.
    """
    from .provisioning_service import provision_instance_for_new_user

    try:
        # Step 1: Create user record
        user = await create_user(
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            referral_source=request.referral_source,
        )

        logger.info(f'New user registered: {user["email"]}')

        # Step 2: Provision instance for user
        # This creates their isolated tenant/workspace
        provisioning_result = await provision_instance_for_new_user(
            user_id=user['id'],
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
        )

        if provisioning_result.success:
            logger.info(
                f'Instance provisioned for user {user["id"]}: '
                f'tenant={provisioning_result.tenant_id}, '
                f'k8s={provisioning_result.k8s_external_url}'
            )
            return RegisterResponse(
                user_id=user['id'],
                email=user['email'],
                message='Account created successfully. Your workspace is ready.',
                tenant_id=provisioning_result.tenant_id,
                realm_name=provisioning_result.realm_name,
                instance_url=provisioning_result.k8s_external_url,
                instance_namespace=provisioning_result.k8s_namespace,
                provisioning_status='completed',
            )
        else:
            # User created but provisioning failed
            # Log error but don't fail registration - user can retry provisioning later
            logger.error(
                f'Instance provisioning failed for user {user["id"]}: '
                f'{provisioning_result.error_message}'
            )
            return RegisterResponse(
                user_id=user['id'],
                email=user['email'],
                message='Account created. Workspace setup pending - please contact support if this persists.',
                tenant_id=None,
                realm_name=None,
                instance_url=None,
                instance_namespace=None,
                provisioning_status='failed',
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


# ========================================
# Billing Endpoints (Stripe tier wiring)
# ========================================


class CheckoutRequest(BaseModel):
    """Request for creating checkout session."""

    tier: str = Field(..., description='Target tier: pro or agency')
    success_url: str = Field(..., description='URL to redirect on success')
    cancel_url: str = Field(..., description='URL to redirect on cancel')


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    checkout_url: str


class PortalRequest(BaseModel):
    """Request for billing portal session."""

    return_url: str = Field(..., description='URL to return to after portal')


class PortalResponse(BaseModel):
    """Billing portal session response."""

    portal_url: str


class BillingStatusResponse(BaseModel):
    """User's billing status."""

    tier: str
    tier_name: str
    stripe_subscription_status: Optional[str]
    current_period_end: Optional[str]
    tasks_used: int
    tasks_limit: int
    concurrency_limit: int
    max_runtime_seconds: int


@router.get('/billing/status', response_model=BillingStatusResponse)
async def get_billing_status(user: Dict[str, Any] = Depends(require_user)):
    """
    Get current user's billing status.

    Returns tier, limits, and Stripe subscription status.
    """
    pool = await get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database unavailable')

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                u.tier_id,
                st.name as tier_name,
                u.stripe_subscription_status,
                u.stripe_current_period_end,
                u.tasks_used_this_month,
                u.tasks_limit,
                u.concurrency_limit,
                u.max_runtime_seconds
            FROM users u
            LEFT JOIN subscription_tiers st ON u.tier_id = st.id
            WHERE u.id = $1
            """,
            user['id'],
        )

    if not row:
        raise HTTPException(status_code=404, detail='User not found')

    return BillingStatusResponse(
        tier=row['tier_id'] or 'free',
        tier_name=row['tier_name'] or 'Free',
        stripe_subscription_status=row['stripe_subscription_status'],
        current_period_end=row['stripe_current_period_end'].isoformat()
        if row['stripe_current_period_end']
        else None,
        tasks_used=row['tasks_used_this_month'] or 0,
        tasks_limit=row['tasks_limit'] or 10,
        concurrency_limit=row['concurrency_limit'] or 1,
        max_runtime_seconds=row['max_runtime_seconds'] or 600,
    )


@router.post('/billing/checkout', response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    user: Dict[str, Any] = Depends(require_user),
):
    """
    Create a Stripe Checkout session to upgrade tier.

    Valid tiers: pro, agency
    """
    if request.tier not in ('pro', 'agency'):
        raise HTTPException(
            status_code=400,
            detail='Invalid tier. Must be "pro" or "agency".',
        )

    try:
        from .user_billing import create_user_checkout_session

        checkout_url = await create_user_checkout_session(
            user_id=user['id'],
            tier_id=request.tier,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )

        if not checkout_url:
            raise HTTPException(
                status_code=500, detail='Failed to create checkout session'
            )

        return CheckoutResponse(checkout_url=checkout_url)

    except ImportError:
        raise HTTPException(
            status_code=503, detail='Billing module not available'
        )
    except Exception as e:
        logger.error(f'Checkout error: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/billing/portal', response_model=PortalResponse)
async def create_billing_portal(
    request: PortalRequest,
    user: Dict[str, Any] = Depends(require_user),
):
    """
    Create a Stripe Billing Portal session.

    Allows user to manage payment methods, view invoices, and cancel subscription.
    """
    if not user.get('stripe_customer_id'):
        raise HTTPException(
            status_code=400,
            detail='No billing account. Subscribe first via /billing/checkout.',
        )

    try:
        from .user_billing import create_user_billing_portal_session

        portal_url = await create_user_billing_portal_session(
            user_id=user['id'],
            return_url=request.return_url,
        )

        if not portal_url:
            raise HTTPException(
                status_code=500, detail='Failed to create portal session'
            )

        return PortalResponse(portal_url=portal_url)

    except ImportError:
        raise HTTPException(
            status_code=503, detail='Billing module not available'
        )
    except Exception as e:
        logger.error(f'Portal error: {e}')
        raise HTTPException(status_code=500, detail=str(e))
