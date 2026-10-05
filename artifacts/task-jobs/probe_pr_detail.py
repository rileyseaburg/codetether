"""Read-only detail for one PR: commits, review bodies, workflow position."""

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


async def report(number: int, native: int) -> None:
    """Collect commit authorship, formal reviews, and workflow pending work."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    db = import_module('a2a_server.database')
    base = os.environ['FORGEJO_API_URL']
    root = f'/repos/{REPO}'
    commits = await fj('GET', base, f'{root}/pulls/{number}/commits?limit=50')
    reviews = await fj('GET', base, f'{root}/pulls/{number}/reviews?limit=50')
    comments = await fj(
        'GET', base, f'{root}/issues/{number}/comments?limit=50'
    )
    client = import_module('a2a_server.temporal.client')
    handle = await client.workflow_handle(native)
    desc = await asyncio.wait_for(handle.describe(), timeout=15)
    raw = desc.raw_description
    pending = [
        {
            'type': a.activity_type.name,
            'state': str(a.state),
            'attempt': a.attempt,
            'last_failure': a.last_failure.message
            if a.HasField('last_failure')
            else None,
        }
        for a in raw.pending_activities
    ]
    try:
        state = await asyncio.wait_for(handle.query('state'), timeout=15)
    except Exception as exc:
        state = {'error': type(exc).__name__}
    history = []
    async for event in handle.fetch_history_events():
        kind = event.event_type
        name = None
        if event.HasField('activity_task_scheduled_event_attributes'):
            name = event.activity_task_scheduled_event_attributes.activity_type.name
        if event.HasField('workflow_execution_signaled_event_attributes'):
            name = (
                event.workflow_execution_signaled_event_attributes.signal_name
            )
        if event.HasField('activity_task_failed_event_attributes'):
            name = event.activity_task_failed_event_attributes.failure.message[
                :160
            ]
        history.append(
            {
                'id': event.event_id,
                'time': event.event_time.ToJsonString(),
                'type': kind,
                'name': name,
            }
        )
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT id,title,status,left(result,1800) AS result
            FROM tasks WHERE id = ANY($1::text[])
        """,
            [
                '33b529b6-ecaa-45a5-a93e-97b397b1036e',
                'c2d38f4d-00a3-4f18-bf7a-d26ae90e9d93',
                'f18cdeb2-bdaf-459c-8db4-dc576b2d3b3a',
            ],
        )
    await pool.close()
    print(
        json.dumps(
            {
                'commits': [
                    {
                        'sha': c['sha'],
                        'author': (c.get('author') or {}).get('login'),
                        'committer': (c.get('committer') or {}).get('login'),
                        'date': c['commit']['committer']['date'],
                        'message': c['commit']['message'][:160],
                    }
                    for c in commits
                ],
                'reviews': [
                    {
                        'id': r['id'],
                        'state': r['state'],
                        'user': (r.get('user') or {}).get('login'),
                        'commit': r.get('commit_id'),
                        'submitted': r.get('submitted_at'),
                        'body': (r.get('body') or '')[:1500],
                    }
                    for r in reviews
                ],
                'comments': [
                    {
                        'user': (c.get('user') or {}).get('login'),
                        'created': c['created_at'],
                        'body': (c.get('body') or '')[:600],
                    }
                    for c in comments
                ],
                'workflow': {
                    'status': desc.status.name,
                    'pending': pending,
                    'state': state,
                    'history': history[-45:],
                },
                'task_results': [dict(r) for r in results],
            },
            default=str,
        )
    )


def main() -> None:
    """Run inside the ready Temporal worker and save a timestamped artifact."""
    number, native = int(sys.argv[1]), int(sys.argv[2])
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
            str(native),
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
    path = Path('artifacts/task-jobs') / f'pr-{number}-detail-{stamp}.json'
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(int(sys.argv[-2]), int(sys.argv[-1])))
    else:
        main()
