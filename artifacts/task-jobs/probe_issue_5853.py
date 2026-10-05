"""Read current issue 5853 state without reading Temporal/session history."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path


async def report():
    """Correlate current native, CodeTether, inbox, and workflow state."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    root = '/repos/riley/spotlessbinco'
    native = await fj('GET', base, root + '/agent/tasks/534')
    pr = await fj('GET', base, root + '/pulls/6003')
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id,status,title,error,created_at,updated_at,
              completed_at,metadata
            FROM tasks WHERE metadata->>'repo'='riley/spotlessbinco'
              AND (metadata->>'issue_number'='5853'
                OR metadata->>'pr_number'='6003')
            ORDER BY created_at DESC LIMIT 18
        """)
        recovery = await conn.fetchrow("""
            SELECT id,status,title,error,created_at,updated_at,
              completed_at,metadata
            FROM tasks WHERE id='db9a4575-7e48-4d90-b403-2749fd907adf'
        """)
        receipts = await conn.fetch("""
            SELECT delivery_id,state,native_task_id,received_at,updated_at,
              context->>'comment_id' AS comment_id,
              context->>'body' AS request
            FROM forgejo_webhook_inbox
            WHERE context->>'repo'='riley/spotlessbinco'
              AND context->>'number'='5853'
            ORDER BY received_at
        """)
    tasks = []
    for row in [*rows, recovery]:
        if not row:
            continue
        item = dict(row)
        meta = item.pop('metadata')
        if isinstance(meta, str):
            meta = json.loads(meta)
        item['metadata'] = {
            key: meta.get(key)
            for key in (
                'workflow_stage',
                'temporal_orchestrated',
                'temporal_workflow_id',
                'temporal_attempt',
                'forgejo_agent_task_id',
                'pr_head_sha',
                'review_verdict',
                'review_error_reason',
                'recovery_state',
                'recovery_blocker',
                'recovery_reconciled',
                'recovery_task_id',
                'recovery_next_owner',
                'recovery_native_request',
                'review_owner_id',
                'job_wait_reason',
                'job_controller_failed',
                'job_failure_notified',
            )
        }
        tasks.append(item)
    client = import_module('a2a_server.temporal.client')
    handle = await client.workflow_handle(534)
    state = {}
    try:
        description = await asyncio.wait_for(handle.describe(), timeout=20)
        state['execution_status'] = description.status.name
        state['run_id'] = description.run_id
        state['closed_at'] = str(description.close_time)
        if state['execution_status'] == 'RUNNING':
            state['query'] = await asyncio.wait_for(
                handle.query('state'), timeout=20
            )
    except Exception as exc:
        state['query_error_type'] = type(exc).__name__
    files = await fj('GET', base, root + '/pulls/6003/files?limit=100')
    checks = await fj(
        'GET', base, root + f'/commits/{pr["head"]["sha"]}/status?limit=100'
    )
    data = {
        'files': [f.get('filename') for f in files],
        'checks': [
            {
                k: s.get(k)
                for k in ('context', 'status', 'description', 'target_url')
            }
            for s in (checks.get('statuses') or [])
        ],
        'at': datetime.now(UTC).isoformat(),
        'native': {
            key: native.get(key)
            for key in (
                'id',
                'status',
                'operation',
                'branch',
                'head_sha',
                'external_task_id',
                'external_session_id',
                'updated_at',
                'error',
            )
        },
        'pr': {
            key: pr.get(key)
            for key in (
                'number',
                'html_url',
                'state',
                'merged',
                'updated_at',
            )
        }
        | {'head': pr['head']['sha']},
        'workflow': state,
        'tasks': tasks,
        'receipts': [dict(r) for r in receipts],
    }
    print(json.dumps(data, default=str))
    await pool.close()


def main():
    """Save only current operational evidence in a timestamped artifact."""
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
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        check=False,
        timeout=160,
    )
    if run.returncode:
        print(run.stderr[-1200:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    path = Path('artifacts/task-jobs') / (
        'issue-5853-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S') + '.json'
    )
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)
    print('NATIVE', json.dumps(data['native']))
    print('WORKFLOW', json.dumps(data['workflow']))
    print('PR', json.dumps(data['pr']))
    print('FILES', json.dumps(data['files']))
    print('CHECKS', json.dumps(data['checks']))
    print('RECEIPTS', json.dumps(data['receipts']))
    for task in data['tasks']:
        print('TASK', json.dumps(task))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report())
    else:
        main()
