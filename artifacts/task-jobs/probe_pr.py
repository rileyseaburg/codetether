"""Read-only lifecycle probe for one spotlessbinco PR; no mutations."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path


REPO = 'riley/spotlessbinco'
KEYS = (
    'workflow_stage',
    'issue_number',
    'pr_number',
    'pr_head_sha',
    'branch_name',
    'forgejo_agent_task_id',
    'temporal_workflow_id',
    'temporal_attempt',
    'review_owner',
    'review_owner_id',
    'review_verdict',
    'review_error_reason',
    'review_attempt',
    'review_chunk_task_ids',
    'recovery_state',
    'recovery_blocker',
    'recovery_task_id',
    'recovery_next_owner',
    'recovery_native_request',
    'recovery_attempt',
    'recovery_reconciled',
    'job_name',
    'job_wait_reason',
    'job_controller_failed',
    'job_cleanup_scheduled',
    'forgejo_published_pr',
)


def _slim(row):
    item = dict(row)
    meta = item.pop('metadata') or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    item['metadata'] = {k: meta.get(k) for k in KEYS if meta.get(k) is not None}
    return item


async def report(number):
    """Correlate PR, checks, tasks, native tasks, and workflows."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    root = f'/repos/{REPO}'
    pr = await fj('GET', base, f'{root}/pulls/{number}')
    sha = pr['head']['sha']
    status = await fj('GET', base, f'{root}/commits/{sha}/status?limit=100')
    files = await fj('GET', base, f'{root}/pulls/{number}/files?limit=100')
    issue = None
    body = str(pr.get('body') or '')
    for token in body.replace('#', ' #').split():
        if token.startswith('#') and token[1:].isdigit():
            issue = int(token[1:])
            break
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id,status,title,error,created_at,updated_at,completed_at,
                   metadata
            FROM tasks WHERE metadata->>'repo'=$1
              AND (metadata->>'pr_number'=$2
                OR ($3::text IS NOT NULL AND metadata->>'issue_number'=$3)
                OR metadata->>'branch_name'=$4)
            ORDER BY created_at
        """,
            REPO,
            str(number),
            str(issue) if issue else None,
            pr['head']['ref'],
        )
    await pool.close()
    tasks = [_slim(r) for r in rows]
    natives = sorted(
        {
            int(t['metadata']['forgejo_agent_task_id'])
            for t in tasks
            if t['metadata'].get('forgejo_agent_task_id')
        }
        | {
            int(t['metadata']['recovery_native_request'])
            for t in tasks
            if t['metadata'].get('recovery_native_request')
        }
    )
    native_state = []
    client = import_module('a2a_server.temporal.client')
    for nid in natives:
        task = await fj('GET', base, f'{root}/agent/tasks/{nid}')
        entry = {
            k: task.get(k)
            for k in (
                'id',
                'status',
                'operation',
                'branch',
                'head_sha',
                'error',
                'external_task_id',
                'updated_at',
            )
        }
        try:
            handle = await client.workflow_handle(nid)
            desc = await asyncio.wait_for(handle.describe(), timeout=15)
            entry['workflow'] = {
                'status': desc.status.name,
                'run_id': desc.run_id,
                'closed': str(desc.close_time),
            }
        except Exception as exc:
            entry['workflow'] = {'error': type(exc).__name__}
        native_state.append(entry)
    print(
        json.dumps(
            {
                'at': datetime.now(UTC).isoformat(),
                'pr': {
                    'number': number,
                    'state': pr['state'],
                    'merged': pr['merged'],
                    'mergeable': pr.get('mergeable'),
                    'head': sha,
                    'ref': pr['head']['ref'],
                    'title': pr['title'],
                    'issue': issue,
                    'updated_at': pr['updated_at'],
                },
                'checks': [
                    {
                        k: s.get(k)
                        for k in (
                            'context',
                            'status',
                            'description',
                            'updated_at',
                        )
                    }
                    for s in (status.get('statuses') or [])
                ],
                'files': [f.get('filename') for f in files],
                'tasks': tasks,
                'natives': native_state,
            },
            default=str,
        )
    )


def main():
    """Run inside the ready Temporal worker and save a timestamped artifact."""
    number = int(sys.argv[1])
    pods = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'pods',
                '-o',
                'json',
            ]
        )
    )['items']
    pod = next(
        p['metadata']['name']
        for p in pods
        if p['metadata']['name'].startswith('a2a-server-temporal-worker-')
        and not p['metadata'].get('deletionTimestamp')
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
            str(number),
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
    path = Path('artifacts/task-jobs') / f'pr-{number}-{stamp}.json'
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)
    print('PR', json.dumps(data['pr']))
    print('CHECKS', json.dumps(data['checks']))
    print('FILES', len(data['files']), json.dumps(data['files'][:15]))
    for n in data['natives']:
        print('NATIVE', json.dumps(n))
    for t in data['tasks']:
        print('TASK', json.dumps(t, default=str))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(int(sys.argv[-1])))
    else:
        main()
