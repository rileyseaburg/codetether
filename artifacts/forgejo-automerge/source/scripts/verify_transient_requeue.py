"""Exercise the transient-requeue SQL against the real tasks schema.

Creates a scratch task, marks it failed with a transient provider error, runs
the same UPDATE used by the release endpoint, and asserts the row returns to
`pending` with an advanced retry counter. The scratch row is always removed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import asyncpg

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from a2a_server import transient_retry  # noqa: E402


async def main() -> int:
    dsn = os.environ['DATABASE_URL']
    task_id = str(uuid.uuid4())
    workspace_id = f'transient-probe-{task_id[:8]}'
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO tasks (id, workspace_id, title, prompt, agent_type,
                               status, priority, error, metadata)
            VALUES ($1, $2, 'transient requeue probe', 'probe', 'build',
                    'failed', 100, $3, $4::jsonb)
            """,
            task_id,
            workspace_id,
            'Error: codex-retryable: Our servers are currently overloaded.',
            json.dumps({'source': 'probe', 'repo': 'riley/probe'}),
        )

        row = await conn.fetchrow(
            'SELECT status, metadata, error FROM tasks WHERE id = $1', task_id
        )
        metadata = row['metadata']
        if isinstance(metadata, str):
            metadata = json.loads(metadata or '{}')

        assert row['status'] == 'failed', row['status']
        assert transient_retry.should_requeue('failed', row['error'], metadata)

        updated = transient_retry.next_metadata(metadata, row['error'])
        delay = transient_retry.backoff_seconds(
            updated[transient_retry.ATTEMPT_KEY]
        )

        await conn.execute(
            """
            UPDATE tasks
            SET status = 'pending',
                worker_id = NULL,
                error = NULL,
                started_at = NULL,
                metadata = $2::jsonb,
                updated_at = now() + ($3 || ' seconds')::interval
            WHERE id = $1
            """,
            task_id,
            json.dumps(updated),
            str(delay),
        )

        after = await conn.fetchrow(
            'SELECT status, worker_id, error, metadata FROM tasks WHERE id = $1',
            task_id,
        )
        after_metadata = after['metadata']
        if isinstance(after_metadata, str):
            after_metadata = json.loads(after_metadata or '{}')

        assert after['status'] == 'pending', after['status']
        assert after['worker_id'] is None, after['worker_id']
        assert after['error'] is None, after['error']
        assert after_metadata[transient_retry.ATTEMPT_KEY] == 1
        assert after_metadata['repo'] == 'riley/probe'

        # Budget must stop the third retry.
        exhausted = dict(after_metadata)
        exhausted[transient_retry.ATTEMPT_KEY] = transient_retry.max_attempts()
        assert not transient_retry.should_requeue(
            'failed', 'currently overloaded', exhausted
        )

        print('requeue_sql_ok=true')
        print(f'attempts_after={after_metadata[transient_retry.ATTEMPT_KEY]}')
        print(f'backoff_seconds={delay}')
        return 0
    finally:
        await conn.execute('DELETE FROM tasks WHERE id = $1', task_id)
        await conn.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))