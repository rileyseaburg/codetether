"""Measure metadata sizes and safely adjust API burst memory via Argo."""

import asyncio
import json
import logging
import subprocess
import sys

from importlib import import_module
from pathlib import Path


async def report():
    """Read logical JSON sizes without returning the payloads themselves."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        data = await conn.fetch("""
            SELECT status,count(*) AS count,
                   max(octet_length(metadata::text)) AS largest_bytes,
                   sum(octet_length(metadata::text)) AS total_bytes
            FROM tasks WHERE metadata->>'job_execution'='true'
            AND metadata->>'job_cleanup_scheduled' IS DISTINCT FROM 'true'
            GROUP BY status
        """)
        task_sizes = await conn.fetch("""
            SELECT max(octet_length(prompt)) AS largest_prompt,
                   max(octet_length(result)) AS largest_result,
                   sum(octet_length(result)) AS total_result
            FROM tasks
        """)
    print(json.dumps([dict(r) for r in data]))
    print(json.dumps([dict(r) for r in task_sizes]))
    await pool.close()


def adjust():
    """Reserve realistic memory and bound the API at 4 GiB during recovery."""
    app = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'argocd',
                'get',
                'application',
                'codetether-a2a-server',
                '-o',
                'json',
            ]
        )
    )
    prefix = '/spec/source/helm/valuesObject/resources/'
    patch = [
        {
            'op': 'test',
            'path': '/metadata/resourceVersion',
            'value': app['metadata']['resourceVersion'],
        }
    ]
    for path, value in [('requests/memory', '1Gi'), ('limits/memory', '4Gi')]:
        patch.append({'op': 'replace', 'path': prefix + path, 'value': value})
    subprocess.run(
        [
            'kubectl',
            '-n',
            'argocd',
            'patch',
            'application',
            'codetether-a2a-server',
            '--type=json',
            '-p',
            json.dumps(patch),
        ],
        check=True,
    )


if __name__ == '__main__':
    if '--adjust' in sys.argv:
        adjust()
    elif '--remote' in sys.argv:
        asyncio.run(report())
    else:
        pods = json.loads(
            subprocess.check_output(
                ['kubectl', '-n', 'a2a-system', 'get', 'pods', '-o', 'json']
            )
        )['items']
        pod = next(
            p['metadata']['name']
            for p in pods
            if p['metadata']['name'].startswith('a2a-server-temporal-worker-')
            and not p['metadata'].get('deletionTimestamp')
        )
        result = subprocess.run(
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
            ],
            input=Path(__file__).read_text(),
            text=True,
            check=False,
        )
        raise SystemExit(result.returncode)
