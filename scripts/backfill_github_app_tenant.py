#!/usr/bin/env python3
"""Backfill tenant_id for legacy GitHub App tasks that were created unscoped."""

from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg

GITHUB_TASK_PREDICATE = """
(metadata->>'source' = 'github-app'
 OR metadata ? 'github_installation_id'
 OR metadata ? 'github_issue_url')
"""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    database_url = os.environ.get('DATABASE_URL') or os.environ.get('A2A_DATABASE_URL')
    if not database_url:
        raise SystemExit('DATABASE_URL or A2A_DATABASE_URL is required')

    conn = await asyncpg.connect(database_url)
    try:
        tenant_exists = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM tenants WHERE id = $1)', args.tenant_id)
        if not tenant_exists:
            raise SystemExit(f'tenant_id not found: {args.tenant_id}')

        task_count = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks WHERE tenant_id IS NULL AND {GITHUB_TASK_PREDICATE}"
        )
        workspace_count = await conn.fetchval(
            f"""
            SELECT COUNT(DISTINCT workspace_id)
            FROM tasks
            WHERE tenant_id IS NULL AND workspace_id IS NOT NULL AND {GITHUB_TASK_PREDICATE}
            """
        )
        run_count = await conn.fetchval(
            f"""
            SELECT COUNT(*)
            FROM task_runs tr
            WHERE tr.tenant_id IS NULL
              AND EXISTS (SELECT 1 FROM tasks t WHERE t.id = tr.task_id AND {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')})
            """
        )
        counts = {'tasks': task_count, 'workspaces': workspace_count, 'runs': run_count}
        print(counts)
        if args.dry_run:
            return

        async with conn.transaction():
            await conn.execute(
                f"""
                UPDATE tasks
                SET tenant_id = $1::uuid,
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || jsonb_build_object('tenant_id', $1::text),
                    updated_at = NOW()
                WHERE tenant_id IS NULL AND {GITHUB_TASK_PREDICATE}
                """,
                args.tenant_id,
            )
            await conn.execute(
                f"""
                UPDATE workspaces w
                SET tenant_id = $1::uuid, updated_at = NOW()
                WHERE tenant_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.workspace_id = w.id AND {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')}
                  )
                """,
                args.tenant_id,
            )
            await conn.execute(
                f"""
                UPDATE task_runs tr
                SET tenant_id = $1::uuid, updated_at = NOW()
                WHERE tenant_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.id = tr.task_id AND {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')}
                  )
                """,
                args.tenant_id,
            )

        remaining_tasks = await conn.fetchval(
            f"SELECT COUNT(*) FROM tasks WHERE tenant_id IS NULL AND {GITHUB_TASK_PREDICATE}"
        )
        remaining_runs = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM task_runs tr
            WHERE tr.tenant_id IS NULL
              AND EXISTS (SELECT 1 FROM tasks t WHERE t.id = tr.task_id AND {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')})
            """
        )
        print('remaining', {'tasks': remaining_tasks, 'runs': remaining_runs})
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
