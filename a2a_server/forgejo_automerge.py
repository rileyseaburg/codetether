"""Opt-in, head-pinned auto-merge for CodeTether-published Forgejo PRs."""
# ruff: noqa: PLC0415, E501

import asyncio
import json
import logging
import os

from urllib.parse import quote

from a2a_server.forgejo_automation_policy import pr_is_paused


logger = logging.getLogger(__name__)
_MERGE_RECONCILER = None


def start_auto_merge_reconciler():
    """Do not let slow unrelated terminal reconciliation block this gate."""
    global _MERGE_RECONCILER
    if _MERGE_RECONCILER is not None and not _MERGE_RECONCILER.done():
        return
    if not os.getenv('FORGEJO_AUTO_MERGE_REQUIRED_CHECKS'):
        return

    async def loop():
        while True:
            await asyncio.sleep(60)
            try:
                await reconcile_auto_merges()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning('Forgejo auto-merge reconciliation withheld')

    _MERGE_RECONCILER = asyncio.create_task(loop())


def required_checks(repo):
    """Missing or malformed repository policy disables merging, never weakens it."""
    try:
        rules = json.loads(
            os.getenv('FORGEJO_AUTO_MERGE_REQUIRED_CHECKS', '{}')
        )
        checks = rules.get(repo)
        if (
            isinstance(checks, list)
            and checks
            and all(isinstance(c, str) and c.strip() for c in checks)
        ):
            return set(checks)
    except (ValueError, AttributeError):
        pass
    return set()


def checks_succeeded(combined, required, sha):
    if not required or combined.get('state') != 'success':
        return False
    if combined.get('sha') != sha:
        return False
    rows = combined.get('statuses')
    if not isinstance(rows, list) or not rows:
        return False
    if combined.get('total_count', len(rows)) != len(rows):
        return False
    states = {}
    for row in rows:
        context = row.get('context')
        if not context or row.get('status') != 'success':
            return False
        states[context] = row['status']
    return required <= states.keys()


def changes_requested(reviews):
    """Respect the latest substantive review from each reviewer."""
    latest = {}
    for review in sorted(reviews, key=lambda r: int(r.get('id') or 0)):
        state = str(review.get('state') or '').upper()
        user = (review.get('user') or {}).get('id')
        if state in {
            'REQUEST_CHANGES',
            'CHANGES_REQUESTED',
            'APPROVED',
            'DISMISSED',
        }:
            if user is None:
                return True
            latest[user] = state
    return any(
        v in {'REQUEST_CHANGES', 'CHANGES_REQUESTED'} for v in latest.values()
    )


async def _record_terminal(conn, repo, number):
    await conn.execute(
        """UPDATE tasks SET metadata=jsonb_set(
        metadata,'{forgejo_published_pr,automerge_terminal}','true'::jsonb)
        WHERE metadata->>'source'='forgejo-webhook' AND metadata->>'repo'=$1
        AND metadata->'forgejo_published_pr'->>'number'=$2""",
        repo,
        str(number),
    )


async def maybe_merge(repo, number, issue_number, *, execute=False):
    """Read-only by default; caller must explicitly authorize an evaluated merge."""
    from a2a_server import database
    from a2a_server.forgejo_webhooks import forgejo_json

    required = required_checks(repo)
    if (
        not required
        or pr_is_paused(repo, number)
        or pr_is_paused(repo, issue_number)
    ):
        return {'eligible': False, 'reason': 'disabled-or-paused'}
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    owner, name = repo.split('/', 1)
    root = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    pool = await database.get_pool()
    if pool is None:
        return {'eligible': False, 'reason': 'ownership-storage-unavailable'}
    lock = f'forgejo-automerge:{base}:{repo}:{number}'
    async with pool.acquire() as conn:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1,0))', lock
        )
        try:
            # Only publication checkpoints owned by this integration are eligible.
            managed = await conn.fetchval(
                """SELECT metadata->>'forgejo_agent_task_id' FROM tasks
                WHERE metadata->>'source'='forgejo-webhook' AND metadata->>'repo'=$1
                AND metadata->>'issue_number'=$2
                AND metadata->'forgejo_published_pr'->>'number'=$3
                LIMIT 1""",
                repo,
                str(issue_number),
                str(number),
            )
            if not managed:
                return {'eligible': False, 'reason': 'not-managed'}
            pr = await forgejo_json('GET', base, f'{root}/pulls/{number}')
            head = pr.get('head') or {}
            sha = str(head.get('sha') or '')
            if pr.get('state') != 'open' or pr.get('merged'):
                if execute:
                    await _record_terminal(conn, repo, number)
                return {'eligible': False, 'reason': 'not-open'}
            if (
                pr.get('draft')
                or pr.get('work_in_progress')
                or str(pr.get('title', ''))
                .lower()
                .startswith(('wip:', '[wip]', 'draft:'))
            ):
                return {'eligible': False, 'reason': 'draft'}
            if pr.get('mergeable') is not True:
                return {'eligible': False, 'reason': 'not-mergeable'}
            if (
                head.get('ref') != f'codetether/issue-{issue_number}'
                or (head.get('repo') or {}).get('full_name') != repo
            ):
                return {'eligible': False, 'reason': 'branch-binding-mismatch'}
            repository = await forgejo_json('GET', base, root)
            if (pr.get('base') or {}).get('ref') != repository.get(
                'default_branch'
            ):
                return {'eligible': False, 'reason': 'unexpected-target'}
            if not repository.get('allow_merge_commits'):
                return {'eligible': False, 'reason': 'merge-commits-disabled'}
            combined = await forgejo_json(
                'GET', base, f'{root}/commits/{sha}/status?limit=100'
            )
            from a2a_server.forgejo_review_owner import enabled, identities

            if enabled(repo):
                rows = combined.get('statuses') or []
                if combined.get('total_count', len(rows)) != len(rows):
                    return {
                        'eligible': False,
                        'reason': 'check-evidence-truncated',
                    }
                retired = 'CodeTether PR Review / CodeTether Review (pull_request_target)'
                rows = [r for r in rows if r.get('context') != retired]
                combined = {
                    **combined,
                    'statuses': rows,
                    'total_count': len(rows),
                    'state': 'success'
                    if rows and all(r.get('status') == 'success' for r in rows)
                    else 'failure',
                }
            if not checks_succeeded(combined, required, sha):
                return {
                    'eligible': False,
                    'reason': 'checks-not-all-successful',
                    'head': sha,
                }
            if enabled(repo):
                owner_id, _ = identities(repo, number, sha)
                review = await database.db_get_task(owner_id)
                metadata = (review or {}).get('metadata') or {}
                if (
                    not review
                    or review.get('status') != 'completed'
                    or metadata.get('review_verdict') != 'APPROVED'
                    or not metadata.get('review_published')
                ):
                    return {
                        'eligible': False,
                        'reason': 'single-review-not-approved',
                    }
            native = await forgejo_json(
                'GET', base, f'{root}/agent/tasks/{int(managed)}'
            )
            if (
                native.get('status') == 'cancelled'
                or native.get('operation') != 'fix'
            ):
                return {
                    'eligible': False,
                    'reason': 'native-request-not-active',
                }
            if int(
                native.get('issue_index') or 0
            ) != issue_number or native.get('branch') != head.get('ref'):
                return {'eligible': False, 'reason': 'native-request-mismatch'}
            reviews = []
            for page in range(1, 21):
                batch = await forgejo_json(
                    'GET',
                    base,
                    f'{root}/pulls/{number}/reviews?limit=50&page={page}',
                )
                if not isinstance(batch, list):
                    return {
                        'eligible': False,
                        'reason': 'review-evidence-unavailable',
                    }
                if not batch:
                    break
                if any(
                    r.get('id') in {x.get('id') for x in reviews} for r in batch
                ):
                    return {
                        'eligible': False,
                        'reason': 'review-pagination-unreliable',
                    }
                reviews.extend(batch)
            else:
                return {
                    'eligible': False,
                    'reason': 'review-evidence-truncated',
                }
            if changes_requested(reviews):
                return {'eligible': False, 'reason': 'changes-requested'}
            current = await forgejo_json('GET', base, f'{root}/pulls/{number}')
            if (
                (current.get('head') or {}).get('sha') != sha
                or current.get('state') != 'open'
                or current.get('mergeable') is not True
            ):
                return {'eligible': False, 'reason': 'pr-changed'}
            if (
                current.get('draft')
                or current.get('work_in_progress')
                or str(current.get('title', ''))
                .lower()
                .startswith(('wip:', '[wip]', 'draft:'))
            ):
                return {'eligible': False, 'reason': 'pr-changed'}
            if (current.get('base') or {}).get('ref') != repository.get(
                'default_branch'
            ):
                return {'eligible': False, 'reason': 'pr-changed'}
            if not execute:
                return {'eligible': True, 'head': sha, 'dry_run': True}
            await forgejo_json(
                'POST',
                base,
                f'{root}/pulls/{number}/merge',
                {
                    'Do': 'merge',
                    'head_commit_id': sha,
                    'force_merge': False,
                    'merge_when_checks_succeed': False,
                    'delete_branch_after_merge': False,
                },
            )
            observed = await forgejo_json('GET', base, f'{root}/pulls/{number}')
            if observed.get('merged'):
                await _record_terminal(conn, repo, number)
            return {
                'eligible': True,
                'head': sha,
                'merged': bool(observed.get('merged')),
                'url': observed.get('html_url'),
            }
        finally:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1,0))', lock
            )


async def reconcile_auto_merges():
    """Periodic recovery for missed status hooks, limited to configured repositories."""
    from a2a_server import database

    try:
        rules = json.loads(
            os.getenv('FORGEJO_AUTO_MERGE_REQUIRED_CHECKS', '{}')
        )
        repos = [repo for repo in rules if required_checks(repo)]
    except (ValueError, TypeError):
        return
    if not repos:
        return
    pool = await database.get_pool()
    if pool is None:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT metadata->>'repo' AS repo,
            metadata->>'issue_number' AS issue,
            metadata->'forgejo_published_pr'->>'number' AS pr
            FROM tasks WHERE metadata->>'source'='forgejo-webhook'
            AND metadata->>'repo'=ANY($1::text[]) AND metadata ? 'forgejo_published_pr'
            AND metadata->'forgejo_published_pr'->>'automerge_terminal' IS DISTINCT FROM 'true'
            ORDER BY pr DESC LIMIT 50""",
            repos,
        )
    for row in rows:
        try:
            await maybe_merge(
                row['repo'], int(row['pr']), int(row['issue']), execute=True
            )
        except Exception:
            logger.warning(
                'Forgejo auto-merge withheld for %s PR %s',
                row['repo'],
                row['pr'],
            )
