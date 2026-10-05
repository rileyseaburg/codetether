"""Read-only: who creates merge-from-main heads, and does Actions run on them?

Uses a long HTTP timeout because the Actions list endpoints time out at the
default client limit. Prints metadata only, never tokens or log contents.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys

from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import httpx

REPO = 'riley/spotlessbinco'


async def _get(client, path):
    try:
        r = await client.get(path)
        if r.status_code >= 400:
            return {'http_error': r.status_code}
        return r.json()
    except Exception as exc:
        return {'error': type(exc).__name__}


async def report(branch: str) -> None:
    """Summarize recent PR heads, their authors, and Actions runs/runners."""
    logging.disable(logging.CRITICAL)
    token = import_module('a2a_server.forgejo_agent_client')._token()
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    root = f'/repos/{REPO}'
    headers = {'Authorization': 'token ' + token}
    async with httpx.AsyncClient(
        base_url=base, headers=headers, timeout=150
    ) as client:
        prs = await _get(
            client, f'{root}/pulls?state=open&limit=50&sort=recentupdate'
        )
        heads = []
        for pr in prs if isinstance(prs, list) else []:
            sha = pr['head']['sha']
            commit = await _get(client, f'{root}/git/commits/{sha}')
            status = await _get(
                client, f'{root}/commits/{sha}/status?limit=100'
            )
            info = commit.get('commit', {}) if isinstance(commit, dict) else {}
            heads.append(
                {
                    'pr': pr['number'],
                    'ref': pr['head']['ref'],
                    'updated': pr['updated_at'],
                    'head': sha[:10],
                    'author': (commit.get('author') or {}).get('login')
                    if isinstance(commit, dict)
                    else None,
                    'committer_name': (info.get('committer') or {}).get('name'),
                    'committed': (info.get('committer') or {}).get('date'),
                    'message': (info.get('message') or '').splitlines()[0][:80]
                    if info.get('message')
                    else None,
                    'parents': len(commit.get('parents') or [])
                    if isinstance(commit, dict)
                    else None,
                    'checks': sorted(
                        s['context'] for s in (status.get('statuses') or [])
                    )
                    if isinstance(status, dict)
                    else status,
                }
            )
        runs = await _get(
            client, f'{root}/actions/runs?limit=30&branch={branch}'
        )
        recent = await _get(client, f'{root}/actions/runs?limit=40')
        runners = await _get(client, f'{root}/actions/runners')
        repo_runners = await _get(client, '/admin/actions/runners')
    slim = (
        'id',
        'display_title',
        'status',
        'conclusion',
        'event',
        'head_branch',
        'head_sha',
        'path',
        'created_at',
        'trigger_actor',
    )

    def runs_of(data):
        items = (
            (data or {}).get('workflow_runs')
            if isinstance(data, dict)
            else None
        )
        if items is None:
            return data
        out = []
        for i in items:
            row = {k: i.get(k) for k in slim}
            actor = row.get('trigger_actor')
            row['trigger_actor'] = (
                (actor or {}).get('login') if isinstance(actor, dict) else actor
            )
            row['head_sha'] = str(row.get('head_sha') or '')[:10]
            out.append(row)
        return out

    def runners_of(data):
        items = None
        if isinstance(data, dict):
            items = data.get('runners') or data.get('entries')
        if items is None:
            return data
        return [
            {
                k: r.get(k)
                for k in ('id', 'name', 'status', 'busy', 'labels', 'version')
            }
            for r in items
        ]

    print(
        json.dumps(
            {
                'at': datetime.now(UTC).isoformat(),
                'heads': heads,
                'branch_runs': runs_of(runs),
                'recent_runs': runs_of(recent),
                'repo_runners': runners_of(runners),
                'admin_runners': runners_of(repo_runners),
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
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S')
    path = Path('artifacts/task-jobs') / f'ci-infra-{stamp}.json'
    path.write_text(json.dumps(data, indent=2) + '\n')
    print('ARTIFACT', path)


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report(sys.argv[-1]))
    else:
        main()
