"""Read-only: authorship/committer/parents of explicit commit SHAs."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path

REPO = 'riley/spotlessbinco'


async def report(shas: list[str]) -> None:
    """Print one line of metadata per commit."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    out = []
    for sha in shas:
        c = await fj('GET', base, f'/repos/{REPO}/git/commits/{sha}')
        info = c.get('commit') or {}
        out.append(
            {
                'sha': c.get('sha', sha)[:12],
                'author_login': (c.get('author') or {}).get('login'),
                'committer_login': (c.get('committer') or {}).get('login'),
                'author': (info.get('author') or {}).get('name'),
                'committer': (info.get('committer') or {}).get('name'),
                'date': (info.get('committer') or {}).get('date'),
                'parents': [p['sha'][:10] for p in c.get('parents') or []],
                'message': (info.get('message') or '').splitlines()[0][:100],
                'verified': (info.get('verification') or {}).get('verified'),
                'signer': (info.get('verification') or {}).get('reason'),
            }
        )
    print(json.dumps(out))


def main() -> None:
    """Run in the ready Temporal worker."""
    names = subprocess.check_output(
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
    ).split()
    pod = next(p for p in names if p.startswith('a2a-server-temporal-worker-'))
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
        timeout=300,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    for row in json.loads(run.stdout):
        print(json.dumps(row))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[sys.argv.index('--remote') + 1 :]))
    else:
        main()
