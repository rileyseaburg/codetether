"""
OpenCode Bridge - Integrates OpenCode AI coding agent with A2A Server

This module provides a bridge between the A2A protocol server and OpenCode,
allowing web UI triggers to start AI agents working on registered codebases.
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

import aiohttp

logger = logging.getLogger(__name__)

# Default database path - use env var or /tmp fallback
DEFAULT_OPENCODE_DB_PATH = os.environ.get(
    'OPENCODE_DB_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'opencode.db'),
)


class AgentStatus(str, Enum):
    """Status of an OpenCode agent instance."""
    IDLE = "idle"
    RUNNING = "running"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"
    WATCHING = "watching"  # Agent is watching for tasks


class AgentTaskStatus(str, Enum):
    """Status of an agent task."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """Represents a task assigned to an agent."""
    id: str
    codebase_id: str
    title: str
    prompt: str
    agent_type: str = "build"  # build, plan, general, explore
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    priority: int = 0  # Higher = more urgent
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "codebase_id": self.codebase_id,
            "title": self.title,
            "prompt": self.prompt,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass
class RegisteredCodebase:
    """Represents a codebase registered for agent work."""
    id: str
    name: str
    path: str
    description: str = ""
    registered_at: datetime = field(default_factory=datetime.utcnow)
    agent_config: Dict[str, Any] = field(default_factory=dict)
    last_triggered: Optional[datetime] = None
    status: AgentStatus = AgentStatus.IDLE
    opencode_port: Optional[int] = None
    session_id: Optional[str] = None
    watch_mode: bool = False  # Whether agent is in watch mode
    watch_interval: int = 5  # Seconds between task checks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "registered_at": self.registered_at.isoformat(),
            "agent_config": self.agent_config,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "status": self.status.value,
            "opencode_port": self.opencode_port,
            "session_id": self.session_id,
            "watch_mode": self.watch_mode,
            "watch_interval": self.watch_interval,
        }


@dataclass
class AgentTriggerRequest:
    """Request to trigger an agent on a codebase."""
    codebase_id: str
    prompt: str
    agent: str = "build"  # build, plan, general, explore
    model: Optional[str] = None
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTriggerResponse:
    """Response from triggering an agent."""
    success: bool
    session_id: Optional[str] = None
    message: str = ""
    codebase_id: Optional[str] = None
    agent: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "session_id": self.session_id,
            "message": self.message,
            "codebase_id": self.codebase_id,
            "agent": self.agent,
            "error": self.error,
        }


class OpenCodeBridge:
    """
    Bridge between A2A Server and OpenCode.

    Manages codebase registrations, task queues, and triggers OpenCode agents
    through its HTTP API. Supports watch mode where agents poll for tasks.
    """

    def __init__(
        self,
        opencode_bin: Optional[str] = None,
        default_port: int = 9777,
        auto_start: bool = True,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the OpenCode bridge.

        Args:
            opencode_bin: Path to opencode binary (auto-detected if None)
            default_port: Default port for OpenCode server
            auto_start: Whether to auto-start OpenCode when triggering
            db_path: Path to SQLite database for persistence
        """
        self.opencode_bin = opencode_bin or self._find_opencode_binary()
        self.default_port = default_port
        self.auto_start = auto_start

        # Database persistence
        self.db_path = db_path or DEFAULT_OPENCODE_DB_PATH
        self._db_lock = threading.Lock()
        self._local = threading.local()
        self._use_sqlite = False

        # Initialize SQLite database
        self._init_database()

        # In-memory caches (populated from DB)
        self._codebases: Dict[str, RegisteredCodebase] = {}
        self._tasks: Dict[str, AgentTask] = {}  # task_id -> task
        self._codebase_tasks: Dict[str, List[str]] = {}  # codebase_id -> [task_ids]

        # Load persisted data
        self._load_from_database()

        # Watch mode background tasks
        self._watch_tasks: Dict[str, asyncio.Task] = {}  # codebase_id -> asyncio task

        # Active OpenCode processes
        self._processes: Dict[str, subprocess.Popen] = {}

        # Port allocations
        self._port_allocations: Dict[str, int] = {}
        self._next_port = default_port

        # Event callbacks
        self._on_status_change: List[Callable] = []
        self._on_message: List[Callable] = []
        self._on_task_update: List[Callable] = []

        # HTTP session for API calls
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(f"OpenCode bridge initialized with binary: {self.opencode_bin}")
        logger.info(f"Using database: {self.db_path} (sqlite={self._use_sqlite})")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_database(self) -> bool:
        """Initialize SQLite database schema."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Codebases table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS codebases (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    registered_at TEXT NOT NULL,
                    agent_config TEXT DEFAULT '{}',
                    last_triggered TEXT,
                    status TEXT DEFAULT 'idle',
                    opencode_port INTEGER,
                    session_id TEXT,
                    watch_mode INTEGER DEFAULT 0,
                    watch_interval INTEGER DEFAULT 5
                )
            ''')

            # Tasks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    codebase_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    agent_type TEXT DEFAULT 'build',
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    session_id TEXT,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (codebase_id) REFERENCES codebases(id)
                )
            ''')

            # Index for faster task queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_codebase_status
                ON tasks(codebase_id, status)
            ''')

            conn.commit()
            conn.close()

            self._use_sqlite = True
            logger.info(f"✓ SQLite database initialized at {self.db_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to initialize SQLite: {e}, using in-memory only")
            self._use_sqlite = False
            return False

    def _load_from_database(self):
        """Load codebases and tasks from database into memory."""
        if not self._use_sqlite:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Load codebases
            cursor.execute('SELECT * FROM codebases')
            for row in cursor.fetchall():
                codebase = RegisteredCodebase(
                    id=row['id'],
                    name=row['name'],
                    path=row['path'],
                    description=row['description'] or '',
                    registered_at=datetime.fromisoformat(row['registered_at']),
                    agent_config=json.loads(row['agent_config'] or '{}'),
                    last_triggered=datetime.fromisoformat(row['last_triggered']) if row['last_triggered'] else None,
                    status=AgentStatus(row['status']) if row['status'] else AgentStatus.IDLE,
                    opencode_port=row['opencode_port'],
                    session_id=row['session_id'],
                    watch_mode=bool(row['watch_mode']),
                    watch_interval=row['watch_interval'] or 5,
                )
                self._codebases[codebase.id] = codebase

            # Load tasks
            cursor.execute('SELECT * FROM tasks ORDER BY priority DESC, created_at ASC')
            for row in cursor.fetchall():
                task = AgentTask(
                    id=row['id'],
                    codebase_id=row['codebase_id'],
                    title=row['title'],
                    prompt=row['prompt'],
                    agent_type=row['agent_type'] or 'build',
                    status=AgentTaskStatus(row['status']) if row['status'] else AgentTaskStatus.PENDING,
                    priority=row['priority'] or 0,
                    created_at=datetime.fromisoformat(row['created_at']),
                    started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    result=row['result'],
                    error=row['error'],
                    session_id=row['session_id'],
                    metadata=json.loads(row['metadata'] or '{}'),
                )
                self._tasks[task.id] = task

                # Build codebase tasks index
                if task.codebase_id not in self._codebase_tasks:
                    self._codebase_tasks[task.codebase_id] = []
                self._codebase_tasks[task.codebase_id].append(task.id)

            logger.info(f"Loaded {len(self._codebases)} codebases and {len(self._tasks)} tasks from database")

        except Exception as e:
            logger.error(f"Failed to load from database: {e}")

    def _save_codebase(self, codebase: RegisteredCodebase):
        """Save or update a codebase in the database."""
        if not self._use_sqlite:
            return

        try:
            with self._db_lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO codebases
                    (id, name, path, description, registered_at, agent_config,
                     last_triggered, status, opencode_port, session_id, watch_mode, watch_interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    codebase.id,
                    codebase.name,
                    codebase.path,
                    codebase.description,
                    codebase.registered_at.isoformat(),
                    json.dumps(codebase.agent_config),
                    codebase.last_triggered.isoformat() if codebase.last_triggered else None,
                    codebase.status.value,
                    codebase.opencode_port,
                    codebase.session_id,
                    1 if codebase.watch_mode else 0,
                    codebase.watch_interval,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save codebase: {e}")

    def _delete_codebase(self, codebase_id: str):
        """Delete a codebase from the database."""
        if not self._use_sqlite:
            return

        try:
            with self._db_lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM codebases WHERE id = ?', (codebase_id,))
                cursor.execute('DELETE FROM tasks WHERE codebase_id = ?', (codebase_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete codebase: {e}")

    def _save_task(self, task: AgentTask):
        """Save or update a task in the database."""
        if not self._use_sqlite:
            return

        try:
            with self._db_lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO tasks
                    (id, codebase_id, title, prompt, agent_type, status, priority,
                     created_at, started_at, completed_at, result, error, session_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task.id,
                    task.codebase_id,
                    task.title,
                    task.prompt,
                    task.agent_type,
                    task.status.value,
                    task.priority,
                    task.created_at.isoformat(),
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.result,
                    task.error,
                    task.session_id,
                    json.dumps(task.metadata),
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save task: {e}")

    def _update_codebase_status(self, codebase: RegisteredCodebase, status: AgentStatus):
        """Update codebase status and persist to database."""
        codebase.status = status
        self._save_codebase(codebase)

    def _find_opencode_binary(self) -> str:
        """Find the opencode binary in common locations."""
        # Check common locations
        locations = [
            # Local project
            str(Path(__file__).parent.parent / "opencode" / "packages" / "opencode" / "bin" / "opencode"),
            # System paths
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
            # User paths
            str(Path.home() / ".local" / "bin" / "opencode"),
            str(Path.home() / "bin" / "opencode"),
            str(Path.home() / ".opencode" / "bin" / "opencode"),
            # npm/bun global
            str(Path.home() / ".bun" / "bin" / "opencode"),
            str(Path.home() / ".npm-global" / "bin" / "opencode"),
        ]

        for loc in locations:
            if Path(loc).exists() and os.access(loc, os.X_OK):
                return loc

        # Try which command
        try:
            result = subprocess.run(["which", "opencode"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback to just "opencode" (assume in PATH)
        return "opencode"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close the bridge and cleanup resources."""
        # Stop all running processes
        for codebase_id in list(self._processes.keys()):
            await self.stop_agent(codebase_id)

        # Close HTTP session
        if self._session and not self._session.closed:
            await self._session.close()

    def register_codebase(
        self,
        name: str,
        path: str,
        description: str = "",
        agent_config: Optional[Dict[str, Any]] = None,
    ) -> RegisteredCodebase:
        """
        Register a codebase for agent work.

        Args:
            name: Display name for the codebase
            path: Absolute path to the codebase directory
            description: Optional description
            agent_config: Optional OpenCode agent configuration

        Returns:
            The registered codebase entry
        """
        # Validate path
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            raise ValueError(f"Codebase path does not exist: {path}")

        # Generate ID
        codebase_id = str(uuid.uuid4())[:8]

        codebase = RegisteredCodebase(
            id=codebase_id,
            name=name,
            path=path,
            description=description,
            agent_config=agent_config or {},
        )

        self._codebases[codebase_id] = codebase
        self._save_codebase(codebase)  # Persist to database
        logger.info(f"Registered codebase: {name} ({codebase_id}) at {path}")

        return codebase

    def unregister_codebase(self, codebase_id: str) -> bool:
        """Remove a codebase from the registry."""
        if codebase_id in self._codebases:
            # Stop any running agent
            if codebase_id in self._processes:
                asyncio.create_task(self.stop_agent(codebase_id))

            del self._codebases[codebase_id]
            self._delete_codebase(codebase_id)  # Remove from database
            logger.info(f"Unregistered codebase: {codebase_id}")
            return True
        return False

    def get_codebase(self, codebase_id: str) -> Optional[RegisteredCodebase]:
        """Get a registered codebase by ID."""
        return self._codebases.get(codebase_id)

    def list_codebases(self) -> List[RegisteredCodebase]:
        """List all registered codebases."""
        return list(self._codebases.values())

    def _allocate_port(self, codebase_id: str) -> int:
        """Allocate a port for an OpenCode instance."""
        if codebase_id in self._port_allocations:
            return self._port_allocations[codebase_id]

        port = self._next_port
        self._port_allocations[codebase_id] = port
        self._next_port += 1
        return port

    async def _start_opencode_server(self, codebase: RegisteredCodebase) -> int:
        """
        Start an OpenCode server for a codebase.

        Returns the port number.
        """
        port = self._allocate_port(codebase.id)

        # Build command
        cmd = [
            self.opencode_bin,
            "--port", str(port),
            "--no-tui",
        ]

        logger.info(f"Starting OpenCode server for {codebase.name} on port {port}")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            # Start process in the codebase directory
            process = subprocess.Popen(
                cmd,
                cwd=codebase.path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "NO_COLOR": "1"},
            )

            self._processes[codebase.id] = process
            codebase.opencode_port = port
            self._update_codebase_status(codebase, AgentStatus.RUNNING)

            # Wait a moment for server to start
            await asyncio.sleep(2)

            # Verify server is running
            if process.poll() is not None:
                # Process exited
                stderr = process.stderr.read().decode() if process.stderr else ""
                raise RuntimeError(f"OpenCode server failed to start: {stderr}")

            logger.info(f"OpenCode server started successfully on port {port}")
            return port

        except Exception as e:
            logger.error(f"Failed to start OpenCode server: {e}")
            self._update_codebase_status(codebase, AgentStatus.ERROR)
            raise

    async def stop_agent(self, codebase_id: str) -> bool:
        """Stop a running OpenCode agent."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return False

        process = self._processes.get(codebase_id)
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

            del self._processes[codebase_id]

        self._update_codebase_status(codebase, AgentStatus.STOPPED)
        codebase.opencode_port = None

        # Free port allocation
        if codebase_id in self._port_allocations:
            del self._port_allocations[codebase_id]

        logger.info(f"Stopped OpenCode agent for {codebase.name}")
        return True

    async def trigger_agent(
        self,
        request: AgentTriggerRequest,
    ) -> AgentTriggerResponse:
        """
        Trigger an OpenCode agent to work on a codebase.

        Args:
            request: The trigger request with prompt and configuration

        Returns:
            Response with session ID and status
        """
        codebase = self._codebases.get(request.codebase_id)
        if not codebase:
            return AgentTriggerResponse(
                success=False,
                error=f"Codebase not found: {request.codebase_id}",
            )

        try:
            # Ensure OpenCode server is running
            if not codebase.opencode_port or codebase.status != AgentStatus.RUNNING:
                if self.auto_start:
                    await self._start_opencode_server(codebase)
                else:
                    return AgentTriggerResponse(
                        success=False,
                        error="OpenCode server not running and auto_start is disabled",
                    )

            # Build API URL
            base_url = f"http://localhost:{codebase.opencode_port}"

            session = await self._get_session()

            # Create a new session
            async with session.post(f"{base_url}/session") as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Failed to create session: {await resp.text()}")
                session_data = await resp.json()
                session_id = session_data.get("id")

            codebase.session_id = session_id
            codebase.last_triggered = datetime.utcnow()
            self._update_codebase_status(codebase, AgentStatus.BUSY)

            # Build prompt parts
            parts = [{"type": "text", "text": request.prompt}]

            # Add file references if specified
            for file_path in request.files:
                full_path = os.path.join(codebase.path, file_path)
                if os.path.exists(full_path):
                    parts.append({
                        "type": "file",
                        "url": f"file://{full_path}",
                        "filename": file_path,
                        "mime": "text/plain",
                    })

            # Trigger prompt
            prompt_payload = {
                "sessionID": session_id,
                "parts": parts,
                "agent": request.agent,
            }

            if request.model:
                parts_model = request.model.split("/")
                if len(parts_model) == 2:
                    prompt_payload["model"] = {
                        "providerID": parts_model[0],
                        "modelID": parts_model[1],
                    }

            async with session.post(
                f"{base_url}/session/{session_id}/prompt",
                json=prompt_payload,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Failed to send prompt: {await resp.text()}")

            # Notify callbacks
            await self._notify_status_change(codebase)

            logger.info(f"Triggered agent {request.agent} on {codebase.name} (session: {session_id})")

            return AgentTriggerResponse(
                success=True,
                session_id=session_id,
                message=f"Agent '{request.agent}' triggered successfully",
                codebase_id=codebase.id,
                agent=request.agent,
            )

        except Exception as e:
            logger.error(f"Failed to trigger agent: {e}")
            self._update_codebase_status(codebase, AgentStatus.ERROR)
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=codebase.id,
            )

    async def get_agent_status(self, codebase_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an agent."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return None

        result = codebase.to_dict()

        # If running, try to get more info from OpenCode API
        if codebase.opencode_port and codebase.session_id:
            try:
                session = await self._get_session()
                base_url = f"http://localhost:{codebase.opencode_port}"

                async with session.get(
                    f"{base_url}/session/{codebase.session_id}/message",
                    params={"limit": 10},
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        result["recent_messages"] = messages

            except Exception as e:
                logger.debug(f"Could not fetch session info: {e}")

        return result

    async def send_message(
        self,
        codebase_id: str,
        message: str,
        agent: Optional[str] = None,
    ) -> AgentTriggerResponse:
        """Send an additional message to an active agent session."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return AgentTriggerResponse(
                success=False,
                error=f"Codebase not found: {codebase_id}",
            )

        if not codebase.session_id or not codebase.opencode_port:
            return AgentTriggerResponse(
                success=False,
                error="No active session for this codebase",
            )

        try:
            session = await self._get_session()
            base_url = f"http://localhost:{codebase.opencode_port}"

            payload = {
                "sessionID": codebase.session_id,
                "parts": [{"type": "text", "text": message}],
            }

            if agent:
                payload["agent"] = agent

            async with session.post(
                f"{base_url}/session/{codebase.session_id}/prompt",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Failed to send message: {await resp.text()}")

            self._update_codebase_status(codebase, AgentStatus.BUSY)
            codebase.last_triggered = datetime.utcnow()

            return AgentTriggerResponse(
                success=True,
                session_id=codebase.session_id,
                message="Message sent successfully",
                codebase_id=codebase.id,
            )

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return AgentTriggerResponse(
                success=False,
                error=str(e),
                codebase_id=codebase.id,
            )

    async def interrupt_agent(self, codebase_id: str) -> bool:
        """Interrupt the current agent task."""
        codebase = self._codebases.get(codebase_id)
        if not codebase or not codebase.session_id or not codebase.opencode_port:
            return False

        try:
            session = await self._get_session()
            base_url = f"http://localhost:{codebase.opencode_port}"

            async with session.post(
                f"{base_url}/session/{codebase.session_id}/interrupt"
            ) as resp:
                if resp.status == 200:
                    self._update_codebase_status(codebase, AgentStatus.RUNNING)
                    logger.info(f"Interrupted agent for {codebase.name}")
                    return True

        except Exception as e:
            logger.error(f"Failed to interrupt agent: {e}")

        return False

    def on_status_change(self, callback: Callable):
        """Register a callback for status changes."""
        self._on_status_change.append(callback)

    def on_message(self, callback: Callable):
        """Register a callback for agent messages."""
        self._on_message.append(callback)

    async def _notify_status_change(self, codebase: RegisteredCodebase):
        """Notify registered callbacks of status change."""
        for callback in self._on_status_change:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(codebase)
                else:
                    callback(codebase)
            except Exception as e:
                logger.error(f"Error in status change callback: {e}")

    # ========================================
    # Task Management
    # ========================================

    def create_task(
        self,
        codebase_id: str,
        title: str,
        prompt: str,
        agent_type: str = "build",
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentTask]:
        """Create a new task for an agent."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            logger.error(f"Cannot create task: codebase {codebase_id} not found")
            return None

        task_id = str(uuid.uuid4())
        task = AgentTask(
            id=task_id,
            codebase_id=codebase_id,
            title=title,
            prompt=prompt,
            agent_type=agent_type,
            priority=priority,
            metadata=metadata or {},
        )

        self._tasks[task_id] = task

        # Add to codebase task list
        if codebase_id not in self._codebase_tasks:
            self._codebase_tasks[codebase_id] = []
        self._codebase_tasks[codebase_id].append(task_id)

        # Persist to database
        self._save_task(task)

        logger.info(f"Created task {task_id} for {codebase.name}: {title}")

        # Notify callbacks
        asyncio.create_task(self._notify_task_update(task))

        return task

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        codebase_id: Optional[str] = None,
        status: Optional[AgentTaskStatus] = None,
    ) -> List[AgentTask]:
        """List tasks, optionally filtered by codebase or status."""
        tasks = list(self._tasks.values())

        if codebase_id:
            tasks = [t for t in tasks if t.codebase_id == codebase_id]

        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by priority (desc) then created_at (asc)
        tasks.sort(key=lambda t: (-t.priority, t.created_at))

        return tasks

    def get_next_pending_task(self, codebase_id: str) -> Optional[AgentTask]:
        """Get the next pending task for a codebase."""
        pending = self.list_tasks(codebase_id=codebase_id, status=AgentTaskStatus.PENDING)
        return pending[0] if pending else None

    def update_task_status(
        self,
        task_id: str,
        status: AgentTaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[AgentTask]:
        """Update task status."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.status = status

        if status == AgentTaskStatus.RUNNING:
            task.started_at = datetime.utcnow()
        elif status in (AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED, AgentTaskStatus.CANCELLED):
            task.completed_at = datetime.utcnow()

        if result:
            task.result = result
        if error:
            task.error = error

        # Persist to database
        self._save_task(task)

        asyncio.create_task(self._notify_task_update(task))

        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status not in (AgentTaskStatus.PENDING, AgentTaskStatus.ASSIGNED):
            return False

        task.status = AgentTaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()

        # Persist to database
        self._save_task(task)

        asyncio.create_task(self._notify_task_update(task))

        return True

    def on_task_update(self, callback: Callable):
        """Register a callback for task updates."""
        self._on_task_update.append(callback)

    async def _notify_task_update(self, task: AgentTask):
        """Notify registered callbacks of task update."""
        for callback in self._on_task_update:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f"Error in task update callback: {e}")

    # ========================================
    # Watch Mode (Persistent Agent Workers)
    # ========================================

    async def start_watch_mode(self, codebase_id: str, interval: int = 5) -> bool:
        """
        Start watch mode for a codebase - agent will poll for and execute tasks.

        Args:
            codebase_id: ID of the codebase
            interval: Seconds between task checks

        Returns:
            True if watch mode started successfully
        """
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            logger.error(f"Cannot start watch mode: codebase {codebase_id} not found")
            return False

        if codebase_id in self._watch_tasks:
            logger.warning(f"Watch mode already running for {codebase.name}")
            return True

        # Start the OpenCode server if not running
        if not codebase.opencode_port or codebase.status in (AgentStatus.IDLE, AgentStatus.STOPPED):
            try:
                await self._start_opencode_server(codebase)
            except Exception as e:
                logger.error(f"Failed to start OpenCode server for watch mode: {e}")
                return False

        codebase.watch_mode = True
        codebase.watch_interval = interval
        self._update_codebase_status(codebase, AgentStatus.WATCHING)

        # Start background task
        watch_task = asyncio.create_task(self._watch_loop(codebase_id))
        self._watch_tasks[codebase_id] = watch_task

        logger.info(f"Started watch mode for {codebase.name} (interval: {interval}s)")
        await self._notify_status_change(codebase)

        return True

    async def stop_watch_mode(self, codebase_id: str) -> bool:
        """Stop watch mode for a codebase."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return False

        # Cancel watch task
        watch_task = self._watch_tasks.get(codebase_id)
        if watch_task:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
            del self._watch_tasks[codebase_id]

        codebase.watch_mode = False
        self._update_codebase_status(codebase, AgentStatus.RUNNING if codebase.opencode_port else AgentStatus.IDLE)

        logger.info(f"Stopped watch mode for {codebase.name}")
        await self._notify_status_change(codebase)

        return True

    async def _watch_loop(self, codebase_id: str):
        """Background loop that checks for and executes tasks."""
        codebase = self._codebases.get(codebase_id)
        if not codebase:
            return

        logger.info(f"Watch loop started for {codebase.name}")

        try:
            while True:
                # Check for pending tasks
                task = self.get_next_pending_task(codebase_id)

                if task:
                    logger.info(f"Watch loop found task: {task.title}")
                    await self._execute_task(task)

                # Wait before next check
                await asyncio.sleep(codebase.watch_interval)

        except asyncio.CancelledError:
            logger.info(f"Watch loop cancelled for {codebase.name}")
            raise
        except Exception as e:
            logger.error(f"Watch loop error for {codebase.name}: {e}")
            self._update_codebase_status(codebase, AgentStatus.ERROR)

    async def _execute_task(self, task: AgentTask):
        """Execute a task using the OpenCode agent."""
        codebase = self._codebases.get(task.codebase_id)
        if not codebase:
            task.status = AgentTaskStatus.FAILED
            task.error = "Codebase not found"
            return

        # Update task status
        task.status = AgentTaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await self._notify_task_update(task)

        # Update codebase status
        self._update_codebase_status(codebase, AgentStatus.BUSY)
        await self._notify_status_change(codebase)

        try:
            # Create trigger request
            request = AgentTriggerRequest(
                codebase_id=task.codebase_id,
                prompt=task.prompt,
                agent=task.agent_type,
                metadata=task.metadata,
            )

            # Trigger the agent
            response = await self.trigger_agent(request)

            if response.success:
                task.session_id = response.session_id

                # Wait for agent to finish (poll status)
                await self._wait_for_agent_completion(task, codebase)

            else:
                task.status = AgentTaskStatus.FAILED
                task.error = response.error
                task.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            task.status = AgentTaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()

        finally:
            # Restore codebase status if in watch mode
            if codebase.watch_mode:
                self._update_codebase_status(codebase, AgentStatus.WATCHING)
            else:
                self._update_codebase_status(codebase, AgentStatus.RUNNING)

            await self._notify_status_change(codebase)
            await self._notify_task_update(task)

    async def _wait_for_agent_completion(self, task: AgentTask, codebase: RegisteredCodebase, timeout: int = 600):
        """Wait for an agent to complete its work."""
        if not codebase.opencode_port or not task.session_id:
            return

        base_url = f"http://localhost:{codebase.opencode_port}"
        session = await self._get_session()

        start_time = datetime.utcnow()

        while True:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                task.status = AgentTaskStatus.FAILED
                task.error = "Timeout waiting for agent completion"
                task.completed_at = datetime.utcnow()
                return

            try:
                # Check session status
                async with session.get(
                    f"{base_url}/session/{task.session_id}",
                    params={"directory": codebase.path},
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get("status", {})

                        # Check if agent is idle (completed)
                        if status.get("idle", False) or status.get("status") == "idle":
                            task.status = AgentTaskStatus.COMPLETED
                            task.completed_at = datetime.utcnow()

                            # Get last message as result
                            async with session.get(
                                f"{base_url}/session/{task.session_id}/message",
                                params={"limit": 1, "directory": codebase.path},
                            ) as msg_resp:
                                if msg_resp.status == 200:
                                    messages = await msg_resp.json()
                                    if messages:
                                        # Extract text content
                                        parts = messages[0].get("parts", [])
                                        text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
                                        task.result = "\n".join(text_parts)[:5000]  # Limit result size

                            return

            except Exception as e:
                logger.debug(f"Error checking agent status: {e}")

            # Wait before next check
            await asyncio.sleep(2)


# Global bridge instance
_bridge: Optional[OpenCodeBridge] = None


def get_bridge() -> OpenCodeBridge:
    """Get the global OpenCode bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = OpenCodeBridge()
    return _bridge


def init_bridge(
    opencode_bin: Optional[str] = None,
    default_port: int = 9777,
    auto_start: bool = True,
) -> OpenCodeBridge:
    """Initialize the global OpenCode bridge instance."""
    global _bridge
    _bridge = OpenCodeBridge(
        opencode_bin=opencode_bin,
        default_port=default_port,
        auto_start=auto_start,
    )
    return _bridge
