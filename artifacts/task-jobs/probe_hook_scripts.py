"""Read-only: fetch the hook-related scripts spotlessbinco runs on commit/push."""

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
FILES = (
    'scripts/dev/commit-cache-prefill-worker.sh',
    'scripts/dev/pre-push-cache-manifest-check.sh',
)


async def report(ref: str) -> None:
    """Print each script's full text (repository content, not secrets)."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    out = {}
    for name in FILES:
        data = await fj(
            'GET',
            base,
            f'/repos/{REPO}/contents/{name}?ref={ref}',
            allow_not_found=True,
        )
        if data is None:
            out[name] = None
            continue
        out[name] = base64.b64decode(data.get('content') or '').decode(
            errors='replace'
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
    for name, text in json.loads(run.stdout).items():
        print(f'===== {name}')
        print(text if text is not None else '(missing)')


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[-1]))
    else:
        main()
