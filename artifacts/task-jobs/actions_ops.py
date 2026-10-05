"""Forgejo Actions operations for spotlessbinco, run from the Temporal pod.

Read-only by default. Mutating subcommands must be named explicitly and act
on one explicit target, so nothing here can fan out across PRs by accident.

  recent                   newest runs, all statuses (read-only)
  workflows                workflow list with ids/state (read-only)
  disable <workflow_file>  disable one workflow (reversible: enable)
  enable <workflow_file>   re-enable one workflow
  cancel <run_id>          cancel one run
"""

import asyncio
import json
import logging
import os
import subprocess
import sys

from http import HTTPStatus
from pathlib import Path

import httpx


REPO = 'riley/spotlessbinco'
MUTATING = {'disable', 'enable', 'cancel'}
COMMAND_ARG = 1
TARGETED_ARGC = 3


def _token() -> str:
    """Return the server's bot token from the pod environment."""
    token = os.environ.get('FORGEJO_TOKEN', '').strip()
    if not token:
        raise SystemExit('FORGEJO_TOKEN is not configured in this pod')
    return token


def _failed(response: httpx.Response) -> bool:
    return response.status_code >= HTTPStatus.BAD_REQUEST


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=os.environ['FORGEJO_API_URL'].rstrip('/'),
        headers={'Authorization': 'token ' + _token()},
        timeout=150,
    )


def _slim(run: dict) -> dict:
    return {
        'id': run.get('id'),
        'status': run.get('status'),
        'event': run.get('event'),
        'workflow': run.get('workflow_id'),
        'ref': run.get('prettyref'),
        'sha': str(run.get('commit_sha') or '')[:10],
        'created': run.get('created'),
        'started': run.get('started'),
    }


async def recent(client: httpx.AsyncClient) -> dict:
    """Return the newest runs across all statuses."""
    r = await client.get(f'/repos/{REPO}/actions/runs?limit=25&page=1')
    if _failed(r):
        return {'http_error': r.status_code}
    return {'runs': [_slim(x) for x in r.json().get('workflow_runs') or []]}


async def workflows(client: httpx.AsyncClient) -> dict:
    """Return the workflow list, or the raw error body if unsupported."""
    r = await client.get(f'/repos/{REPO}/actions/workflows')
    body = (
        r.json()
        if r.headers.get('content-type', '').startswith('application/json')
        else r.text[:300]
    )
    return {'status': r.status_code, 'body': body}


async def toggle(client: httpx.AsyncClient, name: str, action: str) -> dict:
    """Disable or enable one workflow, trying both verbs Forgejo has used."""
    path = f'/repos/{REPO}/actions/workflows/{name}/{action}'
    attempts = {}
    for method in ('PUT', 'POST'):
        r = await client.request(method, path)
        attempts[method] = r.status_code
        if not _failed(r):
            return {'ok': True, 'method': method, 'status': r.status_code}
    return {'ok': False, 'attempts': attempts}


async def cancel(client: httpx.AsyncClient, run_id: str) -> dict:
    """Cancel exactly one run by id."""
    path = f'/repos/{REPO}/actions/runs/{int(run_id)}/cancel'
    r = await client.post(path)
    return {'status': r.status_code, 'body': r.text[:200]}


async def remote(argv: list[str]) -> None:
    """Dispatch one subcommand inside the pod."""
    logging.disable(logging.CRITICAL)
    command, *rest = argv
    async with _client() as client:
        if command == 'recent':
            out = await recent(client)
        elif command == 'workflows':
            out = await workflows(client)
        elif command in {'disable', 'enable'}:
            out = await toggle(client, rest[0], command)
        elif command == 'cancel':
            out = await cancel(client, rest[0])
        else:
            raise SystemExit(f'unknown command {command}')
    print(json.dumps(out, default=str))


def main() -> None:
    """Validate arguments locally, then run the subcommand in the pod."""
    if len(sys.argv) <= COMMAND_ARG:
        raise SystemExit(__doc__)
    if sys.argv[COMMAND_ARG] in MUTATING and len(sys.argv) != TARGETED_ARGC:
        raise SystemExit('mutating commands take exactly one target')
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
        timeout=600,
    )
    if run.returncode:
        print(run.stderr[-1500:])
        raise SystemExit(run.returncode)
    print(json.dumps(json.loads(run.stdout), indent=1))


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(remote(sys.argv[sys.argv.index('--remote') + 1 :]))
    else:
        main()
