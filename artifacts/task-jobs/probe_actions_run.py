"""Read-only: dump the field names and trimmed values of a few runs."""

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


async def report(status: str) -> None:
    """Print the raw schema of recent runs, values truncated."""
    logging.disable(logging.CRITICAL)
    token = import_module('a2a_server.forgejo_agent_client')._token()
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    async with httpx.AsyncClient(
        base_url=base, headers={'Authorization': 'token ' + token}, timeout=120
    ) as client:
        r = await client.get(
            f'/repos/{REPO}/actions/runs?limit=50&status={status}'
        )
    data = r.json()
    runs = data.get('workflow_runs') or []
    out = []
    for run in runs:
        out.append(
            {
                k: (str(v)[:90] if not isinstance(v, (int, bool)) else v)
                for k, v in run.items()
                if not isinstance(v, (dict, list))
            }
        )
    print(
        json.dumps(
            {
                'total_count': data.get('total_count'),
                'keys': sorted(runs[0].keys()) if runs else [],
                'runs': out,
            },
            default=str,
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
        timeout=300,
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
