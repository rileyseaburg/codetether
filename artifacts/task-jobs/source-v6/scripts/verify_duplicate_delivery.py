"""Verify duplicate webhook deliveries are dropped by the real database.

Simulates the observed race: the same `comment.id` arriving through a repository
hook and the instance-wide system hook. Exactly one delivery must win. The
scratch claim rows are always removed.
"""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from a2a_server import forgejo_delivery_claim as claim  # noqa: E402

COMMENT_ID = 999000001
CTX = {
    'repo': 'riley/claim-probe',
    'number': 4857,
    'comment_id': COMMENT_ID,
}


async def main() -> int:
    dsn = os.environ['DATABASE_URL']
    key = claim.delivery_key('issue_comment', CTX)
    print(f'delivery_key={key}')

    conn = await asyncpg.connect(dsn)
    failures: list[str] = []
    try:
        await claim.ensure_table(conn)
        await conn.execute(
            f'DELETE FROM {claim._TABLE} WHERE delivery_key = $1', key
        )

        # Fire both deliveries concurrently, as the two hooks do.
        first, second = await asyncio.gather(
            claim.claim_delivery('issue_comment', CTX),
            claim.claim_delivery('issue_comment', CTX),
        )
        winners = [claimed for claimed, _ in (first, second) if claimed]
        print(f'winners={len(winners)}')
        if len(winners) != 1:
            failures.append(f'expected exactly 1 winner, got {len(winners)}')

        rows = await conn.fetchval(
            f'SELECT count(*) FROM {claim._TABLE} WHERE delivery_key = $1', key
        )
        print(f'claim_rows={rows}')
        if rows != 1:
            failures.append(f'expected 1 claim row, got {rows}')

        # A different comment must still be accepted.
        other = dict(CTX, comment_id=COMMENT_ID + 1)
        accepted, other_key = await claim.claim_delivery('issue_comment', other)
        print(f'new_comment_accepted={accepted}')
        if not accepted:
            failures.append('a genuinely new mention was suppressed')
        await conn.execute(
            f'DELETE FROM {claim._TABLE} WHERE delivery_key = $1', other_key
        )

        if failures:
            for item in failures:
                print(f'FAILURE: {item}')
            return 1
        print('duplicate_suppression_ok=true')
        return 0
    finally:
        await conn.execute(
            f'DELETE FROM {claim._TABLE} WHERE repo = $1', CTX['repo']
        )
        await conn.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
