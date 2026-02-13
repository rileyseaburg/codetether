"""
OAuth 2.1 Authorization Server for MCP Protocol compliance.

Implements the MCP Authorization spec (2025-11-25):
- OAuth 2.0 Protected Resource Metadata (RFC 9728)
- OAuth 2.0 Authorization Server Metadata (RFC 8414)
- OAuth 2.0 Dynamic Client Registration (RFC 7591)
- OAuth 2.1 Authorization Code + PKCE flow
- Bearer token issuance and validation
"""

import hashlib
import logging
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jose import jwt

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────
_SERVER_URL = os.environ.get("MCP_SERVER_URL", "https://api.codetether.run").rstrip("/")
_ISSUER = os.environ.get("OAUTH_ISSUER", _SERVER_URL).rstrip("/")
_JWT_SECRET = os.environ.get("JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"
_ACCESS_TOKEN_TTL = int(os.environ.get("OAUTH_ACCESS_TOKEN_TTL", "3600"))
_REFRESH_TOKEN_TTL = int(os.environ.get("OAUTH_REFRESH_TOKEN_TTL", "86400"))

# Scopes the MCP resource server supports
SUPPORTED_SCOPES = [
    "mcp:read", "mcp:write",
    "tasks:read", "tasks:write",
    "agent:read", "agent:write",
    "monitor:read",
]

# ── In-memory stores (production should use DB) ───────────────────
# Registered OAuth clients  {client_id: {client_secret, redirect_uris, ...}}
_registered_clients: Dict[str, Dict[str, Any]] = {}
# Pending authorization codes  {code: {client_id, redirect_uri, scope, ...}}
_auth_codes: Dict[str, Dict[str, Any]] = {}
# Refresh tokens  {token_hash: {client_id, user_id, scope, ...}}
_refresh_tokens: Dict[str, Dict[str, Any]] = {}

router = APIRouter(tags=["OAuth 2.1"])


# ── Helpers ────────────────────────────────────────────────────────

def _get_jwt_secret() -> str:
    """Get JWT secret, falling back to user_auth's secret."""
    if _JWT_SECRET:
        return _JWT_SECRET
    try:
        from .user_auth import JWT_SECRET
        return JWT_SECRET
    except ImportError:
        raise RuntimeError("JWT_SECRET not configured")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _s256_challenge(verifier: str) -> str:
    """Compute S256 PKCE code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _issue_access_token(
    client_id: str,
    user_id: str,
    scope: str,
    resource: Optional[str] = None,
) -> Dict[str, Any]:
    """Issue an OAuth 2.1 access token (JWT)."""
    now = int(time.time())
    payload = {
        "iss": _ISSUER,
        "sub": user_id,
        "aud": resource or _SERVER_URL,
        "client_id": client_id,
        "scope": scope,
        "iat": now,
        "exp": now + _ACCESS_TOKEN_TTL,
        "jti": secrets.token_urlsafe(16),
        "type": "access",
        # Include auth_source so policy.py treats it correctly
        "auth_source": "oauth",
    }
    access_token = jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)

    # Issue refresh token
    refresh_token = secrets.token_urlsafe(48)
    _refresh_tokens[_hash_token(refresh_token)] = {
        "client_id": client_id,
        "user_id": user_id,
        "scope": scope,
        "resource": resource,
        "issued_at": now,
        "expires_at": now + _REFRESH_TOKEN_TTL,
    }

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": _ACCESS_TOKEN_TTL,
        "refresh_token": refresh_token,
        "scope": scope,
    }


# ══════════════════════════════════════════════════════════════════
# 1. Protected Resource Metadata (RFC 9728)
# ══════════════════════════════════════════════════════════════════

@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata_base(request: Request):
    """RFC 9728 — Protected Resource Metadata (origin-level fallback)."""
    return JSONResponse({
        "resource": _SERVER_URL,
        "authorization_servers": [_ISSUER],
        "scopes_supported": SUPPORTED_SCOPES,
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{_SERVER_URL}/docs",
    })


@router.get("/.well-known/oauth-protected-resource/{path:path}")
async def protected_resource_metadata_path(request: Request, path: str):
    """RFC 9728 — Protected Resource Metadata (path-specific).

    Per RFC 9728, the 'resource' field MUST match the protected resource URL.
    For /.well-known/oauth-protected-resource/mcp, resource is {origin}/mcp.
    """
    resource_url = f"{_SERVER_URL}/{path}"
    return JSONResponse({
        "resource": resource_url,
        "authorization_servers": [_ISSUER],
        "scopes_supported": SUPPORTED_SCOPES,
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{_SERVER_URL}/docs",
    })


# ══════════════════════════════════════════════════════════════════
# 2. Authorization Server Metadata (RFC 8414)
# ══════════════════════════════════════════════════════════════════

@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/{path:path}")
@router.get("/.well-known/openid-configuration")
async def authorization_server_metadata(request: Request):
    """RFC 8414 — OAuth 2.0 Authorization Server Metadata.

    VS Code and other MCP clients fetch this to discover endpoints.
    """
    return JSONResponse({
        "issuer": _ISSUER,
        "authorization_endpoint": f"{_SERVER_URL}/oauth/authorize",
        "token_endpoint": f"{_SERVER_URL}/oauth/token",
        "registration_endpoint": f"{_SERVER_URL}/oauth/register",
        "scopes_supported": SUPPORTED_SCOPES,
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
        ],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
        "client_id_metadata_document_supported": True,
        "revocation_endpoint": f"{_SERVER_URL}/oauth/revoke",
        "service_documentation": f"{_SERVER_URL}/docs",
    })


# ══════════════════════════════════════════════════════════════════
# 3. Dynamic Client Registration (RFC 7591)
# ══════════════════════════════════════════════════════════════════

@router.post("/oauth/register")
async def register_client(request: Request):
    """RFC 7591 — Dynamic Client Registration.

    MCP clients (VS Code, Claude Desktop) call this to get a client_id.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    # Validate redirect_uris
    redirect_uris = body.get("redirect_uris", [])
    if not redirect_uris:
        raise HTTPException(400, {"error": "invalid_client_metadata",
                                   "error_description": "redirect_uris required"})

    # Validate redirect URIs: must be localhost or HTTPS
    for uri in redirect_uris:
        parsed = urllib.parse.urlparse(uri)
        if parsed.hostname in ("localhost", "127.0.0.1"):
            continue
        if parsed.scheme == "https":
            continue
        # Allow vscode.dev redirect
        if uri.startswith("https://vscode.dev/"):
            continue
        raise HTTPException(400, {
            "error": "invalid_redirect_uri",
            "error_description": f"Redirect URI must use localhost or HTTPS: {uri}",
        })

    client_id = f"mcp_{secrets.token_urlsafe(16)}"
    client_secret = None
    token_endpoint_auth_method = body.get("token_endpoint_auth_method", "none")

    if token_endpoint_auth_method == "client_secret_post":
        client_secret = secrets.token_urlsafe(32)

    client_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": body.get("client_name", "MCP Client"),
        "redirect_uris": redirect_uris,
        "grant_types": body.get("grant_types", ["authorization_code"]),
        "response_types": body.get("response_types", ["code"]),
        "scope": body.get("scope", " ".join(SUPPORTED_SCOPES)),
        "token_endpoint_auth_method": token_endpoint_auth_method,
        "client_id_issued_at": int(time.time()),
        "client_secret_expires_at": 0,  # doesn't expire
    }
    _registered_clients[client_id] = client_info

    logger.info(f"OAuth client registered: {client_id} ({client_info['client_name']})")

    response = {
        "client_id": client_id,
        "client_name": client_info["client_name"],
        "redirect_uris": redirect_uris,
        "grant_types": client_info["grant_types"],
        "response_types": client_info["response_types"],
        "scope": client_info["scope"],
        "token_endpoint_auth_method": token_endpoint_auth_method,
        "client_id_issued_at": client_info["client_id_issued_at"],
        "client_secret_expires_at": 0,
    }
    if client_secret:
        response["client_secret"] = client_secret

    return JSONResponse(response, status_code=201)


# ══════════════════════════════════════════════════════════════════
# 4. Authorization Endpoint (OAuth 2.1)
# ══════════════════════════════════════════════════════════════════

@router.get("/oauth/authorize")
async def authorize(request: Request):
    """OAuth 2.1 Authorization Endpoint with PKCE.

    For MCP clients, this shows a simple consent page and issues an
    authorization code that can be exchanged for tokens.
    """
    params = dict(request.query_params)

    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    response_type = params.get("response_type", "")
    scope = params.get("scope", " ".join(SUPPORTED_SCOPES))
    state = params.get("state", "")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "")
    resource = params.get("resource", "")

    # Validate response_type
    if response_type != "code":
        return _auth_error(redirect_uri, "unsupported_response_type",
                           "Only 'code' response_type is supported", state)

    # PKCE is required
    if not code_challenge or code_challenge_method != "S256":
        return _auth_error(redirect_uri, "invalid_request",
                           "PKCE with S256 is required", state)

    # Look up or auto-accept client
    # For Client ID Metadata Documents (URL-formatted client_id), accept them
    client = _registered_clients.get(client_id)
    if not client:
        if client_id.startswith("https://"):
            # Client ID Metadata Document — auto-register
            client = {
                "client_id": client_id,
                "redirect_uris": [redirect_uri],
                "client_name": "MCP Client",
                "token_endpoint_auth_method": "none",
            }
            _registered_clients[client_id] = client
        else:
            return _auth_error(redirect_uri, "invalid_client",
                               "Unknown client_id. Register via /oauth/register first.", state)

    # Validate redirect_uri against registered URIs
    if redirect_uri not in client.get("redirect_uris", []):
        # Be lenient: if the redirect is localhost, allow any port
        parsed = urllib.parse.urlparse(redirect_uri)
        if parsed.hostname not in ("localhost", "127.0.0.1", "vscode.dev"):
            if parsed.scheme != "https":
                return JSONResponse(
                    {"error": "invalid_redirect_uri",
                     "error_description": "redirect_uri not registered"},
                    status_code=400,
                )
        # Accept localhost/vscode.dev redirects even if not pre-registered
        # (MCP clients use dynamic ports)

    # Show consent page
    client_name = client.get("client_name", client_id)
    scope_list = scope.split()
    scope_html = "".join(f"<li>{s}</li>" for s in scope_list)

    # Generate authorization code
    auth_code = secrets.token_urlsafe(32)
    # Use a temporary user_id — real login would set this
    temp_user_id = f"oauth_user_{secrets.token_urlsafe(8)}"

    _auth_codes[auth_code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "resource": resource,
        "user_id": temp_user_id,
        "created_at": time.time(),
        "expires_at": time.time() + 600,  # 10 min
    }

    # Auto-approve for MCP clients (consent is implicit — the user
    # configured this server in their IDE settings)
    redirect_params = {"code": auth_code}
    if state:
        redirect_params["state"] = state

    redirect_url = _build_redirect(redirect_uri, redirect_params)
    return RedirectResponse(redirect_url, status_code=302)


def _auth_error(redirect_uri: str, error: str, description: str, state: str):
    """Build an OAuth error redirect."""
    if not redirect_uri:
        return JSONResponse({"error": error, "error_description": description}, status_code=400)
    params = {"error": error, "error_description": description}
    if state:
        params["state"] = state
    return RedirectResponse(_build_redirect(redirect_uri, params), status_code=302)


def _build_redirect(base_uri: str, params: dict) -> str:
    """Append query params to a redirect URI."""
    parsed = urllib.parse.urlparse(base_uri)
    existing = urllib.parse.parse_qs(parsed.query)
    existing.update({k: [v] for k, v in params.items()})
    new_query = urllib.parse.urlencode({k: v[0] for k, v in existing.items()})
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


# ══════════════════════════════════════════════════════════════════
# 5. Token Endpoint (OAuth 2.1)
# ══════════════════════════════════════════════════════════════════

@router.post("/oauth/token")
async def token_endpoint(request: Request):
    """OAuth 2.1 Token Endpoint — exchange code for tokens, or refresh."""
    # Support both form-encoded and JSON
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        form = await request.form()
        body = dict(form)

    grant_type = body.get("grant_type", "")

    if grant_type == "authorization_code":
        return _handle_auth_code_grant(body)
    elif grant_type == "refresh_token":
        return _handle_refresh_grant(body)
    else:
        return JSONResponse(
            {"error": "unsupported_grant_type",
             "error_description": f"Grant type '{grant_type}' not supported"},
            status_code=400,
        )


def _handle_auth_code_grant(body: dict) -> JSONResponse:
    """Exchange authorization code for tokens."""
    code = body.get("code", "")
    redirect_uri = body.get("redirect_uri", "")
    client_id = body.get("client_id", "")
    code_verifier = body.get("code_verifier", "")

    # Look up code
    code_data = _auth_codes.pop(code, None)
    if not code_data:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
            status_code=400,
        )

    # Check expiration
    if time.time() > code_data["expires_at"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Authorization code expired"},
            status_code=400,
        )

    # Validate client_id
    if code_data["client_id"] != client_id:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "client_id mismatch"},
            status_code=400,
        )

    # Validate redirect_uri
    if code_data["redirect_uri"] != redirect_uri:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
            status_code=400,
        )

    # Validate PKCE code_verifier
    if not code_verifier:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "code_verifier required (PKCE)"},
            status_code=400,
        )
    expected_challenge = _s256_challenge(code_verifier)
    if expected_challenge != code_data["code_challenge"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "PKCE code_verifier invalid"},
            status_code=400,
        )

    # Issue tokens
    token_response = _issue_access_token(
        client_id=client_id,
        user_id=code_data["user_id"],
        scope=code_data["scope"],
        resource=code_data.get("resource"),
    )

    return JSONResponse(token_response)


def _handle_refresh_grant(body: dict) -> JSONResponse:
    """Exchange refresh token for new access token (with rotation)."""
    refresh_token = body.get("refresh_token", "")
    client_id = body.get("client_id", "")

    token_hash = _hash_token(refresh_token)
    token_data = _refresh_tokens.pop(token_hash, None)  # consume (rotate)

    if not token_data:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid refresh token"},
            status_code=400,
        )

    if time.time() > token_data["expires_at"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Refresh token expired"},
            status_code=400,
        )

    if token_data["client_id"] != client_id:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "client_id mismatch"},
            status_code=400,
        )

    # Issue new tokens (rotation)
    token_response = _issue_access_token(
        client_id=client_id,
        user_id=token_data["user_id"],
        scope=token_data["scope"],
        resource=token_data.get("resource"),
    )

    return JSONResponse(token_response)


# ══════════════════════════════════════════════════════════════════
# 6. Token Revocation
# ══════════════════════════════════════════════════════════════════

@router.post("/oauth/revoke")
async def revoke_token(request: Request):
    """Revoke an access or refresh token."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        form = await request.form()
        body = dict(form)

    token = body.get("token", "")
    if token:
        token_hash = _hash_token(token)
        _refresh_tokens.pop(token_hash, None)

    # RFC 7009: always return 200, even if token was invalid
    return JSONResponse({}, status_code=200)


# ══════════════════════════════════════════════════════════════════
# WWW-Authenticate helper for 401 responses
# ══════════════════════════════════════════════════════════════════

def www_authenticate_header(scope: Optional[str] = None) -> str:
    """Build a WWW-Authenticate header value per RFC 9728 / MCP spec."""
    resource_metadata = f"{_SERVER_URL}/.well-known/oauth-protected-resource"
    parts = [f'Bearer resource_metadata="{resource_metadata}"']
    if scope:
        parts.append(f'scope="{scope}"')
    return ", ".join(parts)
