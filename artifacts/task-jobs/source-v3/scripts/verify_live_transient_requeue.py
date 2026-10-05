"""Prove the live release endpoint requeues a transient provider failure.

Creates a scratch task, claims it as a real registered worker, releases it with
an overload error, and asserts the server returned the task to `pending` with an
advanced retry counter. Then releases a permanent error and asserts it stays
failed. The scratch row is always deleted.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import asyncpg
import httpx

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

TRANSIENT_ERROR = (
    'Error: codex-retryable: Our servers are currently overloaded. '
    'Please try again later.'
)
PERMANENT_ERROR = 'DeepSeek API error: Insufficient Balance'


async def _load(conn: asyncpg.Connection, task_id: str) -> dict:
    row = await conn.fetchrow(
        'SELECT status, worker_id, error, metadata FROM tasks WHERE id = $1',
        task_id,
    )
    metadata = row['metadata']
    if isinstance(metadata, str):
        metadata = json.loads(metadata or '{}')
    return {
        'status': row['status'],
        'worker_id': row['worker_id'],
        'error': row['error'],
        'metadata': metadata or {},
    }


async def _release(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    worker_id: str,
    task_id: str,
    error: str,
) -> httpx.Response:
    return await client.post(
        f'{base}/v1/worker/tasks/release',
        headers={
            'X-Worker-ID': worker_id,
            'Authorization': f'Bearer {token}',
        },
        json={
            'task_id': task_id,
            'status': 'failed',
            'result': None,
            'error': error,
            'session_id': None,
            'diagnostics': None,
        },
    )


async def main() -> int:
    dsn = os.environ['DATABASE_URL']
    base = os.environ['SERVER_URL'].rstrip('/')
    token = os.environ['CODETETHER_TOKEN']

    conn = await asyncpg.connect(dsn)
    task_id = str(uuid.uuid4())
    failures: list[str] = []
    try:
        worker = await conn.fetchrow(
            "SELECT worker_id FROM workers WHERE status = 'active' "
            'ORDER BY last_seen DESC LIMIT 1'
        )
        if not worker:
            print('no_active_worker=true')
            return 2
        worker_id = worker['worker_id']

        await conn.execute(
            """
            INSERT INTO tasks (id, workspace_id, title, prompt, agent_type,
                               status, priority, worker_id, metadata)
            VALUES ($1, $2, 'live transient requeue probe', 'probe', 'build',
                    'running', 100, $3, $4::jsonb)
            """,
            task_id,
            f'live-probe-{task_id[:8]}',
            worker_id,
            json.dumps({'source': 'live-probe', 'repo': 'riley/probe'}),
        )

        async with httpx.AsyncClient(timeout=60) as client:
            response = await _release(
                client, base, token, worker_id, task_id, TRANSIENT_ERROR
            )
            print(f'transient_release_http={response.status_code}')
            print(f'transient_release_body={response.text[:200]}')

            after = await _load(conn, task_id)
            print(f'status_after_transient={after["status"]}')
            print(f'worker_id_cleared={after["worker_id"] is None}')
            print(
                'attempts_after_transient='
                f'{after["metadata"].get("transient_retry_attempts")}'
            )
            if after['status'] != 'pending':
                failures.append(
                    f'expected pending, got {after["status"]}'
                )
            if after['metadata'].get('transient_retry_attempts') != 1:
                failures.append('retry counter did not advance to 1')
            if after['metadata'].get('repo') != 'riley/probe':
                failures.append('existing metadata was lost')

            # Permanent failure must remain terminal.
            await conn.execute(
                "UPDATE tasks SET status='running', worker_id=$2 WHERE id=$1",
                task_id,
                worker_id,
            )
            response = await _release(
                client, base, token, worker_id, task_id, PERMANENT_ERROR
            )
            print(f'permanent_release_http={response.status_code}')
            permanent = await _load(conn, task_id)
            print(f'status_after_permanent={permanent["status"]}')
            if permanent['status'] != 'failed':
                failures.append(
                    f'permanent error should stay failed, got {permanent["status"]}'
                )

        if failures:
            for item in failures:
                print(f'FAILURE: {item}')
            return 1
        print('live_requeue_ok=true')
        return 0
    finally:
        await conn.execute('DELETE FROM tasks WHERE id = $1', task_id)
        await conn.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
