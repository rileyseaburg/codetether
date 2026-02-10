"""
PostgreSQL database persistence layer for A2A Server.

Provides durable storage for workers, codebases, tasks, and sessions
that survives server restarts and works across multiple replicas.

Configuration:
    DATABASE_URL: PostgreSQL connection string
        Format: postgresql://user:password@host:port/database
        Example: postgresql://a2a:secret@localhost:5432/a2a_server

Row-Level Security (RLS):
    RLS_ENABLED: Enable database-level tenant isolation (default: false)
    RLS_STRICT_MODE: Require tenant context for all queries (default: false)

    When RLS is enabled, the database enforces tenant isolation at the row level.
    Use the tenant_scope() context manager or set_tenant_context() to set the
    tenant context before executing queries.

    See a2a_server/rls.py for RLS utilities and documentation.
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Database URL from environment — no hardcoded fallback.
# One of DATABASE_URL or A2A_DATABASE_URL MUST be set.
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('A2A_DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError(
        'DATABASE_URL (or A2A_DATABASE_URL) environment variable is required. '
        'Example: postgresql://user:pass@host:5432/dbname'
    )

# Module-level state
_pool = None
_pool_lock = asyncio.Lock()
_initialized = False

# RLS Configuration (can be overridden by environment)
# RLS is enabled by default for multi-tenant isolation.
RLS_ENABLED = os.environ.get('RLS_ENABLED', 'true').lower() == 'true'
RLS_STRICT_MODE = os.environ.get('RLS_STRICT_MODE', 'false').lower() == 'true'


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

            # Initialize task queue for hosted workers
            try:
                from .task_queue import TaskQueue, set_task_queue

                task_queue = TaskQueue(_pool)
                set_task_queue(task_queue)
                logger.info('✓ Task queue initialized for hosted workers')
            except ImportError:
                logger.debug('Task queue module not available')
            except Exception as e:
                logger.warning(f'Failed to initialize task queue: {e}')

            return _pool
        except ImportError:
            logger.warning(
                'asyncpg not installed, PostgreSQL persistence disabled'
            )
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
        # Tenants table (multi-tenant support)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                realm_name TEXT UNIQUE NOT NULL,
                display_name TEXT,
                plan TEXT DEFAULT 'free',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Workers table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                capabilities JSONB DEFAULT '[]'::jsonb,
                hostname TEXT,
                models JSONB DEFAULT '[]'::jsonb,
                global_codebase_id TEXT,
                registered_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'active',
                tenant_id TEXT REFERENCES tenants(id)
            )
        """)

        # Migration: Add models column if it doesn't exist
        try:
            await conn.execute(
                "ALTER TABLE workers ADD COLUMN IF NOT EXISTS models JSONB DEFAULT '[]'::jsonb"
            )
        except Exception:
            pass

        # Migration: Add global_codebase_id column if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE workers ADD COLUMN IF NOT EXISTS global_codebase_id TEXT'
            )
        except Exception:
            pass

        # Migration: Add tenant_id column to workers if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE workers ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)'
            )
        except Exception:
            pass

        # Codebases table
        await conn.execute("""
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
                opencode_port INTEGER,
                tenant_id TEXT REFERENCES tenants(id),
                minio_path TEXT,
                last_sync_at TIMESTAMPTZ
            )
        """)

        # Migration: Add tenant_id column to codebases if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE codebases ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)'
            )
        except Exception:
            pass

        # Migration: Add MinIO columns to codebases
        try:
            await conn.execute(
                'ALTER TABLE codebases ADD COLUMN IF NOT EXISTS minio_path TEXT'
            )
        except Exception:
            pass
        try:
            await conn.execute(
                'ALTER TABLE codebases ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ'
            )
        except Exception:
            pass

        # Migration: Add Git repo columns to codebases
        for col_def in [
            'git_url TEXT',
            'git_branch TEXT DEFAULT \'main\'',
        ]:
            try:
                await conn.execute(
                    f'ALTER TABLE codebases ADD COLUMN IF NOT EXISTS {col_def}'
                )
            except Exception:
                pass

        # Tasks table
        await conn.execute("""
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
                completed_at TIMESTAMPTZ,
                tenant_id TEXT REFERENCES tenants(id)
            )
        """)

        # Migration: Add tenant_id column to tasks if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE tasks ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)'
            )
        except Exception:
            pass

        # Migration: Add model column to tasks if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE tasks ADD COLUMN IF NOT EXISTS model TEXT'
            )
        except Exception:
            pass

        # Sessions table (for worker-synced OpenCode sessions)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                codebase_id TEXT REFERENCES codebases(id) ON DELETE CASCADE,
                project_id TEXT,
                directory TEXT,
                title TEXT,
                version TEXT,
                summary JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                tenant_id TEXT REFERENCES tenants(id),
                knative_service_name TEXT,
                worker_status TEXT DEFAULT 'pending',
                last_activity_at TIMESTAMPTZ
            )
        """)

        # Migration: Add tenant_id column to sessions if it doesn't exist
        try:
            await conn.execute(
                'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id)'
            )
        except Exception:
            pass

        # Migration: Add Knative session worker columns to sessions
        try:
            await conn.execute(
                'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS knative_service_name TEXT'
            )
        except Exception:
            pass
        try:
            await conn.execute(
                "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS worker_status TEXT DEFAULT 'pending'"
            )
        except Exception:
            pass
        try:
            await conn.execute(
                'ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ'
            )
        except Exception:
            pass

        # Messages table (for session messages)
        await conn.execute("""
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
        """)

        # Monitor messages table (for agent monitoring)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS monitor_messages (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                type TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                response_time REAL,
                tokens INTEGER,
                error TEXT
            )
        """)

        # Inbound emails table (for email reply tracking)
        # Note: task_id is not a FK because tasks may be in-memory only
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inbound_emails (
                id TEXT PRIMARY KEY,
                from_email TEXT NOT NULL,
                to_email TEXT NOT NULL,
                subject TEXT,
                body_text TEXT,
                body_html TEXT,
                session_id TEXT,
                codebase_id TEXT,
                task_id TEXT,
                sender_ip TEXT,
                spf_result TEXT,
                status TEXT DEFAULT 'received',
                error TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                received_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                tenant_id TEXT REFERENCES tenants(id)
            )
        """)

        # Outbound emails table (for sent email tracking)
        # Note: task_id is not a FK because tasks may be in-memory only
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS outbound_emails (
                id TEXT PRIMARY KEY,
                to_email TEXT NOT NULL,
                from_email TEXT NOT NULL,
                reply_to TEXT,
                subject TEXT NOT NULL,
                body_html TEXT,
                body_text TEXT,
                task_id TEXT,
                session_id TEXT,
                codebase_id TEXT,
                worker_id TEXT,
                status TEXT DEFAULT 'queued',
                sendgrid_message_id TEXT,
                error TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                sent_at TIMESTAMPTZ,
                tenant_id TEXT REFERENCES tenants(id)
            )
        """)

        # Ralph runs table for autonomous development
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ralph_runs (
                id TEXT PRIMARY KEY,
                prd JSONB NOT NULL,
                codebase_id TEXT,
                model TEXT,
                status TEXT DEFAULT 'pending',
                max_iterations INTEGER DEFAULT 10,
                current_iteration INTEGER DEFAULT 0,
                run_mode TEXT DEFAULT 'sequential',
                max_parallel INTEGER DEFAULT 3,
                story_results JSONB DEFAULT '[]'::jsonb,
                logs JSONB DEFAULT '[]'::jsonb,
                error TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                tenant_id TEXT REFERENCES tenants(id)
            )
        """)

        # Create indexes
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_workers_last_seen ON workers(last_seen)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_codebases_worker ON codebases(worker_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_codebases_status ON codebases(status)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_codebases_path ON codebases(path)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tasks_codebase ON tasks(codebase_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(worker_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_sessions_codebase ON sessions(codebase_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id)'
        )

        # Tenant indexes
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tenants_realm ON tenants(realm_name)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_workers_tenant ON workers(tenant_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_codebases_tenant ON codebases(tenant_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON sessions(tenant_id)'
        )

        # Email indexes
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_inbound_emails_session ON inbound_emails(session_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_inbound_emails_from ON inbound_emails(from_email)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_inbound_emails_received ON inbound_emails(received_at DESC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_inbound_emails_status ON inbound_emails(status)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_outbound_emails_task ON outbound_emails(task_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_outbound_emails_session ON outbound_emails(session_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_outbound_emails_to ON outbound_emails(to_email)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_outbound_emails_created ON outbound_emails(created_at DESC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_outbound_emails_status ON outbound_emails(status)'
        )

        # Ralph indexes
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_ralph_runs_status ON ralph_runs(status)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_ralph_runs_created ON ralph_runs(created_at DESC)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_ralph_runs_codebase ON ralph_runs(codebase_id)'
        )
        await conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_ralph_runs_tenant ON ralph_runs(tenant_id)'
        )

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


async def db_upsert_worker(
    worker_info: Dict[str, Any], tenant_id: Optional[str] = None
) -> bool:
    """Insert or update a worker in the database.

    Args:
        worker_info: The worker data dict
        tenant_id: Optional tenant ID for multi-tenant isolation
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        # Use provided tenant_id or fall back to worker_info dict
        effective_tenant_id = tenant_id or worker_info.get('tenant_id')

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO workers (worker_id, name, capabilities, hostname, models, global_codebase_id, registered_at, last_seen, status, tenant_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (worker_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    capabilities = EXCLUDED.capabilities,
                    hostname = EXCLUDED.hostname,
                    models = EXCLUDED.models,
                    global_codebase_id = EXCLUDED.global_codebase_id,
                    last_seen = EXCLUDED.last_seen,
                    status = EXCLUDED.status,
                    tenant_id = COALESCE(EXCLUDED.tenant_id, workers.tenant_id)
            """,
                worker_info.get('worker_id'),
                worker_info.get('name'),
                json.dumps(worker_info.get('capabilities', [])),
                worker_info.get('hostname'),
                json.dumps(worker_info.get('models', [])),
                worker_info.get('global_codebase_id'),
                _parse_timestamp(worker_info.get('registered_at'))
                or datetime.utcnow(),
                _parse_timestamp(worker_info.get('last_seen'))
                or datetime.utcnow(),
                worker_info.get('status', 'active'),
                effective_tenant_id,
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
            await conn.execute(
                'DELETE FROM workers WHERE worker_id = $1', worker_id
            )
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
            row = await conn.fetchrow(
                'SELECT * FROM workers WHERE worker_id = $1', worker_id
            )
            if row:
                return _row_to_worker(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get worker: {e}')
        return None


async def db_list_workers(
    status: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all workers, optionally filtered by status or tenant."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            query = 'SELECT * FROM workers WHERE 1=1'
            params = []
            param_idx = 1

            if status:
                query += f' AND status = ${param_idx}'
                params.append(status)
                param_idx += 1

            if tenant_id:
                query += f' AND tenant_id = ${param_idx}'
                params.append(tenant_id)
                param_idx += 1

            query += ' ORDER BY last_seen DESC'

            rows = await conn.fetch(query, *params)
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
                worker_id,
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
        'capabilities': json.loads(row['capabilities'])
        if isinstance(row['capabilities'], str)
        else row['capabilities'],
        'hostname': row['hostname'],
        'models': json.loads(row['models'])
        if isinstance(row['models'], str)
        else row['models'],
        'global_codebase_id': row['global_codebase_id'],
        'registered_at': row['registered_at'].isoformat()
        if row['registered_at']
        else None,
        'last_seen': row['last_seen'].isoformat() if row['last_seen'] else None,
        'status': row['status'],
    }


# ========================================
# Codebase Operations
# ========================================


async def db_upsert_codebase(
    codebase: Dict[str, Any], tenant_id: Optional[str] = None
) -> bool:
    """Insert or update a codebase in the database.

    Args:
        codebase: The codebase data dict
        tenant_id: Optional tenant ID for multi-tenant isolation
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        # Handle both 'created_at' and 'registered_at' field names
        created_at = codebase.get('created_at') or codebase.get('registered_at')
        # Use provided tenant_id or fall back to codebase dict
        effective_tenant_id = tenant_id or codebase.get('tenant_id')

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO codebases (id, name, path, description, worker_id, agent_config, created_at, updated_at, status, session_id, opencode_port, tenant_id, git_url, git_branch)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
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
                    opencode_port = EXCLUDED.opencode_port,
                    tenant_id = COALESCE(EXCLUDED.tenant_id, codebases.tenant_id),
                    git_url = COALESCE(EXCLUDED.git_url, codebases.git_url),
                    git_branch = COALESCE(EXCLUDED.git_branch, codebases.git_branch)
            """,
                codebase.get('id'),
                codebase.get('name'),
                codebase.get('path'),
                codebase.get('description', ''),
                codebase.get('worker_id'),
                json.dumps(codebase.get('agent_config', {})),
                _parse_timestamp(created_at) or datetime.utcnow(),
                _parse_timestamp(codebase.get('updated_at'))
                or datetime.utcnow(),
                codebase.get('status', 'active'),
                codebase.get('session_id'),
                codebase.get('opencode_port'),
                effective_tenant_id,
                codebase.get('git_url'),
                codebase.get('git_branch', 'main'),
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
            await conn.execute(
                'DELETE FROM codebases WHERE id = $1', codebase_id
            )
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
            row = await conn.fetchrow(
                'SELECT * FROM codebases WHERE id = $1', codebase_id
            )
            if row:
                return _row_to_codebase(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get codebase: {e}')
        return None


async def db_list_codebases(
    worker_id: Optional[str] = None,
    status: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all codebases, optionally filtered by worker, status, or tenant."""
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

            if tenant_id:
                query += f' AND tenant_id = ${param_idx}'
                params.append(tenant_id)
                param_idx += 1

            query += ' ORDER BY updated_at DESC'

            rows = await conn.fetch(query, *params)
            return [_row_to_codebase(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list codebases: {e}')
        return []


async def db_list_codebases_by_path(path: str) -> List[Dict[str, Any]]:
    """List all codebases matching a specific normalized path.

    Returns codebases ordered by created_at ASC so the oldest (canonical) ID is first.
    This ensures we consistently use the original codebase ID when there are duplicates.
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM codebases WHERE path = $1 ORDER BY created_at ASC',
                path,
            )
            return [_row_to_codebase(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list codebases by path: {e}')
        return []


async def db_get_canonical_codebase_id(path: str) -> Optional[str]:
    """Get the canonical (oldest) codebase ID for a given path.

    This is the authoritative ID that should be used for task routing.
    Returns None if no codebase exists for this path.
    """
    codebases = await db_list_codebases_by_path(path)
    if codebases:
        return codebases[0].get('id')
    return None


async def db_deduplicate_codebases(
    path: str, keep_id: Optional[str] = None
) -> int:
    """Remove duplicate codebase entries for a path, keeping only the canonical one.

    Args:
        path: The normalized path to deduplicate
        keep_id: Optional specific ID to keep. If not provided, keeps the oldest.

    Returns:
        Number of duplicate entries removed.
    """
    pool = await get_pool()
    if not pool:
        return 0

    try:
        async with pool.acquire() as conn:
            # Get all codebases for this path
            rows = await conn.fetch(
                'SELECT id, created_at FROM codebases WHERE path = $1 ORDER BY created_at ASC',
                path,
            )

            if len(rows) <= 1:
                return 0  # No duplicates

            # Determine which ID to keep
            if keep_id:
                canonical_id = keep_id
            else:
                canonical_id = rows[0]['id']  # Oldest

            # Delete all others
            ids_to_delete = [
                row['id'] for row in rows if row['id'] != canonical_id
            ]

            if not ids_to_delete:
                return 0

            deleted = await conn.execute(
                'DELETE FROM codebases WHERE id = ANY($1)',
                ids_to_delete,
            )

            count = int(deleted.split()[-1]) if deleted else 0
            logger.info(
                f'Deduplicated codebases for path {path}: kept {canonical_id}, '
                f'removed {count} duplicates: {ids_to_delete}'
            )
            return count
    except Exception as e:
        logger.error(f'Failed to deduplicate codebases for {path}: {e}')
        return 0


async def db_deduplicate_all_codebases() -> Dict[str, int]:
    """Deduplicate all codebase entries, keeping the oldest for each path.

    Returns:
        Dict mapping path to number of duplicates removed.
    """
    pool = await get_pool()
    if not pool:
        return {}

    results = {}
    try:
        async with pool.acquire() as conn:
            # Find all paths with duplicates
            rows = await conn.fetch("""
                SELECT path, COUNT(*) as count
                FROM codebases
                GROUP BY path
                HAVING COUNT(*) > 1
            """)

            for row in rows:
                path = row['path']
                removed = await db_deduplicate_codebases(path)
                if removed > 0:
                    results[path] = removed

        if results:
            logger.info(f'Deduplicated codebases: {results}')
        return results
    except Exception as e:
        logger.error(f'Failed to deduplicate all codebases: {e}')
        return results


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
        'created_at': row['created_at'].isoformat()
        if row['created_at']
        else None,
        'updated_at': row['updated_at'].isoformat()
        if row['updated_at']
        else None,
        'status': row['status'],
        'session_id': row['session_id'],
        'opencode_port': row['opencode_port'],
        'minio_path': row.get('minio_path'),
        'last_sync_at': row['last_sync_at'].isoformat()
        if row.get('last_sync_at')
        else None,
    }


# ========================================
# Task Operations
# ========================================


async def db_upsert_task(
    task: Dict[str, Any], tenant_id: Optional[str] = None
) -> bool:
    """Insert or update a task in the database.

    Args:
        task: The task data dict
        tenant_id: Optional tenant ID for multi-tenant isolation
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        # Use provided tenant_id or fall back to task dict
        effective_tenant_id = tenant_id or task.get('tenant_id')

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (id, codebase_id, title, prompt, agent_type, status, priority, worker_id, result, error, metadata, created_at, updated_at, started_at, completed_at, tenant_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    worker_id = EXCLUDED.worker_id,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    updated_at = NOW(),
                    started_at = COALESCE(tasks.started_at, EXCLUDED.started_at),
                    completed_at = EXCLUDED.completed_at,
                    tenant_id = COALESCE(EXCLUDED.tenant_id, tasks.tenant_id)
            """,
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
                effective_tenant_id,
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
            row = await conn.fetchrow(
                'SELECT * FROM tasks WHERE id = $1', task_id
            )
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
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List tasks with optional filters including tenant isolation."""
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

            if tenant_id:
                query += f' AND tenant_id = ${param_idx}'
                params.append(tenant_id)
                param_idx += 1

            query += (
                f' ORDER BY priority DESC, created_at ASC LIMIT ${param_idx}'
            )
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [_row_to_task(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list tasks: {e}')
        return []


async def db_get_next_pending_task(
    codebase_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get the next pending task (highest priority, oldest first)."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            if codebase_id:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM tasks
                    WHERE status = 'pending' AND codebase_id = $1
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """,
                    codebase_id,
                )
            else:
                row = await conn.fetchrow("""
                    SELECT * FROM tasks
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """)
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

    task = None
    session_id = None
    is_prd_chat = False

    # Get task metadata before update to check if it's a PRD chat
    try:
        task = await db_get_task(task_id)
        if task:
            metadata = task.get('metadata', {}) or {}
            is_prd_chat = metadata.get('prd_chat') == True
            session_id = metadata.get('session_id')
    except Exception:
        pass

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

            # If this is a PRD chat task and it completed with a result, save to session
            if is_prd_chat and session_id and status == 'completed' and result:
                await db_upsert_message(
                    {
                        'id': str(uuid.uuid4()),
                        'session_id': session_id,
                        'role': 'assistant',
                        'content': result,
                        'created_at': datetime.utcnow().isoformat(),
                    }
                )
                logger.info(f'Saved PRD chat result to session {session_id}')

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
        'created_at': row['created_at'].isoformat()
        if row['created_at']
        else None,
        'updated_at': row['updated_at'].isoformat()
        if row['updated_at']
        else None,
        'started_at': row['started_at'].isoformat()
        if row['started_at']
        else None,
        'completed_at': row['completed_at'].isoformat()
        if row['completed_at']
        else None,
    }


# ========================================
# Session Operations
# ========================================


async def db_upsert_session(
    session: Dict[str, Any], tenant_id: Optional[str] = None
) -> bool:
    """Insert or update a session in the database.

    Args:
        session: The session data dict
        tenant_id: Optional tenant ID for multi-tenant isolation
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        # Use provided tenant_id or fall back to session dict
        effective_tenant_id = tenant_id or session.get('tenant_id')

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, codebase_id, project_id, directory, title, version, summary, created_at, updated_at, tenant_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    version = EXCLUDED.version,
                    summary = EXCLUDED.summary,
                    updated_at = NOW(),
                    tenant_id = COALESCE(EXCLUDED.tenant_id, sessions.tenant_id)
            """,
                session.get('id'),
                session.get('codebase_id'),
                session.get('project_id'),
                session.get('directory'),
                session.get('title'),
                session.get('version'),
                json.dumps(session.get('summary', {})),
                _parse_timestamp(session.get('created_at'))
                or datetime.utcnow(),
                _parse_timestamp(session.get('updated_at'))
                or datetime.utcnow(),
                effective_tenant_id,
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert session: {e}')
        return False


async def db_list_sessions(
    codebase_id: str,
    limit: int = 50,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List sessions for a codebase, optionally filtered by tenant."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            if tenant_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE codebase_id = $1 AND tenant_id = $3
                    ORDER BY updated_at DESC
                    LIMIT $2
                """,
                    codebase_id,
                    limit,
                    tenant_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM sessions
                    WHERE codebase_id = $1
                    ORDER BY updated_at DESC
                    LIMIT $2
                """,
                    codebase_id,
                    limit,
                )
            return [_row_to_session(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list sessions: {e}')
        return []


async def db_list_all_sessions(
    limit: int = 100,
    offset: int = 0,
    tenant_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all sessions across all codebases, optionally filtered by tenant."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            if tenant_id:
                rows = await conn.fetch(
                    """
                    SELECT s.*, c.name as codebase_name, c.path as codebase_path
                    FROM sessions s
                    LEFT JOIN codebases c ON s.codebase_id = c.id
                    WHERE s.tenant_id = $3
                    ORDER BY s.updated_at DESC
                    LIMIT $1 OFFSET $2
                """,
                    limit,
                    offset,
                    tenant_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT s.*, c.name as codebase_name, c.path as codebase_path
                    FROM sessions s
                    LEFT JOIN codebases c ON s.codebase_id = c.id
                    ORDER BY s.updated_at DESC
                    LIMIT $1 OFFSET $2
                """,
                    limit,
                    offset,
                )
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
            row = await conn.fetchrow(
                'SELECT * FROM sessions WHERE id = $1', session_id
            )
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
        'created_at': row['created_at'].isoformat()
        if row['created_at']
        else None,
        'updated_at': row['updated_at'].isoformat()
        if row['updated_at']
        else None,
        'knative_service_name': row.get('knative_service_name'),
        'worker_status': row.get('worker_status', 'pending'),
        'last_activity_at': row['last_activity_at'].isoformat()
        if row.get('last_activity_at')
        else None,
    }


async def db_update_session_worker_status(
    session_id: str,
    worker_status: str,
    knative_service_name: Optional[str] = None,
) -> bool:
    """Update session worker status and optionally the Knative service name.

    Args:
        session_id: The session ID to update
        worker_status: Worker status (pending, creating, ready, running,
                       scaled_to_zero, failed, terminated)
        knative_service_name: Optional Knative Service name
                              (e.g., "opencode-session-ses123")

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            if knative_service_name is not None:
                result = await conn.execute(
                    """
                    UPDATE sessions
                    SET worker_status = $2,
                        knative_service_name = $3,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    session_id,
                    worker_status,
                    knative_service_name,
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE sessions
                    SET worker_status = $2,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    session_id,
                    worker_status,
                )
            return 'UPDATE 1' in result
    except Exception as e:
        logger.error(f'Failed to update session worker status: {e}')
        return False


async def db_update_session_activity(session_id: str) -> bool:
    """Update session's last_activity_at timestamp to now.

    Args:
        session_id: The session ID to update

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE sessions
                SET last_activity_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                session_id,
            )
            return 'UPDATE 1' in result
    except Exception as e:
        logger.error(f'Failed to update session activity: {e}')
        return False


async def db_update_codebase_minio_path(
    codebase_id: str, minio_path: str
) -> bool:
    """Update codebase's MinIO path.

    Args:
        codebase_id: The codebase ID to update
        minio_path: Path in MinIO bucket (e.g., "codebases/cb123.tar.gz")

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE codebases
                SET minio_path = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                codebase_id,
                minio_path,
            )
            return 'UPDATE 1' in result
    except Exception as e:
        logger.error(f'Failed to update codebase MinIO path: {e}')
        return False


async def db_update_codebase_sync_time(codebase_id: str) -> bool:
    """Update codebase's last_sync_at timestamp to now.

    Args:
        codebase_id: The codebase ID to update

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE codebases
                SET last_sync_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                codebase_id,
            )
            return 'UPDATE 1' in result
    except Exception as e:
        logger.error(f'Failed to update codebase sync time: {e}')
        return False


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
            await conn.execute(
                """
                INSERT INTO session_messages (id, session_id, role, content, model, cost, tokens, tool_calls, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id)
                DO UPDATE SET
                    content = EXCLUDED.content,
                    tokens = EXCLUDED.tokens,
                    tool_calls = EXCLUDED.tool_calls
            """,
                message.get('id'),
                message.get('session_id'),
                message.get('role'),
                message.get('content'),
                message.get('model'),
                message.get('cost'),
                json.dumps(message.get('tokens', {})),
                json.dumps(message.get('tool_calls', [])),
                _parse_timestamp(message.get('created_at'))
                or datetime.utcnow(),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert message: {e}')
        return False


async def db_list_messages(
    session_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """List messages for a session."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM session_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
            """,
                session_id,
                limit,
            )
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
        'created_at': row['created_at'].isoformat()
        if row['created_at']
        else None,
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
            codebase_count = await conn.fetchval(
                'SELECT COUNT(*) FROM codebases'
            )
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


# ========================================
# Monitor/Messages Operations
# ========================================


async def db_save_monitor_message(message: Dict[str, Any]) -> bool:
    """Save a monitor message to the database."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO monitor_messages
                (id, timestamp, type, agent_name, content, metadata, response_time, tokens, error)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO NOTHING
            """,
                message.get('id'),
                _parse_timestamp(message.get('timestamp')) or datetime.utcnow(),
                message.get('type'),
                message.get('agent_name'),
                message.get('content'),
                json.dumps(message.get('metadata', {})),
                message.get('response_time'),
                message.get('tokens'),
                message.get('error'),
            )
        return True
    except Exception as e:
        logger.error(f'Failed to save monitor message: {e}')
        return False


async def db_list_monitor_messages(
    limit: int = 100,
    agent_name: Optional[str] = None,
    msg_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List monitor messages from the database."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            query = 'SELECT * FROM monitor_messages WHERE 1=1'
            params = []
            param_idx = 1

            if agent_name:
                query += f' AND agent_name = ${param_idx}'
                params.append(agent_name)
                param_idx += 1

            if msg_type:
                query += f' AND type = ${param_idx}'
                params.append(msg_type)
                param_idx += 1

            query += f' ORDER BY timestamp DESC LIMIT ${param_idx}'
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [_row_to_monitor_message(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list monitor messages: {e}')
        return []


async def db_get_monitor_stats() -> Dict[str, Any]:
    """Get monitor statistics from the database."""
    pool = await get_pool()
    if not pool:
        return {}

    try:
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN type = 'tool' THEN 1 ELSE 0 END) as tool_calls,
                    SUM(CASE WHEN type = 'error' THEN 1 ELSE 0 END) as errors,
                    COALESCE(SUM(tokens), 0) as total_tokens,
                    COUNT(DISTINCT agent_name) as unique_agents
                FROM monitor_messages
            """)
            return dict(stats) if stats else {}
    except Exception as e:
        logger.error(f'Failed to get monitor stats: {e}')
        return {}


async def db_count_monitor_messages() -> int:
    """Count total monitor messages."""
    pool = await get_pool()
    if not pool:
        return 0

    try:
        async with pool.acquire() as conn:
            return await conn.fetchval('SELECT COUNT(*) FROM monitor_messages')
    except Exception:
        return 0


def _row_to_monitor_message(row) -> Dict[str, Any]:
    """Convert a database row to a monitor message dict."""
    metadata = row['metadata']
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    elif metadata is None:
        metadata = {}

    return {
        'id': row['id'],
        'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None,
        'type': row['type'],
        'agent_name': row['agent_name'],
        'content': row['content'],
        'metadata': metadata,
        'response_time': row['response_time'],
        'tokens': row['tokens'],
        'error': row['error'],
    }


# ========================================
# Tenant Operations (Multi-tenant support)
# ========================================


async def create_tenant(
    realm_name: str, display_name: str, plan: str = 'free'
) -> dict:
    """Create a new tenant.

    Args:
        realm_name: Unique realm identifier (e.g., "acme.codetether.run")
        display_name: Human-readable tenant name
        plan: Subscription plan ('free', 'pro', 'enterprise')

    Returns:
        The created tenant dict
    """
    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    tenant_id = str(uuid.uuid4())
    now = datetime.utcnow()

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenants (id, realm_name, display_name, plan, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                tenant_id,
                realm_name,
                display_name,
                plan,
                now,
                now,
            )

        return {
            'id': tenant_id,
            'realm_name': realm_name,
            'display_name': display_name,
            'plan': plan,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }
    except Exception as e:
        logger.error(f'Failed to create tenant: {e}')
        raise


async def get_tenant_by_realm(realm_name: str) -> Optional[dict]:
    """Get a tenant by realm name.

    Args:
        realm_name: The realm identifier (e.g., "acme.codetether.run")

    Returns:
        Tenant dict or None if not found
    """
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM tenants WHERE realm_name = $1', realm_name
            )
            if row:
                return _row_to_tenant(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get tenant by realm: {e}')
        return None


async def get_tenant_by_id(tenant_id: str) -> Optional[dict]:
    """Get a tenant by ID.

    Args:
        tenant_id: The tenant UUID

    Returns:
        Tenant dict or None if not found
    """
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM tenants WHERE id = $1', tenant_id
            )
            if row:
                return _row_to_tenant(row)
        return None
    except Exception as e:
        logger.error(f'Failed to get tenant by id: {e}')
        return None


async def list_tenants(limit: int = 100, offset: int = 0) -> List[dict]:
    """List all tenants with pagination.

    Args:
        limit: Maximum number of tenants to return
        offset: Number of tenants to skip

    Returns:
        List of tenant dicts
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM tenants
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """,
                limit,
                offset,
            )
            return [_row_to_tenant(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list tenants: {e}')
        return []


async def update_tenant(tenant_id: str, **kwargs) -> dict:
    """Update tenant fields.

    Args:
        tenant_id: The tenant UUID
        **kwargs: Fields to update (realm_name, display_name, plan)

    Returns:
        The updated tenant dict

    Raises:
        ValueError: If tenant not found
    """
    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    allowed_fields = {'realm_name', 'display_name', 'plan'}
    updates = []
    params = [tenant_id]
    param_idx = 2

    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f'{field} = ${param_idx}')
            params.append(value)
            param_idx += 1

    if not updates:
        # No valid fields to update, just return current tenant
        tenant = await get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f'Tenant {tenant_id} not found')
        return tenant

    updates.append('updated_at = NOW()')

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                f'UPDATE tenants SET {", ".join(updates)} WHERE id = $1',
                *params,
            )
            if 'UPDATE 0' in result:
                raise ValueError(f'Tenant {tenant_id} not found')

        tenant = await get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f'Tenant {tenant_id} not found')
        return tenant
    except ValueError:
        raise
    except Exception as e:
        logger.error(f'Failed to update tenant: {e}')
        raise


async def update_tenant_stripe(
    tenant_id: str, customer_id: str, subscription_id: str
) -> dict:
    """Update tenant Stripe billing information.

    Args:
        tenant_id: The tenant UUID
        customer_id: Stripe customer ID
        subscription_id: Stripe subscription ID

    Returns:
        The updated tenant dict

    Raises:
        ValueError: If tenant not found
    """
    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database not available')

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tenants
                SET stripe_customer_id = $2,
                    stripe_subscription_id = $3,
                    updated_at = NOW()
                WHERE id = $1
            """,
                tenant_id,
                customer_id,
                subscription_id,
            )
            if 'UPDATE 0' in result:
                raise ValueError(f'Tenant {tenant_id} not found')

        tenant = await get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError(f'Tenant {tenant_id} not found')
        return tenant
    except ValueError:
        raise
    except Exception as e:
        logger.error(f'Failed to update tenant Stripe info: {e}')
        raise


def _row_to_tenant(row) -> dict:
    """Convert a database row to a tenant dict."""
    return {
        'id': row['id'],
        'realm_name': row['realm_name'],
        'display_name': row['display_name'],
        'plan': row['plan'],
        'stripe_customer_id': row['stripe_customer_id'],
        'stripe_subscription_id': row['stripe_subscription_id'],
        'created_at': row['created_at'].isoformat()
        if row['created_at']
        else None,
        'updated_at': row['updated_at'].isoformat()
        if row['updated_at']
        else None,
    }


# ========================================
# Row-Level Security (RLS) Support
# ========================================


async def set_tenant_context(conn, tenant_id: str) -> None:
    """Set the tenant context for the current database connection.

    This sets the PostgreSQL session variable 'app.current_tenant_id' which
    is used by RLS policies to filter rows by tenant.

    Args:
        conn: asyncpg connection object
        tenant_id: The tenant UUID to set as context

    Example:
        async with pool.acquire() as conn:
            await set_tenant_context(conn, tenant_id)
            results = await conn.fetch("SELECT * FROM workers")
            await clear_tenant_context(conn)
    """
    if not tenant_id:
        logger.warning('set_tenant_context called with empty tenant_id')
        return

    if not RLS_ENABLED:
        logger.debug(f'RLS disabled, skipping tenant context: {tenant_id}')
        return

    try:
        await conn.execute(
            "SELECT set_config('app.current_tenant_id', $1, false)", tenant_id
        )
        logger.debug(f'Set tenant context: {tenant_id}')
    except Exception as e:
        logger.error(f'Failed to set tenant context: {e}')
        raise


async def clear_tenant_context(conn) -> None:
    """Clear the tenant context for the current database connection.

    This resets the PostgreSQL session variable 'app.current_tenant_id' to NULL,
    which allows access to all rows when RLS policies check for NULL context.

    Args:
        conn: asyncpg connection object
    """
    if not RLS_ENABLED:
        return

    try:
        await conn.execute('RESET app.current_tenant_id')
        logger.debug('Cleared tenant context')
    except Exception as e:
        logger.warning(f'Failed to clear tenant context: {e}')


async def get_tenant_context(conn) -> Optional[str]:
    """Get the current tenant context from the database connection.

    Args:
        conn: asyncpg connection object

    Returns:
        The current tenant ID or None if not set
    """
    if not RLS_ENABLED:
        return None

    try:
        result = await conn.fetchval(
            "SELECT current_setting('app.current_tenant_id', true)"
        )
        return result
    except Exception as e:
        logger.debug(f'Failed to get tenant context: {e}')
        return None


@asynccontextmanager
async def tenant_scope(tenant_id: str):
    """Context manager for tenant-scoped database operations.

    Acquires a connection from the pool, sets the tenant context,
    yields the connection, and ensures the context is cleared afterward.

    This is the recommended way to perform tenant-scoped operations
    when RLS is enabled.

    Args:
        tenant_id: The tenant UUID to scope operations to

    Yields:
        asyncpg connection with tenant context set

    Example:
        async with tenant_scope("tenant-uuid") as conn:
            results = await conn.fetch("SELECT * FROM workers")

    Raises:
        RuntimeError: If database pool is not available
    """
    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database pool not available')

    conn = await pool.acquire()
    try:
        await set_tenant_context(conn, tenant_id)
        yield conn
    finally:
        try:
            await clear_tenant_context(conn)
        finally:
            await pool.release(conn)


@asynccontextmanager
async def admin_scope():
    """Context manager for admin operations that bypass RLS.

    This acquires a connection without setting tenant context, which
    allows access to all rows when RLS policies allow NULL context.

    WARNING: Use sparingly and only for legitimate administrative operations
    like migrations, auditing, or cross-tenant reporting.

    Yields:
        asyncpg connection with admin-level access

    Example:
        async with admin_scope() as conn:
            # Can access all tenants' data
            results = await conn.fetch("SELECT COUNT(*) FROM workers")
    """
    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database pool not available')

    conn = await pool.acquire()
    try:
        # Clear any existing tenant context to use admin bypass
        if RLS_ENABLED:
            await conn.execute('RESET app.current_tenant_id')
        yield conn
    finally:
        await pool.release(conn)


async def db_execute_as_tenant(tenant_id: str, query: str, *args) -> Any:
    """Execute a query with tenant context.

    Convenience function for executing a single query within tenant scope.

    Args:
        tenant_id: The tenant UUID
        query: SQL query to execute
        *args: Query parameters

    Returns:
        Query result
    """
    async with tenant_scope(tenant_id) as conn:
        return await conn.execute(query, *args)


async def db_fetch_as_tenant(tenant_id: str, query: str, *args) -> List[Any]:
    """Fetch rows with tenant context.

    Convenience function for fetching rows within tenant scope.

    Args:
        tenant_id: The tenant UUID
        query: SQL query to execute
        *args: Query parameters

    Returns:
        List of rows
    """
    async with tenant_scope(tenant_id) as conn:
        return await conn.fetch(query, *args)


async def db_fetchrow_as_tenant(
    tenant_id: str, query: str, *args
) -> Optional[Any]:
    """Fetch a single row with tenant context.

    Args:
        tenant_id: The tenant UUID
        query: SQL query to execute
        *args: Query parameters

    Returns:
        Single row or None
    """
    async with tenant_scope(tenant_id) as conn:
        return await conn.fetchrow(query, *args)


async def db_fetchval_as_tenant(
    tenant_id: str, query: str, *args
) -> Optional[Any]:
    """Fetch a single value with tenant context.

    Args:
        tenant_id: The tenant UUID
        query: SQL query to execute
        *args: Query parameters

    Returns:
        Single value or None
    """
    async with tenant_scope(tenant_id) as conn:
        return await conn.fetchval(query, *args)


# ========================================
# RLS Migration Support
# ========================================


async def db_run_migrations(
    migrations_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run SQL migration files from the migrations directory.

    Executes all .sql files in the migrations directory that haven't been
    applied yet, tracking them in the schema_migrations table.

    Args:
        migrations_dir: Path to migrations directory (default: a2a_server/migrations)

    Returns:
        Dict with migration results:
            - applied: List of newly applied migrations
            - skipped: List of already applied migrations
            - failed: List of failed migrations with errors
    """
    from pathlib import Path

    if migrations_dir is None:
        migrations_path = Path(__file__).parent / 'migrations'
    else:
        migrations_path = Path(migrations_dir)

    if not migrations_path.exists():
        logger.warning(f'Migrations directory not found: {migrations_path}')
        return {'applied': [], 'skipped': [], 'failed': []}

    pool = await get_pool()
    if not pool:
        raise RuntimeError('Database pool not available')

    results: Dict[str, List[Any]] = {'applied': [], 'skipped': [], 'failed': []}

    async with pool.acquire() as conn:
        # Ensure schema_migrations table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                checksum TEXT
            )
        """)

        # Get already applied migrations
        applied = await conn.fetch(
            'SELECT migration_name FROM schema_migrations'
        )
        applied_set = {row['migration_name'] for row in applied}

        # Get all .sql files sorted by name
        migration_files = sorted(migrations_path.glob('*.sql'))

        for migration_file in migration_files:
            migration_name = migration_file.stem

            if migration_name in applied_set:
                results['skipped'].append(migration_name)
                logger.info(
                    f'Skipping already applied migration: {migration_name}'
                )
                continue

            try:
                logger.info(f'Applying migration: {migration_name}')

                # Read and execute migration
                sql_content = migration_file.read_text()

                # Execute in a transaction
                async with conn.transaction():
                    await conn.execute(sql_content)

                    # Record migration
                    await conn.execute(
                        """
                        INSERT INTO schema_migrations (migration_name, checksum)
                        VALUES ($1, $2)
                        ON CONFLICT (migration_name) DO NOTHING
                        """,
                        migration_name,
                        str(hash(sql_content)),
                    )

                results['applied'].append(migration_name)
                logger.info(f'Successfully applied migration: {migration_name}')

            except Exception as e:
                logger.error(f'Failed to apply migration {migration_name}: {e}')
                results['failed'].append(
                    {'name': migration_name, 'error': str(e)}
                )

    return results


async def db_enable_rls() -> Dict[str, Any]:
    """Enable RLS by running the enable_rls.sql migration.

    This enables Row-Level Security on all tenant-scoped tables:
    - workers
    - codebases
    - tasks
    - sessions

    Returns:
        Dict with migration result
    """
    from pathlib import Path

    migrations_path = Path(__file__).parent / 'migrations'
    enable_rls_file = migrations_path / 'enable_rls.sql'

    if not enable_rls_file.exists():
        return {
            'status': 'error',
            'message': f'RLS migration not found: {enable_rls_file}',
        }

    pool = await get_pool()
    if not pool:
        return {'status': 'error', 'message': 'Database pool not available'}

    try:
        async with pool.acquire() as conn:
            sql_content = enable_rls_file.read_text()
            await conn.execute(sql_content)

        logger.info('RLS enabled successfully')
        return {
            'status': 'success',
            'message': 'RLS enabled on all tenant-scoped tables',
        }
    except Exception as e:
        logger.error(f'Failed to enable RLS: {e}')
        return {'status': 'error', 'message': str(e)}


async def db_disable_rls() -> Dict[str, Any]:
    """Disable RLS by running the disable_rls.sql migration.

    This disables Row-Level Security and removes all policies.

    Returns:
        Dict with migration result
    """
    from pathlib import Path

    migrations_path = Path(__file__).parent / 'migrations'
    disable_rls_file = migrations_path / 'disable_rls.sql'

    if not disable_rls_file.exists():
        return {
            'status': 'error',
            'message': f'RLS rollback not found: {disable_rls_file}',
        }

    pool = await get_pool()
    if not pool:
        return {'status': 'error', 'message': 'Database pool not available'}

    try:
        async with pool.acquire() as conn:
            sql_content = disable_rls_file.read_text()
            await conn.execute(sql_content)

        logger.info('RLS disabled successfully')
        return {
            'status': 'success',
            'message': 'RLS disabled on all tenant-scoped tables',
        }
    except Exception as e:
        logger.error(f'Failed to disable RLS: {e}')
        return {'status': 'error', 'message': str(e)}


async def get_rls_status() -> Dict[str, Any]:
    """Get the current RLS status for all tenant-scoped tables.

    Returns:
        Dict with RLS status for each table and overall configuration
    """
    pool = await get_pool()
    if not pool:
        return {'enabled': False, 'database_available': False, 'tables': {}}

    try:
        async with pool.acquire() as conn:
            # Check RLS status on each table
            rows = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    rowsecurity as rls_enabled,
                    forcerowsecurity as rls_forced
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename IN ('workers', 'codebases', 'tasks', 'sessions')
            """)

            tables = {}
            all_enabled = True

            for row in rows:
                tables[row['tablename']] = {
                    'rls_enabled': row['rls_enabled'],
                    'rls_forced': row['rls_forced'],
                }
                if not row['rls_enabled']:
                    all_enabled = False

            # Check for policies
            policies = await conn.fetch("""
                SELECT tablename, policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                AND tablename IN ('workers', 'codebases', 'tasks', 'sessions')
            """)

            policy_count: Dict[str, int] = {}
            for policy in policies:
                table = policy['tablename']
                if table not in policy_count:
                    policy_count[table] = 0
                policy_count[table] += 1

            for table in tables:
                tables[table]['policy_count'] = policy_count.get(table, 0)

            return {
                'enabled': all_enabled and len(tables) == 4,
                'database_available': True,
                'rls_env_enabled': RLS_ENABLED,
                'strict_mode': RLS_STRICT_MODE,
                'tables': tables,
            }

    except Exception as e:
        logger.error(f'Failed to get RLS status: {e}')
        return {
            'enabled': False,
            'database_available': True,
            'error': str(e),
            'tables': {},
        }


def init_rls_config() -> None:
    """Initialize RLS configuration from environment.

    Call this at application startup to configure RLS settings.
    Updates the module-level RLS_ENABLED and RLS_STRICT_MODE variables.
    """
    global RLS_ENABLED, RLS_STRICT_MODE

    RLS_ENABLED = os.environ.get('RLS_ENABLED', 'false').lower() == 'true'
    RLS_STRICT_MODE = (
        os.environ.get('RLS_STRICT_MODE', 'false').lower() == 'true'
    )

    logger.info(
        f'RLS Configuration: enabled={RLS_ENABLED}, strict={RLS_STRICT_MODE}'
    )


# ========================================
# Email Logging Operations
# ========================================


async def db_log_inbound_email(
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    session_id: Optional[str] = None,
    codebase_id: Optional[str] = None,
    task_id: Optional[str] = None,
    sender_ip: Optional[str] = None,
    spf_result: Optional[str] = None,
    status: str = 'received',
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
) -> Optional[str]:
    """
    Log an inbound email to the database.

    Args:
        from_email: Sender email address
        to_email: Recipient email address (the reply-to address)
        subject: Email subject
        body_text: Plain text body
        body_html: HTML body (optional)
        session_id: Parsed session ID from reply-to address
        codebase_id: Parsed codebase ID from reply-to address
        task_id: ID of continuation task created (if any)
        sender_ip: IP address of sender (from SendGrid)
        spf_result: SPF validation result
        status: Processing status (received, processed, failed)
        error: Error message if processing failed
        metadata: Additional metadata
        tenant_id: Tenant ID for multi-tenant isolation

    Returns:
        The email ID if logged successfully, None otherwise
    """
    pool = await get_pool()
    if not pool:
        return None

    email_id = str(uuid.uuid4())

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO inbound_emails (
                    id, from_email, to_email, subject, body_text, body_html,
                    session_id, codebase_id, task_id, sender_ip, spf_result,
                    status, error, metadata, received_at, processed_at, tenant_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW(), $15, $16)
                """,
                email_id,
                from_email,
                to_email,
                subject,
                body_text,
                body_html,
                session_id,
                codebase_id,
                task_id,
                sender_ip,
                spf_result,
                status,
                error,
                json.dumps(metadata or {}),
                datetime.utcnow()
                if status in ('processed', 'failed')
                else None,
                tenant_id,
            )
            logger.debug(f'Logged inbound email {email_id} from {from_email}')
            return email_id
    except Exception as e:
        logger.error(f'Failed to log inbound email: {e}')
        return None


async def db_update_inbound_email(
    email_id: str,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """
    Update an inbound email record after processing.

    Args:
        email_id: The email record ID
        task_id: The continuation task ID created
        status: New status (processed, failed)
        error: Error message if failed

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            updates = []
            params = []
            param_idx = 1

            if task_id is not None:
                updates.append(f'task_id = ${param_idx}')
                params.append(task_id)
                param_idx += 1

            if status is not None:
                updates.append(f'status = ${param_idx}')
                params.append(status)
                param_idx += 1
                if status in ('processed', 'failed'):
                    updates.append('processed_at = NOW()')

            if error is not None:
                updates.append(f'error = ${param_idx}')
                params.append(error)
                param_idx += 1

            if not updates:
                return True

            params.append(email_id)
            query = f'UPDATE inbound_emails SET {", ".join(updates)} WHERE id = ${param_idx}'
            await conn.execute(query, *params)
            return True
    except Exception as e:
        logger.error(f'Failed to update inbound email {email_id}: {e}')
        return False


async def db_log_outbound_email(
    to_email: str,
    from_email: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    reply_to: Optional[str] = None,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    codebase_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    status: str = 'queued',
    sendgrid_message_id: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
) -> Optional[str]:
    """
    Log an outbound email to the database.

    Args:
        to_email: Recipient email address
        from_email: Sender email address
        subject: Email subject
        body_html: HTML body
        body_text: Plain text body
        reply_to: Reply-to address for threading
        task_id: Related task ID
        session_id: Related session ID
        codebase_id: Related codebase ID
        worker_id: Worker that sent the email
        status: Email status (queued, sent, failed)
        sendgrid_message_id: SendGrid message ID if sent
        error: Error message if failed
        metadata: Additional metadata
        tenant_id: Tenant ID for multi-tenant isolation

    Returns:
        The email ID if logged successfully, None otherwise
    """
    pool = await get_pool()
    if not pool:
        return None

    email_id = str(uuid.uuid4())

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO outbound_emails (
                    id, to_email, from_email, reply_to, subject, body_html, body_text,
                    task_id, session_id, codebase_id, worker_id, status,
                    sendgrid_message_id, error, metadata, created_at, sent_at, tenant_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), $16, $17)
                """,
                email_id,
                to_email,
                from_email,
                reply_to,
                subject,
                body_html,
                body_text,
                task_id,
                session_id,
                codebase_id,
                worker_id,
                status,
                sendgrid_message_id,
                error,
                json.dumps(metadata or {}),
                datetime.utcnow() if status == 'sent' else None,
                tenant_id,
            )
            logger.debug(f'Logged outbound email {email_id} to {to_email}')
            return email_id
    except Exception as e:
        logger.error(f'Failed to log outbound email: {e}')
        return None


async def db_update_outbound_email(
    email_id: str,
    status: Optional[str] = None,
    sendgrid_message_id: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """
    Update an outbound email record after sending.

    Args:
        email_id: The email record ID
        status: New status (sent, failed)
        sendgrid_message_id: SendGrid message ID if sent
        error: Error message if failed

    Returns:
        True if updated successfully
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            updates = []
            params = []
            param_idx = 1

            if status is not None:
                updates.append(f'status = ${param_idx}')
                params.append(status)
                param_idx += 1
                if status == 'sent':
                    updates.append('sent_at = NOW()')

            if sendgrid_message_id is not None:
                updates.append(f'sendgrid_message_id = ${param_idx}')
                params.append(sendgrid_message_id)
                param_idx += 1

            if error is not None:
                updates.append(f'error = ${param_idx}')
                params.append(error)
                param_idx += 1

            if not updates:
                return True

            params.append(email_id)
            query = f'UPDATE outbound_emails SET {", ".join(updates)} WHERE id = ${param_idx}'
            await conn.execute(query, *params)
            return True
    except Exception as e:
        logger.error(f'Failed to update outbound email {email_id}: {e}')
        return False


async def db_list_inbound_emails(
    session_id: Optional[str] = None,
    from_email: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List inbound emails with optional filtering.

    Args:
        session_id: Filter by session ID
        from_email: Filter by sender email
        status: Filter by status
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of inbound email records
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            conditions = []
            params = []
            param_idx = 1

            if session_id:
                conditions.append(f'session_id = ${param_idx}')
                params.append(session_id)
                param_idx += 1

            if from_email:
                conditions.append(f'from_email = ${param_idx}')
                params.append(from_email)
                param_idx += 1

            if status:
                conditions.append(f'status = ${param_idx}')
                params.append(status)
                param_idx += 1

            where_clause = (
                f'WHERE {" AND ".join(conditions)}' if conditions else ''
            )
            params.extend([limit, offset])

            query = f"""
                SELECT * FROM inbound_emails
                {where_clause}
                ORDER BY received_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list inbound emails: {e}')
        return []


async def db_list_outbound_emails(
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    to_email: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List outbound emails with optional filtering.

    Args:
        task_id: Filter by task ID
        session_id: Filter by session ID
        to_email: Filter by recipient email
        status: Filter by status
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of outbound email records
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            conditions = []
            params = []
            param_idx = 1

            if task_id:
                conditions.append(f'task_id = ${param_idx}')
                params.append(task_id)
                param_idx += 1

            if session_id:
                conditions.append(f'session_id = ${param_idx}')
                params.append(session_id)
                param_idx += 1

            if to_email:
                conditions.append(f'to_email = ${param_idx}')
                params.append(to_email)
                param_idx += 1

            if status:
                conditions.append(f'status = ${param_idx}')
                params.append(status)
                param_idx += 1

            where_clause = (
                f'WHERE {" AND ".join(conditions)}' if conditions else ''
            )
            params.extend([limit, offset])

            query = f"""
                SELECT * FROM outbound_emails
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list outbound emails: {e}')
        return []


# ============================================================================
# PRD Chat Sessions Database Functions
# ============================================================================


async def db_upsert_prd_chat_session(
    codebase_id: str,
    session_id: str,
    title: Optional[str] = None,
) -> bool:
    """Upsert a PRD chat session link."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prd_chat_sessions (codebase_id, session_id, title, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (codebase_id, session_id)
                DO UPDATE SET updated_at = NOW(), title = COALESCE($3, prd_chat_sessions.title)
                """,
                codebase_id,
                session_id,
                title,
            )
        return True
    except Exception as e:
        logger.error(f'Failed to upsert PRD chat session: {e}')
        return False


async def db_list_prd_chat_sessions(
    codebase_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """List PRD chat sessions for a codebase."""
    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.id, p.codebase_id, p.session_id, p.title, p.created_at, p.updated_at,
                       (SELECT COUNT(*) FROM session_messages WHERE session_id = p.session_id) as message_count
                FROM prd_chat_sessions p
                WHERE p.codebase_id = $1
                ORDER BY p.updated_at DESC
                LIMIT $2
                """,
                codebase_id,
                limit,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f'Failed to list PRD chat sessions: {e}')
        return []


# ============================================================================
# Ralph Runs Database Functions
# ============================================================================


async def db_create_ralph_run(
    run_id: str,
    prd: Dict[str, Any],
    codebase_id: Optional[str] = None,
    model: Optional[str] = None,
    max_iterations: int = 10,
    run_mode: str = 'sequential',
    max_parallel: int = 3,
    tenant_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Create a new Ralph run in the database.

    Args:
        run_id: Unique run identifier
        prd: PRD document as dict
        codebase_id: Target codebase ID
        model: AI model to use
        max_iterations: Maximum iterations per story
        run_mode: 'sequential' or 'parallel'
        max_parallel: Max concurrent stories in parallel mode
        tenant_id: Tenant ID for multi-tenancy

    Returns:
        Created run record or None on failure
    """
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ralph_runs (
                    id, prd, codebase_id, model, status,
                    max_iterations, run_mode, max_parallel, tenant_id
                ) VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7, $8)
                RETURNING *
                """,
                run_id,
                json.dumps(prd),
                codebase_id,
                model,
                max_iterations,
                run_mode,
                max_parallel,
                tenant_id,
            )
            result = dict(row)
            # Parse JSONB fields
            if result.get('prd'):
                result['prd'] = (
                    json.loads(result['prd'])
                    if isinstance(result['prd'], str)
                    else result['prd']
                )
            if result.get('story_results'):
                result['story_results'] = (
                    json.loads(result['story_results'])
                    if isinstance(result['story_results'], str)
                    else result['story_results']
                )
            if result.get('logs'):
                result['logs'] = (
                    json.loads(result['logs'])
                    if isinstance(result['logs'], str)
                    else result['logs']
                )
            return result
    except Exception as e:
        logger.error(f'Failed to create Ralph run: {e}')
        return None


async def db_get_ralph_run(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a Ralph run by ID.

    Args:
        run_id: Run ID to retrieve

    Returns:
        Run record or None if not found
    """
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM ralph_runs WHERE id = $1',
                run_id,
            )
            if not row:
                return None
            result = dict(row)
            # Parse JSONB fields
            if result.get('prd'):
                result['prd'] = (
                    json.loads(result['prd'])
                    if isinstance(result['prd'], str)
                    else result['prd']
                )
            if result.get('story_results'):
                result['story_results'] = (
                    json.loads(result['story_results'])
                    if isinstance(result['story_results'], str)
                    else result['story_results']
                )
            if result.get('logs'):
                result['logs'] = (
                    json.loads(result['logs'])
                    if isinstance(result['logs'], str)
                    else result['logs']
                )
            return result
    except Exception as e:
        logger.error(f'Failed to get Ralph run {run_id}: {e}')
        return None


async def db_update_ralph_run(
    run_id: str,
    status: Optional[str] = None,
    current_iteration: Optional[int] = None,
    story_results: Optional[List[Dict[str, Any]]] = None,
    logs: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a Ralph run.

    Args:
        run_id: Run ID to update
        status: New status
        current_iteration: Current iteration number
        story_results: Updated story results
        logs: Updated logs
        error: Error message if failed
        started_at: Start timestamp
        completed_at: Completion timestamp

    Returns:
        Updated run record or None on failure
    """
    pool = await get_pool()
    if not pool:
        return None

    try:
        updates = []
        params = []
        param_idx = 1

        if status is not None:
            updates.append(f'status = ${param_idx}')
            params.append(status)
            param_idx += 1

        if current_iteration is not None:
            updates.append(f'current_iteration = ${param_idx}')
            params.append(current_iteration)
            param_idx += 1

        if story_results is not None:
            updates.append(f'story_results = ${param_idx}')
            params.append(json.dumps(story_results))
            param_idx += 1

        if logs is not None:
            updates.append(f'logs = ${param_idx}')
            params.append(json.dumps(logs))
            param_idx += 1

        if error is not None:
            updates.append(f'error = ${param_idx}')
            params.append(error)
            param_idx += 1

        if started_at is not None:
            updates.append(f'started_at = ${param_idx}')
            params.append(started_at)
            param_idx += 1

        if completed_at is not None:
            updates.append(f'completed_at = ${param_idx}')
            params.append(completed_at)
            param_idx += 1

        if not updates:
            return await db_get_ralph_run(run_id)

        params.append(run_id)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE ralph_runs
                SET {', '.join(updates)}
                WHERE id = ${param_idx}
                RETURNING *
                """,
                *params,
            )
            if not row:
                return None
            result = dict(row)
            # Parse JSONB fields
            if result.get('prd'):
                result['prd'] = (
                    json.loads(result['prd'])
                    if isinstance(result['prd'], str)
                    else result['prd']
                )
            if result.get('story_results'):
                result['story_results'] = (
                    json.loads(result['story_results'])
                    if isinstance(result['story_results'], str)
                    else result['story_results']
                )
            if result.get('logs'):
                result['logs'] = (
                    json.loads(result['logs'])
                    if isinstance(result['logs'], str)
                    else result['logs']
                )
            return result
    except Exception as e:
        logger.error(f'Failed to update Ralph run {run_id}: {e}')
        return None


async def db_list_ralph_runs(
    status: Optional[str] = None,
    codebase_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List Ralph runs with optional filtering.

    Args:
        status: Filter by status
        codebase_id: Filter by codebase
        tenant_id: Filter by tenant
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of Ralph run records
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        conditions = []
        params = []
        param_idx = 1

        if status:
            conditions.append(f'status = ${param_idx}')
            params.append(status)
            param_idx += 1

        if codebase_id:
            conditions.append(f'codebase_id = ${param_idx}')
            params.append(codebase_id)
            param_idx += 1

        if tenant_id:
            conditions.append(f'tenant_id = ${param_idx}')
            params.append(tenant_id)
            param_idx += 1

        where_clause = f'WHERE {" AND ".join(conditions)}' if conditions else ''
        params.extend([limit, offset])

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM ralph_runs
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params,
            )
            results = []
            for row in rows:
                result = dict(row)
                # Parse JSONB fields
                if result.get('prd'):
                    result['prd'] = (
                        json.loads(result['prd'])
                        if isinstance(result['prd'], str)
                        else result['prd']
                    )
                if result.get('story_results'):
                    result['story_results'] = (
                        json.loads(result['story_results'])
                        if isinstance(result['story_results'], str)
                        else result['story_results']
                    )
                if result.get('logs'):
                    result['logs'] = (
                        json.loads(result['logs'])
                        if isinstance(result['logs'], str)
                        else result['logs']
                    )
                results.append(result)
            return results
    except Exception as e:
        logger.error(f'Failed to list Ralph runs: {e}')
        return []


async def db_delete_ralph_run(run_id: str) -> bool:
    """
    Delete a Ralph run.

    Args:
        run_id: Run ID to delete

    Returns:
        True if deleted, False otherwise
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                'DELETE FROM ralph_runs WHERE id = $1',
                run_id,
            )
            return result == 'DELETE 1'
    except Exception as e:
        logger.error(f'Failed to delete Ralph run {run_id}: {e}')
        return False


async def db_add_ralph_log(
    run_id: str,
    log_type: str,
    message: str,
    story_id: Optional[str] = None,
) -> bool:
    """
    Add a log entry to a Ralph run.

    Args:
        run_id: Run ID
        log_type: Log type (info, error, story_pass, etc.)
        message: Log message
        story_id: Optional story ID

    Returns:
        True if added, False otherwise
    """
    pool = await get_pool()
    if not pool:
        return False

    try:
        log_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'type': log_type,
            'message': message,
            'story_id': story_id,
        }

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ralph_runs
                SET logs = logs || $1::jsonb
                WHERE id = $2
                """,
                json.dumps([log_entry]),
                run_id,
            )
            return True
    except Exception as e:
        logger.error(f'Failed to add log to Ralph run {run_id}: {e}')
        return False


# ---------------------------------------------------------------------------
# Worker Profiles CRUD
# ---------------------------------------------------------------------------

async def db_list_worker_profiles(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    builtin_only: bool = False,
) -> List[Dict[str, Any]]:
    """List worker profiles visible to the caller.

    Returns builtin profiles + tenant/user-owned custom profiles.
    """
    pool = await get_pool()
    if not pool:
        return []

    try:
        clauses = []
        params: list = []
        idx = 1

        if builtin_only:
            clauses.append('is_builtin = TRUE')
        else:
            # Always include builtins
            parts = ['is_builtin = TRUE']
            if tenant_id:
                parts.append(f'tenant_id = ${idx}')
                params.append(tenant_id)
                idx += 1
            if user_id:
                parts.append(f'user_id = ${idx}')
                params.append(user_id)
                idx += 1
            clauses.append(f"({' OR '.join(parts)})")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        query = f'SELECT * FROM worker_profiles {where} ORDER BY is_builtin DESC, name ASC'

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f'Failed to list worker profiles: {e}')
        return []


async def db_get_worker_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """Get a single worker profile by ID or slug."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM worker_profiles WHERE id = $1 OR slug = $1',
                profile_id,
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f'Failed to get worker profile {profile_id}: {e}')
        return None


async def db_create_worker_profile(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new worker profile. Returns the created row."""
    pool = await get_pool()
    if not pool:
        return None

    try:
        profile_id = profile.get('id') or str(uuid.uuid4())
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO worker_profiles
                    (id, slug, name, description, system_prompt,
                     default_capabilities, default_model_tier, default_model_ref,
                     default_agent_type, icon, color, is_builtin, user_id, tenant_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                RETURNING *
                """,
                profile_id,
                profile.get('slug'),
                profile.get('name'),
                profile.get('description', ''),
                profile.get('system_prompt', ''),
                json.dumps(profile.get('default_capabilities', [])),
                profile.get('default_model_tier', 'balanced'),
                profile.get('default_model_ref'),
                profile.get('default_agent_type', 'build'),
                profile.get('icon', '🤖'),
                profile.get('color', '#6366f1'),
                profile.get('is_builtin', False),
                profile.get('user_id'),
                profile.get('tenant_id'),
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f'Failed to create worker profile: {e}')
        return None


async def db_update_worker_profile(
    profile_id: str, updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update a worker profile. Returns the updated row.

    Cannot update builtin profiles except for non-critical fields.
    """
    pool = await get_pool()
    if not pool:
        return None

    allowed_fields = {
        'name', 'slug', 'description', 'system_prompt',
        'default_capabilities', 'default_model_tier', 'default_model_ref',
        'default_agent_type', 'icon', 'color',
    }

    set_parts = []
    params: list = []
    idx = 1

    for field, value in updates.items():
        if field not in allowed_fields:
            continue
        if field == 'default_capabilities':
            value = json.dumps(value) if isinstance(value, (list, dict)) else value
        set_parts.append(f'{field} = ${idx}')
        params.append(value)
        idx += 1

    if not set_parts:
        return await db_get_worker_profile(profile_id)

    set_parts.append(f'updated_at = ${idx}')
    params.append(datetime.utcnow())
    idx += 1

    params.append(profile_id)

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE worker_profiles
                SET {', '.join(set_parts)}
                WHERE id = ${idx} AND is_builtin = FALSE
                RETURNING *
                """,
                *params,
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f'Failed to update worker profile {profile_id}: {e}')
        return None


async def db_delete_worker_profile(profile_id: str) -> bool:
    """Delete a custom worker profile. Builtin profiles cannot be deleted."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                'DELETE FROM worker_profiles WHERE id = $1 AND is_builtin = FALSE',
                profile_id,
            )
            return result == 'DELETE 1'
    except Exception as e:
        logger.error(f'Failed to delete worker profile {profile_id}: {e}')
        return False


async def db_set_worker_profile(worker_id: str, profile_id: Optional[str]) -> bool:
    """Assign (or clear) a profile on a worker."""
    pool = await get_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                'UPDATE workers SET profile_id = $1 WHERE worker_id = $2',
                profile_id,
                worker_id,
            )
        return True
    except Exception as e:
        logger.error(f'Failed to set worker profile: {e}')
        return False
