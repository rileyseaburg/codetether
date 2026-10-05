"""Read-only: Actions queue depth and whether merge heads got any run.

Paginates small pages of /actions/runs with a long timeout because large
list requests time out behind the proxy (HTTP 524).
"""

import asyncio
import collections
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import httpx


REPO = 'riley/spotlessbinco'
PAGE = 50
PAGES = 8


async def report(heads: list[str]) -> None:
    """Count runs by status/event and match head SHAs to runs."""
    logging.disable(logging.CRITICAL)
    token = os.environ['FORGEJO_TOKEN'].strip()
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    runs, errors = [], []
    async with httpx.AsyncClient(
        base_url=base, headers={'Authorization': 'token ' + token}, timeout=120
    ) as client:
        for status in ('waiting', 'running', None):
            for page in range(1, PAGES + 1):
                query = f'limit={PAGE}&page={page}'
                if status:
                    query += f'&status={status}'
                try:
                    r = await client.get(f'/repos/{REPO}/actions/runs?{query}')
                except Exception as exc:
                    errors.append([status, page, type(exc).__name__])
                    break
                if r.status_code >= HTTPStatus.BAD_REQUEST:
                    errors.append([status, page, r.status_code])
                    break
                items = r.json().get('workflow_runs') or []
                for i in items:
                    runs.append(
                        {
                            'id': i.get('id'),
                            'status': i.get('status'),
                            'event': i.get('event'),
                            'path': i.get('workflow_id'),
                            'branch': i.get('prettyref'),
                            'sha': str(i.get('commit_sha') or '')[:10],
                            'created': i.get('created'),
                            'queried': status,
                        }
                    )
                if len(items) < PAGE:
                    break
    unique = {r['id']: r for r in runs}.values()
    by_status = collections.Counter(r['status'] for r in unique)
    by_path = collections.Counter(
        (r['status'], str(r['path']).split('@')[0])
        for r in unique
        if r['status'] in {'waiting', 'running', 'queued'}
    )
    shas = {r['sha'] for r in unique}
    print(
        json.dumps(
            {
                'at': datetime.now(UTC).isoformat(),
                'sampled_runs': len(unique),
                'by_status': by_status,
                'active_by_workflow': [
                    [*k, v] for k, v in by_path.most_common(20)
                ],
                'oldest_waiting': sorted(
                    str(r['created'])
                    for r in unique
                    if r['status'] == 'waiting'
                )[:3],
                'sample': list(unique)[:3],
                'heads_with_any_run': {h: h[:10] in shas for h in heads},
                'errors': errors,
            },
            default=str,
        )
    )


def main() -> None:
    """Run in the ready Temporal worker and save a timestamped artifact."""
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
            *sys.argv[1:],
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        check=False,
        timeout=1500,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
    path = Path('artifacts/task-jobs') / f'actions-queue-{stamp}.json'
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)
    print(json.dumps(data, indent=1))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[sys.argv.index('--remote') + 1 :]))
    else:
        main()
