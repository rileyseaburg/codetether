"""The session workspace reference must follow the real foreign key target.

`sessions.workspace_id` is constrained by a foreign key historically named
`sessions_codebase_id_fkey`. On this deployment it targets the legacy
`codebases` table, while task metadata carries ids that exist in `workspaces`.

An earlier fix accepted a match from *either* candidate table. That reported
success for an id present only in `workspaces`, the insert then violated the
constraint, and no transcript row was written at all.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from a2a_server import forgejo_progress_events as progress


class _Conn:
    """Minimal asyncpg-like connection for foreign key resolution tests."""

    def __init__(
        self,
        fk_target: Optional[str],
        rows: Optional[dict[str, set[str]]] = None,
        fail_target: bool = False,
    ) -> None:
        self.fk_target = fk_target
        self.rows = rows or {}
        self.fail_target = fail_target
        self.queried: list[str] = []

    async def fetchval(self, sql: str, *args: Any):
        if 'pg_constraint' in sql:
            if self.fail_target:
                raise RuntimeError('catalog unavailable')
            return self.fk_target
        for table, ids in self.rows.items():
            if f'FROM {table} ' in sql:
                self.queried.append(table)
                return 1 if args[0] in ids else None
        self.queried.append('unknown')
        return None


@pytest.mark.asyncio
async def test_only_the_fk_target_table_is_consulted() -> None:
    conn = _Conn(
        fk_target='codebases',
        rows={'codebases': set(), 'workspaces': {'ws-1'}},
    )

    ok = await progress._workspace_is_referenceable(conn, 'ws-1')

    assert ok is False, (
        'an id present only in workspaces must not be treated as referenceable '
        'when the constraint targets codebases'
    )
    assert conn.queried == ['codebases'], conn.queried


@pytest.mark.asyncio
async def test_referenceable_when_present_in_target() -> None:
    conn = _Conn(fk_target='codebases', rows={'codebases': {'cb-1'}})

    assert await progress._workspace_is_referenceable(conn, 'cb-1') is True


@pytest.mark.asyncio
async def test_workspaces_target_is_honoured() -> None:
    """A deployment whose constraint points at `workspaces` must still work."""
    conn = _Conn(fk_target='workspaces', rows={'workspaces': {'ws-1'}})

    assert await progress._workspace_is_referenceable(conn, 'ws-1') is True
    assert conn.queried == ['workspaces']


@pytest.mark.asyncio
async def test_no_foreign_key_accepts_any_value() -> None:
    conn = _Conn(fk_target=None)

    assert await progress._workspace_is_referenceable(conn, 'anything') is True


@pytest.mark.asyncio
async def test_catalog_failure_is_not_referenceable() -> None:
    """A null workspace is preferable to losing the whole transcript."""
    conn = _Conn(fk_target='codebases', fail_target=True)

    assert await progress._workspace_is_referenceable(conn, 'ws-1') is False
