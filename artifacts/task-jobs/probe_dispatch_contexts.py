"""Read-only: what statuses do workflow_dispatch runs publish, and on which SHA?

Finds recent completed workflow_dispatch runs of deploy-dev.yml and lists the
commit statuses on their commit, so the server knows which contexts a dispatch
produces versus the required ``(pull_request)`` contexts.
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


async def report(workflow: str) -> None:
    """List dispatch runs of ``workflow`` and the statuses on their commits."""
    logging.disable(logging.CRITICAL)
    token = import_module('a2a_server.forgejo_agent_client')._token()
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    found = []
    async with httpx.AsyncClient(
        base_url=base, headers={'Authorization': 'token ' + token}, timeout=120
    ) as client:
        for page in range(1, 9):
            r = await client.get(
                f'/repos/{REPO}/actions/runs?limit=50&page={page}'
                '&event=workflow_dispatch'
            )
            if r.status_code >= 400:
                found.append({'http_error': r.status_code, 'page': page})
                break
            items = r.json().get('workflow_runs') or []
            found += [
                i
                for i in items
                if i.get('workflow_id') == workflow
                and i.get('event') == 'workflow_dispatch'
            ]
            if len(found) >= 3 or len(items) < 50:
                break
        out = []
        for run in [f for f in found if 'id' in f][:3]:
            sha = run.get('commit_sha')
            st = await client.get(
                f'/repos/{REPO}/commits/{sha}/status?limit=100'
            )
            out.append(
                {
                    'run': run.get('id'),
                    'status': run.get('status'),
                    'ref': run.get('prettyref'),
                    'sha': str(sha)[:10],
                    'contexts': [
                        (s['context'], s['status'])
                        for s in (st.json().get('statuses') or [])
                    ],
                }
            )
    print(
        json.dumps(
            {
                'dispatch_runs': out,
                'errors': [f for f in found if 'http_error' in f],
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
    print(json.dumps(json.loads(run.stdout), indent=1))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[-1]))
    else:
        main()
