"""Inspect task/Job/PR lifecycle metadata without reading session history."""

import asyncio
import json
import logging
import os
import subprocess
import sys

from importlib import import_module
from pathlib import Path


PAGE_SIZE = 50


async def remote_report():
    """Read task outcomes and PR identity, never change live state."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    forgejo_json = import_module('a2a_server.forgejo_webhooks').forgejo_json
    kube = import_module('a2a_server.task_jobs').kube

    jobs = await kube(
        'GET',
        '/apis/batch/v1/namespaces/a2a-system/jobs'
        '?labelSelector=codetether.io%2Ftask-job%3Dtrue',
    )
    names = [j['metadata']['name'] for j in jobs['items']]

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        counts = await conn.fetch("""
            SELECT status,metadata->>'workflow_stage' AS stage,
                   metadata->>'job_wait_reason' AS waiting,count(*) AS count
            FROM tasks WHERE metadata->>'job_execution'='true'
            GROUP BY 1,2,3 ORDER BY 1,2,3
        """)
        retained = await conn.fetch(
            """
            SELECT id,title,status,metadata->>'job_name' AS job,
                   metadata->>'branch_name' AS branch,
                   metadata->>'repo' AS repo,
                   metadata->'job_terminal_evidence' AS evidence
            FROM tasks WHERE metadata->>'job_name'=ANY($1::text[])
            ORDER BY created_at
        """,
            names,
        )
        rows = await conn.fetch("""
            SELECT id,status,title,workspace_id,created_at,updated_at,
                   started_at,completed_at,error,metadata,
                   length(result) AS result_size
            FROM tasks
            WHERE metadata->>'job_execution'='true'
              AND (metadata->>'issue_number'='5853'
                OR metadata->>'workflow_stage'='code')
            ORDER BY (metadata->>'issue_number'='5853') DESC,
                     created_at DESC LIMIT 24
        """)
        queue = await conn.fetch("""
            SELECT id,status,title,created_at,updated_at,
                   metadata->>'workflow_stage' AS stage,
                   metadata->>'job_wait_reason' AS waiting,
                   metadata->>'job_name' AS job
            FROM tasks WHERE metadata->>'job_execution'='true'
              AND status NOT IN ('completed','failed','cancelled')
            ORDER BY created_at LIMIT 12
        """)
    tasks = []
    for row in rows:
        item = dict(row)
        meta = item.pop('metadata')
        if isinstance(meta, str):
            meta = json.loads(meta)
        item['metadata'] = {
            key: meta.get(key)
            for key in (
                'workflow_stage',
                'issue_number',
                'forgejo_agent_task_id',
                'pr_number',
                'branch_name',
                'pr_head_sha',
                'job_name',
                'job_wait_reason',
                'job_cleanup_scheduled',
                'forgejo_published_pr',
                'job_terminal_evidence',
            )
        }
        # No free-form prompt/output is printed by this probe.
        tasks.append(item)
    prs = []
    base = os.environ['FORGEJO_API_URL']
    for page in range(1, 5):
        batch = await forgejo_json(
            'GET',
            base,
            f'/repos/riley/spotlessbinco/pulls?state=all&limit=50&page={page}',
        )
        for pr in batch:
            if pr['head']['ref'].startswith('codetether/issue-'):
                prs.append(
                    {
                        key: pr.get(key)
                        for key in (
                            'number',
                            'state',
                            'merged',
                            'html_url',
                            'created_at',
                            'updated_at',
                        )
                    }
                    | {'branch': pr['head']['ref'], 'head': pr['head']['sha']}
                )
        if len(batch) < PAGE_SIZE:
            break
    # One measured remote comparison to establish this Forgejo API's contract.
    comparison = await forgejo_json(
        'GET',
        base,
        '/repos/riley/spotlessbinco/compare/'
        '3405352953f5fc5eba3c893c3682cae29d524a28...codetether%2Fissue-6026',
    )
    compare_summary = {
        'keys': list(comparison),
        'merge_base': comparison.get('merge_base'),
        'base_commit': comparison.get('base_commit'),
        'status': comparison.get('status'),
        'ahead_by': comparison.get('ahead_by'),
        'behind_by': comparison.get('behind_by'),
        'total_commits': comparison.get('total_commits'),
    }
    print(
        json.dumps(
            {
                'counts': [dict(r) for r in counts],
                'tasks': tasks,
                'comparison': compare_summary,
                'retained': [dict(r) for r in retained],
                'queue': [dict(r) for r in queue],
                'prs': prs,
            },
            default=str,
        )
    )
    await pool.close()


def main():
    """Run the read-only probe in the current API pod and save evidence."""
    pods = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'pods',
                '-l',
                'app.kubernetes.io/component=server,color=green',
                '-o',
                'json',
            ]
        )
    )['items']
    pod = next(
        p['metadata']['name']
        for p in pods
        if any(
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
        ],
        input=Path(__file__).read_text(),
        text=True,
        capture_output=True,
        check=False,
        timeout=150,
    )
    if run.returncode:
        print(run.stderr[-1600:])
        raise SystemExit(run.returncode)
    data = json.loads(run.stdout)
    js = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'jobs',
                '-l',
                'codetether.io/task-job=true',
                '-o',
                'json',
            ]
        )
    )['items']
    data['pod'] = pod
    data['jobs'] = [
        {
            'name': j['metadata']['name'],
            'task': j['metadata']
            .get('annotations', {})
            .get('codetether.io/task-id'),
            'created': j['metadata']['creationTimestamp'],
            'status': j.get('status', {}),
            'ttl': j['spec'].get('ttlSecondsAfterFinished'),
        }
        for j in js
    ]
    Path('artifacts/task-jobs/current-completion.json').write_text(
        json.dumps(data, indent=2) + '\n'
    )
    print('POD', pod, 'JOBS', len(js), 'COUNTS', data['counts'])
    print('QUEUE', json.dumps(data['queue'][:5]))
    print('COMPARE', json.dumps(data['comparison']))
    for item in data['retained']:
        evidence = item.pop('evidence') or []
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        for e in evidence:
            if e.get('container', 'worker') == 'worker':
                try:
                    msg = json.loads(e.get('message', '{}'))
                except ValueError:
                    msg = {}
                item.update(
                    {
                        key: msg.get(key)
                        for key in (
                            'audit_diagnostic',
                            'cleanup_eligible',
                            'unpushed',
                            'workspace_clean',
                            'head_sha',
                            'stash_empty',
                            'diagnostic',
                        )
                    }
                )
        print('RETAINED', json.dumps(item))
    by_branch = {p['branch']: p['number'] for p in data['prs']}
    for item in data['tasks']:
        meta = item['metadata']
        print(
            json.dumps(
                {
                    'task': item['id'],
                    'title': item['title'],
                    'status': item['status'],
                    'stage': meta['workflow_stage'],
                    'updated': item['updated_at'],
                    'error': item['error'],
                    'pr': by_branch.get(meta['branch_name']),
                    'job': meta['job_name'],
                    'result_size': item['result_size'],
                }
            )
        )


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(remote_report())
    else:
        main()
