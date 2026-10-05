"""Read-only: commit statuses per PR head and Actions runs on the branch."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path

REPO = 'riley/spotlessbinco'


async def report(branch: str, shas: list[str]) -> None:
    """Print statuses per SHA plus recent Actions runs and workflow triggers."""
    logging.disable(logging.CRITICAL)
    fj = import_module('a2a_server.forgejo_webhooks').forgejo_json
    base = os.environ['FORGEJO_API_URL']
    root = f'/repos/{REPO}'
    out = {'statuses': {}, 'runs': None, 'workflow': None}
    for sha in shas:
        st = await fj('GET', base, f'{root}/commits/{sha}/status?limit=100')
        out['statuses'][sha[:10]] = {
            'state': st.get('state'),
            'checks': [
                (
                    s['context'],
                    s['status'],
                    s.get('target_url'),
                    s.get('description'),
                    s.get('updated_at'),
                )
                for s in (st.get('statuses') or [])
            ],
        }
    for path in (
        f'{root}/actions/runs?limit=20&branch={branch}',
        f'{root}/actions/runs?limit=30&status=waiting',
    ):
        try:
            data = await fj('GET', base, path)
        except Exception as exc:
            data = {'error': f'{type(exc).__name__}: {str(exc)[:200]}'}
        items = data.get('workflow_runs') or data.get('entries') or []
        out.setdefault('actions', {})[path.split('/')[-1]] = (
            [
                {
                    k: i.get(k)
                    for k in (
                        'id',
                        'name',
                        'display_title',
                        'status',
                        'conclusion',
                        'event',
                        'head_branch',
                        'head_sha',
                        'workflow_id',
                        'created_at',
                        'run_number',
                    )
                }
                for i in items
                if branch in str(i.get('head_branch') or '')
                or any(
                    str(i.get('head_sha') or '').startswith(s[:10])
                    for s in shas
                )
            ]
            if isinstance(data, dict) and 'error' not in data
            else data
        )
    wf = await fj(
        'GET', base, f'{root}/contents/.forgejo/workflows?ref={branch}'
    )
    out['workflow_files'] = (
        [w['name'] for w in wf] if isinstance(wf, list) else wf
    )
    print(json.dumps(out, default=str))


def main() -> None:
    """Run inside the ready Temporal worker."""
    pods = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'pods',
                '-o',
                'json',
            ]
        )
    )['items']
    pod = next(
        p['metadata']['name']
        for p in pods
        if p['metadata']['name'].startswith('a2a-server-temporal-worker-')
        and not p['metadata'].get('deletionTimestamp')
        and any(
            c.get('ready')
            for c in p.get('status', {}).get('containerStatuses', [])
        )
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
        timeout=180,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    print(json.dumps(json.loads(run.stdout), indent=1))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        args = sys.argv[sys.argv.index('--remote') + 1 :]
        asyncio.run(report(args[0], args[1:]))
    else:
        main()