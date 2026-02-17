"""
Monitoring API endpoints for A2A Server.

Provides real-time monitoring, logging, and human intervention capabilities.
Supports multiple storage backends:
- PostgreSQL for durable storage across restarts/replicas (preferred)
- Redis for distributed session sync
- SQLite for persistent storage (default if writable)
- MinIO/S3 for cloud-native deployments
- In-memory fallback when no persistent storage is available
"""

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone, timedelta
from collections import deque
from dataclasses import dataclass, asdict
from fastapi import APIRouter, HTTPException, Request, Depends, Security
from fastapi.responses import (
    StreamingResponse,
    HTMLResponse,
    FileResponse,
    JSONResponse,
)
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import io
import tempfile
from functools import lru_cache

# Import PostgreSQL persistence layer
from . import database as db
from .task_orchestration import orchestrate_task_route
from .vm_workspace_provisioner import (
    VMWorkspaceSpec,
    vm_workspace_provisioner,
    is_enabled as is_vm_workspaces_enabled,
)

logger = logging.getLogger(__name__)

# Router for monitoring endpoints
monitor_router = APIRouter(prefix='/v1/monitor', tags=['monitoring'])

# Default database path - use /tmp as fallback for read-only filesystems
DEFAULT_DB_PATH = os.environ.get(
    'MONITOR_DB_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'monitor.db'),
)

# MinIO/S3 configuration from environment
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY')
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'a2a-monitor')
MINIO_SECURE = os.environ.get('MINIO_SECURE', 'false').lower() == 'true'


@dataclass
class MonitorMessage:
    """Represents a monitored message."""

    id: str
    timestamp: datetime
    type: str  # agent, human, system, tool, error
    agent_name: str
    content: str
    metadata: Dict[str, Any]
    response_time: Optional[float] = None
    tokens: Optional[int] = None
    error: Optional[str] = None


class InterventionRequest(BaseModel):
    """Request model for human intervention."""

    agent_id: str
    message: str
    timestamp: str


class AgentTaskResponse(BaseModel):
    """Response model for an agent task."""

    id: str
    workspace_id: Optional[str] = None
    title: str
    prompt: str
    agent_type: str = 'build'
    model: Optional[str] = None
    status: str
    priority: int = 0
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    target_agent_name: Optional[str] = None


class PersistentMessageStore:
    """SQLite-based persistent storage for monitor messages with fallback to in-memory."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._local = threading.local()
        self._use_sqlite = (
            False  # Start with False, set to True if SQLite init succeeds
        )
        self._use_minio = False
        self._minio_client = None
        self._in_memory_messages = deque(maxlen=10000)  # Fallback storage
        self._in_memory_interventions = deque(
            maxlen=1000
        )  # Fallback for interventions
        self._in_memory_stats = {
            'total_messages': 0,
            'tool_calls': 0,
            'errors': 0,
            'tokens': 0,
            'interventions': 0,
        }
        self._init_storage()

    def _init_storage(self):
        """Initialize storage backend with fallback hierarchy: MinIO -> SQLite -> In-Memory."""
        # Try MinIO first if configured
        if MINIO_ENDPOINT and MINIO_ACCESS_KEY and MINIO_SECRET_KEY:
            if self._init_minio():
                print(
                    f'✓ Using MinIO storage at {MINIO_ENDPOINT}/{MINIO_BUCKET}'
                )
                return

    def _init_minio(self) -> bool:
        """Initialize MinIO/S3 storage backend."""
        try:
            from minio import Minio

            endpoint = (
                MINIO_ENDPOINT.replace('http://', '').replace('https://', '')
                if MINIO_ENDPOINT
                else ''
            )
            self._minio_client = Minio(
                endpoint,
                access_key=MINIO_ACCESS_KEY or '',
                secret_key=MINIO_SECRET_KEY or '',
                secure=MINIO_SECURE,
            )
            # Ensure bucket exists
            if not self._minio_client.bucket_exists(MINIO_BUCKET):
                self._minio_client.make_bucket(MINIO_BUCKET)
            # Test write access
            test_data = b'{"test": true}'
            self._minio_client.put_object(
                MINIO_BUCKET,
                '_health_check',
                io.BytesIO(test_data),
                len(test_data),
                content_type='application/json',
            )
            self._use_minio = True
            self._use_sqlite = False
            # Load existing data from MinIO into memory for fast access
            self._load_from_minio()
            return True
        except ImportError:
            logger.debug('minio package not installed, skipping MinIO backend')
            return False
        except Exception as e:
            logger.warning(f'MinIO initialization failed: {e}')
            return False

    def _init_sqlite(self) -> bool:
        """Initialize SQLite storage backend."""
        try:
            self._init_db()
            self._use_sqlite = True
            self._use_minio = False
            return True
        except Exception as e:
            logger.warning(f'SQLite initialization failed: {e}')
            return False

    def _load_from_minio(self):
        """Load existing messages from MinIO into in-memory cache."""
        if not self._minio_client:
            return
        try:
            # Load recent messages index
            response = self._minio_client.get_object(
                MINIO_BUCKET, 'messages_index.json'
            )
            index_data = json.loads(response.read().decode('utf-8'))
            response.close()
            response.release_conn()

            # Load most recent messages into memory cache
            for msg_id in index_data.get('recent_ids', [])[:1000]:
                try:
                    msg_response = self._minio_client.get_object(
                        MINIO_BUCKET, f'messages/{msg_id}.json'
                    )
                    msg_data = json.loads(msg_response.read().decode('utf-8'))
                    msg_response.close()
                    msg_response.release_conn()
                    self._in_memory_messages.append(msg_data)
                except Exception:
                    pass

            # Load stats
            try:
                stats_response = self._minio_client.get_object(
                    MINIO_BUCKET, 'stats.json'
                )
                self._in_memory_stats = json.loads(
                    stats_response.read().decode('utf-8')
                )
                stats_response.close()
                stats_response.release_conn()
            except Exception:
                pass

            logger.info(
                f'Loaded {len(self._in_memory_messages)} messages from MinIO cache'
            )
        except Exception as e:
            logger.debug(f'No existing MinIO data to load: {e}')

    def _save_to_minio(self, message_dict: Dict[str, Any]):
        """Save a message to MinIO storage."""
        if not self._minio_client:
            return
        try:
            # Save the message
            msg_data = json.dumps(message_dict).encode('utf-8')
            self._minio_client.put_object(
                MINIO_BUCKET,
                f'messages/{message_dict["id"]}.json',
                io.BytesIO(msg_data),
                len(msg_data),
                content_type='application/json',
            )

            # Update index (append message ID)
            try:
                response = self._minio_client.get_object(
                    MINIO_BUCKET, 'messages_index.json'
                )
                index_data = json.loads(response.read().decode('utf-8'))
                response.close()
                response.release_conn()
            except Exception:
                index_data = {'recent_ids': [], 'total_count': 0}

            index_data['recent_ids'].insert(0, message_dict['id'])
            index_data['recent_ids'] = index_data['recent_ids'][
                :10000
            ]  # Keep last 10k
            index_data['total_count'] = index_data.get('total_count', 0) + 1

            index_bytes = json.dumps(index_data).encode('utf-8')
            self._minio_client.put_object(
                MINIO_BUCKET,
                'messages_index.json',
                io.BytesIO(index_bytes),
                len(index_bytes),
                content_type='application/json',
            )

            # Update stats
            stats_bytes = json.dumps(self._in_memory_stats).encode('utf-8')
            self._minio_client.put_object(
                MINIO_BUCKET,
                'stats.json',
                io.BytesIO(stats_bytes),
                len(stats_bytes),
                content_type='application/json',
            )
        except Exception as e:
            logger.error(f'Failed to save message to MinIO: {e}')

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if (
            not hasattr(self._local, 'connection')
            or self._local.connection is None
        ):
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._local.connection = sqlite3.connect(
                self.db_path, check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        """Initialize the database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                content TEXT,
                metadata TEXT,
                response_time REAL,
                tokens INTEGER,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common queries
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_name)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_messages_metadata ON messages(metadata)'
        )

        # Create interventions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create stats table for aggregate tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        # Initialize stats if not present
        cursor.execute(
            "INSERT OR IGNORE INTO stats (key, value) VALUES ('total_messages', 0)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO stats (key, value) VALUES ('tool_calls', 0)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO stats (key, value) VALUES ('errors', 0)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO stats (key, value) VALUES ('tokens', 0)"
        )

        conn.commit()
        logger.info(f'Persistent message store initialized at {self.db_path}')

    def save_message(self, message: MonitorMessage):
        """Save a message to the database or in-memory store."""
        # Convert message to dict for storage
        msg_dict = {
            'id': message.id,
            'timestamp': message.timestamp.isoformat(),
            'type': message.type,
            'agent_name': message.agent_name,
            'content': message.content,
            'metadata': message.metadata,
            'response_time': message.response_time,
            'tokens': message.tokens,
            'error': message.error,
        }

        # Update in-memory stats
        self._in_memory_stats['total_messages'] += 1
        if message.type == 'tool':
            self._in_memory_stats['tool_calls'] += 1
        if message.error:
            self._in_memory_stats['errors'] += 1
        if message.tokens:
            self._in_memory_stats['tokens'] += message.tokens

        # Store to MinIO if available
        if self._use_minio:
            self._in_memory_messages.append(msg_dict)
            self._save_to_minio(msg_dict)
            return

        # Store to SQLite if available
        if self._use_sqlite:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO messages (id, timestamp, type, agent_name, content, metadata, response_time, tokens, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    message.id,
                    message.timestamp.isoformat(),
                    message.type,
                    message.agent_name,
                    message.content,
                    json.dumps(message.metadata),
                    message.response_time,
                    message.tokens,
                    message.error,
                ),
            )

            # Update stats
            cursor.execute(
                "UPDATE stats SET value = value + 1 WHERE key = 'total_messages'"
            )
            if message.type == 'tool':
                cursor.execute(
                    "UPDATE stats SET value = value + 1 WHERE key = 'tool_calls'"
                )
            if message.error:
                cursor.execute(
                    "UPDATE stats SET value = value + 1 WHERE key = 'errors'"
                )
            if message.tokens:
                cursor.execute(
                    "UPDATE stats SET value = value + ? WHERE key = 'tokens'",
                    (message.tokens,),
                )

            conn.commit()
            return

        # Fallback to in-memory only
        self._in_memory_messages.append(msg_dict)

    def _get_messages_from_memory(
        self,
        limit: int = 100,
        message_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        since: Optional[datetime] = None,
        offset: int = 0,
    ) -> List[MonitorMessage]:
        """Return messages from the in-memory cache (used for MinIO and in-memory fallback)."""

        def _parse_ts(value: Any) -> datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except Exception:
                    return datetime.min
            return datetime.min

        def _get_metadata(m: Dict[str, Any]) -> Dict[str, Any]:
            md = m.get('metadata')
            return md if isinstance(md, dict) else {}

        raw = []
        for m in self._in_memory_messages:
            if isinstance(m, dict):
                raw.append(m)
            else:
                # Defensive: some older code paths may store MonitorMessage objects
                try:
                    raw.append(asdict(m))
                except Exception:
                    pass

        # Apply filters
        if message_type:
            raw = [m for m in raw if m.get('type') == message_type]
        if agent_name:
            raw = [m for m in raw if m.get('agent_name') == agent_name]
        if conversation_id:
            raw = [
                m
                for m in raw
                if _get_metadata(m).get('conversation_id') == conversation_id
            ]
        if since:
            raw = [m for m in raw if _parse_ts(m.get('timestamp')) > since]

        # Match SQLite ordering: newest first
        raw.sort(key=lambda m: _parse_ts(m.get('timestamp')), reverse=True)

        # Apply pagination
        page = raw[offset : offset + limit]

        result: List[MonitorMessage] = []
        for m in page:
            result.append(
                MonitorMessage(
                    id=m.get('id', ''),
                    timestamp=_parse_ts(m.get('timestamp'))
                    if m.get('timestamp') is not None
                    else datetime.now(),
                    type=m.get('type', ''),
                    agent_name=m.get('agent_name', ''),
                    content=m.get('content', ''),
                    metadata=_get_metadata(m),
                    response_time=m.get('response_time'),
                    tokens=m.get('tokens'),
                    error=m.get('error'),
                )
            )
        return result

    def get_messages(
        self,
        limit: int = 100,
        message_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        since: Optional[datetime] = None,
        offset: int = 0,
    ) -> List[MonitorMessage]:
        """Get messages with optional filtering."""
        # For MinIO-backed deployments, reads come from the in-memory cache.
        # (MinIO is used as the persistence layer, and the cache is populated on init and on writes.)
        if not self._use_sqlite:
            return self._get_messages_from_memory(
                limit=limit,
                message_type=message_type,
                agent_name=agent_name,
                conversation_id=conversation_id,
                since=since,
                offset=offset,
            )

        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM messages WHERE 1=1'
        params = []

        if message_type:
            query += ' AND type = ?'
            params.append(message_type)

        if agent_name:
            query += ' AND agent_name = ?'
            params.append(agent_name)

        if conversation_id:
            query += ' AND metadata LIKE ?'
            params.append(f'%"conversation_id": "{conversation_id}"%')

        if since:
            query += ' AND timestamp > ?'
            params.append(since.isoformat())

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                MonitorMessage(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    type=row['type'],
                    agent_name=row['agent_name'],
                    content=row['content'],
                    metadata=json.loads(row['metadata'])
                    if row['metadata']
                    else {},
                    response_time=row['response_time'],
                    tokens=row['tokens'],
                    error=row['error'],
                )
            )

        return messages

    def get_message_count(self, message_type: Optional[str] = None) -> int:
        """Get total message count."""
        # For MinIO (and in-memory fallback), counts are tracked in-memory.
        if not self._use_sqlite:
            if message_type:
                return len(
                    [
                        m
                        for m in self._in_memory_messages
                        if isinstance(m, dict) and m.get('type') == message_type
                    ]
                )
            return int(
                self._in_memory_stats.get(
                    'total_messages', len(self._in_memory_messages)
                )
            )

        conn = self._get_connection()
        cursor = conn.cursor()

        if message_type:
            cursor.execute(
                'SELECT COUNT(*) FROM messages WHERE type = ?', (message_type,)
            )
        else:
            cursor.execute('SELECT COUNT(*) FROM messages')

        return cursor.fetchone()[0]

    def save_intervention(self, agent_id: str, message: str, timestamp: str):
        """Save an intervention to the database."""
        # Store in-memory intervention
        intervention = {
            'agent_id': agent_id,
            'message': message,
            'timestamp': timestamp,
        }
        self._in_memory_interventions.append(intervention)
        self._in_memory_stats['interventions'] = (
            self._in_memory_stats.get('interventions', 0) + 1
        )

        if not self._use_sqlite:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO interventions (agent_id, message, timestamp)
            VALUES (?, ?, ?)
        """,
            (agent_id, message, timestamp),
        )

        conn.commit()

    def get_interventions(self, limit: int = 100) -> List[Dict]:
        """Get recent interventions."""
        if not self._use_sqlite:
            return list(self._in_memory_interventions)[-limit:]

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT agent_id, message, timestamp
            FROM interventions
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, int]:
        """Get aggregate statistics."""
        # For MinIO (and in-memory fallback), stats are tracked in-memory.
        if not self._use_sqlite:
            stats = self._in_memory_stats.copy()
            stats['interventions'] = len(self._in_memory_interventions)
            return stats

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT key, value FROM stats')
        stats = {row['key']: row['value'] for row in cursor.fetchall()}

        # Get intervention count
        cursor.execute('SELECT COUNT(*) FROM interventions')
        stats['interventions'] = cursor.fetchone()[0]

        return stats

    def search_messages(
        self, query: str, limit: int = 100
    ) -> List[MonitorMessage]:
        """Full-text search in message content."""
        # For MinIO (and in-memory fallback), search the in-memory cache.
        if not self._use_sqlite:
            query_lower = query.lower()
            results = []
            for m in self._in_memory_messages:
                if isinstance(m, dict):
                    content = str(m.get('content', '')).lower()
                    agent = str(m.get('agent_name', '')).lower()
                    metadata = str(m.get('metadata', '')).lower()
                    if (
                        query_lower in content
                        or query_lower in agent
                        or query_lower in metadata
                    ):
                        results.append(
                            MonitorMessage(
                                id=m.get('id', ''),
                                timestamp=datetime.fromisoformat(m['timestamp'])
                                if isinstance(m.get('timestamp'), str)
                                else m.get('timestamp', datetime.now()),
                                type=m.get('type', ''),
                                agent_name=m.get('agent_name', ''),
                                content=m.get('content', ''),
                                metadata=m.get('metadata', {}),
                                response_time=m.get('response_time'),
                                tokens=m.get('tokens'),
                                error=m.get('error'),
                            )
                        )
            return results[-limit:]

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM messages
            WHERE content LIKE ? OR agent_name LIKE ? OR metadata LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (f'%{query}%', f'%{query}%', f'%{query}%', limit),
        )

        messages = []
        for row in cursor.fetchall():
            messages.append(
                MonitorMessage(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    type=row['type'],
                    agent_name=row['agent_name'],
                    content=row['content'],
                    metadata=json.loads(row['metadata'])
                    if row['metadata']
                    else {},
                    response_time=row['response_time'],
                    tokens=row['tokens'],
                    error=row['error'],
                )
            )

        return messages


class MonitoringService:
    """Service for monitoring agent conversations and enabling human intervention."""

    def __init__(self, db_path: Optional[str] = None):
        # Persistent storage
        self.store = PersistentMessageStore(db_path)

        # In-memory cache for recent messages (for fast access)
        self.messages = deque(maxlen=1000)

        # Load recent messages into cache on startup
        recent = self.store.get_messages(limit=1000)
        for msg in reversed(recent):  # Add in chronological order
            self.messages.append(msg)

        self.active_agents = {}
        self.stats = {
            'response_times': deque(
                maxlen=100
            )  # Keep recent response times in memory
        }
        self.subscribers = []

        logger.info(
            f'Monitoring service initialized with {len(self.messages)} cached messages'
        )

    async def log_message(
        self,
        agent_name: str,
        content: str,
        message_type: str = 'agent',
        metadata: Optional[Dict[str, Any]] = None,
        response_time: Optional[float] = None,
        tokens: Optional[int] = None,
        error: Optional[str] = None,
    ):
        """Log a message from an agent or system."""
        message = MonitorMessage(
            id=f'{datetime.now().timestamp()}',
            timestamp=datetime.now(),
            type=message_type,
            agent_name=agent_name,
            content=content,
            metadata=metadata or {},
            response_time=response_time,
            tokens=tokens,
            error=error,
        )

        # Save to persistent storage
        self.store.save_message(message)

        # Add to in-memory cache
        self.messages.append(message)

        # Track response times in memory for quick avg calculation
        if response_time:
            self.stats['response_times'].append(response_time)

        # Broadcast to all subscribers
        await self.broadcast_message(message)

        logger.info(f'Logged message from {agent_name}: {content[:100]}')

    async def broadcast_message(self, message: MonitorMessage):
        """Broadcast a message to all SSE subscribers."""
        data = {
            'type': message.type,
            'agent_name': message.agent_name,
            'content': message.content,
            'metadata': message.metadata,
            'response_time': message.response_time,
            'tokens': message.tokens,
            'error': message.error,
            'timestamp': message.timestamp.isoformat(),
        }

        message_json = json.dumps(data)
        logger.info(
            f'Broadcasting message to {len(self.subscribers)} subscribers: {message.agent_name} - {message.content[:50]}'
        )

        # Send to all active subscribers
        for queue in self.subscribers:
            try:
                await queue.put(f'data: {message_json}\n\n')
                logger.debug(f'Message queued successfully')
            except Exception as e:
                logger.error(f'Failed to send to subscriber: {e}')
                pass

    async def broadcast_agent_status(self, agent_id: str, agent_data: dict):
        """Broadcast agent status update to all SSE subscribers."""
        data = {
            'agent_id': agent_id,
            'name': agent_data.get('name', 'Unknown'),
            'status': agent_data.get('status', 'active'),
            'messages_count': agent_data.get('messages_count', 0),
        }
        message_json = json.dumps(data)
        logger.info(
            f'Broadcasting agent status to {len(self.subscribers)} subscribers: {agent_id} - {data["name"]}'
        )

        # SSE event format with event type
        sse_message = f'event: agent_status\ndata: {message_json}\n\n'

        for queue in self.subscribers:
            try:
                await queue.put(sse_message)
            except Exception as e:
                logger.error(f'Failed to send agent status to subscriber: {e}')

    async def register_agent(self, agent_id: str, agent_name: str):
        """Register an active agent and broadcast to subscribers."""
        self.active_agents[agent_id] = {
            'id': agent_id,
            'name': agent_name,
            'status': 'active',
            'messages_count': 0,
            'last_seen': datetime.now(),
        }
        logger.info(
            f'Registered agent {agent_name} ({agent_id}), total active: {len(self.active_agents)}'
        )

        # Broadcast to UI subscribers
        await self.broadcast_agent_status(
            agent_id, self.active_agents[agent_id]
        )

    def update_agent_status(self, agent_id: str, status: str):
        """Update agent status."""
        if agent_id in self.active_agents:
            self.active_agents[agent_id]['status'] = status
            self.active_agents[agent_id]['last_seen'] = datetime.now()

    async def handle_intervention(self, agent_id: str, message: str):
        """Handle human intervention for an agent."""
        timestamp = datetime.now().isoformat()

        intervention = {
            'agent_id': agent_id,
            'message': message,
            'timestamp': timestamp,
        }

        # Save to persistent storage
        self.store.save_intervention(agent_id, message, timestamp)

        # Log the intervention as a message
        agent_name = self.active_agents.get(agent_id, {}).get('name', 'Unknown')
        await self.log_message(
            agent_name='Human Operator',
            content=f'Intervention to {agent_name}: {message}',
            message_type='human',
            metadata={'intervention': True, 'target_agent': agent_id},
        )

        return intervention

    def get_messages(
        self,
        limit: int = 100,
        message_type: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict]:
        """Get recent messages."""
        if use_cache and limit <= 1000:
            # Use in-memory cache for fast access
            messages = list(self.messages)
            if message_type:
                messages = [m for m in messages if m.type == message_type]
            return [asdict(m) for m in messages[-limit:]]
        else:
            # Query persistent storage for larger requests
            messages = self.store.get_messages(
                limit=limit, message_type=message_type
            )
            return [asdict(m) for m in messages]

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        # Get persistent stats
        db_stats = self.store.get_stats()

        # Calculate average response time from in-memory cache
        avg_response_time = 0
        if self.stats['response_times']:
            avg_response_time = sum(self.stats['response_times']) / len(
                self.stats['response_times']
            )

        return {
            'total_messages': db_stats.get('total_messages', 0),
            'tool_calls': db_stats.get('tool_calls', 0),
            'errors': db_stats.get('errors', 0),
            'tokens': db_stats.get('tokens', 0),
            'avg_response_time': avg_response_time,
            'active_agents': len(self.active_agents),
            'interventions': db_stats.get('interventions', 0),
        }

    def search_messages(self, query: str, limit: int = 100) -> List[Dict]:
        """Search messages by content, agent name, or metadata."""
        messages = self.store.search_messages(query, limit)
        return [asdict(m) for m in messages]


# Global monitoring service instance
monitoring_service = MonitoringService()


@monitor_router.get('/')
async def serve_monitor_ui():
    """Serve the monitoring UI."""
    # Try new Tailwind UI first
    ui_path = os.path.join(
        os.path.dirname(__file__), '..', 'ui', 'monitor-tailwind.html'
    )
    if os.path.exists(ui_path):
        return FileResponse(ui_path, media_type='text/html')
    # Fallback to old UI
    ui_path = os.path.join(
        os.path.dirname(__file__), '..', 'ui', 'monitor.html'
    )
    if os.path.exists(ui_path):
        return FileResponse(ui_path, media_type='text/html')
    return HTMLResponse(
        content='<h1>Monitor UI not found. Please ensure ui/monitor-tailwind.html exists.</h1>',
        status_code=404,
    )


@monitor_router.get('/classic')
async def serve_classic_ui():
    """Serve the classic monitoring UI."""
    ui_path = os.path.join(
        os.path.dirname(__file__), '..', 'ui', 'monitor.html'
    )
    if os.path.exists(ui_path):
        return FileResponse(ui_path, media_type='text/html')
    return HTMLResponse(
        content='<h1>Classic UI not found.</h1>',
        status_code=404,
    )


@monitor_router.get('/monitor.js')
async def serve_monitor_js():
    """Serve the monitoring JavaScript."""
    js_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'monitor.js')
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type='application/javascript')
    return HTMLResponse(content='// monitor.js not found', status_code=404)


@monitor_router.get('/stream')
async def monitor_stream(request: Request):
    """SSE endpoint for real-time message streaming."""

    async def event_generator():
        # Create a queue for this subscriber
        queue = asyncio.Queue()
        monitoring_service.subscribers.append(queue)
        logger.info(
            f'New SSE subscriber connected. Total subscribers: {len(monitoring_service.subscribers)}'
        )

        try:
            # Send initial connection message
            yield f'data: {json.dumps({"type": "connected", "timestamp": datetime.now().isoformat()})}\n\n'

            # Keep connection alive and send any queued messages
            while True:
                if await request.is_disconnected():
                    logger.info('SSE client disconnected')
                    break

                try:
                    # Wait for messages with a timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    logger.debug(
                        f'Sending message to SSE client: {message[:100]}'
                    )
                    yield message
                except asyncio.TimeoutError:
                    # Send heartbeat on timeout
                    yield f': heartbeat\n\n'
                except asyncio.CancelledError:
                    logger.info('SSE stream cancelled')
                    break

        finally:
            # Cleanup - remove this queue from subscribers
            if queue in monitoring_service.subscribers:
                monitoring_service.subscribers.remove(queue)
                logger.info(
                    f'SSE subscriber disconnected. Remaining subscribers: {len(monitoring_service.subscribers)}'
                )

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@monitor_router.get('/agents')
async def get_active_agents():
    """Get list of active agents."""
    return list(monitoring_service.active_agents.values())


@monitor_router.get('/messages')
async def get_messages(
    limit: int = 100, type: Optional[str] = None, use_cache: bool = True
):
    """Get recent messages. Set use_cache=false to query all persistent logs."""
    return monitoring_service.get_messages(
        limit=limit, message_type=type, use_cache=use_cache
    )


@monitor_router.get('/messages/search')
async def search_messages(q: str, limit: int = 100):
    """Search messages by content, agent name, or metadata."""
    return {
        'query': q,
        'results': monitoring_service.search_messages(q, limit),
        'count': len(monitoring_service.search_messages(q, limit)),
    }


@monitor_router.get('/messages/count')
async def get_message_count(type: Optional[str] = None):
    """Get total message count from persistent storage."""
    return {
        'total': monitoring_service.store.get_message_count(type),
        'type_filter': type,
    }


@monitor_router.get('/workers')
async def monitor_list_workers(search: Optional[str] = None):
    """Proxy to /v1/agent/workers for backward compatibility."""
    return await list_workers(search)


@monitor_router.get('/models')
async def monitor_list_models():
    """Proxy to /v1/agent/models for backward compatibility."""
    return await list_models()


@monitor_router.get('/stats')
async def get_stats():
    """Get monitoring statistics."""
    return monitoring_service.get_stats()


@monitor_router.post('/intervene')
async def send_intervention(intervention: InterventionRequest):
    """Send a human intervention to an agent."""
    try:
        result = await monitoring_service.handle_intervention(
            agent_id=intervention.agent_id, message=intervention.message
        )
        return {'success': True, 'intervention': result}
    except Exception as e:
        logger.error(f'Error handling intervention: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@monitor_router.get('/export/json')
async def export_json(limit: int = 10000, all_messages: bool = False):
    """Export messages as JSON. Set all_messages=true for complete export."""
    if all_messages:
        limit = monitoring_service.store.get_message_count()
    messages = monitoring_service.get_messages(limit=limit, use_cache=False)
    return {
        'export_date': datetime.now().isoformat(),
        'message_count': len(messages),
        'total_in_database': monitoring_service.store.get_message_count(),
        'stats': monitoring_service.get_stats(),
        'messages': messages,
    }


@monitor_router.get('/export/csv')
async def export_csv(limit: int = 10000, all_messages: bool = False):
    """Export messages as CSV. Set all_messages=true for complete export."""
    if all_messages:
        limit = monitoring_service.store.get_message_count()
    messages = monitoring_service.get_messages(limit=limit, use_cache=False)

    # Create CSV content
    csv_lines = ['Timestamp,Type,Agent,Content,Response Time,Tokens,Error']

    for msg in messages:
        timestamp = msg.get('timestamp', '')
        msg_type = msg.get('type', '')
        agent = msg.get('agent_name', '')
        content = str(msg.get('content', '')).replace('"', '""')
        response_time = msg.get('response_time', '')
        tokens = msg.get('tokens', '')
        error = msg.get('error', '')

        csv_lines.append(
            f'"{timestamp}","{msg_type}","{agent}","{content}","{response_time}","{tokens}","{error}"'
        )

    csv_content = '\n'.join(csv_lines)

    return StreamingResponse(
        iter([csv_content]),
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=a2a-logs-{datetime.now().timestamp()}.csv'
        },
    )


# ============================================================================
# Agent Integration - Trigger CodeTether agents on registered workspaces
# ============================================================================

# Import agent bridge (lazy load to avoid circular imports)
_agent_bridge = None

# Worker-synced session data: {workspace_id: [session_dicts]}
_worker_sessions: Dict[str, List[Dict[str, Any]]] = {}
# Worker-synced messages: {session_id: [message_dicts]}
_worker_messages: Dict[str, List[Dict[str, Any]]] = {}
# Real-time task output streams: {task_id: [output_lines]}
_task_output_streams: Dict[str, List[Dict[str, Any]]] = {}

# Optional Redis backing store for worker-synced sessions/messages.
#
# Why: These in-memory dicts work for single-process dev, but in production
# (multiple replicas / restarts) the UI can appear to show only "local" sessions.
# When Redis is available, we persist worker sync payloads there so any instance
# can serve them.
try:
    import redis.asyncio as aioredis  # type: ignore

    _REDIS_AVAILABLE = True
except Exception:  # pragma: no cover
    aioredis = None
    _REDIS_AVAILABLE = False

_redis_lock = asyncio.Lock()
_redis_client = None
_redis_checked = False


async def _get_redis_client():
    """Return a shared async Redis client if configured and reachable."""
    global _redis_client, _redis_checked

    if not _REDIS_AVAILABLE:
        return None

    redis_url = os.environ.get('A2A_REDIS_URL')
    if not redis_url:
        return None

    if _redis_client is not None:
        return _redis_client

    async with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        if _redis_checked:
            return None
        _redis_checked = True

        try:
            client = aioredis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
            )
            await client.ping()
            _redis_client = client
            logger.info('✓ Agent worker sync store using Redis')
            return _redis_client
        except Exception as e:
            logger.warning(
                f'Agent worker sync store: Redis unavailable ({e}); falling back to in-memory'
            )
            _redis_client = None
            return None


def _redis_key_worker_sessions(workspace_id: str) -> str:
    return f'a2a:agent:workspaces:{workspace_id}:sessions'


def _redis_key_worker_messages(session_id: str) -> str:
    return f'a2a:agent:sessions:{session_id}:messages'


async def _append_worker_message(
    session_id: str,
    message: Dict[str, Any],
    worker_id: Optional[str] = None,
) -> None:
    """Append a message to the worker-synced store (memory + Redis)."""
    existing = _worker_messages.get(session_id, [])
    _worker_messages[session_id] = [*existing, message]

    client = await _get_redis_client()
    if not client:
        return

    try:
        payload: Dict[str, Any] = {}
        raw = await client.get(_redis_key_worker_messages(session_id))
        if raw:
            payload = json.loads(raw) if isinstance(raw, str) else {}
        messages = (
            payload.get('messages') if isinstance(payload, dict) else None
        )
        if not isinstance(messages, list):
            messages = []
        messages.append(message)
        resolved_worker_id = (
            payload.get('worker_id') if isinstance(payload, dict) else None
        ) or worker_id
        await client.set(
            _redis_key_worker_messages(session_id),
            json.dumps(
                {
                    'worker_id': resolved_worker_id,
                    'updated_at': datetime.utcnow().isoformat(),
                    'messages': messages,
                }
            ),
        )
    except Exception as e:
        logger.debug(f'Failed to update Redis worker messages: {e}')


def _redis_key_workers_index() -> str:
    return 'a2a:agent:workers:index'


def _redis_key_worker(worker_id: str) -> str:
    return f'a2a:agent:workers:{worker_id}'


def _redis_key_workspaces_index() -> str:
    return 'a2a:agent:workspaces:index'


def _redis_key_workspace_meta(workspace_id: str) -> str:
    return f'a2a:agent:workspaces:{workspace_id}:meta'


async def _redis_upsert_worker(worker_info: Dict[str, Any]) -> None:
    """Best-effort: mirror worker registry to Redis so all replicas can list it."""
    client = await _get_redis_client()
    if not client:
        return

    worker_id = worker_info.get('worker_id')
    if not worker_id:
        return

    try:
        await client.sadd(_redis_key_workers_index(), worker_id)
        await client.set(_redis_key_worker(worker_id), json.dumps(worker_info))
    except Exception as e:
        logger.debug(f'Failed to persist worker to Redis: {e}')


async def _redis_delete_worker(worker_id: str) -> None:
    client = await _get_redis_client()
    if not client:
        return

    try:
        await client.srem(_redis_key_workers_index(), worker_id)
        await client.delete(_redis_key_worker(worker_id))
    except Exception as e:
        logger.debug(f'Failed to delete worker from Redis: {e}')


async def _redis_list_workers() -> List[Dict[str, Any]]:
    client = await _get_redis_client()
    if not client:
        return []

    try:
        worker_ids = await client.smembers(_redis_key_workers_index())
        if not worker_ids:
            return []

        keys = [_redis_key_worker(wid) for wid in worker_ids]
        raw_items = await client.mget(keys)

        workers: List[Dict[str, Any]] = []
        for raw in raw_items:
            if not raw:
                continue
            try:
                workers.append(json.loads(raw))
            except Exception:
                continue
        return workers
    except Exception as e:
        logger.debug(f'Failed to list workers from Redis: {e}')
        return []


async def _redis_get_worker(worker_id: str) -> Optional[Dict[str, Any]]:
    client = await _get_redis_client()
    if not client:
        return None

    try:
        raw = await client.get(_redis_key_worker(worker_id))
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug(f'Failed to get worker from Redis: {e}')
        return None


async def _redis_upsert_workspace_meta(workspace: Dict[str, Any]) -> None:
    """Best-effort: mirror workspace registry to Redis for multi-replica setups."""
    client = await _get_redis_client()
    if not client:
        return

    workspace_id = workspace.get('id')
    if not workspace_id:
        return

    try:
        await client.sadd(_redis_key_workspaces_index(), workspace_id)
        await client.set(
            _redis_key_workspace_meta(workspace_id), json.dumps(workspace)
        )
    except Exception as e:
        logger.debug(f'Failed to persist workspace meta to Redis: {e}')


async def _redis_delete_workspace_meta(workspace_id: str) -> None:
    client = await _get_redis_client()
    if not client:
        return

    try:
        await client.srem(_redis_key_workspaces_index(), workspace_id)
        await client.delete(_redis_key_workspace_meta(workspace_id))
    except Exception as e:
        logger.debug(f'Failed to delete workspace meta from Redis: {e}')


async def _redis_list_workspace_meta() -> List[Dict[str, Any]]:
    client = await _get_redis_client()
    if not client:
        return []

    try:
        workspace_ids = await client.smembers(_redis_key_workspaces_index())
        if not workspace_ids:
            return []

        keys = [_redis_key_workspace_meta(cid) for cid in workspace_ids]
        raw_items = await client.mget(keys)

        workspaces: List[Dict[str, Any]] = []
        for raw in raw_items:
            if not raw:
                continue
            try:
                workspaces.append(json.loads(raw))
            except Exception:
                continue
        return workspaces
    except Exception as e:
        logger.debug(f'Failed to list workspaces from Redis: {e}')
        return []


async def _redis_get_workspace_meta(
    workspace_id: str,
) -> Optional[Dict[str, Any]]:
    client = await _get_redis_client()
    if not client:
        return None

    try:
        raw = await client.get(_redis_key_workspace_meta(workspace_id))
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug(f'Failed to get workspace meta from Redis: {e}')
        return None


def get_agent_bridge():
    """Get or create the Agent bridge instance."""
    global _agent_bridge
    if _agent_bridge is None:
        try:
            from .agent_bridge import AgentBridge

            _agent_bridge = AgentBridge()
            logger.info('Agent bridge initialized')

            # Deduplicate workspaces on startup to clean up any stale entries
            # This runs async in background to not block initialization
            async def _deduplicate_on_startup():
                try:
                    results = await db.db_deduplicate_all_workspaces()
                    if results:
                        total = sum(results.values())
                        logger.info(
                            f'Startup deduplication: removed {total} duplicate workspace entries'
                        )
                except Exception as e:
                    logger.warning(
                        f'Failed to deduplicate workspaces on startup: {e}'
                    )

            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(_deduplicate_on_startup())
                else:
                    loop.run_until_complete(_deduplicate_on_startup())
            except RuntimeError:
                # No event loop, skip initialization
                logger.debug(
                    'No event loop available for startup initialization'
                )

            # Set up SSE worker notification hook for task updates
            try:
                from .worker_sse import (
                    get_worker_registry,
                    notify_workers_of_new_task,
                )

                async def _on_task_update(task):
                    """Notify SSE-connected workers when a task is created/updated."""
                    # Only notify for pending tasks (new tasks that need workers)
                    if (
                        hasattr(task, 'status')
                        and task.status.value == 'pending'
                    ):
                        # Skip SSE notification for Knative tasks - they're routed via CloudEvents
                        is_knative_task = (
                            task.metadata.get('knative', False)
                            if hasattr(task, 'metadata') and task.metadata
                            else False
                        )
                        if is_knative_task:
                            logger.info(
                                f'Task {task.id} is Knative task, skipping SSE notification'
                            )
                            return

                        task_data = {
                            'id': task.id,
                            'title': task.title,
                            'description': task.prompt,
                            'workspace_id': task.workspace_id,
                            'agent_type': task.agent_type,
                            'model': task.model,
                            'priority': task.priority,
                            'status': task.status.value,
                            'created_at': task.created_at.isoformat()
                            if task.created_at
                            else None,
                        }
                        try:
                            notified = await notify_workers_of_new_task(
                                task_data
                            )
                            if notified:
                                logger.debug(
                                    f'Task {task.id} notified {len(notified)} SSE workers'
                                )
                        except Exception as e:
                            logger.warning(
                                f'Failed to notify SSE workers of task {task.id}: {e}'
                            )

                _agent_bridge.on_task_update(_on_task_update)
                logger.info(
                    'SSE worker notification hook installed on agent bridge'
                )
            except ImportError:
                logger.debug(
                    'worker_sse not available, SSE notifications disabled'
                )
            except Exception as e:
                logger.warning(f'Failed to set up SSE worker hook: {e}')

        except Exception as e:
            logger.warning(f'Failed to initialize agent bridge: {e}')
            _agent_bridge = None
    return _agent_bridge


async def _rehydrate_workspace_into_bridge(workspace_id: str):
    """Best-effort: load a workspace from Redis/PostgreSQL into this instance's bridge.

    Some endpoints historically required the workspace to exist in the in-memory
    Agent bridge registry. In multi-replica setups or after restarts, the
    bridge can be empty while PostgreSQL still has durable workspace/session data.

    Returns the registered workspace (if successful) or None.
    """
    bridge = get_agent_bridge()
    if bridge is None:
        return None

    existing = bridge.get_workspace(workspace_id)
    if existing is not None:
        return existing

    meta: Optional[Dict[str, Any]] = None
    try:
        meta = await _redis_get_workspace_meta(workspace_id)
    except Exception:
        meta = None

    if not meta:
        try:
            meta = await db.db_get_workspace(workspace_id)
        except Exception:
            meta = None

    if not meta:
        return None

    name = meta.get('name') or workspace_id
    path = meta.get('path')
    if not isinstance(path, str) or not path:
        return None

    agent_config = meta.get('agent_config')
    if not isinstance(agent_config, dict):
        agent_config = {}

    desired_id = meta.get('id') or workspace_id
    try:
        workspace = await bridge.register_workspace(
            name=name,
            path=path,
            description=meta.get('description') or '',
            agent_config=agent_config,
            worker_id=meta.get('worker_id'),
            workspace_id=desired_id,
        )
        return workspace
    except Exception as e:
        logger.debug(
            f'Failed to rehydrate workspace {workspace_id} into bridge: {e}'
        )
        return None


def _extract_workspace_runtime_meta(
    workspace: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract runtime metadata from a workspace dict."""
    if not isinstance(workspace, dict):
        return {'runtime': 'container'}

    agent_config = workspace.get('agent_config')
    if not isinstance(agent_config, dict):
        agent_config = {}

    runtime = agent_config.get('workspace_runtime') or 'container'
    return {
        'runtime': runtime,
        'vm_name': agent_config.get('vm_name'),
        'vm_namespace': agent_config.get('vm_namespace'),
        'vm_status': agent_config.get('vm_status'),
        'vm_pvc_name': agent_config.get('vm_workspace_pvc'),
        'vm_ssh_service': agent_config.get('vm_ssh_service'),
        'vm_ssh_host': agent_config.get('vm_ssh_host'),
        'vm_ssh_port': agent_config.get('vm_ssh_port'),
    }


def _build_vm_spec_from_registration(registration: 'WorkspaceRegistration') -> VMWorkspaceSpec:
    """Create a VMWorkspaceSpec from request payload with safe defaults."""
    vm_cfg = registration.vm or {}
    cpu_cores = int(vm_cfg.get('cpu_cores', vm_cfg.get('cpuCores', 2)))
    memory = str(vm_cfg.get('memory', '8Gi'))
    disk_size = str(vm_cfg.get('disk_size', vm_cfg.get('diskSize', '30Gi')))
    image = str(vm_cfg.get('image', '')).strip()
    ssh_public_key = str(vm_cfg.get('ssh_public_key', vm_cfg.get('sshPublicKey', ''))).strip()
    ssh_user = str(vm_cfg.get('ssh_user', vm_cfg.get('sshUser', 'coder'))).strip() or 'coder'

    defaults = VMWorkspaceSpec()
    return VMWorkspaceSpec(
        cpu_cores=max(1, cpu_cores),
        memory=memory,
        disk_size=disk_size,
        image=image or defaults.image,
        ssh_public_key=ssh_public_key or defaults.ssh_public_key,
        ssh_user=ssh_user,
    )


class WorkspaceRegistration(BaseModel):
    """Request model for registering a workspace."""

    name: str
    path: str = ''  # Can be empty when git_url is provided
    description: str = ''
    agent_config: Dict[str, Any] = {}
    worker_id: Optional[str] = None  # Associate with a specific worker
    git_url: Optional[str] = None  # HTTPS Git URL to clone
    git_branch: str = 'main'
    git_token: Optional[str] = None  # Access token (stored in Vault, not DB)
    runtime: Literal['container', 'vm'] = 'container'
    vm: Optional[Dict[str, Any]] = None


class AgentTrigger(BaseModel):
    """Request model for triggering an agent."""

    prompt: str
    agent: str = 'build'
    model: Optional[str] = None
    model_ref: Optional[str] = None
    files: List[str] = []
    worker_personality: Optional[str] = None
    notify_email: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AgentMessage(BaseModel):
    """Request model for sending a message to an agent."""

    message: str
    agent: Optional[str] = None


class AgentTaskCreate(BaseModel):
    """Request model for creating an agent task."""

    title: str
    prompt: str
    agent_type: str = 'build'
    priority: int = 0
    metadata: Dict[str, Any] = {}
    workspace_id: Optional[str] = None  # Optional: specify target workspace
    model: Optional[str] = None  # Optional: specify model
    model_ref: Optional[str] = None  # Optional: normalized provider:model
    worker_personality: Optional[str] = None


class WatchModeConfig(BaseModel):
    """Request model for configuring watch mode."""

    interval: int = 5  # Seconds between task checks


# Agent API Router (primary - used by codetether-agent workers via SSE)
agent_router = APIRouter(prefix='/v1/agent', tags=['agent'])

# Backward-compatible alias (deprecated — will be removed in a future release)
agent_router_alias = agent_router


@agent_router.on_event('startup')
async def agent_startup():
    """Load workspaces from PostgreSQL on startup."""
    try:
        bridge = None
        try:
            bridge = get_agent_bridge()
        except Exception:
            pass

        if bridge:
            await bridge._load_workspaces_from_db()
    except Exception as e:
        logger.warning(f'Failed to load workspaces on startup: {e}')


@lru_cache(maxsize=1)
def _get_auth_tokens_set() -> set:
    """Return the set of configured auth tokens (values only)."""
    raw = os.environ.get('A2A_AUTH_TOKENS')
    if not raw:
        return set()
    tokens: set = set()
    for pair in raw.split(','):
        pair = pair.strip()
        if not pair:
            continue
        if ':' in pair:
            _, token = pair.split(':', 1)
            token = token.strip()
            if token:
                tokens.add(token)
    return tokens


def _require_ingest_auth(request: Request) -> None:
    """Optionally require Bearer auth when A2A_AUTH_TOKENS is configured."""
    tokens = _get_auth_tokens_set()
    if not tokens:
        return
    auth = (
        request.headers.get('authorization')
        or request.headers.get('Authorization')
        or ''
    )
    if not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing Bearer token')
    token = auth.removeprefix('Bearer ').strip()
    if not token or token not in tokens:
        raise HTTPException(status_code=403, detail='Invalid token')


@agent_router_alias.get('/status')
async def agent_status():
    """Check Agent worker status including local runtime sessions."""
    bridge = get_agent_bridge()

    # Check for local Agent runtime storage
    runtime_available = False
    runtime_sessions = 0
    runtime_projects = 0
    storage_path = None

    # Try to find Agent storage
    possible_paths = [
        os.path.expanduser('~/.local/share/codetether/storage'),
        '/app/.local/share/codetether/storage',
    ]
    for path in possible_paths:
        if os.path.isdir(path):
            storage_path = path
            runtime_available = True
            # Count projects and sessions
            projects_dir = os.path.join(path, 'project')
            sessions_dir = os.path.join(path, 'session')
            if os.path.isdir(projects_dir):
                runtime_projects = len(
                    [f for f in os.listdir(projects_dir) if f.endswith('.json')]
                )
            if os.path.isdir(sessions_dir):
                for proj_id in os.listdir(sessions_dir):
                    proj_sessions = os.path.join(sessions_dir, proj_id)
                    if os.path.isdir(proj_sessions):
                        runtime_sessions += len(
                            [
                                f
                                for f in os.listdir(proj_sessions)
                                if f.endswith('.json')
                            ]
                        )
            break

    if bridge is None:
        return {
            'available': runtime_available,
            'message': 'Agent worker runtime detected'
            if runtime_available
            else 'Agent worker not available',
            'agent_binary': None,
            'registered_workspaces': 0,
            'runtime': {
                'available': runtime_available,
                'storage_path': storage_path,
                'projects': runtime_projects,
                'sessions': runtime_sessions,
            }
            if runtime_available
            else None,
        }

    registered_workspaces = len(bridge.list_workspaces())
    try:
        # If Redis is configured, it may have the authoritative multi-replica
        # registry even when this instance has an empty local DB.
        redis_workspaces = await _redis_list_workspace_meta()
        registered_workspaces = max(registered_workspaces, len(redis_workspaces))
    except Exception:
        pass

    return {
        'available': True,
        'message': 'Agent bridge ready',
        'agent_binary': bridge.agent_bin,
        'registered_workspaces': registered_workspaces,
        'auto_start': bridge.auto_start,
        'runtime': {
            'available': runtime_available,
            'storage_path': storage_path,
            'projects': runtime_projects,
            'sessions': runtime_sessions,
        }
        if runtime_available
        else None,
    }


@agent_router_alias.get('/database/status')
async def database_status():
    """Check PostgreSQL database status and statistics."""
    return await db.db_health_check()


@agent_router_alias.get('/database/sessions')
async def database_sessions(
    limit: int = 100,
    offset: int = 0,
):
    """
    List all sessions from PostgreSQL database.

    Returns sessions across all workspaces, sorted by most recently updated.
    Use this endpoint for a global view of all agent sessions.
    """
    sessions = await db.db_list_all_sessions(limit=limit, offset=offset)
    return {
        'sessions': sessions,
        'total': len(sessions),
        'limit': limit,
        'offset': offset,
        'source': 'postgresql',
    }


@agent_router_alias.get('/database/workspaces')
async def database_workspaces():
    """
    List all workspaces from PostgreSQL database.

    Returns all registered workspaces with their worker assignments.
    """
    workspaces = await db.db_list_workspaces()
    return {
        'workspaces': workspaces,
        'total': len(workspaces),
        'source': 'postgresql',
    }


@agent_router_alias.post('/database/workspaces/deduplicate')
async def deduplicate_workspaces():
    """
    Remove duplicate workspace entries, keeping the oldest (canonical) ID for each path.

    This is useful after server restarts or when workers have created duplicate entries.
    The canonical ID is preserved to maintain consistency with existing tasks and sessions.
    """
    results = await db.db_deduplicate_all_workspaces()

    total_removed = sum(results.values())
    return {
        'success': True,
        'deduplicated_paths': results,
        'total_duplicates_removed': total_removed,
        'message': f'Removed {total_removed} duplicate workspace entries'
        if total_removed > 0
        else 'No duplicates found',
    }


@agent_router_alias.get('/database/workers')
async def database_workers():
    """
    List all workers from PostgreSQL database.

    Returns all registered workers with their status and capabilities.
    """
    workers = await db.db_list_workers()
    return {
        'workers': workers,
        'total': len(workers),
        'source': 'postgresql',
    }


# =============================================================================
# Agent Runtime Session Endpoints (Direct Storage Access)
# =============================================================================
# These endpoints read directly from agent storage directory
# (~/.local/share/codetether/storage/) without requiring a workspace to be registered.
# This allows users to immediately see and resume their existing sessions.

# XDG Base Directory paths for Agent storage
AGENT_DATA_DIR = os.environ.get(
    'AGENT_DATA_DIR', os.path.expanduser('~/.local/share/codetether')
)
AGENT_STORAGE_DIR = os.path.join(AGENT_DATA_DIR, 'storage')


def _get_agent_storage_path() -> Optional[str]:
    """Get the Agent storage directory path if it exists."""
    if os.path.isdir(AGENT_STORAGE_DIR):
        return AGENT_STORAGE_DIR
    # Fallback locations
    fallbacks = [
        os.path.expanduser('~/.local/share/codetether/storage'),
        '/app/.local/share/codetether/storage',
    ]
    for path in fallbacks:
        if os.path.isdir(path):
            return path
    return None


async def _read_json_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file."""
    try:
        import aiofiles

        async with aiofiles.open(filepath, 'r') as f:
            content = await f.read()
            return json.loads(content)
    except ImportError:
        # Fallback to sync if aiofiles not available
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f'Failed to read {filepath}: {e}')
            return None
    except Exception as e:
        logger.debug(f'Failed to read {filepath}: {e}')
        return None


@agent_router_alias.get('/runtime/status')
async def agent_runtime_status():
    """
    Check if Agent runtime is available on this system.

    Returns information about the local agent installation and storage.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        return {
            'available': False,
            'message': 'Agent storage not found on this system',
            'storage_path': None,
            'projects': 0,
            'sessions': 0,
        }

    # Count projects and sessions
    projects_dir = os.path.join(storage_path, 'project')
    sessions_dir = os.path.join(storage_path, 'session')

    project_count = 0
    session_count = 0

    if os.path.isdir(projects_dir):
        project_count = len(
            [f for f in os.listdir(projects_dir) if f.endswith('.json')]
        )

    if os.path.isdir(sessions_dir):
        for project_id in os.listdir(sessions_dir):
            project_sessions_dir = os.path.join(sessions_dir, project_id)
            if os.path.isdir(project_sessions_dir):
                session_count += len(
                    [
                        f
                        for f in os.listdir(project_sessions_dir)
                        if f.endswith('.json')
                    ]
                )

    return {
        'available': True,
        'message': 'Agent worker runtime detected',
        'storage_path': storage_path,
        'projects': project_count,
        'sessions': session_count,
    }


@agent_router_alias.get('/runtime/projects')
async def list_agent_projects():
    """
    List all Agent projects detected on this system.

    Projects are identified by their git commit hash and include
    the worktree path where the project is located.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        raise HTTPException(
            status_code=503,
            detail='Agent storage not available on this system',
        )

    projects_dir = os.path.join(storage_path, 'project')
    sessions_dir = os.path.join(storage_path, 'session')

    if not os.path.isdir(projects_dir):
        return {'projects': []}

    projects = []
    for filename in os.listdir(projects_dir):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(projects_dir, filename)
        project_data = await _read_json_file(filepath)

        if project_data:
            project_id = project_data.get('id', filename[:-5])

            # Count sessions for this project
            session_count = 0
            project_sessions_dir = os.path.join(sessions_dir, project_id)
            if os.path.isdir(project_sessions_dir):
                session_count = len(
                    [
                        f
                        for f in os.listdir(project_sessions_dir)
                        if f.endswith('.json')
                    ]
                )

            projects.append(
                {
                    'id': project_id,
                    'worktree': project_data.get('worktree', '/'),
                    'vcs': project_data.get('vcs'),
                    'vcs_dir': project_data.get('vcsDir'),
                    'created_at': project_data.get('time', {}).get('created'),
                    'updated_at': project_data.get('time', {}).get('updated'),
                    'session_count': session_count,
                }
            )

    # Sort by most recently updated
    projects.sort(key=lambda p: p.get('updated_at') or 0, reverse=True)

    return {'projects': projects}


@agent_router_alias.get('/runtime/sessions')
async def list_all_runtime_sessions(
    project_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all Agent sessions, optionally filtered by project.

    Sessions are sorted by most recently updated first.
    Use project_id to filter sessions for a specific project.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        raise HTTPException(
            status_code=503,
            detail='Agent storage not available on this system',
        )

    sessions_dir = os.path.join(storage_path, 'session')

    if not os.path.isdir(sessions_dir):
        return {'sessions': [], 'total': 0}

    all_sessions = []

    # Determine which project directories to scan
    if project_id:
        project_dirs = (
            [project_id]
            if os.path.isdir(os.path.join(sessions_dir, project_id))
            else []
        )
    else:
        project_dirs = [
            d
            for d in os.listdir(sessions_dir)
            if os.path.isdir(os.path.join(sessions_dir, d))
        ]

    for proj_id in project_dirs:
        project_sessions_dir = os.path.join(sessions_dir, proj_id)

        for filename in os.listdir(project_sessions_dir):
            if not filename.endswith('.json'):
                continue

            filepath = os.path.join(project_sessions_dir, filename)
            session_data = await _read_json_file(filepath)

            if session_data:
                all_sessions.append(
                    {
                        'id': session_data.get('id', filename[:-5]),
                        'project_id': session_data.get('projectID', proj_id),
                        'directory': session_data.get('directory'),
                        'title': session_data.get('title', 'Untitled Session'),
                        'version': session_data.get('version'),
                        'created_at': session_data.get('time', {}).get(
                            'created'
                        ),
                        'updated_at': session_data.get('time', {}).get(
                            'updated'
                        ),
                        'summary': session_data.get('summary', {}),
                    }
                )

    # Sort by most recently updated
    all_sessions.sort(key=lambda s: s.get('updated_at') or 0, reverse=True)

    total = len(all_sessions)
    paginated = all_sessions[offset : offset + limit]

    return {
        'sessions': paginated,
        'total': total,
        'limit': limit,
        'offset': offset,
    }


@agent_router_alias.get('/runtime/sessions/{session_id}')
async def get_runtime_session(session_id: str):
    """
    Get details for a specific agent session.

    Returns the full session data including metadata.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        raise HTTPException(
            status_code=503,
            detail='Agent storage not available on this system',
        )

    sessions_dir = os.path.join(storage_path, 'session')

    # Search all project directories for the session
    for project_id in os.listdir(sessions_dir):
        project_sessions_dir = os.path.join(sessions_dir, project_id)
        if not os.path.isdir(project_sessions_dir):
            continue

        session_file = os.path.join(project_sessions_dir, f'{session_id}.json')
        if os.path.isfile(session_file):
            session_data = await _read_json_file(session_file)
            if session_data:
                return {
                    'session': {
                        'id': session_data.get('id', session_id),
                        'project_id': session_data.get('projectID', project_id),
                        'directory': session_data.get('directory'),
                        'title': session_data.get('title', 'Untitled Session'),
                        'version': session_data.get('version'),
                        'created_at': session_data.get('time', {}).get(
                            'created'
                        ),
                        'updated_at': session_data.get('time', {}).get(
                            'updated'
                        ),
                        'summary': session_data.get('summary', {}),
                    }
                }

    raise HTTPException(
        status_code=404, detail=f'Session {session_id} not found'
    )


@agent_router_alias.get('/runtime/sessions/{session_id}/messages')
async def get_runtime_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """
    Get messages for a specific agent session.

    Returns the conversation history for the session.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        raise HTTPException(
            status_code=503,
            detail='Agent storage not available on this system',
        )

    messages_dir = os.path.join(storage_path, 'message', session_id)

    if not os.path.isdir(messages_dir):
        return {'messages': [], 'total': 0, 'session_id': session_id}

    all_messages = []

    for filename in os.listdir(messages_dir):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(messages_dir, filename)
        msg_data = await _read_json_file(filepath)

        if msg_data:
            all_messages.append(
                {
                    'id': msg_data.get('id', filename[:-5]),
                    'session_id': msg_data.get('sessionID', session_id),
                    'role': msg_data.get('role'),
                    'created_at': msg_data.get('time', {}).get('created'),
                    'model': _normalize_model_value(msg_data.get('model')),
                    'cost': msg_data.get('cost'),
                    'tokens': msg_data.get('tokens'),
                    'tool_calls': msg_data.get('tool_calls', []),
                }
            )

    # Sort by created time
    all_messages.sort(key=lambda m: m.get('created_at') or 0)

    total = len(all_messages)
    paginated = all_messages[offset : offset + limit]

    return {
        'messages': paginated,
        'total': total,
        'limit': limit,
        'offset': offset,
        'session_id': session_id,
    }


@agent_router_alias.get('/runtime/sessions/{session_id}/parts')
async def get_runtime_session_parts(
    session_id: str,
    message_id: Optional[str] = None,
    limit: int = 100,
):
    """
    Get message parts (content chunks) for a session.

    Parts contain the actual text content, tool calls, and other
    structured data from the conversation.
    """
    storage_path = _get_agent_storage_path()

    if not storage_path:
        raise HTTPException(
            status_code=503,
            detail='Agent storage not available on this system',
        )

    # Parts are stored per message: storage/part/{message_id}/*.json
    parts_base_dir = os.path.join(storage_path, 'part')

    if not os.path.isdir(parts_base_dir):
        return {'parts': [], 'session_id': session_id}

    all_parts = []

    # If message_id specified, only get parts for that message
    if message_id:
        message_parts_dir = os.path.join(parts_base_dir, message_id)
        if os.path.isdir(message_parts_dir):
            for filename in os.listdir(message_parts_dir):
                if not filename.endswith('.json'):
                    continue
                filepath = os.path.join(message_parts_dir, filename)
                part_data = await _read_json_file(filepath)
                if part_data:
                    all_parts.append(part_data)
    else:
        # Get messages for this session first, then their parts
        messages_dir = os.path.join(storage_path, 'message', session_id)
        if os.path.isdir(messages_dir):
            for msg_filename in os.listdir(messages_dir):
                if not msg_filename.endswith('.json'):
                    continue
                msg_id = msg_filename[:-5]
                message_parts_dir = os.path.join(parts_base_dir, msg_id)
                if os.path.isdir(message_parts_dir):
                    for filename in os.listdir(message_parts_dir)[:limit]:
                        if not filename.endswith('.json'):
                            continue
                        filepath = os.path.join(message_parts_dir, filename)
                        part_data = await _read_json_file(filepath)
                        if part_data:
                            part_data['message_id'] = msg_id
                            all_parts.append(part_data)

    return {
        'parts': all_parts[:limit],
        'session_id': session_id,
        'message_id': message_id,
    }


@agent_router_alias.get('/models')
async def list_models():
    """List available AI models from SSE-connected codetether-agent workers only."""
    models_by_id = {}  # id -> (model_dict, has_pricing)

    # Only use SSE-connected workers (codetether-agent)
    connected_worker_ids: set = set()
    try:
        from .worker_sse import get_worker_registry

        sse_registry = get_worker_registry()
        sse_workers = await sse_registry.list_workers()
        connected_worker_ids = {
            str(w.get('worker_id', '')) for w in sse_workers if w.get('worker_id')
        }
    except Exception:
        pass

    if not connected_worker_ids:
        return {'models': [], 'default': None}

    all_workers = await list_workers()
    workers = [
        w for w in all_workers
        if str(w.get('worker_id', '')) in connected_worker_ids
    ]

    for worker in workers:
        worker_models = worker.get('models', [])
        for m in worker_models:
            mid = m.get('id')
            if not mid:
                continue
            # Copy to avoid mutating the stored model dict in-place
            model = dict(m)
            if 'provider' in model:
                provider_base = model['provider']
                via_suffix = f' (via {worker.get("name", "worker")})'
                if via_suffix not in provider_base:
                    model['provider'] = provider_base + via_suffix
            has_pricing = model.get('input_cost_per_million') is not None
            existing = models_by_id.get(mid)
            # Keep this version if: no existing, or this one has pricing and existing doesn't
            if existing is None or (has_pricing and not existing[1]):
                models_by_id[mid] = (model, has_pricing)

    all_models = [entry[0] for entry in models_by_id.values()]

    if all_models:
        # Sort models: Gemini 3 Flash first, then by provider
        all_models.sort(
            key=lambda x: (
                0 if 'gemini-3-flash' in x['id'].lower() else 1,
                x.get('provider', ''),
                x.get('name', ''),
            )
        )

        # Find a good default (prefer Gemini 3 Flash)
        default_model = 'google/gemini-3-flash-preview'
        found_default = False
        for m in all_models:
            if m['id'] == default_model:
                found_default = True
                break

        if not found_default and all_models:
            default_model = all_models[0]['id']

        return {'models': all_models, 'default': default_model}

    # Return empty list if no workers registered
    return {'models': [], 'default': None}


@agent_router_alias.get('/providers')
async def list_providers():
    """List available AI providers from HashiCorp Vault (source of truth).

    Reads the configured providers from Vault at secret/codetether/providers/,
    cross-references with worker model data for model counts, and returns
    a structured list of providers with metadata.
    """
    from .vault_client import get_vault_client

    vault = get_vault_client()

    # 1. List providers from Vault (source of truth)
    vault_providers = await vault.list_secrets('codetether/providers')
    # Remove trailing slashes and filter out 'test'
    vault_provider_ids = [
        p.rstrip('/') for p in vault_providers if p.rstrip('/') != 'test'
    ]

    # 2. Get unique model counts per provider from workers (deduplicate by model ID)
    workers = await list_workers()
    provider_model_ids: Dict[str, set] = {}
    for worker in workers:
        for m in worker.get('models', []):
            pid = m.get('provider_id', '')
            mid = m.get('id', '')
            if pid in vault_provider_ids and mid:
                if pid not in provider_model_ids:
                    provider_model_ids[pid] = set()
                provider_model_ids[pid].add(mid)

    # 3. Read provider metadata from Vault (has api_key, base_url, etc.)
    provider_details = []
    for pid in sorted(vault_provider_ids):
        secret = await vault.read_secret(f'codetether/providers/{pid}')
        has_api_key = bool(secret and secret.get('api_key'))
        has_base_url = bool(secret and secret.get('base_url'))
        provider_details.append({
            'provider_id': pid,
            'configured': has_api_key,
            'has_base_url': has_base_url,
            'model_count': len(provider_model_ids.get(pid, set())),
        })

    return {
        'providers': provider_details,
        'total': len(provider_details),
        'source': 'vault',
    }


def _normalize_workspace_path(path: Optional[str]) -> Optional[str]:
    if not path or not isinstance(path, str):
        return None
    try:
        return os.path.abspath(os.path.expanduser(path))
    except Exception:
        return path


@agent_router_alias.get('/workspaces')
async def get_workspaces(
    path: Optional[str] = None,
    include_duplicates: bool = False,
):
    """Backward-compatible GET handler.

    - If `path` is provided, returns the normalized filesystem path.
    - If `path` is omitted, returns the list of registered workspaces.

    Historically, the UI called this as a listing endpoint; FastAPI treated
    `path` as required and returned 422. We keep the path-normalization behavior
    while also supporting listing to prevent client errors.
    """
    if path:
        return _normalize_workspace_path(path)
    return await list_workspaces(include_duplicates=include_duplicates)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Normalize to naive UTC for consistent comparisons/subtraction.
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _workspace_sort_key(cb: Dict[str, Any]) -> tuple:
    # Prefer most recently updated, then created, then stable id
    updated = _parse_iso_datetime(cb.get('updated_at'))
    created = _parse_iso_datetime(cb.get('created_at'))
    # None sorts last
    return (
        updated or datetime.min,
        created or datetime.min,
        str(cb.get('id') or ''),
    )


async def _get_active_worker_ids() -> set:
    """Best-effort set of worker_ids considered "active" based on last_seen."""
    window_seconds = int(
        os.environ.get('A2A_WORKER_ACTIVE_WINDOW_SECONDS', '300')
    )
    now = datetime.utcnow()

    db_workers = await db.db_list_workers()
    redis_workers = await _redis_list_workers()

    merged: Dict[str, Dict[str, Any]] = {}
    # Keep the freshest last_seen per worker_id
    for w in list(_registered_workers.values()) + redis_workers + db_workers:
        wid = w.get('worker_id')
        if not wid:
            continue
        prev = merged.get(wid)
        if prev is None:
            merged[wid] = w
            continue
        prev_seen = _parse_iso_datetime(prev.get('last_seen'))
        cur_seen = _parse_iso_datetime(w.get('last_seen'))
        if (cur_seen or datetime.min) > (prev_seen or datetime.min):
            merged[wid] = w

    active: set = set()
    for wid, w in merged.items():
        if w.get('status') and str(w.get('status')).lower() != 'active':
            continue
        last_seen = _parse_iso_datetime(w.get('last_seen'))
        if not last_seen:
            continue
        if (now - last_seen).total_seconds() <= window_seconds:
            active.add(wid)
    return active


def _dedupe_workspaces_by_path(
    workspaces: List[Dict[str, Any]],
    active_worker_ids: set,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    passthrough: List[Dict[str, Any]] = []

    for cb in workspaces:
        path = _normalize_workspace_path(cb.get('path'))
        if not path:
            passthrough.append(cb)
            continue
        grouped.setdefault(path, []).append(cb)

    deduped: List[Dict[str, Any]] = []

    for path, cbs in grouped.items():
        if len(cbs) == 1:
            cb = cbs[0]
            cb['path'] = path
            deduped.append(cb)
            continue

        active_candidates = [
            cb for cb in cbs if cb.get('worker_id') in active_worker_ids
        ]
        if active_candidates:
            candidates = active_candidates
        else:
            # Prefer worker-owned entries even if the worker is currently inactive.
            owned_candidates = [cb for cb in cbs if cb.get('worker_id')]
            candidates = owned_candidates if owned_candidates else cbs
        chosen = max(candidates, key=_workspace_sort_key)

        # Provide visibility into de-duping without breaking older clients.
        chosen = dict(chosen)
        chosen['path'] = path
        chosen['aliases'] = [
            cb.get('id') for cb in cbs if cb.get('id') != chosen.get('id')
        ]
        chosen['duplicate_count'] = len(cbs)
        deduped.append(chosen)

    # Keep stable ordering
    deduped.sort(key=lambda cb: (cb.get('name') or '', cb.get('path') or ''))
    passthrough.sort(
        key=lambda cb: (cb.get('name') or '', str(cb.get('id') or ''))
    )
    return deduped + passthrough


@agent_router_alias.get('/workspaces/list')
async def list_workspaces(include_duplicates: bool = False):
    """List all registered workspaces.

    By default, de-duplicates entries that share the same filesystem path and
    prefers workspaces owned by recently-seen workers. Pass include_duplicates=true
    to return the raw, unfiltered list.
    """
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # Collect from all sources: PostgreSQL > Redis > local bridge
    local_workspaces = [cb.to_dict() for cb in bridge.list_workspaces()]
    redis_workspaces = await _redis_list_workspace_meta()
    db_workspaces = await db.db_list_workspaces()

    merged: Dict[str, Dict[str, Any]] = {}

    # Local first (most up-to-date for this instance)
    for cb in local_workspaces:
        cid = cb.get('id')
        if cid:
            merged[cid] = cb

    # Redis (may have workspaces from other instances)
    for cb in redis_workspaces:
        cid = cb.get('id')
        if cid and cid not in merged:
            merged[cid] = cb

    # PostgreSQL (durable, survives restarts)
    for cb in db_workspaces:
        cid = cb.get('id')
        if cid and cid not in merged:
            merged[cid] = cb

    result = list(merged.values())
    if include_duplicates:
        return result

    try:
        active_worker_ids = await _get_active_worker_ids()
    except Exception:
        active_worker_ids = set()

    return _dedupe_workspaces_by_path(result, active_worker_ids)


@agent_router_alias.post('/workspaces')
async def register_workspace(registration: WorkspaceRegistration):
    """
    Register a new workspace for agent work.

    If worker_id is provided (from a worker), the workspace is registered directly
    since the worker has already validated the path exists locally.

    If NO worker_id is provided (from UI), a registration task is created for
    workers to pick up, validate the path, and confirm registration.
    """
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # ── Git URL registration ─────────────────────────────────────
    # If a git_url is provided, validate it, store credentials in Vault,
    # and create a clone task for workers. The path is resolved after cloning.
    if registration.git_url:
        from .git_service import validate_git_url, store_git_credentials
        if not validate_git_url(registration.git_url):
            raise HTTPException(
                status_code=400,
                detail='Invalid Git URL. Only HTTPS URLs from GitHub, GitLab, Bitbucket, and Azure DevOps are allowed.',
            )

        import hashlib
        workspace_id = hashlib.sha256(
            registration.git_url.encode()
        ).hexdigest()[:16]

        # Store Git token in Vault if provided (never persisted in DB)
        if registration.git_token:
            await store_git_credentials(workspace_id, registration.git_token)

        # Register workspace with git_url (path TBD after clone)
        workspace_data = {
            'id': workspace_id,
            'name': registration.name,
            'path': registration.path or f'/var/lib/codetether/repos/{workspace_id}',
            'description': registration.description,
            'agent_config': registration.agent_config,
            'git_url': registration.git_url,
            'git_branch': registration.git_branch,
            'status': 'cloning',
        }
        await db.db_upsert_workspace(workspace_data)

        # Create a clone task for workers to pick up
        task = await bridge.create_task(
            codebase_id=workspace_id,
            title=f'Clone repository: {registration.name}',
            prompt=f'Clone Git repo {registration.git_url} (branch: {registration.git_branch})',
            agent_type='clone_repo',
            metadata={
                'git_url': registration.git_url,
                'git_branch': registration.git_branch,
                'workspace_id': workspace_id,
            },
        )

        return {
            'success': True,
            'workspace_id': workspace_id,
            'pending': True,
            'task_id': task.id if task else None,
            'message': f'Repository registration created. A worker will clone {registration.git_url}.',
        }

    # ── VM workspace registration (KubeVirt/Harvester) ────────────────
    if registration.runtime == 'vm':
        if registration.worker_id:
            raise HTTPException(
                status_code=400,
                detail='worker_id cannot be provided when runtime=vm',
            )
        if not is_vm_workspaces_enabled():
            raise HTTPException(
                status_code=400,
                detail=(
                    'VM workspace provisioning is disabled. '
                    'Set VM_WORKSPACES_ENABLED=true in the server environment.'
                ),
            )

        workspace_id = str(uuid.uuid4())[:8]
        workspace_path = registration.path or '/workspace'
        try:
            vm_spec = _build_vm_spec_from_registration(registration)
        except (TypeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid VM spec in registration payload: {e}',
            )

        vm_result = await vm_workspace_provisioner.provision_workspace_vm(
            workspace_id=workspace_id,
            workspace_name=registration.name,
            tenant_id='default',
            spec=vm_spec,
        )
        if not vm_result.success:
            raise HTTPException(
                status_code=502,
                detail=(
                    vm_result.error_message
                    or 'Failed to provision VM workspace'
                ),
            )

        runtime_agent_config = dict(registration.agent_config or {})
        runtime_agent_config.update(
            {
                'workspace_runtime': 'vm',
                'vm_provider': 'kubevirt',
                'vm_name': vm_result.vm_name,
                'vm_namespace': vm_result.namespace,
                'vm_status': vm_result.status,
                'vm_workspace_pvc': vm_result.pvc_name,
                'vm_ssh_service': vm_result.ssh_service_name,
                'vm_ssh_host': vm_result.ssh_host,
                'vm_ssh_port': vm_result.ssh_port,
                'vm_spec': {
                    'cpu_cores': vm_spec.cpu_cores,
                    'memory': vm_spec.memory,
                    'disk_size': vm_spec.disk_size,
                    'image': vm_spec.image,
                },
            }
        )

        workspace_data = {
            'id': workspace_id,
            'name': registration.name,
            'path': workspace_path,
            'description': registration.description,
            'agent_config': runtime_agent_config,
            'status': 'active',
        }

        # Persist to PostgreSQL + Redis first (source of truth)
        await db.db_upsert_workspace(workspace_data)
        await _redis_upsert_workspace_meta(workspace_data)

        # Mirror into in-memory bridge for local API workflows.
        try:
            workspace = await bridge.register_workspace(
                name=registration.name,
                path=workspace_path,
                description=registration.description,
                agent_config=runtime_agent_config,
                workspace_id=workspace_id,
            )
            workspace_data = workspace.to_dict()
            workspace_data['agent_config'] = runtime_agent_config
            await db.db_upsert_workspace(workspace_data)
            await _redis_upsert_workspace_meta(workspace_data)
        except Exception as e:
            logger.warning(
                f'VM workspace {workspace_id} provisioned but bridge registration failed: {e}'
            )

        await monitoring_service.log_message(
            agent_name='CodeTether Agent',
            content=f'Provisioned VM workspace: {registration.name}',
            message_type='system',
            metadata={
                'workspace_id': workspace_id,
                'runtime': 'vm',
                'vm_name': vm_result.vm_name,
                'vm_namespace': vm_result.namespace,
                'vm_status': vm_result.status,
            },
        )

        return {
            'success': True,
            'workspace_id': workspace_id,
            'workspace': workspace_data,
            'runtime': 'vm',
            'vm': vm_result.to_dict(),
        }

    # If worker_id provided, this is a confirmed registration from a worker
    # The worker has already validated the path exists on its machine
    if registration.worker_id:
        try:
            normalized_path = (
                _normalize_workspace_path(registration.path) or registration.path
            )

            # If we've seen this path before (e.g., after a server restart), reuse
            # the existing workspace ID from PostgreSQL to prevent duplicates.
            existing_id: Optional[str] = None
            try:
                existing = await db.db_list_workspaces_by_path(normalized_path)
                if existing:
                    # Prefer most recently updated entry.
                    existing_id = existing[0].get('id')
            except Exception:
                existing_id = None

            workspace = await bridge.register_workspace(
                name=registration.name,
                path=normalized_path,
                description=registration.description,
                agent_config=registration.agent_config,
                worker_id=registration.worker_id,
                workspace_id=existing_id,
            )

            workspace_dict = workspace.to_dict()

            # Primary persistence: PostgreSQL
            await db.db_upsert_workspace(workspace_dict)

            # Secondary: Redis for distributed session sync
            await _redis_upsert_workspace_meta(workspace_dict)

            await monitoring_service.log_message(
                agent_name='CodeTether Agent',
                content=f'Registered workspace: {registration.name} at {registration.path} (worker: {registration.worker_id})',
                message_type='system',
                metadata={
                    'workspace_id': workspace.id,
                    'path': registration.path,
                    'worker_id': registration.worker_id,
                },
            )

            return {'success': True, 'workspace': workspace_dict}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # No worker_id - this is a registration REQUEST from UI
    # Create a task for workers to validate and claim this workspace
    # Check if any workers are registered (check all sources)
    db_workers = await db.db_list_workers()
    redis_workers = await _redis_list_workers()
    all_workers = (
        list(_registered_workers.values()) + db_workers + redis_workers
    )
    if not all_workers:
        raise HTTPException(
            status_code=400,
            detail='No workers available. Start a worker on the machine with access to this path.',
        )

    # Create a "register_workspace" task that workers will pick up
    task = await bridge.create_task(
        codebase_id='__pending__',  # Special marker for registration tasks
        title=f'Register workspace: {registration.name}',
        prompt=f'Validate and register workspace at path: {registration.path}',
        agent_type='register_workspace',
        metadata={
            'name': registration.name,
            'path': registration.path,
            'description': registration.description,
            'agent_config': registration.agent_config,
        },
    )

    if task:
        await monitoring_service.log_message(
            agent_name='CodeTether Agent',
            content=f'Created registration task for: {registration.name} at {registration.path}',
            message_type='system',
            metadata={
                'task_id': task.id,
                'path': registration.path,
            },
        )

        return {
            'success': True,
            'pending': True,
            'task_id': task.id,
            'message': f'Registration task created. A worker will validate the path and confirm registration.',
        }
    else:
        raise HTTPException(
            status_code=500, detail='Failed to create registration task'
        )


@agent_router_alias.get('/workspaces/{workspace_id}')
async def get_workspace(workspace_id: str, include_runtime_status: bool = False):
    """Get details of a registered workspace."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # Check local bridge first
    workspace = bridge.get_workspace(workspace_id)
    if workspace:
        workspace_dict = workspace.to_dict()
        if include_runtime_status:
            runtime_meta = _extract_workspace_runtime_meta(workspace_dict)
            if runtime_meta.get('runtime') == 'vm' and runtime_meta.get('vm_name'):
                vm_status = await vm_workspace_provisioner.get_vm_status(
                    runtime_meta['vm_name']
                )
                if isinstance(workspace_dict.get('agent_config'), dict):
                    workspace_dict['agent_config']['vm_status'] = vm_status
        return workspace_dict

    # Check PostgreSQL
    db_workspace = await db.db_get_workspace(workspace_id)
    if db_workspace:
        if include_runtime_status:
            runtime_meta = _extract_workspace_runtime_meta(db_workspace)
            if runtime_meta.get('runtime') == 'vm' and runtime_meta.get('vm_name'):
                vm_status = await vm_workspace_provisioner.get_vm_status(
                    runtime_meta['vm_name']
                )
                if isinstance(db_workspace.get('agent_config'), dict):
                    db_workspace['agent_config']['vm_status'] = vm_status
        return db_workspace

    # Check Redis fallback
    redis_workspace = await _redis_get_workspace_meta(workspace_id)
    if redis_workspace:
        if include_runtime_status:
            runtime_meta = _extract_workspace_runtime_meta(redis_workspace)
            if runtime_meta.get('runtime') == 'vm' and runtime_meta.get('vm_name'):
                vm_status = await vm_workspace_provisioner.get_vm_status(
                    runtime_meta['vm_name']
                )
                if isinstance(redis_workspace.get('agent_config'), dict):
                    redis_workspace['agent_config']['vm_status'] = vm_status
        return redis_workspace

    raise HTTPException(status_code=404, detail='Workspace not found')


@agent_router_alias.delete('/workspaces/{workspace_id}')
async def unregister_workspace(workspace_id: str):
    """Unregister a workspace."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    workspace_name = workspace.name if workspace else None
    success = False

    # Check all sources before deletion for proper response
    db_workspace = await db.db_get_workspace(workspace_id)
    redis_workspace = await _redis_get_workspace_meta(workspace_id)
    bridge_workspace_dict = workspace.to_dict() if workspace else None
    workspace_snapshot = bridge_workspace_dict or db_workspace or redis_workspace

    if workspace:
        success = await bridge.unregister_workspace(workspace_id)
        workspace_name = workspace.name

    if not workspace_name and db_workspace:
        workspace_name = db_workspace.get('name')

    if not workspace_name and redis_workspace:
        workspace_name = redis_workspace.get('name')

    runtime_meta = _extract_workspace_runtime_meta(workspace_snapshot)
    vm_cleanup_ok: Optional[bool] = None
    if runtime_meta.get('runtime') == 'vm':
        vm_cleanup_ok = await vm_workspace_provisioner.delete_workspace_vm(
            workspace_id=workspace_id,
            vm_name=runtime_meta.get('vm_name'),
            delete_pvc=True,
        )
        if not vm_cleanup_ok:
            logger.warning(
                f'Workspace {workspace_id} removed from registry but VM cleanup was incomplete'
            )

    # Delete from PostgreSQL
    await db.db_delete_workspace(workspace_id)

    # Delete from Redis
    await _redis_delete_workspace_meta(workspace_id)

    if success or db_workspace or redis_workspace:
        if workspace_name:
            await monitoring_service.log_message(
                agent_name='CodeTether Agent',
                content=f'Unregistered workspace: {workspace_name}',
                message_type='system',
                metadata={
                    'workspace_id': workspace_id,
                    'runtime': runtime_meta.get('runtime'),
                    'vm_cleanup_ok': vm_cleanup_ok,
                },
            )
        return {'success': True}

    raise HTTPException(status_code=404, detail='Workspace not found')


@agent_router_alias.post('/workspaces/{workspace_id}/trigger')
async def trigger_agent(workspace_id: str, trigger: AgentTrigger):
    """Trigger a CodeTether agent to work on a workspace.

    When Knative is enabled, this will spawn an ephemeral Knative worker
    for the session. Otherwise, it creates a task for SSE-connected workers.
    """
    # Look up workspace from database (primary source of truth)
    db_workspace = await db.db_get_workspace(workspace_id)
    if not db_workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    workspace_name = db_workspace.get('name', workspace_id)
    worker_id = db_workspace.get('worker_id')
    routing_decision, routed_metadata = orchestrate_task_route(
        prompt=trigger.prompt,
        agent_type=trigger.agent,
        files=trigger.files or [],
        metadata=trigger.metadata or {},
        model=trigger.model,
        model_ref=trigger.model_ref,
        worker_personality=trigger.worker_personality,
    )
    effective_model = routed_metadata.get('model') or trigger.model
    effective_model_ref = routing_decision.model_ref

    # Log the user's prompt separately so monitoring/UIs attribute it to the human.
    # (Otherwise the prompt text often appears inside system/agent log lines.)
    try:
        await monitoring_service.log_message(
            agent_name='User',
            content=trigger.prompt,
            message_type='human',
            metadata={
                'action': 'agent.trigger',
                'workspace_id': workspace_id,
                'workspace_name': workspace_name,
                'agent': trigger.agent,
                'model': effective_model,
                'model_ref': effective_model_ref,
                'worker_personality': routing_decision.worker_personality,
            },
        )
    except Exception as e:
        logger.debug(f'Failed to log user trigger prompt: {e}')

    # Try to use the bridge's trigger_agent for Knative support
    bridge = get_agent_bridge()
    if bridge is not None:
        from .agent_bridge import is_knative_enabled, AgentTriggerRequest

        # If Knative is enabled, use the bridge which has Knative integration
        if is_knative_enabled():
            logger.info(
                f'Using Knative path for trigger on workspace {workspace_id}'
            )
            trigger_request = AgentTriggerRequest(
                workspace_id=workspace_id,
                prompt=trigger.prompt,
                agent=trigger.agent,
                model=effective_model,
                files=trigger.files or [],
                metadata=routed_metadata,
            )
            response = await bridge.trigger_agent(trigger_request)
            if response.success:
                return {
                    'success': True,
                    'session_id': response.session_id,
                    'message': response.message or 'Task triggered via Knative',
                    'workspace_id': workspace_id,
                    'agent': trigger.agent,
                    'knative': True,
                    'routing': {
                        'complexity': routing_decision.complexity,
                        'model_tier': routing_decision.model_tier,
                        'model_ref': routing_decision.model_ref,
                        'target_agent_name': routing_decision.target_agent_name,
                        'worker_personality': routing_decision.worker_personality,
                    },
                }
            else:
                # Fall through to legacy path if Knative fails
                logger.warning(
                    f'Knative trigger failed: {response.error}, falling back to SSE workers'
                )

    # Legacy path: Create a task in the database for SSE workers to pick up
    task_id = str(uuid.uuid4())
    task_title = trigger.prompt[:80] + (
        '...' if len(trigger.prompt) > 80 else ''
    )
    task_data = {
        'id': task_id,
        'workspace_id': workspace_id,
        'title': task_title,
        'prompt': trigger.prompt,
        'agent_type': trigger.agent,
        'status': 'pending',
        'priority': 0,
        'metadata': {
            **routed_metadata,
            'files': trigger.files,
            **(
                {'notify_email': trigger.notify_email}
                if trigger.notify_email
                else {}
            ),
        },
        'worker_id': worker_id,
        'target_agent_name': routing_decision.target_agent_name,
        'model_ref': effective_model_ref,
    }
    saved = await db.db_upsert_task(task_data)
    if not saved:
        raise HTTPException(
            status_code=500, detail='Failed to persist task to database'
        )

    logger.info(
        f'Created task {task_id} for workspace {workspace_name} (worker: {worker_id})'
    )

    # Notify SSE-connected workers of the new task
    notified: list = []
    try:
        from .worker_sse import notify_workers_of_new_task

        notified = await notify_workers_of_new_task(task_data)
        if notified:
            logger.info(
                f'Task {task_id} pushed to {len(notified)} SSE workers: {notified}'
            )
        else:
            logger.warning(
                f'Task {task_id} created but no SSE workers available for workspace {workspace_id}'
            )
    except Exception as e:
        logger.warning(f'Failed to notify SSE workers of task {task_id}: {e}')

    workers_notified = len(notified) if notified else 0
    if workers_notified > 0:
        task_status = 'dispatched'
        message = f'Task dispatched to {workers_notified} worker(s)'
    else:
        task_status = 'waiting_for_worker'
        message = 'Task saved but no workers are online to execute it. Connect a worker to start processing.'

    # Log the trigger
    await monitoring_service.log_message(
        agent_name='CodeTether Agent',
        content=f"Triggered agent '{trigger.agent}' on {workspace_name}",
        message_type='system',
        metadata={
            'workspace_id': workspace_id,
            'agent': trigger.agent,
            'task_id': task_id,
            'task_status': task_status,
            'workers_notified': workers_notified,
            'routing': {
                'complexity': routing_decision.complexity,
                'model_tier': routing_decision.model_tier,
                'model_ref': routing_decision.model_ref,
                'target_agent_name': routing_decision.target_agent_name,
                'worker_personality': routing_decision.worker_personality,
            },
        },
    )

    return {
        'success': True,
        'session_id': task_id,
        'message': message,
        'task_status': task_status,
        'workers_notified': workers_notified,
        'workspace_id': workspace_id,
        'agent': trigger.agent,
        'routing': {
            'complexity': routing_decision.complexity,
            'model_tier': routing_decision.model_tier,
            'model_ref': routing_decision.model_ref,
            'target_agent_name': routing_decision.target_agent_name,
            'worker_personality': routing_decision.worker_personality,
        },
    }


@agent_router_alias.post('/workspaces/{workspace_id}/message')
async def send_agent_message(workspace_id: str, msg: AgentMessage):
    """Send a follow-up message to an active agent session."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    # Log user follow-up messages as human so they render correctly in monitoring UIs.
    try:
        await monitoring_service.log_message(
            agent_name='User',
            content=msg.message,
            message_type='human',
            metadata={
                'action': 'agent.message',
                'workspace_id': workspace_id,
                'workspace_name': workspace.name,
                'agent': msg.agent,
            },
        )
    except Exception as e:
        logger.debug(f'Failed to log user follow-up message: {e}')

    response = await bridge.send_message(
        codebase_id=workspace_id,
        message=msg.message,
        agent=msg.agent,
    )

    return response.to_dict()


@agent_router_alias.post('/workspaces/{workspace_id}/interrupt')
async def interrupt_agent(workspace_id: str):
    """Interrupt the current agent task."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    success = await bridge.interrupt_agent(workspace_id)

    if success:
        workspace = bridge.get_workspace(workspace_id)
        await monitoring_service.log_message(
            agent_name='CodeTether Agent',
            content=f'Interrupted agent on {workspace.name if workspace else workspace_id}',
            message_type='system',
            metadata={'workspace_id': workspace_id},
        )

    return {'success': success}


@agent_router_alias.post('/workspaces/{workspace_id}/stop')
async def stop_agent(workspace_id: str):
    """Stop the CodeTether agent for a workspace."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    success = await bridge.stop_agent(workspace_id)

    if success:
        workspace = bridge.get_workspace(workspace_id)
        await monitoring_service.log_message(
            agent_name='CodeTether Agent',
            content=f'Stopped agent for {workspace.name if workspace else workspace_id}',
            message_type='system',
            metadata={'workspace_id': workspace_id},
        )

    return {'success': success}


@agent_router_alias.get('/workspaces/{workspace_id}/status')
async def get_agent_status(workspace_id: str):
    """Get the current status of an agent."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    status = await bridge.get_agent_status(workspace_id)
    if not status:
        raise HTTPException(status_code=404, detail='Workspace not found')

    return status


def _parse_agent_output_line(
    line: str,
    task_id: str,
    worker_id: Optional[str],
    session_id: Optional[str],
) -> Optional[str]:
    """Parse an agent JSON output line and return an SSE frame.

    Agent with --format json outputs lines like:
    - {"type":"step_start","part":{...}}
    - {"type":"text","part":{"text":"Hello world"}}
    - {"type":"tool_use","part":{...}}
    - {"type":"step_finish","part":{...}}

    This function parses these and returns appropriate SSE events,
    extracting just the text content for "text" type events.
    """
    line = line.strip()
    if not line:
        return None

    try:
        event = json.loads(line)
        event_type = event.get('type', 'message')

        # For text events, extract the actual text content
        if event_type == 'text':
            part = event.get('part', {})
            text = part.get('text', '')
            if text:
                payload = {
                    'type': 'text',
                    'content': text,  # Just the text, not the JSON wrapper
                    'task_id': task_id,
                    'worker_id': worker_id,
                    'session_id': session_id,
                }
                return f'event: message\ndata: {json.dumps(payload)}\n\n'
            return None  # Skip empty text events

        # For step_start/step_finish, emit status events
        if event_type in ('step_start', 'step_finish'):
            payload = {
                'type': event_type,
                'task_id': task_id,
                'worker_id': worker_id,
                'session_id': session_id,
            }
            return f'event: status\ndata: {json.dumps(payload)}\n\n'

        # For tool_use events, emit tool info
        if event_type == 'tool_use':
            part = event.get('part', {})
            payload = {
                'type': 'tool_use',
                'tool': part.get('tool'),
                'state': part.get('state'),
                'task_id': task_id,
                'worker_id': worker_id,
                'session_id': session_id,
            }
            return f'event: tool\ndata: {json.dumps(payload)}\n\n'

        # For other events, pass through with parsed structure
        event['task_id'] = task_id
        event['worker_id'] = worker_id
        event['session_id'] = session_id
        return f'event: {event_type}\ndata: {json.dumps(event)}\n\n'

    except json.JSONDecodeError:
        # Not JSON - treat as plain text if it's not empty
        if line and not line.startswith('{'):
            payload = {
                'type': 'text',
                'content': line,
                'task_id': task_id,
                'worker_id': worker_id,
                'session_id': session_id,
            }
            return f'event: message\ndata: {json.dumps(payload)}\n\n'
        return None


@agent_router_alias.get('/workspaces/{workspace_id}/events')
async def stream_agent_events(workspace_id: str, request: Request):
    """Stream real-time events from a CodeTether agent session via SSE.

    Events include:
    - message.updated: Full message updates
    - message.part.updated: Streaming text/tool updates
    - session.status: Status changes (idle, running, etc.)
    - Tool execution states (pending, running, completed, error)
    """
    import aiohttp

    # "global" is a virtual workspace used by the dashboard when no specific
    # Workspace is selected.  Return a keep-alive SSE stream so the browser
    # EventSource stays connected instead of retrying on 404.
    if workspace_id == 'global':
        import asyncio as _asyncio

        async def _global_keepalive():
            yield 'event: status\ndata: {"status": "idle", "workspace": "global"}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                yield ': keepalive\n\n'
                await _asyncio.sleep(30)

        return StreamingResponse(
            _global_keepalive(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # Resolve workspace metadata across all backends.
    # NOTE: AgentBridge persists to PostgreSQL, while the server also persists
    # Workspaces to Redis for durability and multi-replica support.
    # The SSE stream must therefore not depend solely on bridge._workspaces.
    workspace_obj = bridge.get_workspace(workspace_id)
    workspace_meta: Optional[Dict[str, Any]] = (
        workspace_obj.to_dict() if workspace_obj else None
    )

    if not workspace_meta:
        try:
            workspace_meta = await db.db_get_workspace(workspace_id)
        except Exception:
            workspace_meta = None

    if not workspace_meta:
        workspace_meta = await _redis_get_workspace_meta(workspace_id)

    if not workspace_meta:
        raise HTTPException(status_code=404, detail='Workspace not found')

    worker_id = workspace_meta.get('worker_id')
    agent_port = workspace_meta.get('agent_port')
    workspace_path = workspace_meta.get('path') or ''

    # For remote workers, use task-based events
    if worker_id:

        async def remote_event_generator():
            """Stream events for remote worker workspaces from task output/results.

            Previously this stream ended immediately after dumping a small batch of
            completed task results, which caused browser EventSource clients to
            reconnect in a loop and spam "disconnected" messages.
            """
            import time

            def _format_task_result_events(
                raw_result: Any, session_id: Optional[str] = None
            ):
                """Yield SSE frames for a stored task result payload."""
                try:
                    result_data = (
                        json.loads(raw_result)
                        if isinstance(raw_result, str)
                        else raw_result
                    )
                    if isinstance(result_data, list):
                        for event in result_data:
                            if not isinstance(event, dict):
                                yield (
                                    'event: message\n'
                                    f'data: {json.dumps({"type": "text", "content": str(event)})}\n\n'
                                )
                                continue

                            if session_id and 'session_id' not in event:
                                event['session_id'] = session_id

                            event_type = event.get('type', 'message')
                            yield f'event: {event_type}\ndata: {json.dumps(event)}\n\n'
                    else:
                        if (
                            isinstance(result_data, dict)
                            and session_id
                            and 'session_id' not in result_data
                        ):
                            result_data['session_id'] = session_id
                        yield f'event: message\ndata: {json.dumps(result_data)}\n\n'
                except (json.JSONDecodeError, TypeError):
                    yield (
                        'event: message\n'
                        f'data: {json.dumps({"type": "text", "content": str(raw_result)})}\n\n'
                    )

            yield (
                'event: connected\n'
                f'data: {json.dumps({"workspace_id": workspace_id, "status": "connected", "remote": True, "worker_id": worker_id})}\n\n'
            )

            emitted_task_ids: set[str] = set()
            output_cursors: Dict[str, int] = {}
            last_task_status: Dict[str, str] = {}

            # Emit recent completed task results on initial connect.
            all_tasks = await bridge.list_tasks(codebase_id=workspace_id)
            recent_tasks = all_tasks[-10:] if len(all_tasks) > 10 else all_tasks
            for t in recent_tasks:
                task_metadata = (
                    (t.metadata or {}) if hasattr(t, 'metadata') else {}
                )
                resume_session_id = None
                try:
                    resume_session_id = task_metadata.get('resume_session_id')
                except Exception:
                    resume_session_id = None

                if t.status.value == 'completed' and t.result:
                    for frame in _format_task_result_events(
                        t.result, session_id=resume_session_id
                    ):
                        yield frame
                    emitted_task_ids.add(t.id)

            # Inform the client we're in remote mode, then stay connected.
            yield (
                'event: status\n'
                f'data: {json.dumps({"status": "idle", "message": "Remote worker workspace - streaming task output/results"})}\n\n'
            )

            keepalive_interval_s = 15.0
            poll_interval_s = 0.5
            last_keepalive = time.monotonic()

            try:
                while True:
                    if await request.is_disconnected():
                        break

                    all_tasks = await bridge.list_tasks(codebase_id=workspace_id)
                    recent_tasks = (
                        all_tasks[-25:] if len(all_tasks) > 25 else all_tasks
                    )

                    for t in recent_tasks:
                        task_metadata = (
                            (t.metadata or {}) if hasattr(t, 'metadata') else {}
                        )
                        resume_session_id = None
                        try:
                            resume_session_id = task_metadata.get(
                                'resume_session_id'
                            )
                        except Exception:
                            resume_session_id = None

                        # Emit status transitions (lightweight breadcrumbs).
                        current_status = t.status.value
                        previous_status = last_task_status.get(t.id)
                        if previous_status is None:
                            # Establish baseline without spamming historical status.
                            last_task_status[t.id] = current_status
                        elif previous_status != current_status:
                            last_task_status[t.id] = current_status
                            yield (
                                'event: status\n'
                                f'data: {json.dumps({"status": current_status, "message": f"Task: {t.title} ({current_status})", "task_id": t.id, "resume_session_id": resume_session_id, "session_id": resume_session_id})}\n\n'
                            )

                        # Stream any new output chunks received from the worker.
                        outputs = _task_output_streams.get(t.id, [])
                        cursor = output_cursors.get(t.id, 0)
                        if len(outputs) > cursor:
                            for chunk in outputs[cursor:]:
                                content = (chunk or {}).get('output')
                                if content:
                                    # Parse agent JSON output to extract actual events
                                    # Agent outputs lines like: {"type":"text","part":{"text":"Hello"}}
                                    parsed_event = _parse_agent_output_line(
                                        content,
                                        t.id,
                                        (chunk or {}).get('worker_id'),
                                        resume_session_id,
                                    )
                                    if parsed_event:
                                        yield parsed_event
                            output_cursors[t.id] = len(outputs)

                        # Stream newly completed results (only once).
                        if (
                            current_status == 'completed'
                            and t.result
                            and t.id not in emitted_task_ids
                        ):
                            for frame in _format_task_result_events(
                                t.result, session_id=resume_session_id
                            ):
                                yield frame
                            emitted_task_ids.add(t.id)
                        elif (
                            current_status in ('failed', 'cancelled')
                            and (t.error or t.result)
                            and t.id not in emitted_task_ids
                        ):
                            payload = {
                                'type': 'error'
                                if current_status == 'failed'
                                else 'status',
                                'message': t.error
                                or t.result
                                or f'Task {current_status}',
                                'task_id': t.id,
                                'title': t.title,
                                'resume_session_id': resume_session_id,
                                'session_id': resume_session_id,
                            }
                            yield f'event: message\ndata: {json.dumps(payload)}\n\n'
                            emitted_task_ids.add(t.id)

                    # Send SSE comment keepalives to prevent idle timeouts.
                    now = time.monotonic()
                    if now - last_keepalive >= keepalive_interval_s:
                        yield ': keep-alive\n\n'
                        last_keepalive = now

                    await asyncio.sleep(poll_interval_s)
            except asyncio.CancelledError:
                logger.info(f'Remote event stream cancelled for {workspace_id}')
            except Exception as e:
                logger.error(f'Error streaming remote events: {e}')
                yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'

        return StreamingResponse(
            remote_event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

    if not agent_port:

        async def offline_event_generator():
            """Keep an SSE stream open even when no agent is currently running.

            This avoids EventSource error spam in the UI and still allows clients
            to receive task output/results for workspaces that execute work via the
            task queue (or become available later).
            """
            import time

            yield (
                'event: connected\n'
                f'data: {json.dumps({"workspace_id": workspace_id, "status": "connected", "remote": bool(worker_id), "worker_id": worker_id})}\n\n'
            )

            yield (
                'event: status\n'
                f'data: {json.dumps({"status": "offline", "message": "Agent not running (yet). Waiting for tasks/output…"})}\n\n'
            )

            emitted_task_ids: set[str] = set()
            output_cursors: Dict[str, int] = {}

            keepalive_interval_s = 15.0
            poll_interval_s = 1.0
            last_keepalive = time.monotonic()

            try:
                while True:
                    if await request.is_disconnected():
                        break

                    # Stream any available task output/results.
                    try:
                        all_tasks = await bridge.list_tasks(
                            codebase_id=workspace_id
                        )
                    except Exception:
                        all_tasks = []

                    recent_tasks = (
                        all_tasks[-25:] if len(all_tasks) > 25 else all_tasks
                    )

                    for t in recent_tasks:
                        task_metadata = (
                            (t.metadata or {}) if hasattr(t, 'metadata') else {}
                        )
                        resume_session_id = None
                        try:
                            resume_session_id = task_metadata.get(
                                'resume_session_id'
                            )
                        except Exception:
                            resume_session_id = None

                        outputs = _task_output_streams.get(t.id, [])
                        cursor = output_cursors.get(t.id, 0)
                        if len(outputs) > cursor:
                            for chunk in outputs[cursor:]:
                                content = (chunk or {}).get('output')
                                if content:
                                    yield (
                                        'event: message\n'
                                        f'data: {json.dumps({"type": "text", "content": content, "task_id": t.id, "worker_id": (chunk or {}).get("worker_id"), "resume_session_id": resume_session_id, "session_id": resume_session_id})}\n\n'
                                    )
                            output_cursors[t.id] = len(outputs)

                        # Emit completed/failed terminal payload once.
                        status_value = t.status.value
                        if (
                            status_value == 'completed'
                            and t.result
                            and t.id not in emitted_task_ids
                        ):
                            payload = {
                                'type': 'status',
                                'message': 'Task completed',
                                'task_id': t.id,
                                'title': t.title,
                                'resume_session_id': resume_session_id,
                                'session_id': resume_session_id,
                                'result': t.result,
                            }
                            yield f'event: message\ndata: {json.dumps(payload)}\n\n'
                            emitted_task_ids.add(t.id)
                        elif (
                            status_value == 'failed'
                            and (t.error or t.result)
                            and t.id not in emitted_task_ids
                        ):
                            payload = {
                                'type': 'error',
                                'message': t.error or 'Task failed',
                                'task_id': t.id,
                                'title': t.title,
                                'resume_session_id': resume_session_id,
                                'session_id': resume_session_id,
                                'result': t.result,
                            }
                            yield f'event: message\ndata: {json.dumps(payload)}\n\n'
                            emitted_task_ids.add(t.id)

                    now = time.monotonic()
                    if now - last_keepalive >= keepalive_interval_s:
                        yield ': keep-alive\n\n'
                        last_keepalive = now

                    await asyncio.sleep(poll_interval_s)
            except asyncio.CancelledError:
                logger.info(f'Offline event stream cancelled for {workspace_id}')
            except Exception as e:
                logger.error(f'Error streaming offline events: {e}')
                yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'

        return StreamingResponse(
            offline_event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

    async def event_generator():
        """Proxy events from agent SSE endpoint."""
        try:
            port_int = int(agent_port)
        except Exception:
            port_int = None

        if port_int is None:
            raise HTTPException(status_code=400, detail='Agent not running')

        base_url = bridge._get_agent_base_url(port_int)

        yield f'event: connected\ndata: {json.dumps({"workspace_id": workspace_id, "status": "connected"})}\n\n'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{base_url}/event',
                    params={'directory': workspace_path},
                    timeout=aiohttp.ClientTimeout(total=None),
                ) as resp:
                    if resp.status != 200:
                        yield f'event: error\ndata: {json.dumps({"error": "Failed to connect to agent"})}\n\n'
                        return

                    async for line in resp.content:
                        if await request.is_disconnected():
                            break

                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data:'):
                            try:
                                event_data = json.loads(line_text[5:].strip())
                                # Transform and forward the event
                                transformed = transform_agent_event(
                                    event_data, workspace_id
                                )
                                if transformed:
                                    yield f'event: {transformed["event_type"]}\ndata: {json.dumps(transformed)}\n\n'
                            except json.JSONDecodeError:
                                pass
                        elif line_text:
                            yield f'data: {line_text}\n\n'

        except asyncio.CancelledError:
            logger.info(f'Event stream cancelled for {workspace_id}')
        except Exception as e:
            logger.error(f'Error streaming events: {e}')
            yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@agent_router_alias.get('/codebases/{codebase_id}/events')
async def stream_agent_events_legacy(codebase_id: str, request: Request):
    """Backward-compatible SSE route for older dashboard clients."""
    return await stream_agent_events(codebase_id, request)


def transform_agent_event(
    event: Dict[str, Any], workspace_id: str
) -> Optional[Dict[str, Any]]:
    """Transform agent events into UI-friendly format."""
    event_type = event.get('type', '')
    properties = event.get('properties', {})

    # Message updates
    if event_type == 'message.updated':
        info = properties.get('info', {})
        return {
            'event_type': 'message',
            'workspace_id': workspace_id,
            'message_id': info.get('id'),
            'session_id': info.get('sessionID'),
            'role': info.get('role'),
            'time': info.get('time', {}),
            'model': info.get('model'),
            'agent': info.get('agent'),
            'cost': info.get('cost'),
            'tokens': info.get('tokens'),
        }

    # Part updates (streaming text, tool calls)
    if event_type == 'message.part.updated':
        part = properties.get('part', {})
        delta = properties.get('delta')
        part_type = part.get('type')

        result = {
            'event_type': f'part.{part_type}',
            'workspace_id': workspace_id,
            'part_id': part.get('id'),
            'message_id': part.get('messageID'),
            'session_id': part.get('sessionID'),
            'part_type': part_type,
        }

        if part_type == 'text':
            result['text'] = part.get('text', '')
            result['delta'] = delta
        elif part_type == 'reasoning':
            result['text'] = part.get('text', '')
            result['delta'] = delta
        elif part_type == 'tool':
            state = part.get('state', {})
            result['tool_name'] = part.get('tool')
            result['call_id'] = part.get('callID')
            result['status'] = state.get('status')
            result['input'] = state.get('input')
            result['output'] = state.get('output')
            result['title'] = state.get('title')
            result['error'] = state.get('error')
            result['metadata'] = state.get('metadata')
            result['time'] = state.get('time')
        elif part_type == 'step-start':
            result['snapshot'] = part.get('snapshot')
        elif part_type == 'step-finish':
            result['reason'] = part.get('reason')
            result['cost'] = part.get('cost')
            result['tokens'] = part.get('tokens')
        elif part_type == 'file':
            result['filename'] = part.get('filename')
            result['url'] = part.get('url')
            result['mime'] = part.get('mime')
        elif part_type == 'agent':
            result['agent_name'] = part.get('name')

        return result

    # Session status
    if event_type == 'session.status':
        return {
            'event_type': 'status',
            'workspace_id': workspace_id,
            'session_id': properties.get('sessionID'),
            'status': properties.get('status'),
            'agent': properties.get('agent'),
        }

    if event_type == 'session.idle':
        return {
            'event_type': 'idle',
            'workspace_id': workspace_id,
            'session_id': properties.get('sessionID'),
        }

    # RLM routing decision
    if event_type == 'rlm.routing.decision':
        return {
            'event_type': 'rlm.routing',
            'workspace_id': workspace_id,
            'session_id': properties.get('sessionID'),
            'tool': properties.get('tool'),
            'call_id': properties.get('callID'),
            'decision': properties.get('decision'),
            'reason': properties.get('reason'),
            'estimated_tokens': properties.get('estimatedTokens'),
            'context_limit': properties.get('contextLimit'),
            'threshold': properties.get('threshold'),
            'mode': properties.get('mode'),
        }

    # File edits
    if event_type == 'file.edited':
        return {
            'event_type': 'file_edit',
            'workspace_id': workspace_id,
            'path': properties.get('path'),
            'hash': properties.get('hash'),
        }

    # Command execution
    if event_type == 'command.executed':
        return {
            'event_type': 'command',
            'workspace_id': workspace_id,
            'command': properties.get('command'),
            'exit_code': properties.get('exitCode'),
            'output': properties.get('output'),
        }

    # LSP diagnostics
    if event_type == 'lsp.diagnostics':
        return {
            'event_type': 'diagnostics',
            'workspace_id': workspace_id,
            'path': properties.get('path'),
            'diagnostics': properties.get('diagnostics'),
        }

    # Todo updates
    if event_type == 'todo.updated':
        return {
            'event_type': 'todo',
            'workspace_id': workspace_id,
            'todos': properties.get('info'),
        }

    # Default: pass through with generic type
    return {
        'event_type': event_type.replace('.', '_'),
        'workspace_id': workspace_id,
        'raw': event,
    }


@agent_router_alias.get('/workspaces/{workspace_id}/messages')
async def get_session_messages(workspace_id: str, limit: int = 50):
    """Get recent messages from an agent session."""
    import aiohttp

    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge._workspaces.get(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    if not workspace.agent_port or not workspace.session_id:
        return {'messages': [], 'session_id': None}

    try:
        base_url = bridge._get_agent_base_url(workspace.agent_port)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{base_url}/session/{workspace.session_id}/message',
                params={'limit': limit, 'directory': workspace.path},
            ) as resp:
                if resp.status == 200:
                    messages = await resp.json()
                    return {
                        'messages': messages,
                        'session_id': workspace.session_id,
                    }
                return {'messages': [], 'error': f'Status {resp.status}'}
    except Exception as e:
        return {'messages': [], 'error': str(e)}


# ========================================
# Agent Task Management Endpoints
# ========================================


def _is_recent_heartbeat(
    heartbeat_value: Optional[str], max_age_seconds: int = 120
) -> bool:
    """Return True when heartbeat timestamp is within max_age_seconds."""
    if not heartbeat_value:
        return False
    try:
        normalized = heartbeat_value.replace('Z', '+00:00')
        last = datetime.fromisoformat(normalized)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age <= max_age_seconds
    except Exception:
        return False


async def _validate_target_worker_is_available(
    metadata: Dict[str, Any],
) -> None:
    """Validate target worker availability; fall back to auto-select if unavailable.

    Instead of rejecting with 409, this removes the target_worker_id from
    metadata so the task gets routed to any available worker.  A warning is
    stored in metadata['_routing_warning'] for the caller to surface.
    """
    target_worker_id = metadata.get('target_worker_id')
    if not target_worker_id:
        return

    target_worker_id = str(target_worker_id).strip()
    if not target_worker_id:
        return

    try:
        from .worker_sse import get_worker_registry

        registry = get_worker_registry()
        sse_workers = await registry.list_workers()
    except Exception as e:
        # Cannot validate — fall back to auto-select rather than 503
        logger.warning(f'Cannot validate target worker availability: {e}; falling back to auto-select')
        metadata.pop('target_worker_id', None)
        metadata['_routing_warning'] = f'Could not validate target worker; auto-selecting.'
        return

    target_worker = next(
        (w for w in sse_workers if str(w.get('worker_id') or '') == target_worker_id),
        None,
    )
    if not target_worker:
        logger.info(
            f'Target worker "{target_worker_id}" is not connected via SSE; falling back to auto-select'
        )
        metadata.pop('target_worker_id', None)
        metadata['_routing_warning'] = (
            f'Target worker "{target_worker_id}" is not connected; task auto-routed to available worker.'
        )
        return

    last_heartbeat = target_worker.get('last_heartbeat')
    if not _is_recent_heartbeat(str(last_heartbeat) if last_heartbeat else None):
        logger.info(
            f'Target worker "{target_worker_id}" has stale heartbeat ({last_heartbeat}); falling back to auto-select'
        )
        metadata.pop('target_worker_id', None)
        metadata['_routing_warning'] = (
            f'Target worker "{target_worker_id}" is stale (last heartbeat: {last_heartbeat}); task auto-routed.'
        )


@agent_router_alias.get('/tasks')
async def list_all_tasks(
    workspace_id: Optional[str] = None,
    codebase_id: Optional[str] = None,
    status: Optional[str] = None,
    worker_id: Optional[str] = None,
):
    """List all agent tasks, optionally filtered by workspace, status, or worker."""
    # Use database as primary source of truth for tasks
    tasks = await db.db_list_tasks(
        workspace_id=workspace_id,
        codebase_id=codebase_id,
        status=status,
        worker_id=worker_id,
    )
    return tasks


@agent_router_alias.post('/tasks')
async def create_global_task(task_data: AgentTaskCreate):
    """Create a new task, optionally tied to a specific workspace.

    If workspace_id is provided, the task will run in that workspace's directory.
    Otherwise, it runs as a 'global' task (worker's home directory).
    """
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # Use provided workspace_id or fall back to 'global'
    effective_workspace_id = task_data.workspace_id or 'global'

    # Build metadata + routing policy outputs.
    base_metadata = task_data.metadata.copy() if task_data.metadata else {}
    if task_data.model:
        base_metadata['model'] = task_data.model
    if task_data.model_ref:
        base_metadata['model_ref'] = task_data.model_ref

    routing_decision, routed_metadata = orchestrate_task_route(
        prompt=task_data.prompt,
        agent_type=task_data.agent_type,
        metadata=base_metadata,
        model=task_data.model,
        model_ref=task_data.model_ref,
        worker_personality=task_data.worker_personality,
    )
    await _validate_target_worker_is_available(routed_metadata)

    # Create task with the specified workspace context
    task = await bridge.create_task(
        codebase_id=effective_workspace_id,
        title=task_data.title,
        prompt=task_data.prompt,
        agent_type=task_data.agent_type,
        priority=task_data.priority,
        model=routed_metadata.get('model'),
        metadata=routed_metadata,
        model_ref=routing_decision.model_ref,
    )

    if not task:
        raise HTTPException(status_code=500, detail='Failed to create task')

    return task


@agent_router_alias.post('/workspaces/{workspace_id}/tasks')
async def create_agent_task(workspace_id: str, task_data: AgentTaskCreate):
    """Create a new task for an agent to work on."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        # Workspace may exist durably in PostgreSQL/Redis but not in the local
        # in-memory registry (e.g., after restart or when requests are routed
        # to a different replica). Rehydrate so task creation works reliably.
        try:
            workspace = await _rehydrate_workspace_into_bridge(workspace_id)
        except Exception:
            workspace = None
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    base_metadata = task_data.metadata.copy() if task_data.metadata else {}
    if task_data.model:
        base_metadata['model'] = task_data.model
    if task_data.model_ref:
        base_metadata['model_ref'] = task_data.model_ref

    routing_decision, routed_metadata = orchestrate_task_route(
        prompt=task_data.prompt,
        agent_type=task_data.agent_type,
        metadata=base_metadata,
        model=task_data.model,
        model_ref=task_data.model_ref,
        worker_personality=task_data.worker_personality,
    )
    await _validate_target_worker_is_available(routed_metadata)

    task = await bridge.create_task(
        codebase_id=workspace_id,
        title=task_data.title,
        prompt=task_data.prompt,
        agent_type=task_data.agent_type,
        priority=task_data.priority,
        model=routed_metadata.get('model'),
        metadata=routed_metadata,
        model_ref=routing_decision.model_ref,
    )

    if not task:
        raise HTTPException(status_code=500, detail='Failed to create task')

    # Log the task prompt as a human message so UIs don't attribute it to the agent.
    try:
        await monitoring_service.log_message(
            agent_name='User',
            content=task_data.prompt,
            message_type='human',
            metadata={
                'action': 'agent.task.create',
                'task_id': task.id,
                'workspace_id': workspace_id,
                'workspace_name': workspace.name,
                'agent_type': task_data.agent_type,
                'priority': task_data.priority,
                'title': task_data.title,
                'routing': {
                    'complexity': routing_decision.complexity,
                    'model_tier': routing_decision.model_tier,
                    'model_ref': routing_decision.model_ref,
                    'target_agent_name': routing_decision.target_agent_name,
                    'worker_personality': routing_decision.worker_personality,
                },
            },
        )
    except Exception as e:
        logger.debug(f'Failed to log user task prompt: {e}')

    # Log the task creation
    await monitoring_service.log_message(
        agent_name='CodeTether Agent',
        content=f'Task created: {task_data.title}',
        message_type='system',
        metadata={
            'task_id': task.id,
            'workspace_id': workspace_id,
            'routing': {
                'complexity': routing_decision.complexity,
                'model_tier': routing_decision.model_tier,
                'model_ref': routing_decision.model_ref,
                'target_agent_name': routing_decision.target_agent_name,
                'worker_personality': routing_decision.worker_personality,
            },
        },
    )

    return {'success': True, 'task': task.to_dict()}


@agent_router_alias.get('/workspaces/{workspace_id}/tasks')
async def list_workspace_tasks(workspace_id: str, status: Optional[str] = None):
    """List all tasks for a specific workspace."""
    # Use database as primary source of truth for tasks
    tasks = await db.db_list_tasks(
        workspace_id=workspace_id,
        status=status,
    )
    return tasks


@agent_router_alias.get('/tasks/{task_id}', response_model=AgentTaskResponse)
async def get_task(task_id: str):
    """Get details of a specific task."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    task = await bridge.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    return task.to_dict()


@agent_router_alias.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: str):
    """Cancel a pending task."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    success = bridge.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail='Cannot cancel task (may already be running or completed)',
        )

    return {'success': True, 'message': 'Task cancelled'}


# ========================================
# Session Management Endpoints
# ========================================


class SessionResumeRequest(BaseModel):
    """Request to resume a session."""

    prompt: Optional[str] = None
    agent: str = 'build'
    model: Optional[str] = None
    model_ref: Optional[str] = None
    worker_personality: Optional[str] = None


def _session_sort_key(session: Dict[str, Any]) -> tuple:
    """Best-effort sort key across agent/worker/DB session shapes."""

    def _dt(value: Any) -> Optional[datetime]:
        normalized = _normalize_iso_timestamp(value)
        if not normalized:
            return None
        return _parse_iso_datetime(normalized)

    updated = _dt(session.get('updated_at') or session.get('updated'))
    created = _dt(session.get('created_at') or session.get('created'))
    return (
        updated or created or datetime.min,
        created or datetime.min,
        str(session.get('id') or ''),
    )


async def _merge_sessions_with_database(
    workspace_id: str,
    sessions: List[Dict[str, Any]],
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Merge durable DB sessions into a source-specific session list."""
    if not sessions:
        return sessions
    if not isinstance(sessions, list):
        return []

    sessions = [s for s in sessions if isinstance(s, dict)]
    if not sessions:
        return []

    try:
        persisted = await db.db_list_sessions(
            workspace_id=workspace_id, limit=limit
        )
    except Exception as e:
        logger.debug(f'Failed to merge DB sessions: {e}')
        return sessions

    if not persisted:
        return sessions

    by_id: Dict[str, Dict[str, Any]] = {}
    for s in sessions:
        sid = s.get('id')
        if isinstance(sid, str) and sid:
            by_id[sid] = s

    for p in persisted:
        sid = p.get('id')
        if not isinstance(sid, str) or not sid:
            continue
        if sid in by_id:
            combined = dict(p)
            combined.update(by_id[sid])
            if isinstance(p.get('summary'), dict) and isinstance(
                by_id[sid].get('summary'), dict
            ):
                summary = dict(p['summary'])
                summary.update(by_id[sid]['summary'])
                combined['summary'] = summary
            by_id[sid] = combined
        else:
            by_id[sid] = p

    merged = list(by_id.values())
    merged.sort(key=_session_sort_key, reverse=True)
    return merged


@agent_router_alias.get('/workspaces/{workspace_id}/sessions')
async def list_sessions(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
):
    """List sessions for a workspace with pagination.

    Args:
        workspace_id: The workspace ID
        limit: Max sessions to return (default 50, max 200)
        offset: Number of sessions to skip for pagination
    """
    import aiohttp

    # Clamp limit to reasonable bounds
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    bridge = get_agent_bridge()
    workspace = bridge.get_workspace(workspace_id) if bridge is not None else None

    def _session_matches_query(session: Dict[str, Any], query: str) -> bool:
        needle = query.strip().lower()
        if not needle:
            return True

        values: List[str] = []
        for key in ('id', 'title', 'project_id', 'directory', 'agent', 'model'):
            value = session.get(key)
            if isinstance(value, str) and value:
                values.append(value)

        summary = session.get('summary')
        if isinstance(summary, dict):
            for value in summary.values():
                if isinstance(value, str) and value:
                    values.append(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, str) and item:
                            values.append(item)
        elif isinstance(summary, str) and summary:
            values.append(summary)

        if not values:
            return False

        return any(needle in value.lower() for value in values)

    def _paginate_sessions(sessions: list, source: str, synced_at=None) -> dict:
        """Apply pagination to sessions list and return response dict."""
        filtered = (
            [s for s in sessions if _session_matches_query(s, q)]
            if q
            else sessions
        )
        # Sort by updated/created time descending
        sorted_sessions = sorted(
            filtered,
            key=lambda s: s.get('updated') or s.get('created') or '',
            reverse=True,
        )
        total = len(sorted_sessions)
        paginated = sorted_sessions[offset : offset + limit]
        return {
            'sessions': paginated,
            'total': total,
            'limit': limit,
            'offset': offset,
            'hasMore': offset + len(paginated) < total,
            'source': source,
            'synced_at': synced_at,
        }

    # Check Redis-backed worker-synced sessions first (for remote workspaces / multi-replica).
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            raw = await redis_client.get(
                _redis_key_worker_sessions(workspace_id)
            )
            if raw:
                payload = json.loads(raw)
                sessions = (
                    payload.get('sessions')
                    if isinstance(payload, dict)
                    else None
                )
                if sessions:
                    merged = await _merge_sessions_with_database(
                        workspace_id, sessions
                    )
                    return _paginate_sessions(
                        merged,
                        'worker_sync',
                        payload.get('updated_at')
                        if isinstance(payload, dict)
                        else None,
                    )
        except Exception as e:
            logger.debug(f'Failed to read worker sessions from Redis: {e}')

    # Check if we have worker-synced sessions first (for remote workspaces)
    if workspace_id in _worker_sessions and _worker_sessions[workspace_id]:
        merged = await _merge_sessions_with_database(
            workspace_id, _worker_sessions[workspace_id]
        )
        return _paginate_sessions(merged, 'worker_sync')

    # If we don't have a workspace locally, try to rehydrate it so we can query
    # the agent API / local state for local workspaces.
    if workspace is None and bridge is not None:
        workspace = await _rehydrate_workspace_into_bridge(workspace_id)

    # If there's a running agent instance, query its API
    if workspace and workspace.agent_port:
        try:
            base_url = bridge._get_agent_base_url(workspace.agent_port)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{base_url}/session',
                    params={'directory': workspace.path},
                ) as resp:
                    if resp.status == 200:
                        sessions = await resp.json()
                        merged = await _merge_sessions_with_database(
                            workspace_id, sessions
                        )
                        return _paginate_sessions(merged, 'agent_api')
        except Exception as e:
            logger.warning(f'Failed to query agent API: {e}')

    # Fallback: Read sessions from agent's local state directory
    if workspace:
        sessions = await _read_local_sessions(workspace.path)
        if sessions:
            merged = await _merge_sessions_with_database(workspace_id, sessions)
            return _paginate_sessions(merged, 'local_state')

    # Durable fallback: PostgreSQL persistence (common for remote workers).
    try:
        persisted = await db.db_list_sessions(
            workspace_id=workspace_id, limit=500
        )
        if persisted:
            return _paginate_sessions(persisted, 'database')
    except Exception as e:
        logger.debug(f'Failed to read sessions from PostgreSQL: {e}')

    # At this point, we have no sessions from any source. If the workspace exists
    # in Redis/PostgreSQL, return an empty list; otherwise treat it as unknown.
    try:
        exists = await _redis_get_workspace_meta(workspace_id)
    except Exception:
        exists = None
    if not exists:
        try:
            exists = await db.db_get_workspace(workspace_id)
        except Exception:
            exists = None
    if not exists:
        raise HTTPException(status_code=404, detail='Workspace not found')

    return _paginate_sessions([], 'database')


class SessionSyncRequest(BaseModel):
    """Request model for syncing sessions from a worker."""

    worker_id: str
    sessions: List[Dict[str, Any]]


class ExternalSessionIngestRequest(BaseModel):
    """Ingest an external chat/session transcript (e.g. VS Code chat)."""

    source: Optional[str] = None
    worker_id: Optional[str] = None
    session: Optional[Dict[str, Any]] = None
    messages: Optional[List[Dict[str, Any]]] = None


def _normalize_iso_timestamp(value: Any) -> Optional[str]:
    """Normalize timestamps coming from workers.

    Workers may send ISO strings (preferred) or epoch times (agent often uses
    milliseconds since epoch). We normalize to an ISO-8601 string when possible
    so PostgreSQL ordering and UI displays behave consistently.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()

    if isinstance(value, str):
        v = value.strip()
        return v or None

    if isinstance(value, (int, float)):
        # Heuristic: treat large values as epoch milliseconds.
        ts = float(value)
        if ts > 1e11:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            return None

    return None


def _normalize_model_value(model: Any) -> Optional[str]:
    """Normalize model values to string format.

    Agent stores models as objects like {providerID: 'anthropic', modelID: 'claude-...'}.
    We normalize to the standard 'provider/model' string format for the UI.
    """
    if model is None:
        return None

    if isinstance(model, str):
        return model if model.strip() else None

    if isinstance(model, dict):
        provider_id = model.get('providerID')
        model_id = model.get('modelID')
        if provider_id and model_id:
            return f'{provider_id}/{model_id}'

    return None


@agent_router_alias.post('/workspaces/{workspace_id}/sessions/{session_id}/ingest')
async def ingest_external_session(
    workspace_id: str,
    session_id: str,
    payload: ExternalSessionIngestRequest,
    request: Request,
):
    """Persist an externally-captured session transcript into durable storage.

    This endpoint is designed for tools like a VS Code extension to upload chat
    turns without overwriting the worker session caches (unlike /sessions/sync).
    """
    _require_ingest_auth(request)

    source = (payload.source or 'external').strip() or 'external'
    session_data: Dict[str, Any] = (
        payload.session if isinstance(payload.session, dict) else {}
    )
    messages: List[Dict[str, Any]] = (
        payload.messages if isinstance(payload.messages, list) else []
    )

    created_at = (
        _normalize_iso_timestamp(
            session_data.get('created_at') or session_data.get('created')
        )
        or datetime.now(timezone.utc).isoformat()
    )
    updated_at = (
        _normalize_iso_timestamp(
            session_data.get('updated_at') or session_data.get('updated')
        )
        or datetime.now(timezone.utc).isoformat()
    )

    summary: Dict[str, Any] = {}
    if isinstance(session_data.get('summary'), dict):
        summary = dict(session_data['summary'])
    summary.setdefault('source', source)
    if payload.worker_id:
        summary.setdefault('worker_id', payload.worker_id)

    await db.db_upsert_session(
        {
            'id': session_id,
            'workspace_id': workspace_id,
            'project_id': session_data.get('project_id')
            or session_data.get('projectID'),
            'directory': session_data.get('directory')
            or session_data.get('path'),
            'title': session_data.get('title'),
            'version': session_data.get('version'),
            'summary': summary,
            'created_at': created_at,
            'updated_at': updated_at,
        }
    )

    def _stringify(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _extract_message_content(msg: Dict[str, Any]) -> Optional[str]:
        c = msg.get('content')
        content_str = _stringify(c)
        if isinstance(content_str, str) and content_str.strip():
            return content_str

        parts = msg.get('parts')
        if isinstance(parts, list):
            texts: List[str] = []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                t = p.get('text')
                if isinstance(t, str) and t:
                    texts.append(t)
            if texts:
                return ''.join(texts)

        info = msg.get('info')
        if isinstance(info, dict):
            ic = info.get('content')
            ic_str = _stringify(ic)
            if isinstance(ic_str, str) and ic_str.strip():
                return ic_str

        return None

    def _extract_role(msg: Dict[str, Any]) -> Optional[str]:
        r = msg.get('role')
        if isinstance(r, str) and r:
            return r
        info = msg.get('info')
        if isinstance(info, dict):
            r2 = info.get('role')
            if isinstance(r2, str) and r2:
                return r2
        return None

    def _extract_model(msg: Dict[str, Any]) -> Optional[str]:
        m = msg.get('model')
        normalized = _normalize_model_value(m)
        if normalized:
            return normalized
        info = msg.get('info')
        if isinstance(info, dict):
            m2 = info.get('model')
            return _normalize_model_value(m2)
        return None

    def _extract_created_at(msg: Dict[str, Any]) -> Optional[str]:
        ca = msg.get('created_at')
        normalized = _normalize_iso_timestamp(ca)
        if normalized:
            return normalized
        time_obj = msg.get('time')
        if isinstance(time_obj, dict):
            created = time_obj.get('created')
            normalized2 = _normalize_iso_timestamp(created)
            if normalized2:
                return normalized2
        return None

    ingested = 0
    for msg_data in messages:
        if not isinstance(msg_data, dict):
            continue
        msg_id = msg_data.get('id')
        if not isinstance(msg_id, str) or not msg_id:
            msg_id = str(uuid.uuid4())

        tokens = msg_data.get('tokens')
        if not isinstance(tokens, dict):
            tokens = {}

        tool_calls = msg_data.get('tool_calls')
        if not isinstance(tool_calls, list):
            tool_calls = msg_data.get('toolCalls')
        if not isinstance(tool_calls, list):
            tool_calls = []

        await db.db_upsert_message(
            {
                'id': msg_id,
                'session_id': session_id,
                'role': _extract_role(msg_data),
                'content': _extract_message_content(msg_data),
                'model': _extract_model(msg_data),
                'cost': msg_data.get('cost'),
                'tokens': tokens,
                'tool_calls': tool_calls,
                'created_at': _extract_created_at(msg_data)
                or datetime.now(timezone.utc).isoformat(),
            }
        )
        ingested += 1

    return {
        'success': True,
        'session_id': session_id,
        'source': source,
        'messages_ingested': ingested,
    }


@agent_router_alias.post('/workspaces/{workspace_id}/sessions/sync')
async def sync_sessions(workspace_id: str, request: SessionSyncRequest):
    """Receive synced sessions from a worker.

    This endpoint accepts session data from workers and persists it to PostgreSQL
    and Redis. It does NOT require the workspace to exist in the in-memory bridge -
    workers can sync sessions for any workspace_id they manage.
    """
    # Store the synced sessions
    _worker_sessions[workspace_id] = request.sessions

    # Best-effort persist to PostgreSQL (primary persistence)
    for session_data in request.sessions:
        try:
            created_at = _normalize_iso_timestamp(
                session_data.get('created_at') or session_data.get('created')
            )
            updated_at = _normalize_iso_timestamp(
                session_data.get('updated_at') or session_data.get('updated')
            )
            await db.db_upsert_session(
                {
                    'id': session_data.get('id'),
                    'workspace_id': workspace_id,
                    'project_id': session_data.get('project_id'),
                    'directory': session_data.get('directory'),
                    'title': session_data.get('title'),
                    'version': session_data.get('version'),
                    'summary': session_data.get('summary', {}),
                    'created_at': created_at,
                    'updated_at': updated_at,
                }
            )
        except Exception as e:
            logger.debug(f'Failed to persist session to PostgreSQL: {e}')

    # Best-effort persist to Redis (if configured) so sessions survive restarts / replicas.
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            await redis_client.set(
                _redis_key_worker_sessions(workspace_id),
                json.dumps(
                    {
                        'worker_id': request.worker_id,
                        'updated_at': datetime.utcnow().isoformat(),
                        'sessions': request.sessions,
                    }
                ),
            )
        except Exception as e:
            logger.debug(f'Failed to persist worker sessions to Redis: {e}')

    logger.info(
        f'Synced {len(request.sessions)} sessions for workspace {workspace_id} from worker {request.worker_id}'
    )
    return {'success': True, 'sessions_count': len(request.sessions)}


class MessageSyncRequest(BaseModel):
    """Request model for syncing messages from a worker."""

    worker_id: str
    messages: List[Dict[str, Any]]


@agent_router_alias.post(
    '/workspaces/{workspace_id}/sessions/{session_id}/messages/sync'
)
async def sync_session_messages(
    workspace_id: str, session_id: str, request: MessageSyncRequest
):
    """Receive synced messages from a worker.

    This endpoint accepts message data from workers and persists it to PostgreSQL
    and Redis. It does NOT require the workspace to exist in the in-memory bridge -
    workers can sync messages for any session they manage.
    """
    # Store the synced messages
    _worker_messages[session_id] = request.messages

    def _extract_message_content(msg: Dict[str, Any]) -> Optional[str]:
        def _looks_like_worker_registry_payload(value: Any) -> bool:
            if isinstance(value, dict):
                keys = set(value.keys())
                if {'worker_id', 'models', 'registered_at'}.issubset(keys):
                    return True
                if 'models' in keys and {
                    'global_workspace_id',
                    'last_seen',
                }.issubset(keys):
                    return True
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, dict) for item in value)
            ):
                sample = value[:3]
                if all(
                    'provider_id' in item and 'capabilities' in item
                    for item in sample
                ):
                    return True
            return False

        # Preferred: explicit content
        c = msg.get('content')
        if isinstance(c, str) and c.strip():
            return c

        # Worker-synced agent shape: parts[].text
        parts = msg.get('parts')
        if isinstance(parts, list):
            texts: List[str] = []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                t = p.get('text')
                if isinstance(t, str) and t:
                    texts.append(t)
            if texts:
                return ''.join(texts)

        # Alternate shape: info.content
        info = msg.get('info')
        if isinstance(info, dict):
            ic = info.get('content')
            if isinstance(ic, str) and ic.strip():
                return ic
            if ic is not None:
                if _looks_like_worker_registry_payload(ic):
                    return None
                if isinstance(ic, (dict, list)):
                    return json.dumps(ic, ensure_ascii=True)

        return None

    def _extract_role(msg: Dict[str, Any]) -> Optional[str]:
        r = msg.get('role')
        if isinstance(r, str) and r:
            return r
        info = msg.get('info')
        if isinstance(info, dict):
            r2 = info.get('role')
            if isinstance(r2, str) and r2:
                return r2
        return None

    def _extract_model(msg: Dict[str, Any]) -> Optional[str]:
        m = msg.get('model')
        normalized = _normalize_model_value(m)
        if normalized:
            return normalized
        info = msg.get('info')
        if isinstance(info, dict):
            m2 = info.get('model')
            return _normalize_model_value(m2)
        return None

    def _extract_created_at(msg: Dict[str, Any]) -> Optional[str]:
        ca = msg.get('created_at')
        normalized = _normalize_iso_timestamp(ca)
        if normalized:
            return normalized
        time_obj = msg.get('time')
        if isinstance(time_obj, dict):
            created = time_obj.get('created')
            normalized2 = _normalize_iso_timestamp(created)
            if normalized2:
                return normalized2
        return None

    # Best-effort persist to PostgreSQL (primary persistence)
    for msg_data in request.messages:
        try:
            await db.db_upsert_message(
                {
                    'id': msg_data.get('id'),
                    'session_id': session_id,
                    'role': _extract_role(msg_data),
                    'content': _extract_message_content(msg_data),
                    'model': _extract_model(msg_data),
                    'cost': msg_data.get('cost'),
                    'tokens': msg_data.get('tokens', {}),
                    'tool_calls': msg_data.get('tool_calls', []),
                    'created_at': _extract_created_at(msg_data),
                }
            )
        except Exception as e:
            logger.debug(f'Failed to persist message to PostgreSQL: {e}')

    # Best-effort token billing: record token usage for assistant messages
    try:
        from .token_billing import TokenCounts, get_token_billing_service

        # Resolve tenant_id from workspace
        tenant_id = None
        try:
            workspace_record = await db.db_get_workspace(workspace_id)
            if workspace_record:
                tenant_id = workspace_record.get('tenant_id')
        except Exception:
            pass

        if tenant_id:
            token_billing = get_token_billing_service()
            for msg_data in request.messages:
                role = _extract_role(msg_data)
                tokens_raw = msg_data.get('tokens')
                model = _extract_model(msg_data)
                if role == 'assistant' and tokens_raw and model:
                    tokens = TokenCounts.from_dict(tokens_raw if isinstance(tokens_raw, dict) else {})
                    if tokens.total > 0 or tokens.cache_read_tokens > 0:
                        # Extract provider from model string (e.g., "anthropic/claude-opus-4-5")
                        if '/' in model:
                            provider, model_name = model.split('/', 1)
                        else:
                            provider, model_name = 'unknown', model
                        await token_billing.record_usage(
                            tenant_id=tenant_id,
                            provider=provider,
                            model=model_name,
                            tokens=tokens,
                            session_id=session_id,
                            message_id=msg_data.get('id'),
                        )
    except Exception as e:
        logger.debug(f'Token billing recording failed (non-fatal): {e}')

    # Best-effort persist to Redis (if configured) so messages are available across replicas.
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            await redis_client.set(
                _redis_key_worker_messages(session_id),
                json.dumps(
                    {
                        'worker_id': request.worker_id,
                        'updated_at': datetime.utcnow().isoformat(),
                        'messages': request.messages,
                    }
                ),
            )
        except Exception as e:
            logger.debug(f'Failed to persist worker messages to Redis: {e}')

    return {'success': True, 'messages_count': len(request.messages)}


@agent_router_alias.get('/workspaces/{workspace_id}/sessions/{session_id}')
async def get_session(workspace_id: str, session_id: str):
    """Get details of a specific session."""
    import aiohttp

    bridge = get_agent_bridge()
    workspace = bridge.get_workspace(workspace_id) if bridge is not None else None

    # If there's a running agent instance, query its API
    if workspace and workspace.agent_port:
        try:
            base_url = bridge._get_agent_base_url(workspace.agent_port)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{base_url}/session/{session_id}',
                    params={'directory': workspace.path},
                ) as resp:
                    if resp.status == 200:
                        session_data = await resp.json()
                        return session_data
        except Exception as e:
            logger.warning(f'Failed to query agent API: {e}')

    # Fallback: Read from local state
    if workspace:
        session_data = await _read_local_session(workspace.path, session_id)
        if session_data:
            return session_data

    # Final fallback: PostgreSQL persistence.
    try:
        persisted = await db.db_get_session(session_id=session_id)
        if persisted and persisted.get('workspace_id') == workspace_id:
            return persisted
    except Exception as e:
        logger.debug(f'Failed to read session from PostgreSQL: {e}')

    raise HTTPException(status_code=404, detail='Session not found')


@agent_router_alias.get('/workspaces/{workspace_id}/sessions/{session_id}/messages')
async def get_session_messages_by_id(
    workspace_id: str, session_id: str, limit: int = 100
):
    """Get messages from a specific session."""
    import aiohttp
    import traceback

    try:
        return await _get_session_messages_impl(workspace_id, session_id, limit)
    except Exception as e:
        logger.error(
            f'Unhandled error in get_session_messages_by_id: {e}\n{traceback.format_exc()}'
        )
        # Return empty response instead of 500
        return {
            'messages': [],
            'session_id': session_id,
            'source': 'error',
            'error': str(e),
        }


async def _get_session_messages_impl(
    workspace_id: str, session_id: str, limit: int = 100
):
    """Internal implementation for get_session_messages_by_id."""
    import aiohttp

    try:
        bridge = get_agent_bridge()
        workspace = (
            bridge.get_workspace(workspace_id) if bridge is not None else None
        )
    except Exception as e:
        logger.warning(
            f'Failed to get bridge/workspace for session messages: {e}'
        )
        workspace = None
        bridge = None

    # Check Redis-backed worker-synced messages first.
    try:
        redis_client = await _get_redis_client()
    except Exception as e:
        logger.warning(f'Failed to get Redis client for session messages: {e}')
        redis_client = None

    if redis_client is not None:
        try:
            raw = await redis_client.get(_redis_key_worker_messages(session_id))
            if raw:
                payload = json.loads(raw)
                messages = (
                    payload.get('messages')
                    if isinstance(payload, dict)
                    else None
                )
                if messages:
                    return {
                        'messages': messages[:limit],
                        'session_id': session_id,
                        'source': 'worker_sync',
                        'synced_at': payload.get('updated_at')
                        if isinstance(payload, dict)
                        else None,
                    }
        except Exception as e:
            logger.debug(f'Failed to read worker messages from Redis: {e}')

    # Check if we have worker-synced messages
    if session_id in _worker_messages and _worker_messages[session_id]:
        messages = _worker_messages[session_id][:limit]
        return {
            'messages': messages,
            'session_id': session_id,
            'source': 'worker_sync',
        }

    # If we don't have a workspace locally, try to rehydrate it so we can query
    # the agent API / local state for local workspaces.
    if workspace is None and bridge is not None:
        try:
            workspace = await _rehydrate_workspace_into_bridge(workspace_id)
        except Exception as e:
            logger.warning(
                f'Failed to rehydrate workspace for session messages: {e}'
            )
            workspace = None

    # If there's a running agent instance, query its API
    if workspace and workspace.agent_port:
        try:
            base_url = bridge._get_agent_base_url(workspace.agent_port)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{base_url}/session/{session_id}/message',
                    params={'directory': workspace.path, 'limit': limit},
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        return {'messages': messages, 'session_id': session_id}
        except Exception as e:
            logger.warning(f'Failed to query agent API: {e}')

    # Fallback: Read from local state (only works when the server has filesystem access).
    if workspace:
        try:
            messages = await _read_local_session_messages(
                workspace.path, session_id
            )
            if messages:
                return {
                    'messages': messages[:limit],
                    'session_id': session_id,
                    'source': 'local_state',
                }
        except Exception as e:
            logger.warning(f'Failed to read local session messages: {e}')

    # Final fallback: PostgreSQL persistence (common for remote workers).
    try:
        persisted = await db.db_list_messages(
            session_id=session_id, limit=limit
        )
        if persisted:
            # Normalize DB rows into the shape expected by the Swift client
            # (SessionMessage: {id, sessionID, role, info{...}, time{created}, model, ...}).
            normalized: List[Dict[str, Any]] = []
            for row in persisted:
                role = row.get('role')
                model = row.get('model')
                content = row.get('content')
                created_at = row.get('created_at')
                normalized.append(
                    {
                        'id': row.get('id'),
                        'sessionID': session_id,
                        'role': role,
                        'info': {
                            'role': role,
                            'model': model,
                            'content': content,
                        },
                        'time': {'created': created_at},
                        'model': model,
                        'cost': row.get('cost'),
                        'tokens': row.get('tokens', {}),
                    }
                )
            return {
                'messages': normalized,
                'session_id': session_id,
                'source': 'database',
            }
    except Exception as e:
        logger.debug(f'Failed to read session messages from PostgreSQL: {e}')

    return {'messages': [], 'session_id': session_id, 'source': 'local_state'}


@agent_router_alias.post('/workspaces/{workspace_id}/sessions/{session_id}/resume')
async def resume_session(
    workspace_id: str, session_id: str, request: SessionResumeRequest
):
    """Resume an old session and optionally send a new prompt."""
    import aiohttp

    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        workspace = await _rehydrate_workspace_into_bridge(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    resume_prompt = request.prompt or 'Continue where we left off'
    resume_metadata: Dict[str, Any] = {'resume_session_id': session_id}
    if request.model:
        resume_metadata['model'] = request.model
    if request.model_ref:
        resume_metadata['model_ref'] = request.model_ref

    routing_decision, routed_resume_metadata = orchestrate_task_route(
        prompt=resume_prompt,
        agent_type=request.agent,
        metadata=resume_metadata,
        model=request.model,
        model_ref=request.model_ref,
        worker_personality=request.worker_personality,
    )
    effective_resume_model = (
        routed_resume_metadata.get('model') or request.model
    )

    # If the user provided a prompt, log it as a human message for correct attribution.
    if request.prompt:
        try:
            await monitoring_service.log_message(
                agent_name='User',
                content=request.prompt,
                message_type='human',
                metadata={
                    'action': 'agent.session.resume',
                    'workspace_id': workspace_id,
                    'workspace_name': workspace.name,
                    'resume_session_id': session_id,
                    'agent': request.agent,
                    'model': effective_resume_model,
                    'model_ref': routing_decision.model_ref,
                    'worker_personality': routing_decision.worker_personality,
                },
            )
        except Exception as e:
            logger.debug(f'Failed to log user resume prompt: {e}')

        # Persist the user prompt so chat history feels like a normal chat app.
        message_id = f'msg_{uuid.uuid4().hex}'
        part_id = f'prt_{uuid.uuid4().hex}'
        created_at = datetime.utcnow().isoformat()
        user_message = {
            'id': message_id,
            'sessionID': session_id,
            'role': 'user',
            'time': {'created': created_at},
            'info': {
                'id': message_id,
                'sessionID': session_id,
                'role': 'user',
                'content': request.prompt,
                'time': {'created': created_at},
            },
            'parts': [
                {
                    'id': part_id,
                    'sessionID': session_id,
                    'messageID': message_id,
                    'type': 'text',
                    'text': request.prompt,
                }
            ],
        }

        try:
            await db.db_upsert_message(
                {
                    'id': message_id,
                    'session_id': session_id,
                    'role': 'user',
                    'content': request.prompt,
                    'model': None,
                    'created_at': created_at,
                }
            )
        except Exception as e:
            logger.debug(f'Failed to persist user message: {e}')

        try:
            await _append_worker_message(
                session_id,
                user_message,
                worker_id=workspace.worker_id if workspace else None,
            )
        except Exception as e:
            logger.debug(f'Failed to append user message to worker cache: {e}')

    # For remote workers, create a task with the session_id in metadata
    if workspace.worker_id:
        task = await bridge.create_task(
            codebase_id=workspace_id,
            title=f'Resume session: {request.prompt[:50] if request.prompt else "Continue"}',
            prompt=resume_prompt,
            agent_type=request.agent,
            model=effective_resume_model,
            metadata=routed_resume_metadata,
            model_ref=routing_decision.model_ref,
        )
        return {
            'success': True,
            'message': f'Task queued to resume session {session_id}',
            'task_id': task.id if task else None,
            'session_id': session_id,
            # For follow-up UI actions, this is the session the user is interacting with.
            'active_session_id': session_id,
            'routing': {
                'complexity': routing_decision.complexity,
                'model_tier': routing_decision.model_tier,
                'model_ref': routing_decision.model_ref,
                'target_agent_name': routing_decision.target_agent_name,
                'worker_personality': routing_decision.worker_personality,
            },
        }

    # For local workspaces with running agent, use the API
    if workspace.agent_port:
        try:
            base_url = bridge._get_agent_base_url(workspace.agent_port)
            async with aiohttp.ClientSession() as session:
                # First, initialize the session
                async with session.post(
                    f'{base_url}/session/{session_id}/init',
                    params={'directory': workspace.path},
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise HTTPException(
                            status_code=resp.status,
                            detail=f'Failed to init session: {error}',
                        )

                # If there's a prompt, send a message
                if request.prompt:
                    payload = {
                        'content': request.prompt,
                        'agent': request.agent,
                    }
                    # Best-effort: allow overriding model when agent supports it.
                    if effective_resume_model:
                        payload['model'] = effective_resume_model

                    async def _send_message(body: Dict[str, Any]):
                        async with session.post(
                            f'{base_url}/session/{session_id}/message',
                            params={'directory': workspace.path},
                            json=body,
                        ) as resp:
                            return resp.status, await resp.text()

                    status, text = await _send_message(payload)
                    if status == 422 and effective_resume_model:
                        # Compatibility: some agent builds may not accept a `model` field.
                        payload.pop('model', None)
                        status, text = await _send_message(payload)

                    if status == 200:
                        try:
                            result = json.loads(text) if text else None
                        except Exception:
                            result = None
                        # Update workspace session_id
                        workspace.session_id = session_id
                        return {
                            'success': True,
                            'message': 'Session resumed',
                            'session_id': session_id,
                            'active_session_id': session_id,
                            'response': result,
                        }
                else:
                    # Update workspace session_id
                    workspace.session_id = session_id
                    return {
                        'success': True,
                        'message': 'Session initialized',
                        'session_id': session_id,
                        'active_session_id': session_id,
                    }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Failed to resume session: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    # If no running agent, start one with the session
    from .agent_bridge import AgentTriggerRequest

    trigger_request = AgentTriggerRequest(
        workspace_id=workspace_id,
        prompt=request.prompt or 'Continue the conversation',
        agent=request.agent,
        model=effective_resume_model,
        metadata=routed_resume_metadata,
    )

    response = await bridge.trigger_agent(trigger_request)
    return {
        'success': response.success,
        'message': 'Session resumed with new agent instance',
        'session_id': session_id,
        'new_session_id': response.session_id,
        # When agent is started on-demand, follow-up messages should target the active agent session.
        'active_session_id': response.session_id or session_id,
        'error': response.error,
        'routing': {
            'complexity': routing_decision.complexity,
            'model_tier': routing_decision.model_tier,
            'model_ref': routing_decision.model_ref,
            'target_agent_name': routing_decision.target_agent_name,
            'worker_personality': routing_decision.worker_personality,
        },
    }


async def _read_local_sessions(workspace_path: str) -> List[Dict[str, Any]]:
    """Read sessions from agent's local state directory."""
    import glob

    sessions = []
    # Agent stores state in .codetether directory
    state_dir = os.path.join(workspace_path, '.codetether', 'state')

    if not os.path.exists(state_dir):
        return sessions

    # Look for session files
    session_files = glob.glob(os.path.join(state_dir, 'session', '*.json'))

    for session_file in session_files:
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
                sessions.append(
                    {
                        'id': session_data.get(
                            'id',
                            os.path.basename(session_file).replace('.json', ''),
                        ),
                        'created': session_data.get('created'),
                        'updated': session_data.get('updated'),
                        'title': session_data.get('title', 'Untitled Session'),
                        'agent': session_data.get('agent'),
                        'model': session_data.get('model'),
                        'messageCount': len(session_data.get('messages', [])),
                    }
                )
        except Exception as e:
            logger.warning(f'Failed to read session file {session_file}: {e}')

    # Sort by updated time, most recent first
    sessions.sort(key=lambda s: s.get('updated', ''), reverse=True)
    return sessions


async def _read_local_session(
    workspace_path: str, session_id: str
) -> Optional[Dict[str, Any]]:
    """Read a specific session from agent's local state directory."""
    session_file = os.path.join(
        workspace_path, '.codetether', 'state', 'session', f'{session_id}.json'
    )

    if not os.path.exists(session_file):
        return None

    try:
        with open(session_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'Failed to read session file {session_file}: {e}')
        return None


async def _read_local_session_messages(
    workspace_path: str, session_id: str
) -> List[Dict[str, Any]]:
    """Read messages from a session's local state."""
    session_data = await _read_local_session(workspace_path, session_id)
    if session_data:
        return session_data.get('messages', [])
    return []


# ========================================
# Watch Mode Endpoints (Persistent Workers)
# ========================================


@agent_router_alias.post('/workspaces/{workspace_id}/watch/start')
async def start_watch_mode(
    workspace_id: str, config: Optional[WatchModeConfig] = None
):
    """
    Start watch mode for a workspace - agent will automatically process tasks.

    The agent will poll for pending tasks and execute them in order of priority.
    """
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    interval = config.interval if config else 5

    success = await bridge.start_watch_mode(workspace_id, interval=interval)
    if not success:
        raise HTTPException(
            status_code=500, detail='Failed to start watch mode'
        )

    await monitoring_service.log_message(
        agent_name='CodeTether Agent',
        content=f'Watch mode started for {workspace.name} (interval: {interval}s)',
        message_type='system',
        metadata={'workspace_id': workspace_id, 'interval': interval},
    )

    return {
        'success': True,
        'message': f'Watch mode started for {workspace.name}',
        'interval': interval,
    }


@agent_router_alias.post('/workspaces/{workspace_id}/watch/stop')
async def stop_watch_mode(workspace_id: str):
    """Stop watch mode for a workspace."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    success = await bridge.stop_watch_mode(workspace_id)
    if not success:
        raise HTTPException(status_code=500, detail='Failed to stop watch mode')

    await monitoring_service.log_message(
        agent_name='CodeTether Agent',
        content=f'Watch mode stopped for {workspace.name}',
        message_type='system',
        metadata={'workspace_id': workspace_id},
    )

    return {
        'success': True,
        'message': f'Watch mode stopped for {workspace.name}',
    }


@agent_router_alias.get('/workspaces/{workspace_id}/watch/status')
async def get_watch_status(workspace_id: str):
    """Get watch mode status for a workspace."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    pending_tasks = await bridge.list_tasks(
        codebase_id=workspace_id,
        status=bridge._tasks.__class__.PENDING
        if hasattr(bridge._tasks, '__class__')
        else None,
    )
    from .agent_bridge import AgentTaskStatus

    pending_count = len(
        await bridge.list_tasks(
            codebase_id=workspace_id, status=AgentTaskStatus.PENDING
        )
    )
    running_count = len(
        await bridge.list_tasks(
            codebase_id=workspace_id, status=AgentTaskStatus.RUNNING
        )
    )

    return {
        'workspace_id': workspace_id,
        'name': workspace.name,
        'watch_mode': workspace.watch_mode,
        'status': workspace.status.value,
        'interval': workspace.watch_interval,
        'pending_tasks': pending_count,
        'running_tasks': running_count,
    }


# Helper function to integrate monitoring with existing A2A server
async def log_agent_message(
    agent_name: str,
    content: Optional[str] = None,
    message: Optional[str] = None,
    **kwargs,
):
    """Helper function to log agent messages.

    Args:
        agent_name: Name of the agent sending the message
        content: Message content (preferred parameter name)
        message: Alternative parameter name for message content
        **kwargs: Additional metadata (message_type, metadata, etc.)
    """
    # Support both 'content' and 'message' parameter names
    message_content = content or message
    if not message_content:
        raise ValueError(
            "Either 'content' or 'message' parameter must be provided"
        )

    await monitoring_service.log_message(
        agent_name=agent_name, content=message_content, **kwargs
    )


# ========================================
# Worker Registration & Management
# ========================================

# In-memory worker registry (workers are transient - they re-register on start)
_registered_workers: Dict[str, Dict[str, Any]] = {}


class WorkerRegistration(BaseModel):
    """Worker registration request."""

    worker_id: str
    name: str
    capabilities: List[str] = []
    hostname: Optional[str] = None
    models: List[Dict[str, Any]] = []
    global_workspace_id: Optional[str] = None
    workspaces: List[str] = []  # List of workspace IDs this worker handles
    agents: List[Dict[str, Any]] = []  # Custom agent definitions this worker supports


class TaskStatusUpdate(BaseModel):
    """Task status update from worker."""

    status: str
    worker_id: str
    session_id: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


@agent_router_alias.post('/workers/register')
async def register_worker(registration: WorkerRegistration):
    """Register a worker with the A2A server."""
    worker_info = {
        'worker_id': registration.worker_id,
        'name': registration.name,
        'capabilities': registration.capabilities,
        'hostname': registration.hostname,
        'models': registration.models,
        'global_workspace_id': registration.global_workspace_id,
        'workspaces': registration.workspaces,  # Workspace IDs for task routing
        'registered_at': datetime.utcnow().isoformat(),
        'last_seen': datetime.utcnow().isoformat(),
        'status': 'active',
    }

    # In-memory cache for this instance
    _registered_workers[registration.worker_id] = worker_info

    # Primary persistence: PostgreSQL (survives restarts/multi-replica)
    await db.db_upsert_worker(worker_info)

    # Secondary persistence: Redis (for session sync and fallback)
    await _redis_upsert_worker(worker_info)

    # Persist agent definitions from this worker
    if registration.agents:
        for agent_def in registration.agents:
            agent_def['worker_id'] = registration.worker_id
            if not agent_def.get('id'):
                agent_def['id'] = str(uuid.uuid4())
            await db.db_upsert_agent_definition(agent_def)
        logger.info(
            f'Worker {registration.worker_id} registered {len(registration.agents)} agent(s): '
            f'{", ".join(a.get("name", "?") for a in registration.agents)}'
        )

    logger.info(
        f'Worker registered: {registration.name} (ID: {registration.worker_id})'
    )

    await monitoring_service.log_message(
        agent_name='Worker Registry',
        content=f"Worker '{registration.name}' connected from {registration.hostname}",
        message_type='system',
        metadata=worker_info,
    )

    return {'success': True, 'worker': worker_info}


@agent_router_alias.post('/workers/{worker_id}/unregister')
async def unregister_worker(worker_id: str):
    """Unregister a worker."""
    worker_info = None

    # Remove from in-memory
    if worker_id in _registered_workers:
        worker_info = _registered_workers.pop(worker_id)

    # Remove agent definitions for this worker
    await db.db_delete_agent_definitions_by_worker(worker_id)

    # Remove from PostgreSQL
    await db.db_delete_worker(worker_id)

    # Remove from Redis
    await _redis_delete_worker(worker_id)

    if worker_info:
        logger.info(
            f'Worker unregistered: {worker_info.get("name")} (ID: {worker_id})'
        )
        await monitoring_service.log_message(
            agent_name='Worker Registry',
            content=f"Worker '{worker_info.get('name')}' disconnected",
            message_type='system',
        )
        return {'success': True, 'message': 'Worker unregistered'}

    # Check if it existed in DB/Redis
    db_worker = await db.db_get_worker(worker_id)
    redis_worker = await _redis_get_worker(worker_id)
    if db_worker or redis_worker:
        return {'success': True, 'message': 'Worker unregistered'}

    return {'success': False, 'message': 'Worker not found'}


@agent_router_alias.get('/workers')
async def list_workers(search: Optional[str] = None):
    """List all registered workers with optional model search filter."""
    def _classify_worker_runtime(
        worker: Dict[str, Any],
        sse_worker: Optional[Dict[str, Any]],
    ) -> str:
        source = str(worker.get('_registry_source') or '')
        worker_id = str(worker.get('worker_id') or '').lower()
        name = str(worker.get('name') or '').lower()
        capabilities = [
            str(cap).lower() for cap in (worker.get('capabilities') or [])
        ]
        sse_agent_name = (
            str(sse_worker.get('agent_name') or '').lower()
            if sse_worker
            else ''
        )

        rust_markers = [
            'rust',
            'codetether-agent',
            'a2a-rs',
            'worker-rs',
        ]
        python_markers = [
            'python',
            'agent',
            'hosted-worker',
            'hosted_worker',
        ]

        rust_hint = any(
            marker in worker_id
            or marker in name
            or marker in sse_agent_name
            or any(marker in cap for cap in capabilities)
            for marker in rust_markers
        )
        python_hint = any(
            marker in worker_id
            or marker in name
            or any(marker in cap for cap in capabilities)
            for marker in python_markers
        )

        # SSE-connected workers are Rust workers.
        # This must take precedence over storage source, since Rust workers
        # also register into the in-memory/Redis/Postgres registries.
        if sse_worker:
            return 'rust'

        # Local in-memory registrations are legacy Python workers (deprecated),
        # unless clear Rust hints are present.
        if source == 'memory':
            if rust_hint and not python_hint:
                return 'rust'
            return 'python'

        # Durable remote entries are typically Rust workers unless explicitly marked python.
        if source in ('redis', 'database'):
            if python_hint and not rust_hint:
                return 'python'
            return 'rust'

        if python_hint and not rust_hint:
            return 'python'
        if rust_hint:
            return 'rust'
        return 'python'

    def _runtime_label(runtime: str) -> str:
        if runtime == 'rust':
            return 'Rust Worker'
        return 'Legacy Python Worker (deprecated)'

    # Priority: PostgreSQL > Redis > in-memory
    db_workers = await db.db_list_workers()
    redis_workers = await _redis_list_workers()

    merged: Dict[str, Dict[str, Any]] = {}

    # In-memory first (most up-to-date for this instance)
    for w in _registered_workers.values():
        wid = w.get('worker_id')
        if wid:
            worker = dict(w)
            worker['_registry_source'] = 'memory'
            merged[wid] = worker

    # Redis (may have workers from other instances)
    for w in redis_workers:
        wid = w.get('worker_id')
        if wid and wid not in merged:
            worker = dict(w)
            worker['_registry_source'] = 'redis'
            merged[wid] = worker

    # PostgreSQL (durable, survives restarts)
    for w in db_workers:
        wid = w.get('worker_id')
        if wid and wid not in merged:
            worker = dict(w)
            worker['_registry_source'] = 'database'
            merged[wid] = worker

    workers = list(merged.values())

    # Include connected SSE worker metadata to improve runtime classification.
    sse_workers_by_id: Dict[str, Dict[str, Any]] = {}
    try:
        from .worker_sse import get_worker_registry

        sse_registry = get_worker_registry()
        sse_workers = await sse_registry.list_workers()
        for sse_worker in sse_workers:
            wid = sse_worker.get('worker_id')
            if wid:
                sse_workers_by_id[str(wid)] = sse_worker
    except Exception as e:
        logger.debug(f'Unable to load SSE worker registry for classification: {e}')

    annotated_workers: List[Dict[str, Any]] = []
    for worker in workers:
        wid = str(worker.get('worker_id') or '')
        sse_worker = sse_workers_by_id.get(wid)
        runtime = _classify_worker_runtime(worker, sse_worker)
        annotated = dict(worker)
        annotated['worker_runtime'] = runtime
        annotated['worker_runtime_label'] = _runtime_label(runtime)
        annotated.pop('_registry_source', None)
        annotated_workers.append(annotated)
    workers = annotated_workers

    if search:
        search_lower = search.lower()
        workers = [
            w
            for w in workers
            if any(
                search_lower in str(m).lower()
                for m in w.get('models', [])
            )
        ]

    return workers


@agent_router_alias.get('/workers/{worker_id}')
async def get_worker(worker_id: str):
    """Get worker details."""
    # Check in-memory first
    if worker_id in _registered_workers:
        return _registered_workers[worker_id]

    # Check PostgreSQL
    db_worker = await db.db_get_worker(worker_id)
    if db_worker:
        return db_worker

    # Check Redis fallback
    redis_worker = await _redis_get_worker(worker_id)
    if redis_worker:
        return redis_worker

    raise HTTPException(status_code=404, detail='Worker not found')


@agent_router_alias.post('/workers/{worker_id}/heartbeat')
async def worker_heartbeat(worker_id: str):
    """Update worker last-seen timestamp."""
    now = datetime.utcnow().isoformat()

    # Update in-memory cache
    if worker_id in _registered_workers:
        _registered_workers[worker_id]['last_seen'] = now

    # Update PostgreSQL - check if it actually updated a row
    db_updated = await db.db_update_worker_heartbeat(worker_id)

    # If worker wasn't in DB, it may need to be re-registered
    # This can happen after DB reset while in-memory cache still has worker
    if not db_updated:
        # Check if we have the worker info to re-insert
        worker_info = _registered_workers.get(worker_id)
        if worker_info:
            # Re-insert worker into DB
            worker_info['last_seen'] = now
            await db.db_upsert_worker(worker_info)
            logger.info(
                f'Re-inserted worker {worker_id} into DB during heartbeat'
            )
        else:
            # Try to get from Redis and re-insert
            redis_worker = await _redis_get_worker(worker_id)
            if redis_worker:
                redis_worker['last_seen'] = now
                await db.db_upsert_worker(redis_worker)
                await _redis_upsert_worker(redis_worker)
                logger.info(
                    f'Re-inserted worker {worker_id} from Redis into DB during heartbeat'
                )
                return {'success': True}
            else:
                # Check if worker is connected via SSE (different registry)
                try:
                    from .worker_sse import get_worker_registry
                    sse_registry = get_worker_registry()
                    sse_workers = await sse_registry.list_workers()
                    sse_worker = next(
                        (w for w in sse_workers if w.get('worker_id') == worker_id),
                        None,
                    )
                    if sse_worker:
                        # Auto-register SSE worker into main registry
                        worker_info = {
                            'worker_id': worker_id,
                            'name': sse_worker.get('agent_name', 'unknown'),
                            'capabilities': sse_worker.get('capabilities', []),
                            'hostname': '',
                            'models': [],
                            'workspaces': list(sse_worker.get('workspaces', [])),
                            'registered_at': now,
                            'last_seen': now,
                            'status': 'active',
                        }
                        _registered_workers[worker_id] = worker_info
                        await db.db_upsert_worker(worker_info)
                        await _redis_upsert_worker(worker_info)
                        logger.info(
                            f'Auto-registered SSE worker {worker_id} into main registry during heartbeat'
                        )
                        return {'success': True}
                except Exception as e:
                    logger.debug(f'SSE registry check failed: {e}')

                # Worker not found anywhere - return 404 so worker re-registers
                raise HTTPException(
                    status_code=404,
                    detail='Worker not found - please re-register',
                )

    # Update Redis
    if worker_id in _registered_workers:
        await _redis_upsert_worker(_registered_workers[worker_id])
    else:
        # Get from DB and update Redis
        db_worker = await db.db_get_worker(worker_id)
        if db_worker:
            db_worker['last_seen'] = now
            await _redis_upsert_worker(db_worker)

    return {'success': True}


# ---------------------------------------------------------------------------
# Worker Profiles – Pydantic models
# ---------------------------------------------------------------------------

class WorkerProfileCreate(BaseModel):
    """Request body for creating a custom worker profile."""
    slug: str
    name: str
    description: str = ''
    system_prompt: str = ''
    default_capabilities: List[str] = []
    default_model_tier: str = 'balanced'
    default_model_ref: Optional[str] = None
    default_agent_type: str = 'build'
    icon: str = '🤖'
    color: str = '#6366f1'


class WorkerProfileUpdate(BaseModel):
    """Request body for updating a custom worker profile."""
    slug: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    default_capabilities: Optional[List[str]] = None
    default_model_tier: Optional[str] = None
    default_model_ref: Optional[str] = None
    default_agent_type: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class WorkerProfileAssign(BaseModel):
    """Assign a profile to a worker."""
    profile_id: Optional[str] = None  # None clears the assignment


# ---------------------------------------------------------------------------
# Worker Profiles – CRUD endpoints
# ---------------------------------------------------------------------------

@agent_router_alias.get('/worker-profiles')
async def list_worker_profiles(
    builtin_only: bool = False,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """List all visible worker profiles (builtins + user-owned)."""
    profiles = await db.db_list_worker_profiles(
        tenant_id=tenant_id, user_id=user_id, builtin_only=builtin_only
    )
    # Parse JSONB fields that come back as strings
    for p in profiles:
        caps = p.get('default_capabilities')
        if isinstance(caps, str):
            try:
                p['default_capabilities'] = json.loads(caps)
            except Exception:
                pass
    return profiles


@agent_router_alias.get('/worker-profiles/{profile_id}')
async def get_worker_profile(profile_id: str):
    """Get a single worker profile by ID or slug."""
    profile = await db.db_get_worker_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail='Worker profile not found')
    caps = profile.get('default_capabilities')
    if isinstance(caps, str):
        try:
            profile['default_capabilities'] = json.loads(caps)
        except Exception:
            pass
    return profile


@agent_router_alias.post('/worker-profiles')
async def create_worker_profile(
    body: WorkerProfileCreate,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Create a custom worker profile."""
    data = body.dict()
    data['is_builtin'] = False
    if user_id:
        data['user_id'] = user_id
    if tenant_id:
        data['tenant_id'] = tenant_id
    profile = await db.db_create_worker_profile(data)
    if not profile:
        raise HTTPException(
            status_code=500, detail='Failed to create worker profile (slug may already exist)'
        )
    caps = profile.get('default_capabilities')
    if isinstance(caps, str):
        try:
            profile['default_capabilities'] = json.loads(caps)
        except Exception:
            pass
    return profile


@agent_router_alias.patch('/worker-profiles/{profile_id}')
async def update_worker_profile(profile_id: str, body: WorkerProfileUpdate):
    """Update a custom worker profile. Builtin profiles cannot be modified."""
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail='No fields to update')
    profile = await db.db_update_worker_profile(profile_id, updates)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail='Profile not found or is a builtin profile (cannot modify)',
        )
    caps = profile.get('default_capabilities')
    if isinstance(caps, str):
        try:
            profile['default_capabilities'] = json.loads(caps)
        except Exception:
            pass
    return profile


@agent_router_alias.delete('/worker-profiles/{profile_id}')
async def delete_worker_profile(profile_id: str):
    """Delete a custom worker profile. Builtin profiles cannot be deleted."""
    deleted = await db.db_delete_worker_profile(profile_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail='Profile not found or is a builtin profile (cannot delete)',
        )
    return {'success': True}


@agent_router_alias.post('/workers/{worker_id}/profile')
async def assign_worker_profile(worker_id: str, body: WorkerProfileAssign):
    """Assign (or clear) a personality profile on a worker."""
    if body.profile_id:
        profile = await db.db_get_worker_profile(body.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail='Profile not found')
    ok = await db.db_set_worker_profile(worker_id, body.profile_id)
    if not ok:
        raise HTTPException(status_code=500, detail='Failed to assign profile')
    return {'success': True, 'worker_id': worker_id, 'profile_id': body.profile_id}


# ---------------------------------------------------------------------------
# Agent Definitions – CRUD endpoints
# ---------------------------------------------------------------------------


class AgentDefinitionCreate(BaseModel):
    """Request body for creating a custom agent definition."""
    name: str
    description: Optional[str] = None
    mode: str = 'primary'
    hidden: bool = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_steps: Optional[int] = None
    system_prompt: Optional[str] = None


class AgentDefinitionUpdate(BaseModel):
    """Request body for updating a custom agent definition."""
    name: Optional[str] = None
    description: Optional[str] = None
    mode: Optional[str] = None
    hidden: Optional[bool] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_steps: Optional[int] = None
    system_prompt: Optional[str] = None


@agent_router_alias.get('/agents')
async def list_agent_definitions(
    worker_id: Optional[str] = None,
    include_builtins: bool = True,
):
    """List all agent definitions, optionally filtered by worker.

    Returns a merged list of built-in agents and custom per-worker agents.
    """
    builtin_agents = [
        {
            'id': f'builtin-{name}',
            'name': name,
            'description': desc,
            'mode': mode,
            'native': True,
            'hidden': False,
            'model': None,
            'temperature': None,
            'top_p': None,
            'max_steps': max_steps,
            'system_prompt': None,
            'worker_id': None,
        }
        for name, desc, mode, max_steps in [
            ('build', 'Full access agent for development work', 'primary', 100),
            ('plan', 'Read-only agent for analysis and code exploration', 'primary', 50),
            ('coder', 'Code writing focused agent', 'primary', 100),
            ('explore', 'Fast agent for workspace search and exploration', 'subagent', 20),
            ('swarm', 'Parallel sub-agents for complex tasks', 'primary', 200),
        ]
    ]

    # Get custom agents from database
    custom_agents = await db.db_list_agent_definitions(
        worker_id=worker_id,
        include_hidden=False,
        include_native=False,
    )

    if include_builtins:
        return builtin_agents + custom_agents
    return custom_agents


@agent_router_alias.get('/workers/{worker_id}/agents')
async def list_worker_agents(worker_id: str):
    """List agent definitions for a specific worker."""
    agents = await db.db_list_agent_definitions(worker_id=worker_id)
    return agents


@agent_router_alias.post('/workers/{worker_id}/agents')
async def create_worker_agent(
    worker_id: str,
    body: AgentDefinitionCreate,
):
    """Create a custom agent definition for a worker."""
    # Verify worker exists
    worker = _registered_workers.get(worker_id) or await db.db_get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail='Worker not found')

    agent_def = {
        'id': str(uuid.uuid4()),
        'name': body.name,
        'description': body.description,
        'mode': body.mode,
        'native': False,
        'hidden': body.hidden,
        'model': body.model,
        'temperature': body.temperature,
        'top_p': body.top_p,
        'max_steps': body.max_steps,
        'system_prompt': body.system_prompt,
        'worker_id': worker_id,
    }

    ok = await db.db_upsert_agent_definition(agent_def)
    if not ok:
        raise HTTPException(status_code=500, detail='Failed to create agent definition')

    return {'success': True, 'agent': agent_def}


@agent_router_alias.get('/agents/{agent_id}')
async def get_agent_definition(agent_id: str):
    """Get a single agent definition by ID."""
    agent = await db.db_get_agent_definition(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail='Agent definition not found')
    return agent


@agent_router_alias.put('/workers/{worker_id}/agents/{agent_id}')
async def update_worker_agent(
    worker_id: str,
    agent_id: str,
    body: AgentDefinitionUpdate,
):
    """Update a custom agent definition."""
    existing = await db.db_get_agent_definition(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail='Agent definition not found')
    if existing.get('worker_id') != worker_id:
        raise HTTPException(status_code=403, detail='Agent belongs to a different worker')
    if existing.get('native'):
        raise HTTPException(status_code=400, detail='Cannot modify built-in agents')

    updates = body.model_dump(exclude_none=True)
    merged = {**existing, **updates}
    ok = await db.db_upsert_agent_definition(merged)
    if not ok:
        raise HTTPException(status_code=500, detail='Failed to update agent definition')

    return {'success': True, 'agent': merged}


@agent_router_alias.delete('/workers/{worker_id}/agents/{agent_id}')
async def delete_worker_agent(worker_id: str, agent_id: str):
    """Delete a custom agent definition."""
    existing = await db.db_get_agent_definition(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail='Agent definition not found')
    if existing.get('worker_id') != worker_id:
        raise HTTPException(status_code=403, detail='Agent belongs to a different worker')
    if existing.get('native'):
        raise HTTPException(status_code=400, detail='Cannot delete built-in agents')

    ok = await db.db_delete_agent_definition(agent_id)
    if not ok:
        raise HTTPException(status_code=500, detail='Failed to delete agent definition')

    return {'success': True}


@agent_router_alias.put('/tasks/{task_id}/status')
async def update_task_status(task_id: str, update: TaskStatusUpdate):
    """Update task status (called by workers)."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    from .agent_bridge import AgentTaskStatus

    try:
        status = AgentTaskStatus(update.status)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f'Invalid status: {update.status}'
        )

    task = await bridge.update_task_status(
        task_id=task_id,
        status=status,
        result=update.result,
        error=update.error,
        session_id=update.session_id,
        worker_id=update.worker_id,
    )

    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    # Update worker last-seen
    if update.worker_id in _registered_workers:
        _registered_workers[update.worker_id]['last_seen'] = (
            datetime.utcnow().isoformat()
        )
        await _redis_upsert_worker(_registered_workers[update.worker_id])
    else:
        # Best-effort: keep Redis mirror fresh even if this instance missed initial registration.
        redis_worker = await _redis_get_worker(update.worker_id)
        if redis_worker is not None:
            redis_worker['last_seen'] = datetime.utcnow().isoformat()
            await _redis_upsert_worker(redis_worker)

    await monitoring_service.log_message(
        agent_name='Task Manager',
        content=f"Task '{task.title}' status: {update.status}",
        message_type='system',
        metadata={
            'task_id': task_id,
            'status': update.status,
            'worker_id': update.worker_id,
            'session_id': update.session_id,
        },
    )

    return {'success': True, 'task': task.to_dict()}


class TaskOutputChunk(BaseModel):
    """Model for streaming task output."""

    worker_id: str
    output: str
    timestamp: Optional[str] = None


@agent_router_alias.post('/tasks/{task_id}/output')
async def stream_task_output(task_id: str, chunk: TaskOutputChunk):
    """Receive streaming output from a worker (called by workers)."""
    if task_id not in _task_output_streams:
        _task_output_streams[task_id] = []

    _task_output_streams[task_id].append(
        {
            'output': chunk.output,
            'timestamp': chunk.timestamp or datetime.utcnow().isoformat(),
            'worker_id': chunk.worker_id,
        }
    )

    # Keep only last 1000 lines per task
    if len(_task_output_streams[task_id]) > 1000:
        _task_output_streams[task_id] = _task_output_streams[task_id][-1000:]

    # Also broadcast to any SSE listeners
    await monitoring_service.log_message(
        agent_name='Agent Output',
        content=chunk.output,
        message_type='agent',
        metadata={
            'task_id': task_id,
            'worker_id': chunk.worker_id,
            'streaming': True,
        },
    )

    return {'success': True}


@agent_router_alias.get('/tasks/{task_id}/output')
async def get_task_output(task_id: str, since: Optional[int] = None):
    """Get streaming output for a task."""
    outputs = _task_output_streams.get(task_id, [])

    if since is not None and since < len(outputs):
        outputs = outputs[since:]

    return {
        'task_id': task_id,
        'outputs': outputs,
        'total': len(_task_output_streams.get(task_id, [])),
    }


@agent_router_alias.get('/tasks/{task_id}/output/stream')
async def stream_task_output_sse(task_id: str, request: Request):
    """SSE stream for real-time task output."""
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        last_index = 0
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            outputs = _task_output_streams.get(task_id, [])
            if len(outputs) > last_index:
                for output in outputs[last_index:]:
                    yield {
                        'event': 'output',
                        'data': json.dumps(output),
                    }
                last_index = len(outputs)

            # Check task status
            bridge = get_agent_bridge()
            if bridge:
                task = await bridge.get_task(task_id)
                if task and task.status.value in (
                    'completed',
                    'failed',
                    'cancelled',
                ):
                    yield {
                        'event': 'done',
                        'data': json.dumps({'status': task.status.value}),
                    }
                    break

            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())


@agent_router_alias.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: str):
    """Cancel a pending task."""
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    success = bridge.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail='Cannot cancel task (may already be completed or not found)',
        )

    return {'success': True, 'message': 'Task cancelled'}


# ========================================
# Task Reaper / Stuck Task Recovery
# ========================================


@agent_router_alias.get('/tasks/stuck')
async def get_stuck_tasks(
    timeout_seconds: int = 300,
):
    """
    Get list of tasks that appear to be stuck.

    A task is considered stuck if:
    - Status is 'running'
    - started_at is older than timeout_seconds

    Args:
        timeout_seconds: How long before a task is considered stuck (default: 300)
    """
    from datetime import timedelta

    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)

    async with pool.acquire() as conn:
        stuck_tasks = await conn.fetch(
            """
            SELECT id, workspace_id, title, status, priority, worker_id,
                   started_at, created_at,
                   EXTRACT(EPOCH FROM (NOW() - started_at))::int as stuck_seconds,
                   COALESCE((metadata->>'attempts')::int, 1) as attempts,
                   error
            FROM tasks
            WHERE status = 'running'
              AND started_at < $1
            ORDER BY started_at ASC
            """,
            cutoff,
        )

    return {
        'timeout_seconds': timeout_seconds,
        'count': len(stuck_tasks),
        'tasks': [dict(t) for t in stuck_tasks],
    }


@agent_router_alias.post('/tasks/stuck/recover')
async def recover_stuck_tasks():
    """
    Manually trigger recovery of stuck tasks.

    This will:
    1. Find all tasks stuck in 'running' status
    2. Requeue them for retry (if under max attempts)
    3. Mark them as failed (if max attempts exceeded)

    Returns statistics about the recovery operation.
    """
    try:
        from .task_reaper import get_task_reaper, TaskReaper

        reaper = get_task_reaper()
        if reaper is None:
            # Create a temporary reaper for manual recovery
            reaper = TaskReaper()

        stats = await reaper.recover_stuck_tasks()

        return {
            'success': True,
            'stats': stats.to_dict(),
        }
    except Exception as e:
        logger.error(f'Manual task recovery failed: {e}', exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@agent_router_alias.post('/tasks/{task_id}/requeue')
async def requeue_task(task_id: str):
    """
    Manually requeue a specific task.

    This will reset the task to 'pending' status so it can be picked up
    by a worker again. Useful for recovering a single stuck task.
    """
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    async with pool.acquire() as conn:
        # Check if task exists and is in a recoverable state
        task = await conn.fetchrow(
            'SELECT id, status, metadata FROM tasks WHERE id = $1',
            task_id,
        )

        if not task:
            raise HTTPException(status_code=404, detail='Task not found')

        if task['status'] not in ('running', 'failed'):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot requeue task with status '{task['status']}'. "
                f"Only 'running' or 'failed' tasks can be requeued.",
            )

        # Update attempt count in metadata
        import json

        metadata = task['metadata']
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        elif metadata is None:
            metadata = {}

        attempts = metadata.get('attempts', 1)
        metadata['attempts'] = attempts + 1
        metadata['manual_requeue_at'] = datetime.utcnow().isoformat()

        # Requeue the task
        await conn.execute(
            """
            UPDATE tasks SET
                status = 'pending',
                started_at = NULL,
                completed_at = NULL,
                worker_id = NULL,
                error = $2,
                metadata = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            task_id,
            f'Manually requeued (attempt {attempts + 1})',
            json.dumps(metadata),
        )

    # Notify workers
    try:
        from .worker_sse import get_worker_registry

        registry = get_worker_registry()
        if registry:
            await registry.broadcast_task_available(task_id)
    except Exception:
        pass

    return {
        'success': True,
        'task_id': task_id,
        'message': f'Task requeued for retry (attempt {attempts + 1})',
    }


@agent_router_alias.get('/reaper/health')
async def get_reaper_health():
    """Get the health status of the task reaper."""
    try:
        from .task_reaper import get_task_reaper

        reaper = get_task_reaper()
        if reaper is None:
            return {
                'status': 'not_running',
                'message': 'Task reaper is not initialized',
            }

        return {
            'status': 'healthy',
            **reaper.get_health(),
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
        }


# ========================================
# Authentication & User Session Management
# ========================================

# Import Keycloak auth service
_keycloak_auth = None


def get_keycloak_auth():
    """Get or create the Keycloak auth service instance."""
    global _keycloak_auth
    if _keycloak_auth is None:
        try:
            from .keycloak_auth import keycloak_auth

            _keycloak_auth = keycloak_auth
            logger.info('Keycloak auth service initialized')
        except Exception as e:
            logger.warning(f'Failed to initialize Keycloak auth: {e}')
            _keycloak_auth = None
    return _keycloak_auth


# Auth router
auth_router = APIRouter(prefix='/v1/auth', tags=['authentication'])


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None  # ios, macos, web, linux


class RefreshRequest(BaseModel):
    """Token refresh request model."""

    refresh_token: str


class WorkspaceAccessRequest(BaseModel):
    """Request to associate/check workspace access."""

    workspace_id: str
    role: str = 'owner'


@auth_router.post('/login')
async def login(request: LoginRequest, req: Request):
    """Authenticate user with username/password."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    device_info = {
        'device_id': request.device_id or str(uuid.uuid4()),
        'device_name': request.device_name,
        'device_type': request.device_type,
        'ip_address': req.client.host if req.client else None,
        'user_agent': req.headers.get('user-agent'),
    }

    session = await auth.authenticate_password(
        username=request.username,
        password=request.password,
        device_info=device_info,
    )

    return {
        'success': True,
        'session': session.to_dict(),
        'access_token': session.access_token,
        'refresh_token': session.refresh_token,
        'expires_at': session.expires_at.isoformat(),
    }


@auth_router.post('/refresh')
async def refresh_token(request: RefreshRequest):
    """Refresh an expired session."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    session = await auth.refresh_session(request.refresh_token)

    return {
        'success': True,
        'session': session.to_dict(),
        'access_token': session.access_token,
        'refresh_token': session.refresh_token,
        'expires_at': session.expires_at.isoformat(),
    }


@auth_router.post('/logout')
async def logout(
    session_id: Optional[str] = None, authorization: Optional[str] = None
):
    """Logout and invalidate session."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    if session_id:
        await auth.logout(session_id)

    return {'success': True, 'message': 'Logged out'}


@auth_router.get('/session')
async def get_session(session_id: str):
    """Get current session info."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    session = await auth.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404, detail='Session not found or expired'
        )

    return session.to_dict()


@auth_router.get('/sync')
async def sync_session_state(user_id: str):
    """Get synchronized state across all user devices."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    return auth.sync_session_state(user_id)


@auth_router.get('/user/{user_id}/workspaces')
async def get_user_workspaces(user_id: str):
    """Get all workspaces associated with a user."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    workspaces = auth.get_user_workspaces(user_id)
    return [c.to_dict() for c in workspaces]


@auth_router.post('/user/{user_id}/workspaces')
async def associate_user_workspace(user_id: str, request: WorkspaceAccessRequest):
    """Associate a workspace with a user."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    # Get workspace info from bridge
    bridge = get_agent_bridge()
    if bridge is None:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    workspace = bridge.get_workspace(request.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')

    association = auth.associate_workspace(
        user_id=user_id,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        workspace_path=workspace.path,
        role=request.role,
    )

    return {'success': True, 'association': association.to_dict()}


@auth_router.delete('/user/{user_id}/workspaces/{workspace_id}')
async def remove_user_workspace(user_id: str, workspace_id: str):
    """Remove a workspace association from a user."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    success = auth.remove_workspace_association(user_id, workspace_id)
    return {'success': success}


@auth_router.get('/user/{user_id}/agent-sessions')
async def get_user_agent_sessions(user_id: str):
    """Get all agent sessions for a user."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    sessions = auth.get_user_agent_sessions(user_id)
    return [s.to_dict() for s in sessions]


@auth_router.post('/user/{user_id}/agent-sessions')
async def create_agent_session(
    user_id: str,
    workspace_id: str,
    agent_type: str = 'build',
    device_id: Optional[str] = None,
):
    """Create a new agent session for a user."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    # Verify user has access to workspace
    if not auth.can_access_workspace(user_id, workspace_id):
        raise HTTPException(
            status_code=403, detail='User does not have access to this workspace'
        )

    session = auth.create_agent_session(
        user_id=user_id,
        workspace_id=workspace_id,
        agent_type=agent_type,
        device_id=device_id,
    )

    return {'success': True, 'session': session.to_dict()}


@auth_router.get('/agent-sessions/{session_id}')
async def get_agent_session(session_id: str):
    """Get an agent session by ID."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    session = auth.get_agent_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Agent session not found')

    return session.to_dict()


@auth_router.delete('/agent-sessions/{session_id}')
async def close_agent_session(session_id: str):
    """Close an agent session."""
    auth = get_keycloak_auth()
    if auth is None:
        raise HTTPException(
            status_code=503, detail='Authentication service not available'
        )

    auth.close_agent_session(session_id)
    return {'success': True, 'message': 'Session closed'}


@auth_router.get('/status')
async def auth_status():
    """Check authentication service status."""
    auth = get_keycloak_auth()

    if auth is None:
        return {
            'available': False,
            'message': 'Keycloak authentication not configured',
            'keycloak_url': None,
        }

    return {
        'available': True,
        'message': 'Keycloak authentication ready',
        'keycloak_url': auth.keycloak_url,
        'realm': auth.realm,
        'active_sessions': len(auth._sessions),
        'agent_sessions': len(auth._agent_sessions),
    }


# NextAuth Compatibility Router (for Cypress tests)
nextauth_router = APIRouter(prefix='/api/auth', tags=['nextauth'])


@nextauth_router.get('/csrf')
async def get_csrf():
    """NextAuth compatibility: Get CSRF token."""
    return {'csrfToken': 'csrf-' + str(uuid.uuid4())}


@nextauth_router.post('/signin/keycloak')
async def signin_keycloak(request: Request):
    """NextAuth compatibility: Initiate Keycloak signin."""
    auth = get_keycloak_auth()
    if not auth:
        raise HTTPException(status_code=503, detail='Auth service unavailable')

    # Construct Keycloak auth URL
    # The Cypress command expects a redirect or a location header.
    try:
        # Try to get callbackUrl from form data
        form_data = await request.form()
        callback_url = form_data.get('callbackUrl')
    except Exception:
        callback_url = None

    if not callback_url:
        callback_url = 'http://localhost:3001/api/auth/callback/keycloak'

    from urllib.parse import urlencode

    params = {
        'client_id': auth.client_id,
        'redirect_uri': callback_url,
        'response_type': 'code',
        'scope': 'openid profile email',
        'state': str(uuid.uuid4()),
    }

    auth_url = f'{auth.auth_url}?{urlencode(params)}'

    # Return 200 with the URL in the body and Location header
    # Cypress cy.request() will follow redirects if followRedirect is true (default)
    # or we can just return the URL for the test to use.
    return JSONResponse(
        status_code=200,
        content={'url': auth_url},
        headers={'Location': auth_url},
    )


@nextauth_router.get('/session')
async def get_nextauth_session(request: Request):
    """NextAuth compatibility: Get current session."""
    # Return empty to indicate no active session
    return {}


@nextauth_router.get('/callback/keycloak')
async def nextauth_callback(code: str, state: str):
    """NextAuth compatibility: Handle Keycloak callback."""
    # This would normally exchange the code for a token and set a cookie.
    # For Cypress, we can just redirect back to the app.
    return JSONResponse(
        status_code=302,
        headers={'Location': 'http://localhost:3001/dashboard'},
    )


# =============================================================================
# API Key Management Endpoints (Per-User, Vault-backed)
# =============================================================================
# These endpoints allow users to manage their LLM provider API keys through the UI.
# Keys are stored in HashiCorp Vault, scoped to the authenticated user.

from .vault_client import (
    KNOWN_PROVIDERS,
    get_user_api_key,
    set_user_api_key,
    delete_user_api_key,
    list_user_api_keys,
    get_all_user_api_keys,
    get_all_user_api_keys_with_diagnostics,
    get_worker_sync_data,
    check_vault_connection,
    test_api_key as vault_test_api_key,
)
from .keycloak_auth import (
    get_current_user as get_keycloak_user,
    require_auth,
    UserSession,
)
from .user_auth import get_current_user as get_self_service_user


@dataclass
class ApiKeyUser:
    user_id: str
    email: str = ''
    auth_source: str = 'keycloak'


_api_key_auth_scheme = HTTPBearer(auto_error=False)


async def get_current_api_key_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        _api_key_auth_scheme
    ),
) -> Optional[ApiKeyUser]:
    if not credentials:
        return None

    keycloak_user = await get_keycloak_user(credentials)
    if keycloak_user:
        return ApiKeyUser(
            user_id=keycloak_user.user_id,
            email=keycloak_user.email,
            auth_source='keycloak',
        )

    try:
        self_service_user = await get_self_service_user(credentials)
    except HTTPException:
        self_service_user = None

    if self_service_user:
        user_id = self_service_user.get('id') or self_service_user.get(
            'user_id'
        )
        if user_id:
            return ApiKeyUser(
                user_id=user_id,
                email=self_service_user.get('email', ''),
                auth_source='self-service',
            )

    return None


class APIKeyCreate(BaseModel):
    """Request model for creating/updating an API key."""

    provider_id: str  # e.g., 'anthropic', 'openai', 'minimax-m2'
    api_key: str
    provider_name: Optional[str] = None  # Display name
    base_url: Optional[str] = None  # Custom base URL for provider


@agent_router_alias.get('/providers')
async def list_providers():
    """List all known LLM providers with their configuration."""
    return {
        'providers': [
            {
                'id': pid,
                'name': pconfig.get('name', pid),
                'description': pconfig.get('description', ''),
                'npm': pconfig.get('npm'),
                'has_base_url': 'base_url' in pconfig,
                'requires_base_url': pconfig.get('requires_base_url', False),
                'has_models': 'models' in pconfig,
                'auth_type': pconfig.get('auth_type', 'api'),
            }
            for pid, pconfig in KNOWN_PROVIDERS.items()
        ]
    }


@agent_router_alias.get('/vault/status')
async def vault_status(
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Check Vault connectivity status."""
    return await check_vault_connection(user_id=user.user_id if user else None)


@agent_router_alias.get('/api-keys')
async def list_api_keys(
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """List all configured API keys for the current user (without exposing full keys)."""
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')

    all_keys, vault_error, vault_error_status = (
        await get_all_user_api_keys_with_diagnostics(user.user_id)
    )

    response = {
        'keys': [
            {
                'provider_id': pid,
                'provider_name': data.get('provider_name')
                or KNOWN_PROVIDERS.get(pid, {}).get('name', pid),
                'key_preview': f'...{data["api_key"][-4:]}'
                if data.get('api_key') and len(data['api_key']) > 4
                else '****',
                'updated_at': data.get('updated_at', ''),
                'has_base_url': 'base_url' in data,
            }
            for pid, data in all_keys.items()
        ],
        'user_id': user.user_id,
    }

    if vault_error:
        response['vault_error'] = vault_error
    if vault_error_status is not None:
        response['vault_error_status'] = vault_error_status

    return response


@agent_router_alias.post('/api-keys')
async def create_or_update_api_key(
    key_data: APIKeyCreate,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Create or update an API key for a provider for the current user."""
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')

    if not key_data.provider_id or not key_data.api_key:
        raise HTTPException(
            status_code=400, detail='provider_id and api_key are required'
        )

    # Get provider name from known providers or use provided name
    provider_name = key_data.provider_name or KNOWN_PROVIDERS.get(
        key_data.provider_id, {}
    ).get('name', key_data.provider_id)

    result = await set_user_api_key(
        user_id=user.user_id,
        provider_id=key_data.provider_id,
        api_key=key_data.api_key,
        provider_name=provider_name,
        base_url=key_data.base_url,
    )

    if not result:
        raise HTTPException(
            status_code=500, detail='Failed to save API key to Vault'
        )

    return {
        'success': True,
        'provider_id': key_data.provider_id,
        'provider_name': provider_name,
        'message': f'API key for {provider_name} saved successfully',
    }


@agent_router_alias.delete('/api-keys/{provider_id}')
async def delete_api_key(
    provider_id: str,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Delete an API key for a provider for the current user."""
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')

    result = await delete_user_api_key(user.user_id, provider_id)
    if not result:
        raise HTTPException(
            status_code=404, detail=f'API key for {provider_id} not found'
        )

    return {'success': True, 'message': f'API key for {provider_id} deleted'}


@agent_router_alias.get('/api-keys/sync')
async def get_api_keys_for_sync(
    user_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """
    Get all API keys for worker sync.

    If user_id is provided (worker request), returns that user's keys.
    Otherwise, returns the authenticated user's keys.

    Workers should authenticate and provide the user_id for the workspace owner.
    """
    # Determine which user's keys to fetch
    target_user_id = user_id
    if not target_user_id and user:
        target_user_id = user.user_id

    if not target_user_id:
        raise HTTPException(
            status_code=400,
            detail='user_id required or authentication required',
        )

    # TODO: In production, verify worker has permission to access this user's keys
    # This could be done by checking if the worker is assigned to a workspace owned by the user

    sync_data = await get_worker_sync_data(target_user_id)
    return sync_data


@agent_router_alias.post('/api-keys/test')
async def test_api_key_endpoint(
    key_data: APIKeyCreate,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Test an API key by making a simple request to the provider."""
    # Allow testing without auth (just testing the key itself)
    result = await vault_test_api_key(key_data.provider_id, key_data.api_key)
    return result


# =============================================================================
# Workspace Storage Endpoints (MinIO Upload/Download)
# =============================================================================
# These endpoints allow uploading/downloading workspace tarballs to MinIO
# and syncing from workers.


def _get_minio_client():
    """Get or create a MinIO client for workspace storage."""
    if not MINIO_ENDPOINT or not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        return None

    try:
        from minio import Minio

        endpoint = (
            MINIO_ENDPOINT.replace('http://', '').replace('https://', '')
            if MINIO_ENDPOINT
            else ''
        )
        client = Minio(
            endpoint,
            access_key=MINIO_ACCESS_KEY or '',
            secret_key=MINIO_SECRET_KEY or '',
            secure=MINIO_SECURE,
        )
        return client
    except ImportError:
        logger.debug('minio package not installed')
        return None
    except Exception as e:
        logger.warning(f'Failed to create MinIO client: {e}')
        return None


async def _verify_workspace_ownership(
    workspace_id: str, tenant_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Verify that a workspace exists and optionally belongs to a tenant.

    Returns the workspace dict if valid, None otherwise.
    """
    workspace = await db.db_get_workspace(workspace_id)
    if not workspace:
        return None

    # If RLS/tenant enforcement is enabled and tenant_id provided, check ownership
    if tenant_id and db.RLS_ENABLED:
        workspace_tenant = workspace.get('tenant_id')
        if workspace_tenant and workspace_tenant != tenant_id:
            return None

    return workspace


class WorkspaceSyncRequest(BaseModel):
    """Request model for workspace sync from worker."""

    size_bytes: int
    files_changed: int = 0
    worker_id: Optional[str] = None


class WorkerStatusResponse(BaseModel):
    """Response model for worker status."""

    status: str  # pending, creating, ready, failed, not_found
    url: Optional[str] = None
    created_at: Optional[str] = None
    last_activity: Optional[str] = None
    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None
    error_message: Optional[str] = None


@agent_router_alias.post('/workspaces/{workspace_id}/upload')
async def upload_workspace_tarball(
    workspace_id: str,
    request: Request,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Upload a workspace tarball to MinIO.

    This endpoint accepts multipart/form-data with a file field containing
    the workspace tarball (typically .tar.gz).

    The file is stored at workspaces/{workspace_id}.tar.gz in the configured
    MinIO bucket.

    Args:
        workspace_id: The workspace ID to upload to
        request: The FastAPI request (for multipart parsing)
        user: Optional authenticated user for tenant validation

    Returns:
        JSON with minio_path and size_bytes
    """
    # Verify workspace exists
    tenant_id = user.user_id if user else None
    workspace = await _verify_workspace_ownership(workspace_id, tenant_id)
    if not workspace:
        raise HTTPException(
            status_code=404, detail=f'Workspace {workspace_id} not found'
        )

    # Get MinIO client
    minio_client = _get_minio_client()
    if not minio_client:
        raise HTTPException(
            status_code=503,
            detail='MinIO storage not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY.',
        )

    # Parse multipart form data
    from fastapi import UploadFile, File
    import aiofiles

    try:
        form = await request.form()
        file = form.get('file')
        if not file:
            raise HTTPException(
                status_code=400,
                detail='No file provided. Include a "file" field in multipart form data.',
            )

        # Read file content
        content = await file.read()
        size_bytes = len(content)

        # Validate size (max 500MB)
        max_size = 500 * 1024 * 1024
        if size_bytes > max_size:
            raise HTTPException(
                status_code=413,
                detail=f'File too large. Maximum size is {max_size // (1024 * 1024)}MB.',
            )

        # Determine file path in MinIO
        minio_path = f'workspaces/{workspace_id}.tar.gz'

        # Ensure bucket exists
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)

        # Upload to MinIO
        minio_client.put_object(
            MINIO_BUCKET,
            minio_path,
            io.BytesIO(content),
            length=size_bytes,
            content_type='application/gzip',
        )

        # Update workspace record with minio_path
        pool = await db.get_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE workspaces
                    SET minio_path = $2, last_sync_at = NOW(), updated_at = NOW()
                    WHERE id = $1
                    """,
                    workspace_id,
                    minio_path,
                )

        logger.info(
            f'Uploaded workspace {workspace_id} to MinIO: {minio_path} ({size_bytes} bytes)'
        )

        return {
            'minio_path': minio_path,
            'size_bytes': size_bytes,
            'bucket': MINIO_BUCKET,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to upload workspace {workspace_id}: {e}')
        raise HTTPException(status_code=500, detail=f'Upload failed: {str(e)}')


@agent_router_alias.get('/workspaces/{workspace_id}/download')
async def download_workspace_tarball(
    workspace_id: str,
    stream: bool = False,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Get a presigned URL or stream the workspace tarball from MinIO.

    By default, returns a presigned URL that expires in 1 hour.
    Set stream=true to stream the file directly.

    Args:
        workspace_id: The workspace ID to download
        stream: If True, stream the file directly instead of returning a URL
        user: Optional authenticated user for tenant validation

    Returns:
        JSON with presigned url and expiry, or streams the file directly
    """
    # Verify workspace exists
    tenant_id = user.user_id if user else None
    workspace = await _verify_workspace_ownership(workspace_id, tenant_id)
    if not workspace:
        raise HTTPException(
            status_code=404, detail=f'Workspace {workspace_id} not found'
        )

    # Get MinIO client
    minio_client = _get_minio_client()
    if not minio_client:
        raise HTTPException(
            status_code=503,
            detail='MinIO storage not configured',
        )

    # Determine file path - prefer stored path, fall back to convention
    minio_path = workspace.get('minio_path') or f'workspaces/{workspace_id}.tar.gz'

    # Check if file exists
    try:
        minio_client.stat_object(MINIO_BUCKET, minio_path)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f'Workspace tarball not found at {minio_path}',
        )

    if stream:
        # Stream the file directly
        try:
            response = minio_client.get_object(MINIO_BUCKET, minio_path)

            def iterfile():
                try:
                    for chunk in response.stream(32 * 1024):
                        yield chunk
                finally:
                    response.close()
                    response.release_conn()

            return StreamingResponse(
                iterfile(),
                media_type='application/gzip',
                headers={
                    'Content-Disposition': f'attachment; filename="{workspace_id}.tar.gz"'
                },
            )
        except Exception as e:
            logger.error(f'Failed to stream workspace {workspace_id}: {e}')
            raise HTTPException(
                status_code=500, detail=f'Download failed: {str(e)}'
            )
    else:
        # Generate presigned URL
        try:
            expires_in = 3600  # 1 hour
            url = minio_client.presigned_get_object(
                MINIO_BUCKET,
                minio_path,
                expires=timedelta(seconds=expires_in),
            )

            return {
                'url': url,
                'expires_in': expires_in,
                'minio_path': minio_path,
            }
        except Exception as e:
            logger.error(
                f'Failed to generate presigned URL for {workspace_id}: {e}'
            )
            raise HTTPException(
                status_code=500, detail=f'Failed to generate URL: {str(e)}'
            )


@agent_router_alias.post('/workspaces/{workspace_id}/sync')
async def sync_workspace_from_worker(
    workspace_id: str,
    sync_request: WorkspaceSyncRequest,
):
    """Receive sync notification from a worker (webhook).

    Workers call this endpoint after syncing their local workspace to MinIO.
    This updates the last_sync_at timestamp in the database.

    Args:
        workspace_id: The workspace ID being synced
        sync_request: Sync details (size_bytes, files_changed)

    Returns:
        JSON acknowledgment
    """
    # Verify workspace exists (no tenant validation for worker sync)
    workspace = await db.db_get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=404, detail=f'Workspace {workspace_id} not found'
        )

    # Update the workspace record
    pool = await db.get_pool()
    if not pool:
        raise HTTPException(status_code=503, detail='Database not available')

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE workspaces
                SET last_sync_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                workspace_id,
            )

        logger.info(
            f'Workspace {workspace_id} synced from worker {sync_request.worker_id}: '
            f'{sync_request.size_bytes} bytes, {sync_request.files_changed} files changed'
        )

        # Update worker last-seen if provided
        if sync_request.worker_id:
            await db.db_update_worker_heartbeat(sync_request.worker_id)

        return {
            'acknowledged': True,
            'workspace_id': workspace_id,
            'size_bytes': sync_request.size_bytes,
            'files_changed': sync_request.files_changed,
            'synced_at': datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f'Failed to update sync status for {workspace_id}: {e}')
        raise HTTPException(status_code=500, detail=f'Sync failed: {str(e)}')


@agent_router_alias.get('/sessions/{session_id}/worker-status')
async def get_session_worker_status(
    session_id: str,
    user: Optional[ApiKeyUser] = Depends(get_current_api_key_user),
):
    """Get Knative worker status for a session.

    Returns the status of the Knative service worker associated with
    this session, including URL, creation time, and last activity.

    Args:
        session_id: The session ID to check

    Returns:
        WorkerStatusResponse with status details
    """
    # First check the sessions table for knative metadata
    session = await db.db_get_session(session_id)

    if session:
        # Check if we have Knative service info stored
        knative_service_name = session.get('knative_service_name')
        worker_status = session.get('worker_status', 'pending')
        last_activity = session.get('last_activity_at')

        if not knative_service_name:
            # Session exists but no Knative worker
            return WorkerStatusResponse(
                status='pending',
                workspace_id=session.get('workspace_id'),
                created_at=session.get('created_at'),
                last_activity=last_activity,
            )

    # Try to get status from Knative spawner
    try:
        from .knative_spawner import get_worker_status, KNATIVE_ENABLED

        if not KNATIVE_ENABLED:
            return WorkerStatusResponse(
                status='disabled',
                error_message='Knative spawning is not enabled',
            )

        worker_info = await get_worker_status(session_id)

        return WorkerStatusResponse(
            status=worker_info.status.value,
            url=worker_info.url,
            created_at=worker_info.created_at.isoformat()
            if worker_info.created_at
            else None,
            last_activity=worker_info.last_activity_at.isoformat()
            if hasattr(worker_info, 'last_activity_at')
            and worker_info.last_activity_at
            else None,
            tenant_id=worker_info.tenant_id,
            workspace_id=worker_info.workspace_id,
            error_message=worker_info.error_message,
        )

    except ImportError:
        # Knative spawner not available
        logger.debug('Knative spawner not available')

        # Return status from session if available
        if session:
            return WorkerStatusResponse(
                status=session.get('worker_status', 'unknown'),
                workspace_id=session.get('workspace_id'),
                created_at=session.get('created_at'),
                last_activity=session.get('last_activity_at'),
                error_message='Knative spawner module not available',
            )

        raise HTTPException(
            status_code=404, detail=f'Session {session_id} not found'
        )

    except Exception as e:
        logger.error(
            f'Failed to get worker status for session {session_id}: {e}'
        )
        raise HTTPException(
            status_code=500, detail=f'Failed to get worker status: {str(e)}'
        )


AVAILABLE_VOICES = [
    {'id': 'puck', 'name': 'Puck', 'description': 'Friendly and approachable'},
    {'id': 'charon', 'name': 'Charon', 'description': 'Deep and authoritative'},
    {'id': 'kore', 'name': 'Kore', 'description': 'Warm and conversational'},
    {'id': 'fenrir', 'name': 'Fenrir', 'description': 'Energetic and dynamic'},
    {'id': 'aoede', 'name': 'Aoede', 'description': 'Calm and soothing'},
]


class VoiceSessionRequest(BaseModel):
    workspace_id: Optional[str] = None
    session_id: Optional[str] = None
    voice: str = 'puck'
    mode: str = 'chat'
    playback_style: str = 'verbatim'
    user_id: Optional[str] = None


class VoiceSessionResponse(BaseModel):
    room_name: str
    access_token: str
    livekit_url: str
    voice: str
    mode: str
    playback_style: str
    expires_at: str


voice_router = APIRouter(prefix='/v1/voice', tags=['voice'])


_livekit_bridge_instance = None


def get_livekit_bridge():
    """Get or create the cached LiveKit bridge singleton."""
    global _livekit_bridge_instance
    if _livekit_bridge_instance is not None:
        return _livekit_bridge_instance
    try:
        from .livekit_bridge import create_livekit_bridge

        bridge = create_livekit_bridge()
        if bridge:
            logger.info('LiveKit bridge initialized for voice API')
            _livekit_bridge_instance = bridge
        else:
            logger.info(
                'LiveKit bridge not configured - voice features disabled'
            )
        return bridge
    except Exception as e:
        logger.warning(f'Failed to initialize LiveKit bridge: {e}')
        return None


@voice_router.on_event('shutdown')
async def voice_shutdown():
    """Close LiveKit bridge resources on shutdown."""
    global _livekit_bridge_instance
    if _livekit_bridge_instance is not None:
        await _livekit_bridge_instance.close()
        _livekit_bridge_instance = None


@voice_router.get('/voices')
async def list_voices():
    """List available voice options."""
    return {'voices': AVAILABLE_VOICES}


@voice_router.post('/sessions', response_model=VoiceSessionResponse)
async def create_voice_session(request: VoiceSessionRequest):
    """Start a new voice session."""
    bridge = get_livekit_bridge()
    if not bridge:
        raise HTTPException(
            status_code=503,
            detail='LiveKit not available - voice sessions require LiveKit configuration',
        )

    if request.voice not in [v['id'] for v in AVAILABLE_VOICES]:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid voice: {request.voice}. Available voices: {[v["id"] for v in AVAILABLE_VOICES]}',
        )

    if request.mode not in ['chat', 'playback']:
        raise HTTPException(
            status_code=400, detail='Mode must be "chat" or "playback"'
        )

    if request.playback_style not in ['verbatim', 'summary']:
        raise HTTPException(
            status_code=400,
            detail='Playback style must be "verbatim" or "summary"',
        )

    room_name = f'voice-{uuid.uuid4().hex[:12]}'

    metadata = {
        'voice': request.voice,
        'mode': request.mode,
        'playback_style': request.playback_style,
        'workspace_id': request.workspace_id,
        'session_id': request.session_id,
        'user_id': request.user_id,
    }

    try:
        await bridge.create_room(room_name=room_name, metadata=metadata)
    except Exception as e:
        logger.error(f'Failed to create LiveKit room: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create voice room: {str(e)}'
        )

    voice_agent_name = os.getenv(
        'LIVEKIT_VOICE_AGENT_NAME',
        os.getenv('VOICE_AGENT_NAME', 'codetether-voice-agent'),
    )
    try:
        dispatch = await bridge.dispatch_agent(
            room_name=room_name,
            agent_name=voice_agent_name,
            metadata=json.dumps(metadata),
        )
        logger.info(
            f'Created voice dispatch for room {room_name} '
            f'(agent={voice_agent_name}, dispatch_id={dispatch.get("id")})'
        )
    except Exception as e:
        logger.error(
            f'Failed to create voice dispatch for room {room_name}: {e}'
        )
        try:
            await bridge.delete_room(room_name)
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail='Failed to dispatch voice agent. '
            'Ensure voice worker is online and LIVEKIT_VOICE_AGENT_NAME matches.',
        )

    user_identity = request.user_id or f'user-{uuid.uuid4().hex[:8]}'

    try:
        access_token = bridge.mint_access_token(
            identity=user_identity,
            room_name=room_name,
            a2a_role='participant',
            metadata=json.dumps(metadata),
            ttl_minutes=60,
        )
    except Exception as e:
        logger.error(f'Failed to mint access token: {e}')
        try:
            await bridge.delete_room(room_name)
        except:
            pass
        raise HTTPException(
            status_code=500, detail=f'Failed to generate access token: {str(e)}'
        )

    expires_at = datetime.now() + timedelta(minutes=60)

    logger.info(f'Created voice session {room_name} with voice {request.voice}')

    return VoiceSessionResponse(
        room_name=room_name,
        access_token=access_token,
        livekit_url=bridge.public_url,
        voice=request.voice,
        mode=request.mode,
        playback_style=request.playback_style,
        expires_at=expires_at.isoformat(),
    )


@voice_router.get('/sessions/{room_name}')
async def get_voice_session(room_name: str, user_id: Optional[str] = None):
    """Get session info for a voice session.

    If user_id is provided, a new access token will be generated for reconnection.
    """
    bridge = get_livekit_bridge()
    if not bridge:
        raise HTTPException(status_code=503, detail='LiveKit not available')

    room_info = await bridge.get_room_info(room_name)
    if not room_info:
        raise HTTPException(
            status_code=404, detail=f'Room {room_name} not found'
        )

    metadata_str = room_info.get('metadata', '')
    metadata = {}
    if metadata_str:
        try:
            metadata = (
                json.loads(metadata_str)
                if isinstance(metadata_str, str)
                else metadata_str
            )
        except:
            pass

    response = {
        'room_name': room_name,
        'status': 'active',
        'num_participants': room_info.get('num_participants', 0),
        'created_at': room_info.get('creation_time'),
        'voice': metadata.get('voice'),
        'mode': metadata.get('mode'),
        'playback_style': metadata.get('playback_style'),
        'workspace_id': metadata.get('workspace_id'),
        'session_id': metadata.get('session_id'),
        'livekit_url': bridge.public_url,
    }

    if user_id:
        try:
            access_token = bridge.mint_access_token(
                identity=user_id,
                room_name=room_name,
                a2a_role='participant',
                metadata=json.dumps(metadata),
                ttl_minutes=60,
            )
            response['access_token'] = access_token
            response['expires_at'] = (
                datetime.now() + timedelta(minutes=60)
            ).isoformat()
        except Exception as e:
            logger.warning(f'Failed to mint access token for reconnection: {e}')

    return response


@voice_router.delete('/sessions/{room_name}')
async def delete_voice_session(room_name: str):
    """End a voice session."""
    bridge = get_livekit_bridge()
    if not bridge:
        raise HTTPException(status_code=503, detail='LiveKit not available')

    success = await bridge.delete_room(room_name)
    if not success:
        raise HTTPException(
            status_code=500, detail=f'Failed to delete room {room_name}'
        )

    logger.info(f'Deleted voice session {room_name}')
    return {'success': True, 'room_name': room_name}


@voice_router.get('/sessions/{room_name}/state')
async def get_voice_session_state(room_name: str):
    """Get the current agent state for a voice session.

    Returns the agent's current state: idle, listening, thinking, speaking, or error.
    This endpoint is used by voice clients to update their UI with the agent's status.

    The state is determined by checking:
    1. If the room exists and has metadata with a session_id
    2. If there's an active LiveKit connection
    3. Falls back to 'idle' if state cannot be determined
    """
    bridge = get_livekit_bridge()
    if not bridge:
        raise HTTPException(status_code=503, detail='LiveKit not available')

    try:
        room_info = await bridge.get_room_info(room_name)
        if not room_info:
            raise HTTPException(
                status_code=404, detail=f'Room {room_name} not found'
            )

        metadata_str = room_info.get('metadata', '')
        metadata = {}
        if metadata_str:
            try:
                metadata = (
                    json.loads(metadata_str)
                    if isinstance(metadata_str, str)
                    else metadata_str
                )
            except:
                pass

        session_id = metadata.get('session_id')

        if not session_id:
            return 'idle'

        num_participants = room_info.get('num_participants', 0)

        if num_participants == 0:
            return 'idle'

        if num_participants > 1:
            return 'speaking'

        return 'listening'

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f'Failed to get session state for {room_name}: {e}')
        return 'idle'


# Export the monitoring service, routers and helpers
__all__ = [
    'monitor_router',
    'agent_router',
    'agent_router_alias',  # backward-compat alias for agent_router
    'voice_router',
    'auth_router',
    'nextauth_router',
    'monitoring_service',
    'log_agent_message',
    'get_agent_bridge',
    'get_keycloak_auth',
]
