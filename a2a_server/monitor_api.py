"""
Monitoring API endpoints for A2A Server.

Provides real-time monitoring, logging, and human intervention capabilities.
Supports multiple storage backends:
- SQLite for persistent storage (default if writable)
- MinIO/S3 for cloud-native deployments
- In-memory fallback when no persistent storage is available
"""

import asyncio
import json
import logging
import sqlite3
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
import os
import io
import tempfile

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

        # Try SQLite
        if self._init_sqlite():
            print(f'✓ Using SQLite storage at {self.db_path}')
            return

        # Fallback to in-memory
        print('⚠ Using in-memory storage (data will be lost on restart)')

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
        # Use in-memory fallback if no persistent storage
        if not self._use_sqlite and not self._use_minio:
            messages = list(self._in_memory_messages)
            if message_type:
                messages = [
                    m for m in messages if m.get('type') == message_type
                ]
            if agent_name:
                messages = [
                    m for m in messages if m.get('agent_name') == agent_name
                ]
            # Return as MonitorMessage objects
            result = []
            for m in messages[-limit:]:
                if isinstance(m, dict):
                    result.append(
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
                else:
                    result.append(m)
            return result

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
        # Use in-memory count if no persistent storage
        if not self._use_sqlite and not self._use_minio:
            if message_type:
                return len(
                    [
                        m
                        for m in self._in_memory_messages
                        if m.get('type') == message_type
                    ]
                )
            return self._in_memory_stats.get(
                'total_messages', len(self._in_memory_messages)
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
        # Use in-memory stats if no persistent storage
        if not self._use_sqlite and not self._use_minio:
            return self._in_memory_stats.copy()

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
        # Use in-memory search if no persistent storage
        if not self._use_sqlite and not self._use_minio:
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
        logger.info(f'Broadcasting agent status to {len(self.subscribers)} subscribers: {agent_id} - {data["name"]}')

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
        logger.info(f'Registered agent {agent_name} ({agent_id}), total active: {len(self.active_agents)}')

        # Broadcast to UI subscribers
        await self.broadcast_agent_status(agent_id, self.active_agents[agent_id])

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
# OpenCode Integration - Trigger AI agents on registered codebases
# ============================================================================

# Import OpenCode bridge (lazy load to avoid circular imports)
_opencode_bridge = None

def get_opencode_bridge():
    """Get or create the OpenCode bridge instance."""
    global _opencode_bridge
    if _opencode_bridge is None:
        try:
            from .opencode_bridge import OpenCodeBridge
            _opencode_bridge = OpenCodeBridge()
            logger.info("OpenCode bridge initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenCode bridge: {e}")
            _opencode_bridge = None
    return _opencode_bridge


class CodebaseRegistration(BaseModel):
    """Request model for registering a codebase."""
    name: str
    path: str
    description: str = ""
    agent_config: Dict[str, Any] = {}
    worker_id: Optional[str] = None  # Associate with a specific worker


class AgentTrigger(BaseModel):
    """Request model for triggering an agent."""
    prompt: str
    agent: str = "build"
    model: Optional[str] = None
    files: List[str] = []
    metadata: Dict[str, Any] = {}


class AgentMessage(BaseModel):
    """Request model for sending a message to an agent."""
    message: str
    agent: Optional[str] = None


class AgentTaskCreate(BaseModel):
    """Request model for creating an agent task."""
    title: str
    prompt: str
    agent_type: str = "build"
    priority: int = 0
    metadata: Dict[str, Any] = {}


class WatchModeConfig(BaseModel):
    """Request model for configuring watch mode."""
    interval: int = 5  # Seconds between task checks


# OpenCode API Router
opencode_router = APIRouter(prefix='/v1/opencode', tags=['opencode'])


@opencode_router.get('/status')
async def opencode_status():
    """Check OpenCode integration status."""
    bridge = get_opencode_bridge()
    if bridge is None:
        return {
            "available": False,
            "message": "OpenCode bridge not available",
            "opencode_binary": None,
        }

    return {
        "available": True,
        "message": "OpenCode integration ready",
        "opencode_binary": bridge.opencode_bin,
        "registered_codebases": len(bridge.list_codebases()),
        "auto_start": bridge.auto_start,
    }


@opencode_router.get('/models')
async def list_models():
    """List available AI models from OpenCode configuration."""
    import os
    import json
    
    models = []
    
    # Default models always available
    default_models = [
        # Anthropic
        {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "Anthropic"},
        {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
        {"id": "anthropic/claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "Anthropic"},
        # OpenAI
        {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "openai/o1", "name": "o1", "provider": "OpenAI"},
        {"id": "openai/o1-mini", "name": "o1 Mini", "provider": "OpenAI"},
        {"id": "openai/o3-mini", "name": "o3 Mini", "provider": "OpenAI"},
        # Google
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
        {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "Google"},
        {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
        # DeepSeek
        {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "provider": "DeepSeek"},
        {"id": "deepseek/deepseek-reasoner", "name": "DeepSeek Reasoner", "provider": "DeepSeek"},
        # xAI
        {"id": "xai/grok-2", "name": "Grok 2", "provider": "xAI"},
        {"id": "xai/grok-3", "name": "Grok 3", "provider": "xAI"},
    ]
    
    # Try to read OpenCode config for custom providers
    config_paths = [
        os.path.expanduser("~/.config/opencode/opencode.json"),
        os.path.expanduser("~/.opencode.json"),
        "/app/.config/opencode/opencode.json",
    ]
    
    custom_models = []
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    
                providers = config.get("provider", {})
                for provider_id, provider_config in providers.items():
                    provider_name = provider_config.get("name", provider_id)
                    provider_models = provider_config.get("models", {})
                    
                    for model_id, model_config in provider_models.items():
                        custom_models.append({
                            "id": f"{provider_id}/{model_id}",
                            "name": model_config.get("name", model_id),
                            "provider": provider_name,
                            "custom": True,
                            "capabilities": {
                                "reasoning": model_config.get("reasoning", False),
                                "attachment": model_config.get("attachment", False),
                                "tool_call": model_config.get("tool_call", False),
                            }
                        })
            except Exception as e:
                logger.warning(f"Failed to read OpenCode config from {config_path}: {e}")
    
    # Custom models first, then defaults
    return {"models": custom_models + default_models, "default": custom_models[0]["id"] if custom_models else "anthropic/claude-sonnet-4-20250514"}


@opencode_router.get('/codebases')
async def list_codebases():
    """List all registered codebases."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    return [cb.to_dict() for cb in bridge.list_codebases()]


@opencode_router.post('/codebases')
async def register_codebase(registration: CodebaseRegistration):
    """Register a new codebase for agent work."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    try:
        codebase = bridge.register_codebase(
            name=registration.name,
            path=registration.path,
            description=registration.description,
            agent_config=registration.agent_config,
            worker_id=registration.worker_id,
        )

        # Log the registration
        worker_info = f" (worker: {registration.worker_id})" if registration.worker_id else ""
        await monitoring_service.log_message(
            agent_name="OpenCode Bridge",
            content=f"Registered codebase: {registration.name} at {registration.path}{worker_info}",
            message_type="system",
            metadata={"codebase_id": codebase.id, "path": registration.path, "worker_id": registration.worker_id},
        )

        return {"success": True, "codebase": codebase.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@opencode_router.get('/codebases/{codebase_id}')
async def get_codebase(codebase_id: str):
    """Get details of a registered codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    return codebase.to_dict()


@opencode_router.delete('/codebases/{codebase_id}')
async def unregister_codebase(codebase_id: str):
    """Unregister a codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    success = bridge.unregister_codebase(codebase_id)

    if success:
        await monitoring_service.log_message(
            agent_name="OpenCode Bridge",
            content=f"Unregistered codebase: {codebase.name}",
            message_type="system",
            metadata={"codebase_id": codebase_id},
        )

    return {"success": success}


@opencode_router.post('/codebases/{codebase_id}/trigger')
async def trigger_agent(codebase_id: str, trigger: AgentTrigger):
    """Trigger an OpenCode agent to work on a codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    # Create trigger request
    from .opencode_bridge import AgentTriggerRequest
    request = AgentTriggerRequest(
        codebase_id=codebase_id,
        prompt=trigger.prompt,
        agent=trigger.agent,
        model=trigger.model,
        files=trigger.files,
        metadata=trigger.metadata,
    )

    # Trigger the agent
    response = await bridge.trigger_agent(request)

    # Log the trigger
    if response.success:
        await monitoring_service.log_message(
            agent_name="OpenCode Bridge",
            content=f"Triggered agent '{trigger.agent}' on {codebase.name}: {trigger.prompt[:100]}...",
            message_type="system",
            metadata={
                "codebase_id": codebase_id,
                "agent": trigger.agent,
                "session_id": response.session_id,
            },
        )

    return response.to_dict()


@opencode_router.post('/codebases/{codebase_id}/message')
async def send_agent_message(codebase_id: str, msg: AgentMessage):
    """Send a follow-up message to an active agent session."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    response = await bridge.send_message(
        codebase_id=codebase_id,
        message=msg.message,
        agent=msg.agent,
    )

    return response.to_dict()


@opencode_router.post('/codebases/{codebase_id}/interrupt')
async def interrupt_agent(codebase_id: str):
    """Interrupt the current agent task."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    success = await bridge.interrupt_agent(codebase_id)

    if success:
        codebase = bridge.get_codebase(codebase_id)
        await monitoring_service.log_message(
            agent_name="OpenCode Bridge",
            content=f"Interrupted agent on {codebase.name if codebase else codebase_id}",
            message_type="system",
            metadata={"codebase_id": codebase_id},
        )

    return {"success": success}


@opencode_router.post('/codebases/{codebase_id}/stop')
async def stop_agent(codebase_id: str):
    """Stop the OpenCode agent for a codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    success = await bridge.stop_agent(codebase_id)

    if success:
        codebase = bridge.get_codebase(codebase_id)
        await monitoring_service.log_message(
            agent_name="OpenCode Bridge",
            content=f"Stopped agent for {codebase.name if codebase else codebase_id}",
            message_type="system",
            metadata={"codebase_id": codebase_id},
        )

    return {"success": success}


@opencode_router.get('/codebases/{codebase_id}/status')
async def get_agent_status(codebase_id: str):
    """Get the current status of an agent."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    status = await bridge.get_agent_status(codebase_id)
    if not status:
        raise HTTPException(status_code=404, detail="Codebase not found")

    return status


@opencode_router.get('/codebases/{codebase_id}/events')
async def stream_agent_events(codebase_id: str, request: Request):
    """Stream real-time events from an OpenCode agent session via SSE.

    Events include:
    - message.updated: Full message updates
    - message.part.updated: Streaming text/tool updates
    - session.status: Status changes (idle, running, etc.)
    - Tool execution states (pending, running, completed, error)
    """
    import aiohttp

    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge._codebases.get(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    # For remote workers, check if there are pending tasks and return task-based events
    if codebase.worker_id and not codebase.opencode_port:
        async def remote_event_generator():
            """Stream events for remote worker codebases from completed tasks."""
            yield f"event: connected\ndata: {json.dumps({'codebase_id': codebase_id, 'status': 'connected', 'remote': True, 'worker_id': codebase.worker_id})}\n\n"

            # Check for recent completed tasks and stream their results
            all_tasks = bridge.list_tasks(codebase_id=codebase_id)
            tasks = [{'status': t.status.value, 'result': t.result, 'title': t.title} for t in all_tasks[:10]]
            for task in tasks:
                if task.get('status') == 'completed' and task.get('result'):
                    try:
                        # Parse and stream stored task results as events
                        result_data = json.loads(task['result']) if isinstance(task['result'], str) else task['result']
                        if isinstance(result_data, list):
                            for event in result_data:
                                event_type = event.get('type', 'message')
                                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
                        else:
                            yield f"event: message\ndata: {json.dumps(result_data)}\n\n"
                    except (json.JSONDecodeError, TypeError):
                        yield f"event: message\ndata: {json.dumps({'type': 'text', 'content': str(task['result'])})}\n\n"

            yield f"event: status\ndata: {json.dumps({'status': 'idle', 'message': 'Remote worker codebase - results from completed tasks'})}\n\n"

        return StreamingResponse(
            remote_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    if not codebase.opencode_port:
        raise HTTPException(status_code=400, detail="Agent not running")

    async def event_generator():
        """Proxy events from OpenCode SSE endpoint."""
        base_url = f"http://localhost:{codebase.opencode_port}"

        yield f"event: connected\ndata: {json.dumps({'codebase_id': codebase_id, 'status': 'connected'})}\n\n"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/event",
                    params={"directory": codebase.path},
                    timeout=aiohttp.ClientTimeout(total=None),
                ) as resp:
                    if resp.status != 200:
                        yield f"event: error\ndata: {json.dumps({'error': 'Failed to connect to OpenCode'})}\n\n"
                        return

                    async for line in resp.content:
                        if await request.is_disconnected():
                            break

                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data:'):
                            try:
                                event_data = json.loads(line_text[5:].strip())
                                # Transform and forward the event
                                transformed = transform_opencode_event(event_data, codebase_id)
                                if transformed:
                                    yield f"event: {transformed['event_type']}\ndata: {json.dumps(transformed)}\n\n"
                            except json.JSONDecodeError:
                                pass
                        elif line_text:
                            yield f"data: {line_text}\n\n"

        except asyncio.CancelledError:
            logger.info(f"Event stream cancelled for {codebase_id}")
        except Exception as e:
            logger.error(f"Error streaming events: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def transform_opencode_event(event: Dict[str, Any], codebase_id: str) -> Optional[Dict[str, Any]]:
    """Transform OpenCode events into UI-friendly format."""
    event_type = event.get('type', '')
    properties = event.get('properties', {})

    # Message updates
    if event_type == 'message.updated':
        info = properties.get('info', {})
        return {
            'event_type': 'message',
            'codebase_id': codebase_id,
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
            'codebase_id': codebase_id,
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
            'codebase_id': codebase_id,
            'session_id': properties.get('sessionID'),
            'status': properties.get('status'),
            'agent': properties.get('agent'),
        }

    if event_type == 'session.idle':
        return {
            'event_type': 'idle',
            'codebase_id': codebase_id,
            'session_id': properties.get('sessionID'),
        }

    # File edits
    if event_type == 'file.edited':
        return {
            'event_type': 'file_edit',
            'codebase_id': codebase_id,
            'path': properties.get('path'),
            'hash': properties.get('hash'),
        }

    # Command execution
    if event_type == 'command.executed':
        return {
            'event_type': 'command',
            'codebase_id': codebase_id,
            'command': properties.get('command'),
            'exit_code': properties.get('exitCode'),
            'output': properties.get('output'),
        }

    # LSP diagnostics
    if event_type == 'lsp.diagnostics':
        return {
            'event_type': 'diagnostics',
            'codebase_id': codebase_id,
            'path': properties.get('path'),
            'diagnostics': properties.get('diagnostics'),
        }

    # Todo updates
    if event_type == 'todo.updated':
        return {
            'event_type': 'todo',
            'codebase_id': codebase_id,
            'todos': properties.get('info'),
        }

    # Default: pass through with generic type
    return {
        'event_type': event_type.replace('.', '_'),
        'codebase_id': codebase_id,
        'raw': event,
    }


@opencode_router.get('/codebases/{codebase_id}/messages')
async def get_session_messages(codebase_id: str, limit: int = 50):
    """Get recent messages from an agent session."""
    import aiohttp

    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge._codebases.get(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    if not codebase.opencode_port or not codebase.session_id:
        return {"messages": [], "session_id": None}

    try:
        base_url = f"http://localhost:{codebase.opencode_port}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/session/{codebase.session_id}/message",
                params={"limit": limit, "directory": codebase.path},
            ) as resp:
                if resp.status == 200:
                    messages = await resp.json()
                    return {"messages": messages, "session_id": codebase.session_id}
                return {"messages": [], "error": f"Status {resp.status}"}
    except Exception as e:
        return {"messages": [], "error": str(e)}


# ========================================
# Agent Task Management Endpoints
# ========================================

@opencode_router.get('/tasks')
async def list_all_tasks(
    codebase_id: Optional[str] = None,
    status: Optional[str] = None,
):
    """List all agent tasks, optionally filtered by codebase or status."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    from .opencode_bridge import AgentTaskStatus

    task_status = None
    if status:
        try:
            task_status = AgentTaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = bridge.list_tasks(codebase_id=codebase_id, status=task_status)
    return [t.to_dict() for t in tasks]


@opencode_router.post('/codebases/{codebase_id}/tasks')
async def create_agent_task(codebase_id: str, task_data: AgentTaskCreate):
    """Create a new task for an agent to work on."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    task = bridge.create_task(
        codebase_id=codebase_id,
        title=task_data.title,
        prompt=task_data.prompt,
        agent_type=task_data.agent_type,
        priority=task_data.priority,
        metadata=task_data.metadata,
    )

    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")

    # Log the task creation
    await monitoring_service.log_message(
        agent_name="OpenCode Bridge",
        content=f"Task created: {task_data.title}",
        message_type="system",
        metadata={"task_id": task.id, "codebase_id": codebase_id},
    )

    return {"success": True, "task": task.to_dict()}


@opencode_router.get('/codebases/{codebase_id}/tasks')
async def list_codebase_tasks(codebase_id: str, status: Optional[str] = None):
    """List all tasks for a specific codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    from .opencode_bridge import AgentTaskStatus

    task_status = None
    if status:
        try:
            task_status = AgentTaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = bridge.list_tasks(codebase_id=codebase_id, status=task_status)
    return [t.to_dict() for t in tasks]


@opencode_router.get('/tasks/{task_id}')
async def get_task(task_id: str):
    """Get details of a specific task."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    task = bridge.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()


@opencode_router.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: str):
    """Cancel a pending task."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    success = bridge.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task (may already be running or completed)")

    return {"success": True, "message": "Task cancelled"}


# ========================================
# Watch Mode Endpoints (Persistent Workers)
# ========================================

@opencode_router.post('/codebases/{codebase_id}/watch/start')
async def start_watch_mode(codebase_id: str, config: Optional[WatchModeConfig] = None):
    """
    Start watch mode for a codebase - agent will automatically process tasks.

    The agent will poll for pending tasks and execute them in order of priority.
    """
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    interval = config.interval if config else 5

    success = await bridge.start_watch_mode(codebase_id, interval=interval)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start watch mode")

    await monitoring_service.log_message(
        agent_name="OpenCode Bridge",
        content=f"Watch mode started for {codebase.name} (interval: {interval}s)",
        message_type="system",
        metadata={"codebase_id": codebase_id, "interval": interval},
    )

    return {
        "success": True,
        "message": f"Watch mode started for {codebase.name}",
        "interval": interval,
    }


@opencode_router.post('/codebases/{codebase_id}/watch/stop')
async def stop_watch_mode(codebase_id: str):
    """Stop watch mode for a codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    success = await bridge.stop_watch_mode(codebase_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop watch mode")

    await monitoring_service.log_message(
        agent_name="OpenCode Bridge",
        content=f"Watch mode stopped for {codebase.name}",
        message_type="system",
        metadata={"codebase_id": codebase_id},
    )

    return {"success": True, "message": f"Watch mode stopped for {codebase.name}"}


@opencode_router.get('/codebases/{codebase_id}/watch/status')
async def get_watch_status(codebase_id: str):
    """Get watch mode status for a codebase."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    codebase = bridge.get_codebase(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    pending_tasks = bridge.list_tasks(codebase_id=codebase_id, status=bridge._tasks.__class__.PENDING if hasattr(bridge._tasks, '__class__') else None)
    from .opencode_bridge import AgentTaskStatus
    pending_count = len(bridge.list_tasks(codebase_id=codebase_id, status=AgentTaskStatus.PENDING))
    running_count = len(bridge.list_tasks(codebase_id=codebase_id, status=AgentTaskStatus.RUNNING))

    return {
        "codebase_id": codebase_id,
        "name": codebase.name,
        "watch_mode": codebase.watch_mode,
        "status": codebase.status.value,
        "interval": codebase.watch_interval,
        "pending_tasks": pending_count,
        "running_tasks": running_count,
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


class TaskStatusUpdate(BaseModel):
    """Task status update from worker."""
    status: str
    worker_id: str
    result: Optional[str] = None
    error: Optional[str] = None


@opencode_router.post('/workers/register')
async def register_worker(registration: WorkerRegistration):
    """Register a worker with the A2A server."""
    worker_info = {
        "worker_id": registration.worker_id,
        "name": registration.name,
        "capabilities": registration.capabilities,
        "hostname": registration.hostname,
        "registered_at": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "status": "active",
    }

    _registered_workers[registration.worker_id] = worker_info

    logger.info(f"Worker registered: {registration.name} (ID: {registration.worker_id})")

    await monitoring_service.log_message(
        agent_name="Worker Registry",
        content=f"Worker '{registration.name}' connected from {registration.hostname}",
        message_type="system",
        metadata=worker_info,
    )

    return {"success": True, "worker": worker_info}


@opencode_router.post('/workers/{worker_id}/unregister')
async def unregister_worker(worker_id: str):
    """Unregister a worker."""
    if worker_id in _registered_workers:
        worker_info = _registered_workers.pop(worker_id)
        logger.info(f"Worker unregistered: {worker_info.get('name')} (ID: {worker_id})")

        await monitoring_service.log_message(
            agent_name="Worker Registry",
            content=f"Worker '{worker_info.get('name')}' disconnected",
            message_type="system",
        )

        return {"success": True, "message": "Worker unregistered"}

    return {"success": False, "message": "Worker not found"}


@opencode_router.get('/workers')
async def list_workers():
    """List all registered workers."""
    return list(_registered_workers.values())


@opencode_router.get('/workers/{worker_id}')
async def get_worker(worker_id: str):
    """Get worker details."""
    if worker_id in _registered_workers:
        return _registered_workers[worker_id]
    raise HTTPException(status_code=404, detail="Worker not found")


@opencode_router.post('/workers/{worker_id}/heartbeat')
async def worker_heartbeat(worker_id: str):
    """Update worker last-seen timestamp."""
    if worker_id in _registered_workers:
        _registered_workers[worker_id]["last_seen"] = datetime.utcnow().isoformat()
        return {"success": True}
    raise HTTPException(status_code=404, detail="Worker not found")


@opencode_router.put('/tasks/{task_id}/status')
async def update_task_status(task_id: str, update: TaskStatusUpdate):
    """Update task status (called by workers)."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    from .opencode_bridge import AgentTaskStatus

    try:
        status = AgentTaskStatus(update.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {update.status}")

    task = bridge.update_task_status(
        task_id=task_id,
        status=status,
        result=update.result,
        error=update.error,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update worker last-seen
    if update.worker_id in _registered_workers:
        _registered_workers[update.worker_id]["last_seen"] = datetime.utcnow().isoformat()

    await monitoring_service.log_message(
        agent_name="Task Manager",
        content=f"Task '{task.title}' status: {update.status}",
        message_type="system",
        metadata={"task_id": task_id, "status": update.status, "worker_id": update.worker_id},
    )

    return {"success": True, "task": task.to_dict()}


@opencode_router.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: str):
    """Cancel a pending task."""
    bridge = get_opencode_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="OpenCode bridge not available")

    success = bridge.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel task (may already be completed or not found)")

    return {"success": True, "message": "Task cancelled"}


# Export the monitoring service, routers and helpers
__all__ = ['monitor_router', 'opencode_router', 'monitoring_service', 'log_agent_message', 'get_opencode_bridge']
