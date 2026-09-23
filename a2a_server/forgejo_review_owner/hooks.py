"""Signed PR events and bounded recovery attach to one review owner.

``recovery`` and the package root import this module, so those two peers are
resolved at call time through ``importlib`` rather than at import time.
"""

import asyncio
import json
import logging
import os

from importlib import import_module
from types import ModuleType

from a2a_server import database as db
from a2a_server.forgejo_automerge import required_checks
from a2a_server.forgejo_review_owner import enabled, ensure_review
from a2a_server.forgejo_review_owner import state as review_state
from a2a_server.temporal.config import get_temporal_client


LOG = logging.getLogger(__name__)
_RECONCILER: dict[str, asyncio.Task | None] = {'task': None}
# Forgejo commit-status states that do not change without a new run.
SETTLED_CHECKS = {'success', 'failure', 'error', 'warning'}
RECONCILE_LIMIT = 50
RECONCILE_INTERVAL_SECONDS = 60
LIVE_TASK = {
    'pending',
    'queued',
    'assigned',
    'running',
    'working',
    'in_progress',
}
SELF_ACTORS = {'codetether-bot', 'codetether', 'spotless-agent'}
REVIEW_ACTIONS = {
    'opened',
    'synchronize',
    'synchronized',
    'reopened',
    'ready_for_review',
}


def _recovery() -> ModuleType:
    return import_module('a2a_server.forgejo_review_owner.recovery')


def start_reconciler():
    """Start at most one background reconciler per process."""
    running = _RECONCILER['task']
    if not os.getenv('FORGEJO_SINGLE_REVIEW_REPOS') or (
        running and not running.done()
    ):
        return

    async def loop() -> None:
        while True:
            await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)
            try:
                await reconcile()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.warning('Single-review reconciliation deferred')

    _RECONCILER['task'] = asyncio.create_task(loop())


async def _signal_retry(workflow_id, attempt) -> None:
    client = await get_temporal_client()
    await client.get_workflow_handle(workflow_id).signal('retry', attempt)


async def handle_event(payload):
    """Route one signed pull-request event to its single review owner."""
    repo = (payload.get('repository') or {}).get('full_name', '')
    if not enabled(repo):
        return None
    pr = payload.get('pull_request') or {}
    number = int(pr.get('number') or payload.get('number') or 0)
    action = payload.get('action')
    if action == 'review_requested':
        actor = (payload.get('sender') or {}).get('login', '')
        if actor.lower() in SELF_ACTORS:
            return {'accepted': False, 'reason': 'self-review-request'}
        task_id = await ensure_review(repo, number)
        task = await db.db_get_task(task_id)
        meta = task['metadata']
        if (
            task['status'] in {'failed', 'cancelled', 'completed'}
            and meta.get('review_verdict') != 'APPROVED'
        ):
            await _signal_retry(
                meta['review_workflow_id'],
                int(meta.get('review_attempt', 1)) + 1,
            )
        return {'accepted': True, 'review_task_id': task_id}
    if not number:
        return {'accepted': False, 'reason': 'invalid-pr'}
    if action in REVIEW_ACTIONS:
        task_id = await ensure_review(repo, number)
        return {'accepted': True, 'review_task_id': task_id}
    if action == 'closed':
        await cancel_old_reviews(repo, number, None)
    return {'accepted': False, 'reason': 'no-review-action'}


async def cancel_old_reviews(repo, number, current_sha):
    """Cancel live review owners bound to any other head of this PR."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT metadata->>'review_workflow_id' AS workflow
            FROM tasks WHERE metadata->>'source'='forgejo-review-owner'
            AND metadata->>'repo'=$1 AND metadata->>'pr_number'=$2
            AND ($3::text IS NULL OR metadata->>'pr_head_sha'!=$3)
            AND status NOT IN ('completed','failed','cancelled')""",
            repo,
            str(number),
            current_sha,
        )
    client = await get_temporal_client()
    for row in rows:
        await client.get_workflow_handle(row['workflow']).signal('cancel')


async def _settled_checks(meta, required) -> dict[str, str] | None:
    """Return required check states once all have settled, else None."""
    base, path = review_state.endpoint(meta['repo'])
    result = await review_state.forgejo_json(
        'GET', base, f'{path}/commits/{meta["pr_head_sha"]}/status?limit=100'
    )
    current = {
        r.get('context'): r.get('status')
        for r in (result.get('statuses') or [])
    }
    now = {c: current.get(c) for c in sorted(required)}
    if all(value in SETTLED_CHECKS for value in now.values()):
        return now
    return None


async def _writer_active(meta) -> bool:
    recovery_id = meta.get('recovery_task_id')
    if not recovery_id:
        return False
    recovery = await db.db_get_task(recovery_id)
    return bool(recovery and recovery['status'] in LIVE_TASK)


async def retry_after_checks(task_id):
    """Re-review a blocked head once its previously unsettled checks settle.

    Success lets the reviewer approve. A failure reaches the reviewer as
    concrete evidence, so recovery can repair it instead of stalling on
    "validation pending". Each distinct settled result is retried at most once.
    """
    task = await db.db_get_task(task_id)
    meta = task['metadata']
    if task['status'] != 'failed' or meta.get('review_verdict') != 'BLOCKED':
        return
    required = {
        c
        for c in required_checks(meta['repo'])
        if 'codetether' not in c.lower()
    }
    # An active writer's push will start a new-head review; do not race it.
    if not required or await _writer_active(meta):
        return
    now = await _settled_checks(meta, required)
    if now is None:
        return
    previous = {
        r.get('context'): r.get('status')
        for r in meta.get('review_context', {}).get('ci', [])
    }
    if now == {c: previous.get(c) for c in sorted(required)}:
        return  # The reviewer already judged exactly this evidence.
    signature = json.dumps(now, sort_keys=True)
    if meta.get('review_checks_retry') == signature:
        return
    await review_state.checkpoint(task_id, {'review_checks_retry': signature})
    await _signal_retry(
        meta['review_workflow_id'], int(meta.get('review_attempt', 1)) + 1
    )


async def reconcile():
    """Repair missed events for recently active enrolled PRs.

    Most-recently-touched owners come first so new PRs are never starved by
    old ones, and one PR's failure cannot abort reconciliation of the rest.
    """
    recovery = _recovery()
    await recovery.watch_recoveries()
    pool = await db.get_pool()
    if pool is None:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT metadata->>'repo' AS repo, metadata->>'pr_number' AS pr,
                max(updated_at) AS touched FROM tasks
            WHERE metadata->>'source'='forgejo-review-owner'
            GROUP BY 1, 2 ORDER BY touched DESC LIMIT $1""",
            RECONCILE_LIMIT,
        )
    for row in rows:
        if not enabled(row['repo']):
            continue
        try:
            task_id = await ensure_review(row['repo'], int(row['pr']))
            await retry_after_checks(task_id)
            await recovery.ensure_recovery(task_id)
        except RuntimeError:
            pass  # Closed, paused, or advanced PRs are expected here.
        except Exception as error:
            LOG.warning(
                'Single-review reconciliation deferred for PR #%s: %s',
                row['pr'],
                type(error).__name__,
            )
