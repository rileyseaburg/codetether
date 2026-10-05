"""Read-only: which Git hook tooling does spotlessbinco declare on a ref?"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path


REPO = 'riley/spotlessbinco'
CANDIDATES = (
    '.husky',
    '.husky/pre-commit',
    '.husky/pre-push',
    '.husky/post-commit',
    '.githooks',
    '.git-hooks',
    'lefthook.yml',
    '.lefthook.yml',
    '.pre-commit-config.yaml',
    'package.json',
    'api/package.json',
    'Makefile',
    'AGENTS.md',
    'CONTRIBUTING.md',
)


async def report(ref: str) -> None:
    """Report existence and relevant lines of each hook-related path."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    out = {}
    for name in CANDIDATES:
        data = await fj(
            'GET',
            base,
            f'/repos/{REPO}/contents/{name}?ref={ref}',
            allow_not_found=True,
        )
        if data is None:
            continue
        if isinstance(data, list):
            out[name] = {'dir': [d['name'] for d in data]}
            continue
        text = base64.b64decode(data.get('content') or '').decode(
            errors='replace'
        )
        lines = text.splitlines()
        if name.endswith(('package.json', 'Makefile', '.md')):
            keep = [
                f'{i}: {line.strip()[:160]}'
                for i, line in enumerate(lines, 1)
                if any(
                    k in line.lower()
                    for k in (
                        'husky',
                        'lefthook',
                        'pre-commit',
                        'precommit',
                        'hook',
                        '"prepare"',
                        'post-commit',
                        'pull',
                        'rebase',
                        'merge main',
                        'origin/main',
                    )
                )
            ]
            out[name] = {'matches': keep[:25], 'lines': len(lines)}
        else:
            out[name] = {'text': lines[:60]}
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
