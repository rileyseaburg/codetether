"""
OAuth 2.0 Authorization Server for automation platforms.

This module implements OAuth 2.0 authorization code flow for third-party
integration with Zapier, n8n, Make, and other automation platforms.

Key features:
- Authorization code flow with PKCE support
- Token endpoint for access token exchange
- Refresh token support
- Standard OAuth 2.0 /authorize and /token endpoints
- Scope-based access control
"""

import logging
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field, HttpUrl
from starlette.requests import Request as StarletteRequest

from .database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/oauth', tags=['OAuth 2.0'])


# ========================================
# Configuration
# ========================================

# OAuth Server Configuration
OAUTH_ISSUER = 'https://api.codetether.io'
AUTHORIZATION_CODE_EXPIRY_MINUTES = 10
ACCESS_TOKEN_EXPIRY_MINUTES = 60
REFRESH_TOKEN_EXPIRY_DAYS = 30

# Registered clients (in production, this should be in database)
REGISTERED_CLIENTS = {
    'codetether-zapier': {
        'client_id': 'codetether-zapier',
        'client_secret': os.environ.get(
            'ZAPIER_CLIENT_SECRET', 'Pef3g5N944hAtWVZFP9l2WTX4W7jlqtL'
        ),
        'redirect_uris': [
            'https://zapier.com/dashboard/auth/oauth/return/App235522CLIAPI/',
            'https://auth.zapier.com/oauth/callback',
            'https://zapier.com/oauth/callback',
        ],
        'scopes': [
            'openid',
            'email',
            'profile',
            'tasks:read',
            'tasks:write',
            'automation:read',
            'automation:write',
        ],
        'name': 'CodeTether Zapier',
    },
    'zapier': {
        'client_id': 'zapier_client_id',
        'client_secret': 'zapier_client_secret',
        'redirect_uris': [
            'https://auth.zapier.com/oauth/callback',
            'https://zapier.com/oauth/callback',
        ],
        'scopes': [
            'tasks:read',
            'tasks:write',
            'automation:read',
            'automation:write',
        ],
        'name': 'Zapier',
    },
    'n8n': {
        'client_id': 'n8n_client_id',
        'client_secret': 'n8n_client_secret',
        'redirect_uris': [
            'http://localhost:5678/oauth/callback',
        ],
        'scopes': ['tasks:read', 'tasks:write'],
        'name': 'n8n',
    },
    'make': {
        'client_id': 'make_client_id',
        'client_secret': 'make_client_secret',
        'redirect_uris': [
            'https://www.make.com/oauth/callback',
        ],
        'scopes': ['tasks:read', 'tasks:write', 'automation:write'],
        'name': 'Make',
    },
}

# Available scopes
AVAILABLE_SCOPES = {
    'tasks:read': 'Read task information',
    'tasks:write': 'Create and cancel tasks',
    'automation:read': 'Read automation workflows',
    'automation:write': 'Create and manage automation workflows',
}


# ========================================
# Data Models
# ========================================


@dataclass
class AuthorizationCode:
    """OAuth authorization code storage."""

    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    scopes: List[str]
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=AUTHORIZATION_CODE_EXPIRY_MINUTES)
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class AccessToken:
    """OAuth access token storage."""

    token: str
    refresh_token: str
    client_id: str
    user_id: str
    scopes: List[str]
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# In-memory stores (use database in production)
_authorization_codes: Dict[str, AuthorizationCode] = {}
_access_tokens: Dict[str, AccessToken] = {}
_refresh_tokens: Dict[str, str] = {}  # refresh_token -> access_token mapping


# ========================================
# Request/Response Models
# ========================================


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = 'Bearer'
    expires_in: int
    refresh_token: str
    scope: str


# ========================================
# Helper Functions
# ========================================


def generate_code() -> str:
    """Generate a secure authorization code."""
    return secrets.token_urlsafe(32)


def generate_token() -> str:
    """Generate a secure access token."""
    return secrets.token_urlsafe(32)


def get_client_info(client_id: str) -> Optional[Dict[str, Any]]:
    """Get registered client information."""
    for client in REGISTERED_CLIENTS.values():
        if client['client_id'] == client_id:
            return client
    return None


def validate_redirect_uri(client_id: str, redirect_uri: str) -> bool:
    """Validate redirect URI for client."""
    client = get_client_info(client_id)
    if not client:
        return False

    for allowed_uri in client['redirect_uris']:
        if redirect_uri.startswith(allowed_uri):
            return True

    return False


def validate_scopes(requested_scopes: List[str]) -> List[str]:
    """Validate and filter requested scopes."""
    valid_scopes = []
    for scope in requested_scopes:
        if scope in AVAILABLE_SCOPES:
            valid_scopes.append(scope)
    return valid_scopes


def verify_pkce2(
    code_challenge: str, code_verifier: str, method: str = 'S256'
) -> bool:
    """Verify PKCE code challenge.

    For S256 method: code_challenge = BASE64URL(SHA256(ASCII(code_verifier)))
    """
    import base64
    import hashlib

    if method == 'S256':
        digest = hashlib.sha256(code_verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
        return secrets.compare_digest(code_challenge, expected)

    return False


# ========================================
# API Endpoints
# ========================================


@router.get('/authorize')
async def authorize(
    request: StarletteRequest,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query('tasks:write'),
    state: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
):
    """OAuth 2.0 Authorization Endpoint."""
    if response_type != 'code':
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'unsupported_response_type',
                'error_description': 'Only "code" response type is supported',
            },
        )

    client = get_client_info(client_id)
    if not client:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_client',
                'error_description': 'Unknown client_id',
            },
        )

    if not validate_redirect_uri(client_id, redirect_uri):
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_redirect_uri',
                'error_description': 'Redirect URI not allowed for this client',
            },
        )

    requested_scopes = scope.split()
    valid_scopes = validate_scopes(requested_scopes)
    if not valid_scopes:
        valid_scopes = ['tasks:write']

    if code_challenge:
        if code_challenge_method != 'S256':
            raise HTTPException(
                status_code=400,
                detail={
                    'error': 'invalid_request',
                    'error_description': 'Only S256 code_challenge_method is supported',
                },
            )

    auth_header = request.headers.get('authorization', '')
    user_id = None

    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        if token in _access_tokens:
            user_id = _access_tokens[token].user_id

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'authentication_required',
                'error_description': 'You must authenticate to authorize this request',
                'login_url': '/v1/users/login',
            },
        )

    code = generate_code()
    auth_code = AuthorizationCode(
        code=code,
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scopes=valid_scopes,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    _authorization_codes[code] = auth_code

    redirect_url = (
        f'{redirect_uri}?code={code}&state={state}'
        if state
        else redirect_uri + '?code=' + code
    )

    return RedirectResponse(url=redirect_url)


class TokenRequest(BaseModel):
    """OAuth 2.0 Token Request - supports form-encoded body."""

    grant_type: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    code_verifier: Optional[str] = None
    refresh_token: Optional[str] = None


@router.post('/token', response_model=TokenResponse)
async def token(request: Request):
    """OAuth 2.0 Token Endpoint.

    Accepts both form-encoded body (standard OAuth2) and JSON body.
    """
    content_type = request.headers.get('content-type', '')

    # Parse form data or JSON
    if 'application/x-www-form-urlencoded' in content_type:
        form_data = await request.form()
        data = {k: v for k, v in form_data.items()}
    elif 'application/json' in content_type:
        data = await request.json()
    else:
        # Try form data first (most common for OAuth2)
        try:
            form_data = await request.form()
            data = {k: v for k, v in form_data.items()}
        except Exception:
            data = await request.json()

    grant_type = data.get('grant_type')
    if not grant_type:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_request',
                'error_description': 'grant_type is required',
            },
        )

    if grant_type == 'authorization_code':
        code = data.get('code')
        redirect_uri = data.get('redirect_uri')
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        code_verifier = data.get('code_verifier')

        if not all([code, redirect_uri, client_id, client_secret]):
            raise HTTPException(
                status_code=400,
                detail={
                    'error': 'invalid_request',
                    'error_description': 'code, redirect_uri, client_id, and client_secret are required',
                },
            )

        return await exchange_code(
            code, redirect_uri, client_id, client_secret, code_verifier
        )
    elif grant_type == 'refresh_token':
        refresh_token = data.get('refresh_token')
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')

        if not all([refresh_token, client_id, client_secret]):
            raise HTTPException(
                status_code=400,
                detail={
                    'error': 'invalid_request',
                    'error_description': 'refresh_token, client_id, and client_secret are required',
                },
            )

        return await refresh_access_token(
            refresh_token, client_id, client_secret
        )
    else:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'unsupported_grant_type',
                'error_description': 'Only authorization_code and refresh_token grant types are supported',
            },
        )


async def exchange_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: Optional[str] = None,
) -> JSONResponse:
    """Exchange authorization code for access token."""
    if code not in _authorization_codes:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Invalid or expired authorization code',
            },
        )

    auth_code = _authorization_codes[code]

    if auth_code.expires_at < datetime.now(timezone.utc):
        del _authorization_codes[code]
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Authorization code has expired',
            },
        )

    client = get_client_info(client_id)
    if not client or client['client_secret'] != client_secret:
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'invalid_client',
                'error_description': 'Invalid client credentials',
            },
        )

    if auth_code.client_id != client_id:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Authorization code was issued to a different client',
            },
        )

    if auth_code.redirect_uri != redirect_uri:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Redirect URI does not match',
            },
        )

    if auth_code.code_challenge:
        if not code_verifier:
            raise HTTPException(
                status_code=400,
                detail={
                    'error': 'invalid_request',
                    'error_description': 'code_verifier is required when PKCE was used',
                },
            )

        if not verify_pkce2(
            auth_code.code_challenge,
            code_verifier,
            auth_code.code_challenge_method,
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    'error': 'invalid_grant',
                    'error_description': 'Invalid code_verifier',
                },
            )

    del _authorization_codes[code]

    access_token_str = generate_token()
    refresh_token_str = generate_token()

    access_token = AccessToken(
        token=access_token_str,
        refresh_token=refresh_token_str,
        client_id=client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes,
    )

    _access_tokens[access_token_str] = access_token
    _refresh_tokens[refresh_token_str] = access_token_str

    response = TokenResponse(
        access_token=access_token_str,
        token_type='Bearer',
        expires_in=ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        refresh_token=refresh_token_str,
        scope=' '.join(auth_code.scopes),
    )

    return JSONResponse(content=response.model_dump())


async def refresh_access_token(
    refresh_token: str, client_id: str, client_secret: str
) -> JSONResponse:
    """Refresh an access token using a refresh token."""
    if refresh_token not in _refresh_tokens:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Invalid or expired refresh token',
            },
        )

    old_access_token = _refresh_tokens[refresh_token]

    if old_access_token not in _access_tokens:
        del _refresh_tokens[refresh_token]
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Refresh token is no longer valid',
            },
        )

    old_token_record = _access_tokens[old_access_token]

    client = get_client_info(client_id)
    if not client or client['client_secret'] != client_secret:
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'invalid_client',
                'error_description': 'Invalid client credentials',
            },
        )

    if old_token_record.client_id != client_id:
        raise HTTPException(
            status_code=400,
            detail={
                'error': 'invalid_grant',
                'error_description': 'Refresh token was issued to a different client',
            },
        )

    new_access_token_str = generate_token()
    new_refresh_token_str = generate_token()

    new_access_token = AccessToken(
        token=new_access_token_str,
        refresh_token=new_refresh_token_str,
        client_id=client_id,
        user_id=old_token_record.user_id,
        scopes=old_token_record.scopes,
    )

    del _access_tokens[old_access_token]

    _access_tokens[new_access_token_str] = new_access_token
    _refresh_tokens[new_refresh_token_str] = new_access_token_str
    del _refresh_tokens[refresh_token]

    response = TokenResponse(
        access_token=new_access_token_str,
        token_type='Bearer',
        expires_in=ACCESS_TOKEN_EXPIRY_MINUTES * 60,
        refresh_token=new_refresh_token_str,
        scope=' '.join(new_access_token.scopes),
    )

    return JSONResponse(content=response.model_dump())


@router.get('/')
async def oauth_info():
    """Get OAuth 2.0 server information."""
    return {
        'issuer': OAUTH_ISSUER,
        'authorization_endpoint': f'{OAUTH_ISSUER}/oauth/authorize',
        'token_endpoint': f'{OAUTH_ISSUER}/oauth/token',
        'response_types_supported': ['code'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'token_endpoint_auth_methods_supported': ['client_secret_post'],
        'scopes': AVAILABLE_SCOPES,
        'code_challenge_methods_supported': ['S256'],
    }
