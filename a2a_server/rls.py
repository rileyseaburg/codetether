"""
PostgreSQL Row-Level Security (RLS) Utilities for A2A Server.

This module provides utilities for managing PostgreSQL RLS tenant context
in multi-tenant deployments. RLS provides defense-in-depth database-level
isolation beyond application-level filtering.

Security Architecture:
- Zero Trust: Tenant context must be explicitly set before each operation
- Defense in Depth: RLS adds database-level protection beyond app-level filtering
- Fine-grained Access: Per-table, per-operation policies
- Audit Logging: RLS violations are logged for security monitoring

Usage:
    # Using context manager (recommended)
    from a2a_server.rls import tenant_scope

    async with tenant_scope(tenant_id) as conn:
        results = await conn.fetch("SELECT * FROM workers")

    # Using explicit functions
    from a2a_server.rls import set_tenant_context, clear_tenant_context

    conn = await pool.acquire()
    await set_tenant_context(conn, tenant_id)
    try:
        results = await conn.fetch("SELECT * FROM workers")
    finally:
        await clear_tenant_context(conn)

Configuration:
    RLS_ENABLED: Environment variable to enable/disable RLS (default: false)
    RLS_STRICT_MODE: Require tenant context for all queries (default: false)
    RLS_AUDIT_ENABLED: Enable audit logging of violations (default: true)

See also:
    - a2a_server/database.py: Core database functions with RLS support
    - a2a_server/migrations/enable_rls.sql: RLS migration script
    - a2a_server/migrations/disable_rls.sql: RLS rollback script
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configuration from environment
RLS_ENABLED = os.environ.get('RLS_ENABLED', 'false').lower() == 'true'
RLS_STRICT_MODE = os.environ.get('RLS_STRICT_MODE', 'false').lower() == 'true'
RLS_AUDIT_ENABLED = os.environ.get('RLS_AUDIT_ENABLED', 'true').lower() == 'true'


# ============================================
# Exception Classes
# ============================================


class RLSError(Exception):
    """Base exception for RLS-related errors."""
    pass


class TenantContextError(RLSError):
    """Raised when tenant context is missing or invalid."""
    pass


class RLSPolicyViolation(RLSError):
    """Raised when an RLS policy blocks an operation."""
    pass


# ============================================
# Re-export core functions from database module
# ============================================

# Import and re-export the core RLS functions from database.py
# This provides a clean, focused API for RLS operations
from .database import (
    set_tenant_context,
    clear_tenant_context,
    get_tenant_context,
    tenant_scope,
    admin_scope,
    db_execute_as_tenant,
    db_fetch_as_tenant,
    db_fetchrow_as_tenant,
    db_fetchval_as_tenant,
    db_run_migrations,
    db_enable_rls,
    db_disable_rls,
    get_rls_status,
    init_rls_config,
    RLS_ENABLED as DB_RLS_ENABLED,
    RLS_STRICT_MODE as DB_RLS_STRICT_MODE,
)


# ============================================
# RLS Audit Functions
# ============================================


async def log_rls_violation(
    table_name: str,
    operation: str,
    expected_tenant: str,
    actual_tenant: Optional[str],
    details: Optional[Dict[str, Any]] = None
) -> None:
    """Log an RLS policy violation for security auditing.

    This function logs to both the application logger and the database
    audit table (if available).

    Args:
        table_name: Name of the table where violation occurred
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE)
        expected_tenant: The tenant that was expected
        actual_tenant: The actual tenant_id on the row
        details: Additional context about the violation
    """
    if not RLS_AUDIT_ENABLED:
        return

    # Always log to application logger
    logger.warning(
        f"RLS violation: {table_name}/{operation} "
        f"expected={expected_tenant} actual={actual_tenant} "
        f"details={details}"
    )

    # Attempt to log to database
    from .database import get_pool

    pool = await get_pool()
    if not pool:
        return

    try:
        async with pool.acquire() as conn:
            # Check if audit table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'rls_audit_log'
                )
            """)

            if table_exists:
                import json
                await conn.execute(
                    """
                    INSERT INTO rls_audit_log
                    (table_name, operation, tenant_id, row_tenant_id, details)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    table_name,
                    operation,
                    expected_tenant,
                    actual_tenant,
                    json.dumps(details) if details else '{}'
                )
    except Exception as e:
        # Don't fail on audit log errors
        logger.debug(f"Failed to log RLS violation to database: {e}")


async def get_rls_audit_log(
    limit: int = 100,
    tenant_id: Optional[str] = None,
    table_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve RLS audit log entries.

    Args:
        limit: Maximum number of entries to return
        tenant_id: Filter by tenant ID
        table_name: Filter by table name

    Returns:
        List of audit log entries
    """
    from .database import get_pool

    pool = await get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            # Check if audit table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'rls_audit_log'
                )
            """)

            if not table_exists:
                return []

            query = "SELECT * FROM rls_audit_log WHERE 1=1"
            params: List[Any] = []
            param_idx = 1

            if tenant_id:
                query += f" AND tenant_id = ${param_idx}"
                params.append(tenant_id)
                param_idx += 1

            if table_name:
                query += f" AND table_name = ${param_idx}"
                params.append(table_name)
                param_idx += 1

            query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
            params.append(limit)

            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to get RLS audit log: {e}")
        return []


async def clear_rls_audit_log(
    before_days: int = 30,
    tenant_id: Optional[str] = None
) -> int:
    """Clear old RLS audit log entries.

    Args:
        before_days: Delete entries older than this many days
        tenant_id: Only delete entries for this tenant (optional)

    Returns:
        Number of entries deleted
    """
    from .database import get_pool

    pool = await get_pool()
    if not pool:
        return 0

    try:
        async with pool.acquire() as conn:
            # Check if audit table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'rls_audit_log'
                )
            """)

            if not table_exists:
                return 0

            if tenant_id:
                result = await conn.execute(
                    """
                    DELETE FROM rls_audit_log
                    WHERE timestamp < NOW() - INTERVAL '$1 days'
                    AND tenant_id = $2
                    """,
                    before_days,
                    tenant_id
                )
            else:
                result = await conn.execute(
                    """
                    DELETE FROM rls_audit_log
                    WHERE timestamp < NOW() - INTERVAL '$1 days'
                    """,
                    before_days
                )

            # Parse "DELETE X" result
            if result and 'DELETE' in result:
                try:
                    return int(result.split()[1])
                except (IndexError, ValueError):
                    return 0
            return 0

    except Exception as e:
        logger.error(f"Failed to clear RLS audit log: {e}")
        return 0


# ============================================
# RLS Validation Helpers
# ============================================


def validate_tenant_id(tenant_id: Optional[str]) -> bool:
    """Validate a tenant ID format.

    Args:
        tenant_id: The tenant ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not tenant_id:
        return False

    # Basic UUID format validation
    import re
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(tenant_id))


def require_tenant_context(func):
    """Decorator to require tenant context for a function.

    Use this decorator on functions that must have tenant context set.
    It will raise TenantContextError if RLS_STRICT_MODE is enabled
    and no tenant context is available.

    Example:
        @require_tenant_context
        async def get_workers(conn, tenant_id: str):
            # This will only execute if tenant context is valid
            return await conn.fetch("SELECT * FROM workers")
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if RLS_STRICT_MODE:
            # Check if tenant_id is in kwargs or positional args
            tenant_id = kwargs.get('tenant_id')
            if not tenant_id and len(args) > 1:
                tenant_id = args[1]  # Assume second arg is tenant_id

            if not tenant_id:
                raise TenantContextError(
                    "Tenant context required in strict mode"
                )

            if not validate_tenant_id(tenant_id):
                raise TenantContextError(
                    f"Invalid tenant ID format: {tenant_id}"
                )

        return await func(*args, **kwargs)

    return wrapper


# ============================================
# Module Initialization
# ============================================


def refresh_config() -> None:
    """Refresh RLS configuration from environment.

    Call this after changing environment variables to update the module state.
    """
    global RLS_ENABLED, RLS_STRICT_MODE, RLS_AUDIT_ENABLED

    RLS_ENABLED = os.environ.get('RLS_ENABLED', 'false').lower() == 'true'
    RLS_STRICT_MODE = os.environ.get('RLS_STRICT_MODE', 'false').lower() == 'true'
    RLS_AUDIT_ENABLED = os.environ.get('RLS_AUDIT_ENABLED', 'true').lower() == 'true'

    # Also update the database module
    init_rls_config()

    logger.info(
        f"RLS Configuration refreshed: enabled={RLS_ENABLED}, "
        f"strict={RLS_STRICT_MODE}, audit={RLS_AUDIT_ENABLED}"
    )


# ============================================
# Public API
# ============================================

__all__ = [
    # Exceptions
    'RLSError',
    'TenantContextError',
    'RLSPolicyViolation',

    # Core functions (re-exported from database)
    'set_tenant_context',
    'clear_tenant_context',
    'get_tenant_context',
    'tenant_scope',
    'admin_scope',

    # Query helpers
    'db_execute_as_tenant',
    'db_fetch_as_tenant',
    'db_fetchrow_as_tenant',
    'db_fetchval_as_tenant',

    # Migration functions
    'db_run_migrations',
    'db_enable_rls',
    'db_disable_rls',
    'get_rls_status',
    'init_rls_config',

    # Audit functions
    'log_rls_violation',
    'get_rls_audit_log',
    'clear_rls_audit_log',

    # Validation
    'validate_tenant_id',
    'require_tenant_context',

    # Configuration
    'RLS_ENABLED',
    'RLS_STRICT_MODE',
    'RLS_AUDIT_ENABLED',
    'refresh_config',
]
