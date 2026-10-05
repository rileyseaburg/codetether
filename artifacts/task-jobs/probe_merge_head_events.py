"""Read-only: did Forgejo record any Actions run for recent merge heads?

Scans the newest runs (all statuses) for the given head SHAs and PR refs, and
reports, per PR, whether a pull_request run exists for its current head.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path

import httpx

REPO = 'riley/spotlessbinco'


async def report(pages: int) -> None:
    """Compare open PR heads with the newest Actions runs."""
    logging.disable(logging.CRITICAL)
    token = import_module('a2a_server.forgejo_agent_client')._token()
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    runs = []
    async with httpx.AsyncClient(
        base_url=base, headers={'Authorization': 'token ' + token}, timeout=120
    ) as client:
        prs = (
            await client.get(
                f'/repos/{REPO}/pulls?state=open&limit=50&sort=recentupdate'
            )
        ).json()
        for page in range(1, pages + 1):
            r = await client.get(
                f'/repos/{REPO}/actions/runs?limit=50&page={page}'
            )
            if r.status_code >= 400:
                runs.append({'http_error': r.status_code, 'page': page})
                break
            items = r.json().get('workflow_runs') or []
            runs += items
            if len(items) < 50:
                break
    good = [r for r in runs if 'id' in r]
    by_sha = {}
    for run in good:
        by_sha.setdefault(str(run.get('commit_sha')), []).append(
            [run.get('workflow_id'), run.get('event'), run.get('status')]
        )
    oldest = min((str(r.get('created')) for r in good), default=None)
    rows = []
    for pr in prs:
        sha = pr['head']['sha']
        rows.append(
            {
                'pr': pr['number'],
                'head': sha[:10],
                'updated': pr['updated_at'],
                'runs_for_head': by_sha.get(sha, []),
            }
        )
    print(
        json.dumps(
            {
                'scanned_runs': len(good),
                'oldest_scanned': oldest,
                'errors': [r for r in runs if 'http_error' in r],
                'prs': rows,
            }
        )
    )


def main() -> None:
    """Run in the ready Temporal worker."""
    out = subprocess.check_output(
        [
            'kubectl',
            '-n',
            'a2a-system',
            'get',
            'pods',
            '-o',
            'jsonpath={range .items[*]}{.metadata.name}{"\\n"}{end}',
        ],
        text=True,
    )
    pod = next(
        p for p in out.split() if p.startswith('a2a-server-temporal-worker-')
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
        timeout=900,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    path = Path('artifacts/task-jobs/merge-head-events.json')
    path.write_text(json.dumps(data, indent=2) + '\n')
    print(
        'ARTIFACT',
        path,
        'scanned',
        data['scanned_runs'],
        'since',
        data['oldest_scanned'],
        'errors',
        data['errors'],
    )


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(int(sys.argv[-1])))
    else:
        main()
