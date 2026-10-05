"""Read-only: did completed coding Jobs produce pushed branches and PRs?"""

import asyncio
import json
import logging
import os

from a2a_server import database as db
from a2a_server.forgejo_webhooks import forgejo_json


logging.disable(logging.CRITICAL)


async def main():
    """Read branch and PR metadata for recent coding tasks."""
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    p = await db.get_pool()
    async with p.acquire() as c:
        rows = await c.fetch(
            "SELECT id,status,title,completed_at,metadata->>'job_name' job,"
            "metadata->>'workflow_stage' stage,metadata->>'branch_name' branch,"
            "metadata->>'pr_number' pr,metadata->>'issue_number' issue,"
            "metadata->>'forgejo_agent_task_id' native,metadata->>'repo' repo,"
            "metadata->>'job_cleanup_scheduled' cleanup,"
            'left(result::text,300) result '
            "FROM tasks WHERE metadata->>'job_execution'='true' "
            "AND metadata->>'workflow_stage' IN ('code','review_recovery') "
            "AND created_at > NOW()-interval '30 hours' ORDER BY created_at"
        )
    for r in rows:
        d = dict(r)
        owner, name = d['repo'].split('/', 1)
        d['remote_branch'] = None
        d['open_pr'] = None
        if d['branch']:
            b = await forgejo_json(
                'GET',
                base,
                f'/repos/{owner}/{name}/branches/{d["branch"]}',
                allow_not_found=True,
            )
            d['remote_branch'] = (b or {}).get('commit', {}).get('id')
            prs = await forgejo_json(
                'GET',
                base,
                f'/repos/{owner}/{name}/pulls?state=all&limit=5&head={owner}:{d["branch"]}',
                allow_not_found=True,
            )
            d['open_pr'] = [
                {'n': x['number'], 'state': x['state']} for x in (prs or [])
            ]
        print(json.dumps(d, default=str))
    await p.close()


asyncio.run(main())
