"""Read-only watch of the repaired queue, exact PR checks, and Job outcomes."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path


async def remote_report():
    """Read active task state and independently verified PR check status."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    kube = import_module('a2a_server.task_jobs').kube
    jobs = await kube(
        'GET',
        '/apis/batch/v1/namespaces/a2a-system/jobs'
        '?labelSelector=codetether.io%2Ftask-job%3Dtrue',
    )
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        tasks = await conn.fetch(
            """
            SELECT id,status,title,updated_at,error,
              metadata->>'workflow_stage' AS stage,
              metadata->>'job_name' AS job,
              metadata->>'job_wait_reason' AS waiting,
              metadata->>'pr_number' AS pr,
              metadata->'forgejo_published_pr' AS publication
            FROM tasks WHERE metadata->>'job_execution'='true'
              AND (status IN ('working','running','in_progress')
                OR metadata->>'job_name'=ANY($1::text[])
                OR id IN (
                  '31bc7f21-9b31-4444-96cf-0eb972755a76',
                  '420aa345-9af2-4fdb-8027-f95a79a3d0c3',
                  '9b0f1a26-617f-4383-b302-296d55f811a3',
                  'e6a8b1fe-3777-4b13-adfb-886f3ad2d966'))
            ORDER BY updated_at DESC
        """,
            [
                j['metadata']['name']
                for j in jobs['items']
                if j['metadata']['creationTimestamp'] > '2026-09-14T00:00:00Z'
            ],
        )
        owners = await conn.fetch("""
            SELECT id,status,metadata->>'pr_number' AS pr,
                   metadata->>'review_verdict' AS verdict,
                   metadata->>'review_error_reason' AS reason,
                   metadata->>'recovery_state' AS recovery,
                   metadata->>'recovery_blocker' AS blocker,
                   metadata->'review_findings' AS findings
            FROM tasks WHERE metadata->>'source'='forgejo-review-owner'
              AND metadata->>'pr_number' IN ('6003','6045','6046')
            ORDER BY updated_at DESC LIMIT 3
        """)
    checks = []
    for number in (6003, 6045, 6046, 6072):
        pr = await fj(
            'GET',
            os.environ['FORGEJO_API_URL'],
            f'/repos/riley/spotlessbinco/pulls/{number}',
        )
        sha = pr['head']['sha']
        state = await fj(
            'GET',
            os.environ['FORGEJO_API_URL'],
            f'/repos/riley/spotlessbinco/commits/{sha}/status?limit=100',
        )
        checks.append(
            {
                'pr': number,
                'url': pr['html_url'],
                'head': sha,
                'state': pr['state'],
                'merged': pr['merged'],
                'checks': [
                    {
                        'context': s['context'],
                        'status': s['status'],
                        'description': s.get('description'),
                    }
                    for s in (state.get('statuses') or [])
                ],
            }
        )
    counts = {'running': 0, 'Complete': 0, 'Failed': 0}
    active = []
    for job in jobs['items']:
        state = next(
            (
                c['type']
                for c in job.get('status', {}).get('conditions', [])
                if c['status'] == 'True' and c['type'] in {'Complete', 'Failed'}
            ),
            'running',
        )
        counts[state] += 1
        if state == 'running':
            active.append(
                {
                    'job': job['metadata']['name'],
                    'class': job['metadata']['labels'].get(
                        'codetether.io/job-class'
                    ),
                    'started': job['status'].get('startTime'),
                }
            )
    print(
        json.dumps(
            {
                'at': datetime.now(UTC).isoformat(),
                'counts': counts,
                'active': active,
                'tasks': [dict(r) for r in tasks],
                'prs': checks,
                'review_owners': [dict(r) for r in owners],
            },
            default=str,
        )
    )
    await pool.close()


def main():
    """Save a timestamped live observation without making mutations."""
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
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        timeout=150,
        check=False,
    )
    if run.returncode:
        print(run.stderr[-1000:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    path = Path('artifacts/task-jobs') / (
        'completion-watch-'
        + datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
        + '.json'
    )
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)
    print(json.dumps(data))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(remote_report())
    else:
        main()
