"""Release retention slots held by Jobs that provably contain no user work.

Eligible: Failed Jobs whose task is a cancelled read-only review chunk, or
whose only terminated container is the workspace-prepare init container (no
clone ever succeeded). Complete coding Jobs are left for the controller audit.
Prints one line per decision; never deletes anything not matching the rules.
"""

import json
import subprocess
import sys


NS = 'a2a-system'


def kube(*args: str):
    """Read JSON from the fixed namespace's Kubernetes API."""
    return json.loads(
        subprocess.check_output(['kubectl', '-n', NS, *args, '-o', 'json'])
    )


jobs = kube('get', 'jobs', '-l', 'codetether.io/task-job=true')['items']
tasks = {}
for line in sys.stdin:
    if line.strip():
        row = json.loads(line)
        tasks[row['job']] = row

released = []
for job in jobs:
    name = job['metadata']['name']
    conds = {
        c['type']
        for c in job['status'].get('conditions', [])
        if c['status'] == 'True'
    }
    if 'Failed' not in conds:
        continue
    pods = kube('get', 'pods', '-l', f'batch.kubernetes.io/job-name={name}')[
        'items'
    ]
    init_only = all(
        not any(
            (c.get('state') or {}).get('terminated')
            for c in p['status'].get('containerStatuses', [])
        )
        for p in pods
    )
    task = tasks.get(name, {})
    readonly_cancelled = task.get('ro') == 'true' and task.get('status') in {
        'cancelled',
        'failed',
        'completed',
    }
    if not (readonly_cancelled or init_only):
        print(
            json.dumps(
                {'job': name, 'action': 'retain', 'task': task.get('status')}
            )
        )
        continue
    subprocess.run(
        ['kubectl', '-n', NS, 'delete', 'job', name, '--wait=false'],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    released.append(name)
    print(
        json.dumps(
            {
                'job': name,
                'action': 'released',
                'reason': 'readonly_terminal'
                if readonly_cancelled
                else 'init_failed_no_clone',
                'task': task.get('id'),
            }
        )
    )
print(json.dumps({'released': len(released)}))
