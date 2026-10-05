"""Correlate retained Kubernetes Jobs with their task rows (read-only)."""

import asyncio
import json
import logging
import os

from a2a_server import database as db


logging.disable(logging.CRITICAL)
jobs = dict(
    x.split(':')
    for x in os.environ.get('JOBS', globals().get('JOBS_INLINE', '')).split()
)


async def main():
    """Read retained Job identities and their task states."""
    p = await db.get_pool()
    async with p.acquire() as c:
        rows = await c.fetch(
            "SELECT id,status,title,completed_at,metadata->>'job_name' job,"
            "metadata->>'workflow_stage' stage,metadata->>'job_readonly' ro,"
            "metadata->>'job_cleanup_scheduled' cl,"
            "metadata->>'job_terminal_observed' obs "
            "FROM tasks WHERE metadata->>'job_name' = ANY($1::text[])",
            list(jobs),
        )
        for r in rows:
            d = dict(r)
            d['k8s'] = jobs[d['job']]
            print(json.dumps(d, default=str))
    await p.close()


asyncio.run(main())
