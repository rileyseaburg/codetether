"""Read-only: grep every workflow on a ref for a set of patterns."""

import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import sys

from importlib import import_module
from pathlib import Path

REPO = 'riley/spotlessbinco'


async def report(ref: str, pattern: str) -> None:
    """Print matching lines, with file and line number, across workflows."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    root = f'/repos/{REPO}/contents/.forgejo/workflows'
    files = await fj('GET', base, f'{root}?ref={ref}')
    regex = re.compile(pattern, re.IGNORECASE)
    hits = []
    for item in files:
        data = await fj('GET', base, f'{root}/{item["name"]}?ref={ref}')
        text = base64.b64decode(data['content']).decode(errors='replace')
        for number, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                hits.append([item['name'], number, line.strip()[:160]])
    print(json.dumps(hits))


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
    for hit in json.loads(run.stdout):
        print(*hit, sep=' | ')


if __name__ == '__main__':
    if '--remote' in sys.argv:
        args = sys.argv[sys.argv.index('--remote') + 1 :]
        asyncio.run(report(args[0], args[1]))
    else:
        main()
