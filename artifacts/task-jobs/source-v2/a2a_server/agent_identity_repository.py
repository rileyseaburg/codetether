"""Persistence boundary for immutable agent identity bindings."""

from a2a_server.agent_identity_binding import AgentIdentityBinding
from a2a_server.agent_identity_binding_cache import get as cached
from a2a_server.agent_identity_binding_cache import put
from a2a_server.agent_identity_binding_codec import binding, matches, values
from a2a_server.agent_identity_binding_sql import (
    INSERT,
    SELECT_ANY,
    SELECT_SPIFFE,
)
from a2a_server.agent_identity_errors import (
    IdentityConflictError,
    IdentityUpstreamError,
)


async def save_binding(receipt: dict[str, object]) -> AgentIdentityBinding:
    """Insert an identity binding or verify an exact idempotent replay."""
    expected = values(receipt)
    pool = await _database_pool()
    async with pool.acquire() as connection:
        await connection.execute(INSERT, *expected)
        row = await connection.fetchrow(
            SELECT_ANY, expected[0], expected[2], expected[3]
        )
    if row is None or not matches(row, expected):
        raise IdentityConflictError(
            'workload authority conflicts with prior binding'
        )
    result = binding(row)
    put(result)
    return result


async def get_binding(spiffe_id: str) -> AgentIdentityBinding | None:
    """Load the OPA authority attached to one authenticated SPIFFE ID."""
    existing = cached(spiffe_id)
    if existing:
        return existing
    pool = await _database_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(SELECT_SPIFFE, spiffe_id)
    result = binding(row) if row else None
    if result:
        put(result)
    return result


async def _database_pool() -> object:
    from a2a_server.database import get_pool  # noqa: PLC0415

    pool = await get_pool()
    if pool is None:
        raise IdentityUpstreamError('identity binding database is unavailable')
    return pool
