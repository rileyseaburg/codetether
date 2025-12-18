"""
PostgreSQL database persistence layer for A2A Server.

Provides durable storage for workers, codebases, tasks, and sessions
that survives server restarts and works across multiple replicas.

Configuration:
    DATABASE_URL: PostgreSQL connection string
        Format: postgresql://user:password@host:port/database
        Example: postgresql://a2a:secret@localhost:5432/a2a_server
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', os.environ.get('A2A_DATABASE_URL', ''))

# Module-level state
_pool = None
_pool_lock = asyncio.Lock()
_initialized = False


def _parse_timestamp(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse a timestamp from string or datetime to datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try common formats
                return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                try:
                    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    return datetime.utcnow()
    return datetime.utcnow()


async def get_pool():
    """Get or create the asyncpg connection pool."""
    global _pool, _initialized

    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        return None

    async with _pool_lock:
        if _pool is not None:
            return _pool

        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
            logger.info(f'✓ PostgreSQL connection pool created')

            # Initialize schema if needed
            if not _initialized:
                await _init_schema()
                _initialized = True

            return _pool
        except ImportError:
            logger.warning('asyncpg not installed, PostgreSQL persistence disabled')
            return None
        except Exception as e:
            logger.error(f'Failed to create PostgreSQL pool: {e}')
            return None


async def _init_schema():
    """Initialize database schema if tables don't exist."""
    pool = await get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        # Workers table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                capabilities JSONB DEFAULT '[]'::jsonb,
                hostname TEXT,
                models JSONB DEFAULT '[]'::jsonb,
                global_codebase_id TEXT,
                registered_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'active'
            )
        ''')

        # Migration: Add models column if it doesn't exist
        try:
            await conn.execute('ALTER TABLE workers ADD COLUMN IF NOT EXISTS models JSONB DEFAULT \'[]\'::jsonb')
        except Exception:
            pass

        # Migration: Add global_codebase_id column if it doesn't exist
        try:
            await conn.execute('ALTER TABLE workers ADD COLUMN IF NOT EXISTS global_codebase_id TEXT')
        except Exception:
            pass

        # Codebases table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS codebases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                description TEXT DEFAULT '',
                worker_id TEXT REFERENCES workers(worker_id) ON DELETE SET NULL,
                agent_config JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'active',
                session_id TEXT,
                opencode_port INTEGER
            )
        ''')

        # Tasks table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                codebase_id TEXT REFERENCES codebases(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                agent_type TEXT DEFAULT 'build',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                worker_id TEXT REFERENCES workers(worker_id) ON DELETE SET NULL,
                result TEXT,
                error TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            )
        ''')

        # Sessions table (for worker-synced OpenCode sessions)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                codebase_id TEXT REFERENCES codebases(id) ON DELETE CASCADE,
                project_id TEXT,
                directory TEXT,
                title TEXT,
                version TEXT,
                summary JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')

        # Messages table (for session messages)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS session_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT,
                content TEXT,
                model TEXT,
                cost REAL,
                tokens JSONB DEFAULT '{}'::jsonb,
                tool_calls JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')

        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_workers_last_seen ON workers(last_seen)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_codebases_worker ON codebases(worker_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_codebases_status ON codebases(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_codebases_path ON codebases(path)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_codebase ON tasks(codebase_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(worker_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_codebase ON sessions(codebase_id)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id)')

        logger.info('✓ PostgreSQL schema initialized')


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info('PostgreSQL connection pool closed')


# ========================================
# Worker Operations
# ========================================

async def db_upsert_worker(worker_info: Dict[str, Any]) -> bool:
    """Insert or update a worker in the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO workers (worker_id, name, capabilities, hostname, models, global_codebase_id, registered_at, last_seen, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (worker_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    capabilities = EXCLUDED.capabilities,
                    hostname = EXCLUDED.hostname,
                    models = EXCLUDED.models,
                    global_codebase_id = EXCLUDED.global_codebase_id,
                    last_seen = EXCLUDED.last_seen,
                    status = EXCLUDED.status
            ''',
                worker_info.get('worker_id'),
                worker_info.get('name'),
                json.dumps(worker_info.get('capabilities', [])),
                worker_info.get('hostname'),
                json.dumps(worker_info.get('models', [])),
                worker_info.get('global_codebase_id'),
                _parse_timestamp(worker_info.get('registered_at')) or datetime.utcnow(),
                _parse_timestamp(worker_info.get('last_seen')) or datetime.utcnow(),
                worker_info.get('status', 'active'),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert worker: {e}')
        return False


async def db_delete_worker(worker_id: str) -> bool:
    """Delete a worker from the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM workers WHERE worker_id = $1', worker_id)
        return True
    except Exception as e:
        logger.error(f'Failed to delete worker: {e}')
        return False


async def db_get_worker(worker_id: str) -> Optional[Dict[str, Any]]:
    """Get a worker by ID."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM workers WHERE worker_id = $1', worker_id)
            if row:
                return _row_to_worker(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get worker: {e}')
        return None


async def db_list_workers(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all workers, optionally filtered by status."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    'SELECT * FROM workers WHERE status = $1 ORDER BY last_seen DESC',
                    status
                )
            else:
                rows = await conn.fetch('SELECT * FROM workers ORDER BY last_seen DESC')
            return [_row_to_worker(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list workers: {e}')
        return []


async def db_update_worker_heartbeat(worker_id: str) -> bool:
    """Update worker's last_seen timestamp."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                'UPDATE workers SET last_seen = NOW() WHERE worker_id = $1',
                worker_id
            )
            return 'UPDATE 1' in result
    except Exception as e:
        logger.error(f'Failed to update worker heartbeat: {e}')
        return False


def _row_to_worker(row) -> Dict[str, Any]:
    """Convert a database row to a worker dict."""
    return {
        'worker_id': row['worker_id'],
        'name': row['name'],
        'capabilities': json.loads(row['capabilities']) if isinstance(row['capabilities'], str) else row['capabilities'],
        'hostname': row['hostname'],
        'models': json.loads(row['models']) if isinstance(row['models'], str) else row['models'],
        'global_codebase_id': row['global_codebase_id'],
        'registered_at': row['registered_at'].isoformat() if row['registered_at'] else None,
        'last_seen': row['last_seen'].isoformat() if row['last_seen'] else None,
        'status': row['status'],
    }


# ========================================
# Codebase Operations
# ========================================

async def db_upsert_codebase(codebase: Dict[str, Any]) -> bool:
    """Insert or update a codebase in the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        # Handle both 'created_at' and 'registered_at' field names
        created_at = codebase.get('created_at') or codebase.get('registered_at')

        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO codebases (id, name, path, description, worker_id, agent_config, created_at, updated_at, status, session_id, opencode_port)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    path = EXCLUDED.path,
                    description = EXCLUDED.description,
                    worker_id = EXCLUDED.worker_id,
                    agent_config = EXCLUDED.agent_config,
                    updated_at = NOW(),
                    status = EXCLUDED.status,
                    session_id = EXCLUDED.session_id,
                    opencode_port = EXCLUDED.opencode_port
            ''',
                codebase.get('id'),
                codebase.get('name'),
                codebase.get('path'),
                codebase.get('description', ''),
                codebase.get('worker_id'),
                json.dumps(codebase.get('agent_config', {})),
                _parse_timestamp(created_at) or datetime.utcnow(),
                _parse_timestamp(codebase.get('updated_at')) or datetime.utcnow(),
                codebase.get('status', 'active'),
                codebase.get('session_id'),
                codebase.get('opencode_port'),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert codebase: {e}')
        return False


async def db_delete_codebase(codebase_id: str) -> bool:
    """Delete a codebase from the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM codebases WHERE id = $1', codebase_id)
        return True
    except Exception as e:
        logger.error(f'Failed to delete codebase: {e}')
        return False


async def db_get_codebase(codebase_id: str) -> Optional[Dict[str, Any]]:
    """Get a codebase by ID."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM codebases WHERE id = $1', codebase_id)
            if row:
                return _row_to_codebase(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get codebase: {e}')
        return None


async def db_list_codebases(worker_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all codebases, optionally filtered by worker or status."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            query = 'SELECT * FROM codebases WHERE 1=1'
            params = []
            param_idx = 1

            if worker_id:
                query += f' AND worker_id = ${param_idx}'
                params.append(worker_id)
                param_idx += 1

            if status:
                query += f' AND status = ${param_idx}'
                params.append(status)
                param_idx += 1

            query += ' ORDER BY updated_at DESC'

            rows = await conn.fetch(query, *params)
            return [_row_to_codebase(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list codebases: {e}')
        return []


async def db_list_codebases_by_path(path: str) -> List[Dict[str, Any]]:
    """List all codebases matching a specific normalized path."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM codebases WHERE path = $1 ORDER BY updated_at DESC',
                path,
            )
            return [_row_to_codebase(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list codebases by path: {e}')
        return []


def _row_to_codebase(row) -> Dict[str, Any]:
    """Convert a database row to a codebase dict."""
    agent_config = row['agent_config']
    if isinstance(agent_config, str):
        agent_config = json.loads(agent_config)
    elif agent_config is None:
        agent_config = {}

    return {
        'id': row['id'],
        'name': row['name'],
        'path': row['path'],
        'description': row['description'],
        'worker_id': row['worker_id'],
        'agent_config': agent_config,
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
        'status': row['status'],
        'session_id': row['session_id'],
        'opencode_port': row['opencode_port'],
    }


# ========================================
# Task Operations
# ========================================

async def db_upsert_task(task: Dict[str, Any]) -> bool:
    """Insert or update a task in the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO tasks (id, codebase_id, title, prompt, agent_type, status, priority, worker_id, result, error, metadata, created_at, updated_at, started_at, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    worker_id = EXCLUDED.worker_id,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    updated_at = NOW(),
                    started_at = COALESCE(tasks.started_at, EXCLUDED.started_at),
                    completed_at = EXCLUDED.completed_at
            ''',
                task.get('id'),
                task.get('codebase_id'),
                task.get('title'),
                task.get('prompt'),
                task.get('agent_type', 'build'),
                task.get('status', 'pending'),
                task.get('priority', 0),
                task.get('worker_id'),
                task.get('result'),
                task.get('error'),
                json.dumps(task.get('metadata', {})),
                _parse_timestamp(task.get('created_at')) or datetime.utcnow(),
                _parse_timestamp(task.get('updated_at')) or datetime.utcnow(),
                _parse_timestamp(task.get('started_at')),
                _parse_timestamp(task.get('completed_at')),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert task: {e}')
        return False


async def db_get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task by ID."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
            if row:
                return _row_to_task(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get task: {e}')
        return None


async def db_list_tasks(
    codebase_id: Optional[str] = None,
    status: Optional[str] = None,
    worker_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List tasks with optional filters."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            query = 'SELECT * FROM tasks WHERE 1=1'
            params = []
            param_idx = 1

            if codebase_id:
                query += f' AND codebase_id = ${param_idx}'
                params.append(codebase_id)
                param_idx += 1

            if status:
                query += f' AND status = ${param_idx}'
                params.append(status)
                param_idx += 1

            if worker_id:
                query += f' AND worker_id = ${param_idx}'
                params.append(worker_id)
                param_idx += 1

            query += f' ORDER BY priority DESC, created_at ASC LIMIT ${param_idx}'
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [_row_to_task(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list tasks: {e}')
        return []


async def db_get_next_pending_task(codebase_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the next pending task (highest priority, oldest first)."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            if codebase_id:
                row = await conn.fetchrow('''
                    SELECT * FROM tasks
                    WHERE status = 'pending' AND codebase_id = $1
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                ''', codebase_id)
            else:
                row = await conn.fetchrow('''
                    SELECT * FROM tasks
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                ''')
            if row:
                return _row_to_task(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get next pending task: {e}')
        return None


async def db_update_task_status(
    task_id: str,
    status: str,
    worker_id: Optional[str] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """Update task status and optionally result/error."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            updates = ['status = $2', 'updated_at = NOW()']
            params = [task_id, status]
            param_idx = 3

            if worker_id:
                updates.append(f'worker_id = ${param_idx}')
                params.append(worker_id)
                param_idx += 1

            if result is not None:
                updates.append(f'result = ${param_idx}')
                params.append(result)
                param_idx += 1

            if error is not None:
                updates.append(f'error = ${param_idx}')
                params.append(error)
                param_idx += 1

            if status == 'running':
                updates.append('started_at = NOW()')
            elif status in ('completed', 'failed', 'cancelled'):
                updates.append('completed_at = NOW()')

            query = f'UPDATE tasks SET {", ".join(updates)} WHERE id = $1'
            result_msg = await conn.execute(query, *params)
            return 'UPDATE 1' in result_msg
    except Exception as e:
        logger.error(f'Failed to update task status: {e}')
        return False


def _row_to_task(row) -> Dict[str, Any]:
    """Convert a database row to a task dict."""
    metadata = row['metadata']
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    elif metadata is None:
        metadata = {}

    return {
        'id': row['id'],
        'codebase_id': row['codebase_id'],
        'title': row['title'],
        'prompt': row['prompt'],
        'agent_type': row['agent_type'],
        'status': row['status'],
        'priority': row['priority'],
        'worker_id': row['worker_id'],
        'result': row['result'],
        'error': row['error'],
        'metadata': metadata,
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
        'started_at': row['started_at'].isoformat() if row['started_at'] else None,
        'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
    }


# ========================================
# Session Operations
# ========================================

async def db_upsert_session(session: Dict[str, Any]) -> bool:
    """Insert or update a session in the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO sessions (id, codebase_id, project_id, directory, title, version, summary, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    version = EXCLUDED.version,
                    summary = EXCLUDED.summary,
                    updated_at = NOW()
            ''',
                session.get('id'),
                session.get('codebase_id'),
                session.get('project_id'),
                session.get('directory'),
                session.get('title'),
                session.get('version'),
                json.dumps(session.get('summary', {})),
                _parse_timestamp(session.get('created_at')) or datetime.utcnow(),
                _parse_timestamp(session.get('updated_at')) or datetime.utcnow(),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert session: {e}')
        return False


async def db_list_sessions(codebase_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List sessions for a codebase."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM sessions
                WHERE codebase_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
            ''', codebase_id, limit)
            return [_row_to_session(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list sessions: {e}')
        return []


async def db_list_all_sessions(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List all sessions across all codebases."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT s.*, c.name as codebase_name, c.path as codebase_path
                FROM sessions s
                LEFT JOIN codebases c ON s.codebase_id = c.id
                ORDER BY s.updated_at DESC
                LIMIT $1 OFFSET $2
            ''', limit, offset)
            sessions = []
            for row in rows:
                session = _row_to_session(row)
                session['codebase_name'] = row.get('codebase_name')
                session['codebase_path'] = row.get('codebase_path')
                sessions.append(session)
            return sessions
    except Exception as e:
        logger.error(f'Failed to list all sessions: {e}')
        return []


async def db_get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM sessions WHERE id = $1', session_id)
            if row:
                return _row_to_session(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get session: {e}')
        return None


def _row_to_session(row) -> Dict[str, Any]:
    """Convert a database row to a session dict."""
    summary = row['summary']
    if isinstance(summary, str):
        summary = json.loads(summary)
    elif summary is None:
        summary = {}

    return {
        'id': row['id'],
        'codebase_id': row['codebase_id'],
        'project_id': row['project_id'],
        'directory': row['directory'],
        'title': row['title'],
        'version': row['version'],
        'summary': summary,
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
    }


# ========================================
# Session Message Operations
# ========================================

async def db_upsert_message(message: Dict[str, Any]) -> bool:
    """Insert or update a session message."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO session_messages (id, session_id, role, content, model, cost, tokens, tool_calls, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id)
                DO UPDATE SET
                    content = EXCLUDED.content,
                    tokens = EXCLUDED.tokens,
                    tool_calls = EXCLUDED.tool_calls
            ''',
                message.get('id'),
                message.get('session_id'),
                message.get('role'),
                message.get('content'),
                message.get('model'),
                message.get('cost'),
                json.dumps(message.get('tokens', {})),
                json.dumps(message.get('tool_calls', [])),
                _parse_timestamp(message.get('created_at')) or datetime.utcnow(),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert message: {e}')
        return False


async def db_list_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List messages for a session."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT * FROM session_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
            ''', session_id, limit)
            return [_row_to_message(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list messages: {e}')
        return []


def _row_to_message(row) -> Dict[str, Any]:
    """Convert a database row to a message dict."""
    tokens = row['tokens']
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    elif tokens is None:
        tokens = {}

    tool_calls = row['tool_calls']
    if isinstance(tool_calls, str):
        tool_calls = json.loads(tool_calls)
    elif tool_calls is None:
        tool_calls = []

    return {
        'id': row['id'],
        'session_id': row['session_id'],
        'role': row['role'],
        'content': row['content'],
        'model': row['model'],
        'cost': row['cost'],
        'tokens': tokens,
        'tool_calls': tool_calls,
        'created_at': row['created_at'].isoformat() if row['created_at'] else None,
    }


# ========================================
# Health Check
# ========================================

async def db_health_check() -> Dict[str, Any]:
    """Check database health and return stats."""
    pool = await get_pool()

    if not pool:
        return {
            'available': False,
            'message': 'PostgreSQL not configured (set DATABASE_URL environment variable)',
        }

    try:
        async with pool.acquire() as conn:
            # Check connectivity
            await conn.fetchval('SELECT 1')

            # Get counts
            worker_count = await conn.fetchval('SELECT COUNT(*) FROM workers')
            codebase_count = await conn.fetchval('SELECT COUNT(*) FROM codebases')
            task_count = await conn.fetchval('SELECT COUNT(*) FROM tasks')
            session_count = await conn.fetchval('SELECT COUNT(*) FROM sessions')

            return {
                'available': True,
                'message': 'PostgreSQL connected',
                'stats': {
                    'workers': worker_count,
                    'codebases': codebase_count,
                    'tasks': task_count,
                    'sessions': session_count,
                },
                'pool_size': pool.get_size(),
                'pool_idle': pool.get_idle_size(),
            }
    except Exception as e:
        return {
            'available': False,
            'message': f'PostgreSQL error: {e}',
        }
