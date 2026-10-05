"""Diagnose the single-review reconciler, one step at a time, read-mostly.

Only the read steps run by default. ``ensure_review`` and ``ensure_recovery``
are idempotent but can dispatch work, so they are skipped unless requested.
"""

import asyncio
import json
import logging
import subprocess
import sys
import traceback

from importlib import import_module
from pathlib import Path


async def report(full: bool) -> None:
    """Replay reconcile() stepwise and print the first real traceback."""
    logging.disable(logging.CRITICAL)
    db = import_module('a2a_server.database')
    owner = import_module('a2a_server.forgejo_review_owner')
    recovery = import_module('a2a_server.forgejo_review_owner.recovery')
    try:
        await recovery.watch_recoveries()
        print('watch_recoveries: ok')
    except Exception:
        print('watch_recoveries FAILED')
        print(traceback.format_exc()[-3000:])
        return
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""SELECT DISTINCT metadata->>'repo' AS repo,
            metadata->>'pr_number' AS pr FROM tasks
            WHERE metadata->>'source'='forgejo-review-owner' LIMIT 50""")
    print('owner prs:', len(rows), json.dumps([r['pr'] for r in rows]))
    state = import_module('a2a_server.forgejo_review_owner.state')
    failures = {}
    for row in rows:
        try:
            pr = await state.current_pr(row['repo'], int(row['pr']))
            _ = pr['head']['sha']
        except RuntimeError as exc:
            failures.setdefault(f'RuntimeError:{str(exc)[:60]}', []).append(
                row['pr'])
        except Exception as exc:
            failures.setdefault(
                f'{type(exc).__name__}:{str(exc)[:80]}', []).append(row['pr'])
    print('current_pr outcomes:', json.dumps(failures))
    if not full:
        return
    for row in rows:
        if not owner.enabled(row['repo']):
            continue
        try:
            await owner.ensure_review(row['repo'], int(row['pr']))
        except RuntimeError as exc:
            print('pr', row['pr'], 'RuntimeError (tolerated):', str(exc)[:120])
        except Exception:
            print('pr', row['pr'], 'ensure_review FAILED')
            print(traceback.format_exc()[-2500:])
            return
    print('ensure_review loop: ok')


def main() -> None:
    """Run in the ready API pod, where the reconciler itself runs."""
    pods = json.loads(subprocess.check_output([
        'kubectl', '-n', 'a2a-system', 'get', 'pods', '-l',
        'app.kubernetes.io/component=server,color=green', '-o', 'json',
    ]))['items']
    pod = next(
        p['metadata']['name'] for p in pods
        if not p['metadata'].get('deletionTimestamp')
        and any(c.get('ready') for c in
                p.get('status', {}).get('containerStatuses', [])))
    run = subprocess.run(
        ['kubectl', '-n', 'a2a-system', 'exec', '-i', pod, '--', 'python3',
         '-', '--remote', *sys.argv[1:]],
        input=Path(__file__).read_text(), text=True, capture_output=True,
        check=False, timeout=300)
    print(run.stdout or '', run.stderr[-2500:] if run.returncode else '')


if __name__ == '__main__':
    if '--remote' in sys.argv:
        asyncio.run(report('--full' in sys.argv))
    else:
        main()