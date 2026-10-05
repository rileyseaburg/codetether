"""Transcript continuity and streaming-fault classification.

Two defects observed on a live run of issue #21:

* A truncated stream (`SSE stream error: error decoding response body`) was
  classified as neither transient nor permanent, so the task failed outright
  instead of being requeued.
* The worker's own session id overwrote the derived `task-<id>` session that 77
  recorded transcript rows were stored under, so the Forgejo panel went from 77
  rows back to empty.
"""

from __future__ import annotations

import pytest

from a2a_server import transient_retry


@pytest.mark.parametrize(
    'error',
    [
        'Error: SSE stream error: error decoding response body',
        'SSE stream error: connection closed',
        'error decoding response body',
        'unexpected EOF while reading stream',
        'incomplete message received',
    ],
)
def test_streaming_faults_are_transient(error: str) -> None:
    assert transient_retry.is_transient_failure(error) is True
    assert transient_retry.is_permanent_failure(error) is False
    assert transient_retry.should_requeue('failed', error, {}) is True


@pytest.mark.parametrize(
    'error',
    [
        'OpenRouter API error: Insufficient credits',
        'package has expired',
        'Error: provider rejected prompt as too long after RLM compaction',
    ],
)
def test_permanent_faults_still_win(error: str) -> None:
    assert transient_retry.is_transient_failure(error) is False
    assert transient_retry.should_requeue('failed', error, {}) is False


class _Conn:
    """Minimal asyncpg-like connection recording executed statements."""

    def __init__(self, existing: str, recorded_rows: int) -> None:
        self.existing = existing
        self.recorded_rows = recorded_rows
        self.statements: list[str] = []

    async def fetchval(self, sql: str, *args):
        if 'session_messages' in sql:
            return self.recorded_rows
        if 'FROM tasks' in sql:
            return self.existing
        return None

    async def execute(self, sql: str, *args):
        self.statements.append(' '.join(sql.split()))


class _Acquire:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _Conn:
        return self.conn

    async def __aexit__(self, *args) -> None:
        return None


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


def _install(monkeypatch: pytest.MonkeyPatch, conn: _Conn) -> None:
    async def _pool():
        return _Pool(conn)

    monkeypatch.setattr('a2a_server.database.get_pool', _pool, raising=False)


@pytest.mark.asyncio
async def test_derived_session_with_rows_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a2a_server import worker_sse

    conn = _Conn(existing='task-abc', recorded_rows=77)
    _install(monkeypatch, conn)

    ok = await worker_sse._persist_release_session_id('abc', 'worker-session-1')

    assert ok is True
    joined = ' '.join(conn.statements)
    assert 'worker_session_id' in joined, (
        'the worker id must be recorded without discarding recorded rows'
    )
    assert "'session_id', $2" not in joined, (
        'the derived session holding 77 rows must not be overwritten'
    )


@pytest.mark.asyncio
async def test_derived_session_without_rows_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a2a_server import worker_sse

    conn = _Conn(existing='task-abc', recorded_rows=0)
    _install(monkeypatch, conn)

    await worker_sse._persist_release_session_id('abc', 'worker-session-1')

    joined = ' '.join(conn.statements)
    assert 'session_id' in joined
    assert 'worker_session_id' not in joined, (
        'with no recorded rows the real worker session should be adopted'
    )


@pytest.mark.asyncio
async def test_matching_session_is_not_rewritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a2a_server import worker_sse

    conn = _Conn(existing='worker-session-1', recorded_rows=5)
    _install(monkeypatch, conn)

    await worker_sse._persist_release_session_id('abc', 'worker-session-1')

    assert 'worker_session_id' not in ' '.join(conn.statements)


@pytest.mark.asyncio
async def test_missing_session_id_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from a2a_server import worker_sse

    conn = _Conn(existing='task-abc', recorded_rows=77)
    _install(monkeypatch, conn)

    assert await worker_sse._persist_release_session_id('abc', None) is False
    assert conn.statements == []
