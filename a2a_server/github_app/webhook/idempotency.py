"""Cross-replica idempotency gate for GitHub webhook deliveries.

GitHub redelivers webhooks when the endpoint is slow or returns a non-2xx
status, and multiple worker replicas may receive the same delivery. Without a
claim, each delivery runs ``handle_fix_request`` and posts a duplicate
"Picked up this request" comment.

This module provides an atomic, single-winner claim keyed on the
``X-GitHub-Delivery`` header. The first caller to ``claim_delivery`` for a
given delivery ID wins (returns ``True``); concurrent/repeat callers lose
(return ``False``) and the router short-circuits before any dispatch.

The claim is backed by Postgres ``INSERT ... ON CONFLICT DO NOTHING`` so it is
correct across replicas. If the database is unavailable we fail open (allow
the event) so a transient DB outage never silently drops real work.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

# Deliveries older than this are pruned opportunistically. GitHub retries
# within ~hours, so a few days is more than enough.
_RETENTION = "7 days"


async def _ensure_table(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS github_webhook_deliveries (
            delivery_id TEXT PRIMARY KEY,
            event_name  TEXT,
            claimed_at  TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


async def claim_delivery(delivery_id: str, event_name: str = '') -> bool:
    """Atomically claim a webhook delivery. Returns True for the single winner.

    - Returns ``True`` exactly once per ``delivery_id`` (the caller that should
      process the event).
    - Returns ``False`` for repeat/concurrent deliveries of the same id.
    - Fails open (``True``) when no delivery id is present or the DB is
      unavailable, so we never drop genuine first-time events.
    """
    if not delivery_id:
        # No delivery header (e.g. internal dispatch or test) — can't dedupe,
        # so allow it through rather than blocking real work.
        return True
    try:
        # Imported lazily to avoid a circular import with the database layer
        # (same pattern as ``active_work.has_active_github_app_task``).
        from a2a_server import database as db  # noqa: PLC0415

        pool = await db.get_pool()
        if not pool:
            return True

        async with pool.acquire() as conn:
            await _ensure_table(conn)
            row = await conn.fetchrow(
                """
                INSERT INTO github_webhook_deliveries (delivery_id, event_name)
                VALUES ($1, $2)
                ON CONFLICT (delivery_id) DO NOTHING
                RETURNING delivery_id
                """,
                delivery_id,
                event_name,
            )
            won = row is not None
            if won:
                # Opportunistic prune of stale rows; cheap at low volume.
                await conn.execute(
                    "DELETE FROM github_webhook_deliveries "
                    f"WHERE claimed_at < NOW() - INTERVAL '{_RETENTION}'"
                )
            else:
                logger.info(
                    'duplicate webhook delivery ignored id=%s event=%s',
                    delivery_id,
                    event_name,
                )
            return won
    except Exception as exc:  # pragma: no cover - defensive fail-open
        logger.warning(
            'idempotency claim failed (failing open) id=%s: %s',
            delivery_id,
            exc,
        )
        return True
