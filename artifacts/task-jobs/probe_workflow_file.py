"""Read-only: print the trigger block of selected workflows on a branch."""

import asyncio
import base64
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path

REPO = 'riley/spotlessbinco'


async def report(branch: str, names: list[str]) -> None:
    """Print each workflow's leading lines (triggers and path filters)."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    for name in names:
        data = await fj(
            'GET', base,
            f'/repos/{REPO}/contents/.forgejo/workflows/{name}?ref={branch}')
        text = base64.b64decode(data['content']).decode()
        print(f'===== {name} ({len(text.splitlines())} lines)')
        print('\n'.join(text.splitlines()[:60]))


def main() -> None:
    """Run inside the ready Temporal worker."""
    out = subprocess.check_output([
        'kubectl', '-n', 'a2a-system', 'get', 'pods', '-o',
        'jsonpath={range .items[*]}{.metadata.name}{"\\n"}{end}'], text=True)
    pod = next(p for p in out.split()
               if p.startswith('a2a-server-temporal-worker-'))
    run = subprocess.run(
        ['kubectl', '-n', 'a2a-system', 'exec', '-i', pod, '--', 'python3',
         '-', '--remote', *sys.argv[1:]],
        input=Path(__file__).read_text(), text=True, capture_output=True,
        check=False, timeout=120)
    print(run.stdout or run.stderr[-1500:])


if __name__ == '__main__':
    if '--remote' in sys.argv:
        args = sys.argv[sys.argv.index('--remote') + 1:]
        asyncio.run(report(args[0], args[1:]))
    else:
        main()