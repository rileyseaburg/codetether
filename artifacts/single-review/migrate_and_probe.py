"""Apply only the review snapshot migration through the canonical migration runner."""
import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

logging.disable(logging.CRITICAL)
from a2a_server import database as db


async def main():
    source=Path('/app/a2a_server/migrations/037_forgejo_review_snapshots.sql')
    target=Path(tempfile.mkdtemp(prefix='review-migration-'))
    shutil.copyfile(source,target/source.name)
    result=await db.db_run_migrations(str(target))
    assert not result['failed'], 'Review migration failed'
    pool=await db.get_pool()
    async with pool.acquire() as connection:
        table=await connection.fetchval("SELECT to_regclass('public.forgejo_review_snapshots')::text")
        columns=await connection.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='tasks' AND column_name IN ('workspace_id','metadata')")
    assert table=='forgejo_review_snapshots'
    assert {r['column_name'] for r in columns}=={'workspace_id','metadata'}
    print(json.dumps({'migration':result,'table':table,'task_columns':'compatible'}))
    await pool.close()


asyncio.run(main())