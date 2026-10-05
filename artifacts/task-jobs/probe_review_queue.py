"""Read-only: why is a pending review chunk not admitted?

Reports live read-only Jobs with their tasks and age, plus the FIFO position
of the target chunk in the review lane.
"""

import asyncio
import json
import logging
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path


async def report(target: str) -> None:
    """Correlate live readonly Jobs to tasks and rank the pending lane."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    kube = import_module('a2a_server.task_jobs').kube
    jobs = await kube(
        'GET',
        '/apis/batch/v1/namespaces/a2a-system/jobs'
        '?labelSelector=codetether.io%2Fjob-class%3Dreadonly',
    )
    live = [
        j
        for j in jobs['items']
        if not any(
            c.get('status') == 'True' and c['type'] in ('Complete', 'Failed')
            for c in j.get('status', {}).get('conditions', [])
        )
    ]
    names = [j['metadata']['name'] for j in live]
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        holders = await conn.fetch(
            """
            SELECT id,status,title,updated_at,metadata->>'job_name' AS job,
                   metadata->>'pr_number' AS pr
            FROM tasks WHERE metadata->>'job_name'=ANY($1::text[])
        """,
            names,
        )
        lane = await conn.fetch("""
            SELECT id,title,created_at,
                   metadata->>'job_wait_reason' AS waiting
            FROM tasks WHERE metadata->>'job_execution'='true'
              AND metadata->>'job_readonly'='true'
              AND status IN ('pending','queued','assigned','running',
                             'working','in_progress')
              AND metadata->>'job_cleanup_scheduled' IS DISTINCT FROM 'true'
            ORDER BY COALESCE(metadata->>'job_last_observed_at',''),
                     created_at, id
        """)
    await pool.close()
    now = datetime.now(UTC)
    started = {
        j['metadata']['name']: j.get('status', {}).get('startTime')
        for j in live
    }
    print(
        json.dumps(
            {
                'live_readonly_jobs': [
                    {**dict(h), 'job_started': started.get(h['job'])}
                    for h in holders
                ],
                'live_without_task': sorted(
                    set(names) - {h['job'] for h in holders}
                ),
                'lane_size': len(lane),
                'target_position': next(
                    (i for i, r in enumerate(lane) if r['id'] == target), None
                ),
                'lane_head': [dict(r) for r in lane[:6]],
                'at': now.isoformat(),
            },
            default=str,
        )
    )


def main() -> None:
    """Run in the ready API pod, where admission itself runs."""
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
