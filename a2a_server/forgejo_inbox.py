"""Durable Forgejo intake before any Vault, repository or worker side effect.

PostgreSQL is the intake source of truth; Temporal still owns coding stages
after handoff. Receipt is fail-closed and does not depend on webhook redelivery.
"""
# Lazy database configuration; keep SQL statements readable.
# ruff: noqa: PLC0415, E501

from __future__ import annotations

import hashlib
import json

from contextlib import asynccontextmanager

from fastapi import HTTPException

from a2a_server.forgejo_delivery_claim import delivery_key
from a2a_server.forgejo_execution_ownership import (
    execution_ownership as execution_ownership,  # noqa: PLC0414 (public re-export)
)
from a2a_server.github_app.mention import is_fix_request


async def pool():
    """Require durable storage instead of acknowledging unrecorded work."""
    from a2a_server import database

    value = await database.get_pool()
    if value is None:
        raise HTTPException(503, 'Forgejo inbox storage unavailable')
    return value


async def ensure_schema(conn):
    """Serialize additive schema setup across concurrent API replicas."""
    async with conn.transaction():
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('forgejo-inbox-schema', 0))"
        )
        await _create_schema(conn)


async def _create_schema(conn) -> None:
    """Create the additive inbox; legacy delivery claims remain untouched."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forgejo_webhook_inbox (
            delivery_id TEXT PRIMARY KEY,
            event TEXT NOT NULL,
            context JSONB NOT NULL,
            api_base TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            plan JSONB,
            result JSONB,
            native_task_id BIGINT,
            receipt_notified BOOLEAN NOT NULL DEFAULT FALSE,
            attempts INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (state IN ('pending', 'dispatched', 'acknowledged'))
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS forgejo_inbox_due
        ON forgejo_webhook_inbox (next_attempt_at)
        WHERE state != 'acknowledged'
    """)


def decode(value):
    """Support asyncpg's default JSON codec and configured JSON codecs."""
    return json.loads(value) if isinstance(value, str) else value


async def accept(event, context, base):
    """Commit one immutable receipt, then return its durable identity."""
    event = 'issues' if event == 'issue' else event
    key = delivery_key(event, context)
    if not key:
        raise HTTPException(422, 'Forgejo delivery identity missing')
    identity = hashlib.sha256(f'{base.rstrip("/")}:{key}'.encode()).hexdigest()
    # Do not persist the raw webhook, environment, credentials or API headers.
    kept = {
        name: context.get(name)
        for name in (
            'repo',
            'number',
            'is_pr',
            'body',
            'comment_id',
            'html_url',
            'actor_login',
        )
    }
    kept['repo_data'] = {
        name: (context.get('repo_data') or {}).get(name)
        for name in ('full_name', 'clone_url', 'html_url')
    }
    kept['actionable'] = is_fix_request(str(kept.get('body') or ''))
    db = await pool()
    async with db.acquire() as conn:
        await ensure_schema(conn)
        await conn.execute(
            """
            INSERT INTO forgejo_webhook_inbox
                (delivery_id, event, context, api_base)
            VALUES ($1, $2, $3::jsonb, $4)
            ON CONFLICT (delivery_id) DO NOTHING
        """,
            identity,
            event,
            json.dumps(kept),
            base.rstrip('/'),
        )
        row = await conn.fetchrow(
            """
            SELECT state, result FROM forgejo_webhook_inbox
            WHERE delivery_id = $1
        """,
            identity,
        )
    return {
        'accepted': True,
        'delivery_id': identity,
        'state': row['state'],
        'result': decode(row['result']),
    }


@asynccontextmanager
async def locked_delivery(identity):
    """Hold a session lock across retries; process death releases ownership.

    A bounded dispatcher timeout limits connection occupancy. Session locks
    cannot expire underneath a live worker as time-based leases can.
    """
    db = await pool()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT api_base, context FROM forgejo_webhook_inbox WHERE delivery_id = $1
        """,
            identity,
        )
        if row is None:
            yield None
            return
        ctx = decode(row['context'])
        lock_key = (
            f'forgejo-inbox:{row["api_base"]}:{ctx["repo"]}:{ctx["number"]}'
        )
        owned = await conn.fetchval(
            'SELECT pg_try_advisory_lock(hashtextextended($1, 0))',
            lock_key,
        )
        try:
            yield conn if owned else None
        finally:
            if owned:
                await conn.execute(
                    'SELECT pg_advisory_unlock(hashtextextended($1, 0))',
                    lock_key,
                )


async def due_deliveries(limit=10):
    """Find bounded work independently of webhook retries or worker restarts."""
    db = await pool()
    async with db.acquire() as conn:
        await ensure_schema(conn)
        return await conn.fetch(
            """
            SELECT delivery_id FROM forgejo_webhook_inbox
            WHERE state != 'acknowledged' AND next_attempt_at <= now()
            ORDER BY next_attempt_at LIMIT $1
        """,
            limit,
        )
