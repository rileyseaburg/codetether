"""Read-only watch of Job-backed tasks for the current incident."""

import asyncio
import json
import logging

from a2a_server import database as db


logging.disable(logging.CRITICAL)


async def main():
    """Print the requested issues' and active Jobs' operational status."""
    p = await db.get_pool()
    async with p.acquire() as c:
        rows = await c.fetch(
            "SELECT metadata->>'issue_number' issue,status,error,"
            "metadata->>'workflow_stage' s,metadata->>'job_name' j,"
            "metadata->>'job_wait_reason' w,"
            "metadata->>'job_cleanup_scheduled' cl,"
            "metadata->>'pr_number' pr,updated_at "
            "FROM tasks WHERE metadata->>'job_execution'='true' "
            "AND created_at > NOW()-interval '3 hours' "
            "AND (status IN ('running','in_progress','working') "
            "     OR metadata->>'issue_number' IN ('5853','5966','5967')) "
            'ORDER BY created_at'
        )
        for r in rows:
            print(json.dumps(dict(r), default=str))
        counts = await c.fetch(
            'SELECT status,count(*) FROM tasks '
            "WHERE metadata->>'job_execution'='true' "
            "AND created_at > NOW()-interval '3 hours' GROUP BY 1"
        )
        print('COUNTS', [tuple(r) for r in counts])
    await p.close()


asyncio.run(main())
