"""Post one factual status correction on issue 5853; never enqueue new work."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path


ISSUE_NUMBER = 5853


async def report():
    """Verify native task identities and acknowledge the original follow-up."""
    logging.disable(logging.CRITICAL)
    hooks = import_module('a2a_server.forgejo_webhooks')
    db = import_module('a2a_server.database')
    base = os.environ['FORGEJO_API_URL']
    repo = 'riley/spotlessbinco'
    root = f'/repos/{repo}'
    old = await hooks.forgejo_json('GET', base, root + '/agent/tasks/534')
    new = await hooks.forgejo_json('GET', base, root + '/agent/tasks/623')
    assert old['status'] == 'cancelled'
    assert old.get('error') == 'workflow_terminated'
    assert new['issue_index'] == ISSUE_NUMBER
    assert new['branch'] == 'codetether/issue-5853'
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        stages = await conn.fetch("""
            SELECT id,title,status,error,created_at,
                metadata->>'workflow_stage' AS stage,
                metadata->>'job_wait_reason' AS waiting,
                metadata->>'job_name' AS job
            FROM tasks WHERE metadata->>'forgejo_agent_task_id'='623'
                AND metadata->>'repo'='riley/spotlessbinco'
            ORDER BY created_at
        """)
    await pool.close()
    marker = '<!-- codetether-5853-status-correction-534-623 -->'
    comments = await hooks.forgejo_json(
        'GET', base, root + '/issues/5853/comments?limit=100'
    )
    if not any(marker in (c.get('body') or '') for c in comments):
        body = (
            '## CodeTether status correction\n\n'
            'The old **Task #534 was not still working**. Its Temporal '
            'workflow was terminated on September 12, but Forgejo retained '
            'a stale `running` status. This prevented your September 11 '
            'follow-up instruction from dispatching. The stale native '
            'status is now corrected to `cancelled`; no completed work '
            'was discarded and the existing branch/PR was preserved.\n\n'
            'Your existing follow-up comment has now been handed off as '
            '[Task #623](https://forgejo.quantum-forge.io/riley/spotlessbinco/'
            'agent/tasks/623). Current native status: '
            f'`{new["status"]}`.\n\n'
            '[PR #6003](https://forgejo.quantum-forge.io/riley/spotlessbinco/'
            'pulls/6003) contains the planning documentation. Its approved '
            'Harvester review does **not** establish that the pilot crate, '
            'CI/build-plumbing changes, or baseline timing evidence are done. '
            'This issue remains unfinished.\n\n'
            'The follow-up retains your instruction: make the code changes '
            'and update Forgejo Actions to validate them on its Rust runner, '
            'rather than requiring local compilation. It should update the '
            'existing `codetether/issue-5853` branch and PR, not create a '
            'duplicate. No CI/build success or measured compile-speed '
            'improvement is claimed here.\n\n' + marker
        )
        await hooks.forgejo_json(
            'POST', base, root + '/issues/5853/comments', {'body': body}
        )
        comments = await hooks.forgejo_json(
            'GET', base, root + '/issues/5853/comments?limit=100'
        )
    comment = next(c for c in comments if marker in (c.get('body') or ''))
    print(
        json.dumps(
            {
                'old_task': old['status'],
                'new_task': {
                    'id': new['id'],
                    'status': new['status'],
                    'url': new['html_url'],
                },
                'stages': [dict(s) for s in stages],
                'comment_id': comment['id'],
                'comment_url': comment.get('html_url'),
            },
            default=str,
        )
    )


def main():
    """Run the guarded status publication and retain the exact comment ID."""
    pods = json.loads(
        subprocess.check_output(
            ['kubectl', '-n', 'a2a-system', 'get', 'pods', '-o', 'json']
        )
    )['items']
    pod = next(
        p['metadata']['name']
        for p in pods
        if p['metadata']['name'].startswith('a2a-server-temporal-worker-')
        and not p['metadata'].get('deletionTimestamp')
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
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if run.returncode:
        print(run.stderr[-1200:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    path = Path('artifacts/task-jobs') / (
        'issue-5853-status-'
        + datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
        + '.json'
    )
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(path)
    print(json.dumps(data))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report())
    else:
        main()
