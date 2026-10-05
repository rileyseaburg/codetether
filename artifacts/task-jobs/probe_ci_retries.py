"""Read-only: which review owners did the settled-CI retry signal, and when?"""

import asyncio
import json
import logging
import subprocess
import sys

from importlib import import_module
from pathlib import Path


async def report(since: str) -> None:
    """List owners carrying the retry marker and review-chunk creation rate."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        retried = await conn.fetch("""
            SELECT id,status,metadata->>'pr_number' AS pr,
                   metadata->>'review_checks_retry' AS signature,
                   updated_at
            FROM tasks WHERE metadata->>'source'='forgejo-review-owner'
              AND metadata ? 'review_checks_retry'
            ORDER BY updated_at DESC
        """)
        chunks = await conn.fetch(
            """
            SELECT date_trunc('minute', created_at) AS minute, count(*) AS n
            FROM tasks WHERE metadata->>'workflow_stage'='review_chunk'
              AND created_at >= $1::text::timestamptz
            GROUP BY 1 ORDER BY 1
        """,
            since,
        )
    await pool.close()
    print(
        json.dumps(
            {
                'retried_owners': [dict(r) for r in retried],
                'chunks_per_minute_since': [dict(r) for r in chunks],
            },
            default=str,
        )
    )


def main() -> None:
    """Run in the ready API pod."""
    pods = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'pods',
                '-l',
                'app.kubernetes.io/component=server,color=green',
                '-o',
                'json',
            ]
        )
    )['items']
    pod = next(
        p['metadata']['name']
        for p in pods
        if not p['metadata'].get('deletionTimestamp')
        and any(
            c.get('ready')
            for c in p.get('status', {}).get('containerStatuses', [])
        )
    )
    run = subprocess.run(
        [
            'kubectl',
            '-n',
            'a2a-system',
            'exec',
            '-i',
            pod,
            '--',
            'python3',
            '-',
            '--remote',
            sys.argv[1],
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    print(json.dumps(json.loads(run.stdout), indent=1))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[-1]))
    else:
        main()
