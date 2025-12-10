"""
Keycloak Authentication Service for A2A Server.

Provides OAuth2/OIDC authentication with Keycloak for:
- User authentication and session management
- Cross-device session persistence
- User-scoped agent and codebase management
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
import json
import uuid
import hashlib

import httpx
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from pydantic import BaseModel
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
    OAuth2AuthorizationCodeBearer,
)

logger = logging.getLogger(__name__)

# Keycloak Configuration from environment
KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'https://auth.quantum-forge.io')
KEYCLOAK_REALM = os.environ.get('KEYCLOAK_REALM', 'quantum-forge')
KEYCLOAK_CLIENT_ID = os.environ.get('KEYCLOAK_CLIENT_ID', 'a2a-monitor')
KEYCLOAK_CLIENT_SECRET = os.environ.get(
    'KEYCLOAK_CLIENT_SECRET', 'Boog6oMQhr6dlF5tebfQ2FuLMhAOU4i1'
)
KEYCLOAK_ADMIN_USERNAME = os.environ.get(
    'KEYCLOAK_ADMIN_USERNAME', 'info@evolvingsoftware.io'
)
KEYCLOAK_ADMIN_PASSWORD = os.environ.get(
    'KEYCLOAK_ADMIN_PASSWORD', 'Spr!ng20@4'
)

# JWT Configuration
JWT_ALGORITHM = 'RS256'
JWT_ISSUER = f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}'

# Security schemes
security = HTTPBearer(auto_error=False)


@dataclass
class UserSession:
    """Represents an authenticated user session."""

    user_id: str
    email: str
    username: str
    name: str
    session_id: str
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    device_info: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'email': self.email,
            'username': self.username,
            'name': self.name,
            'session_id': self.session_id,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'device_info': self.device_info,
            'roles': self.roles,
        }

    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at


@dataclass
class UserCodebaseAssociation:
    """Tracks which codebases belong to which user."""

    user_id: str
    codebase_id: str
    codebase_name: str
    codebase_path: str
    role: str = 'owner'  # owner, collaborator, viewer
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'codebase_id': self.codebase_id,
            'codebase_name': self.codebase_name,
            'codebase_path': self.codebase_path,
            'role': self.role,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
        }


@dataclass
class UserAgentSession:
    """Tracks agent sessions per user across devices."""

    user_id: str
    session_id: str
    codebase_id: str
    agent_type: str
    opencode_session_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    device_id: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'codebase_id': self.codebase_id,
            'agent_type': self.agent_type,
            'opencode_session_id': self.opencode_session_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'device_id': self.device_id,
            'message_count': len(self.messages),
        }


class KeycloakAuthService:
    """Manages Keycloak authentication and user sessions."""

    def __init__(self):
        self.keycloak_url = KEYCLOAK_URL
        self.realm = KEYCLOAK_REALM
        self.client_id = KEYCLOAK_CLIENT_ID
        self.client_secret = KEYCLOAK_CLIENT_SECRET

        # Token endpoints
        self.token_url = f'{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token'
        self.auth_url = f'{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/auth'
        self.userinfo_url = f'{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/userinfo'
        self.jwks_url = f'{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/certs'
        self.logout_url = f'{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/logout'

        # Caches
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: Optional[datetime] = None

        # Session storage (in-memory, can be backed by Redis/SQLite)
        self._sessions: Dict[str, UserSession] = {}
        self._user_codebases: Dict[str, List[UserCodebaseAssociation]] = {}
        self._agent_sessions: Dict[str, UserAgentSession] = {}

        logger.info(
            f'KeycloakAuthService initialized for {self.keycloak_url}/realms/{self.realm}'
        )

    async def get_jwks(self) -> Dict[str, Any]:
        """Fetch and cache JWKS from Keycloak."""
        # Return cached JWKS if still valid (5 minutes)
        if self._jwks_cache and self._jwks_cache_time:
            if datetime.utcnow() - self._jwks_cache_time < timedelta(minutes=5):
                return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = datetime.utcnow()
                return self._jwks_cache
        except Exception as e:
            logger.error(f'Failed to fetch JWKS: {e}')
            if self._jwks_cache:
                return self._jwks_cache
            raise HTTPException(
                status_code=503, detail='Authentication service unavailable'
            )

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate a JWT token from Keycloak."""
        try:
            # Get JWKS
            jwks = await self.get_jwks()

            # Decode header to get key ID
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')

            # Find matching key
            public_key = None
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    public_key = jwk.construct(key)
                    break

            if not public_key:
                raise HTTPException(
                    status_code=401, detail='Invalid token: key not found'
                )

            # Verify and decode token
            payload = jwt.decode(
                token,
                public_key.to_pem().decode('utf-8'),
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                audience=self.client_id,
                options={
                    'verify_aud': False
                },  # Keycloak sometimes uses different audience
            )

            return payload

        except JWTError as e:
            logger.warning(f'Token validation failed: {e}')
            raise HTTPException(
                status_code=401, detail=f'Invalid token: {str(e)}'
            )

    async def authenticate_password(
        self,
        username: str,
        password: str,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> UserSession:
        """Authenticate user with username/password and create session."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        'grant_type': 'password',
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'username': username,
                        'password': password,
                        'scope': 'openid profile email',
                    },
                    timeout=10.0,
                )

                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get(
                        'error_description', 'Authentication failed'
                    )
                    raise HTTPException(status_code=401, detail=error_msg)

                token_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f'Keycloak authentication error: {e}')
            raise HTTPException(
                status_code=503, detail='Authentication service unavailable'
            )

        # Validate and decode access token
        payload = await self.validate_token(token_data['access_token'])

        # Get user ID - prefer 'sub', then generate stable ID from email
        # Note: We use email hash as fallback because Keycloak 'sid' changes per session
        user_id = payload.get('sub')
        if not user_id:
            # Generate a stable ID from email for cross-session consistency
            email = payload.get('email', username)
            user_id = 'u-' + hashlib.sha256(email.encode()).hexdigest()[:30]

        # Create session
        session = UserSession(
            user_id=user_id,
            email=payload.get('email', ''),
            username=payload.get('preferred_username', username),
            name=payload.get('name', ''),
            session_id=str(uuid.uuid4()),
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=datetime.utcnow()
            + timedelta(seconds=token_data.get('expires_in', 300)),
            device_info=device_info or {},
            roles=payload.get('realm_access', {}).get('roles', []),
        )

        # Store session
        self._sessions[session.session_id] = session

        logger.info(
            f'User authenticated: {session.username} (session: {session.session_id})'
        )
        return session

    async def refresh_session(self, refresh_token: str) -> UserSession:
        """Refresh an existing session using refresh token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        'grant_type': 'refresh_token',
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'refresh_token': refresh_token,
                    },
                    timeout=10.0,
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=401, detail='Session expired'
                    )

                token_data = response.json()

        except httpx.HTTPError as e:
            logger.error(f'Session refresh error: {e}')
            raise HTTPException(
                status_code=503, detail='Authentication service unavailable'
            )

        # Validate new token
        payload = await self.validate_token(token_data['access_token'])

        # Get user ID - prefer 'sub', then generate stable ID from email
        user_id = payload.get('sub')
        if not user_id:
            email = payload.get('email', '')
            user_id = (
                'u-' + hashlib.sha256(email.encode()).hexdigest()[:30]
                if email
                else str(uuid.uuid4())
            )

        # Find and update existing session or create new
        old_session = None
        for sid, session in self._sessions.items():
            if session.refresh_token == refresh_token:
                old_session = session
                break

        new_session = UserSession(
            user_id=user_id,
            email=payload.get('email', ''),
            username=payload.get('preferred_username', ''),
            name=payload.get('name', ''),
            session_id=old_session.session_id
            if old_session
            else str(uuid.uuid4()),
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_at=datetime.utcnow()
            + timedelta(seconds=token_data.get('expires_in', 300)),
            device_info=old_session.device_info if old_session else {},
            roles=payload.get('realm_access', {}).get('roles', []),
        )

        self._sessions[new_session.session_id] = new_session

        return new_session

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_valid():
            session.last_activity = datetime.utcnow()
            return session
        return None

    async def get_session_by_token(self, token: str) -> Optional[UserSession]:
        """Get a session by access token."""
        for session in self._sessions.values():
            if session.access_token == token and session.is_valid():
                session.last_activity = datetime.utcnow()
                return session
        return None

    async def logout(self, session_id: str):
        """Logout and invalidate session."""
        session = self._sessions.pop(session_id, None)
        if session and session.refresh_token:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        self.logout_url,
                        data={
                            'client_id': self.client_id,
                            'client_secret': self.client_secret,
                            'refresh_token': session.refresh_token,
                        },
                        timeout=5.0,
                    )
            except Exception as e:
                logger.warning(f'Keycloak logout failed: {e}')

        logger.info(f'Session logged out: {session_id}')

    # User-Codebase Association Management

    def associate_codebase(
        self,
        user_id: str,
        codebase_id: str,
        codebase_name: str,
        codebase_path: str,
        role: str = 'owner',
    ) -> UserCodebaseAssociation:
        """Associate a codebase with a user."""
        association = UserCodebaseAssociation(
            user_id=user_id,
            codebase_id=codebase_id,
            codebase_name=codebase_name,
            codebase_path=codebase_path,
            role=role,
        )

        if user_id not in self._user_codebases:
            self._user_codebases[user_id] = []

        # Check if already associated
        for existing in self._user_codebases[user_id]:
            if existing.codebase_id == codebase_id:
                existing.last_accessed = datetime.utcnow()
                return existing

        self._user_codebases[user_id].append(association)
        logger.info(f'Codebase {codebase_name} associated with user {user_id}')
        return association

    def get_user_codebases(self, user_id: str) -> List[UserCodebaseAssociation]:
        """Get all codebases for a user."""
        return self._user_codebases.get(user_id, [])

    def can_access_codebase(self, user_id: str, codebase_id: str) -> bool:
        """Check if user can access a codebase."""
        associations = self._user_codebases.get(user_id, [])
        for assoc in associations:
            if assoc.codebase_id == codebase_id:
                assoc.last_accessed = datetime.utcnow()
                return True
        return False

    def remove_codebase_association(
        self, user_id: str, codebase_id: str
    ) -> bool:
        """Remove a codebase association."""
        if user_id in self._user_codebases:
            original_len = len(self._user_codebases[user_id])
            self._user_codebases[user_id] = [
                a
                for a in self._user_codebases[user_id]
                if a.codebase_id != codebase_id
            ]
            return len(self._user_codebases[user_id]) < original_len
        return False

    # Agent Session Management

    def create_agent_session(
        self,
        user_id: str,
        codebase_id: str,
        agent_type: str,
        device_id: Optional[str] = None,
    ) -> UserAgentSession:
        """Create a new agent session for a user."""
        session = UserAgentSession(
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            codebase_id=codebase_id,
            agent_type=agent_type,
            device_id=device_id,
        )

        self._agent_sessions[session.session_id] = session
        logger.info(
            f'Agent session created: {session.session_id} for user {user_id}'
        )
        return session

    def get_agent_session(self, session_id: str) -> Optional[UserAgentSession]:
        """Get an agent session by ID."""
        return self._agent_sessions.get(session_id)

    def get_user_agent_sessions(self, user_id: str) -> List[UserAgentSession]:
        """Get all agent sessions for a user."""
        return [
            s for s in self._agent_sessions.values() if s.user_id == user_id
        ]

    def get_codebase_sessions(self, codebase_id: str) -> List[UserAgentSession]:
        """Get all agent sessions for a codebase."""
        return [
            s
            for s in self._agent_sessions.values()
            if s.codebase_id == codebase_id
        ]

    def update_agent_session(
        self,
        session_id: str,
        opencode_session_id: Optional[str] = None,
        message: Optional[Dict[str, Any]] = None,
    ):
        """Update an agent session."""
        session = self._agent_sessions.get(session_id)
        if session:
            session.last_activity = datetime.utcnow()
            if opencode_session_id:
                session.opencode_session_id = opencode_session_id
            if message:
                session.messages.append(
                    {**message, 'timestamp': datetime.utcnow().isoformat()}
                )
                # Keep only last 100 messages in memory
                if len(session.messages) > 100:
                    session.messages = session.messages[-100:]

    def close_agent_session(self, session_id: str):
        """Close an agent session."""
        self._agent_sessions.pop(session_id, None)
        logger.info(f'Agent session closed: {session_id}')

    # Session Sync Across Devices

    def get_active_sessions_for_user(self, user_id: str) -> List[UserSession]:
        """Get all active sessions for a user across devices."""
        return [
            s
            for s in self._sessions.values()
            if s.user_id == user_id and s.is_valid()
        ]

    def sync_session_state(self, user_id: str) -> Dict[str, Any]:
        """Get synchronized state for a user across all sessions."""
        user_sessions = self.get_active_sessions_for_user(user_id)
        agent_sessions = self.get_user_agent_sessions(user_id)
        codebases = self.get_user_codebases(user_id)

        return {
            'user_id': user_id,
            'active_devices': len(user_sessions),
            'sessions': [s.to_dict() for s in user_sessions],
            'agent_sessions': [s.to_dict() for s in agent_sessions],
            'codebases': [c.to_dict() for c in codebases],
            'synced_at': datetime.utcnow().isoformat(),
        }


# Global auth service instance
keycloak_auth = KeycloakAuthService()


# FastAPI Dependencies


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[UserSession]:
    """Dependency to get current authenticated user."""
    if not credentials:
        return None

    token = credentials.credentials

    # First try to find existing session
    session = await keycloak_auth.get_session_by_token(token)
    if session:
        return session

    # Otherwise validate token and create temporary session info
    try:
        payload = await keycloak_auth.validate_token(token)

        # Get user ID - prefer 'sub', then generate stable ID from email
        user_id = payload.get('sub')
        if not user_id:
            email = payload.get('email', '')
            user_id = (
                'u-' + hashlib.sha256(email.encode()).hexdigest()[:30]
                if email
                else 'temp-' + str(uuid.uuid4())
            )

        return UserSession(
            user_id=user_id,
            email=payload.get('email', ''),
            username=payload.get('preferred_username', ''),
            name=payload.get('name', ''),
            session_id='temp-' + str(uuid.uuid4()),
            access_token=token,
            refresh_token=None,
            expires_at=datetime.fromtimestamp(payload.get('exp', 0)),
            roles=payload.get('realm_access', {}).get('roles', []),
        )
    except HTTPException:
        return None


async def require_auth(
    user: Optional[UserSession] = Depends(get_current_user),
) -> UserSession:
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    return user


async def require_admin(
    user: UserSession = Depends(require_auth),
) -> UserSession:
    """Dependency that requires admin role."""
    if 'admin' not in user.roles and 'a2a-admin' not in user.roles:
        raise HTTPException(status_code=403, detail='Admin access required')
    return user
