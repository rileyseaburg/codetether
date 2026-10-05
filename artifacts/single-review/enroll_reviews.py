"""Enroll the user's current PRs and verify repeated enrollment attaches."""
import asyncio
import json
import logging

logging.disable(logging.CRITICAL)
from a2a_server import database as db
from a2a_server.forgejo_review_owner import ensure_review


async def main():
    for number in (5918,5907,5909):
        try:
            task_id=await ensure_review('riley/spotlessbinco',number)
        except RuntimeError as error:
            if str(error)!='review_pr_closed':raise
            print(json.dumps({'pr':number,'status':'already_closed'}),flush=True)
            continue
        repeated=await ensure_review('riley/spotlessbinco',number)
        assert repeated==task_id
        task=await db.db_get_task(task_id);meta=task['metadata']
        print(json.dumps({'pr':number,'owner_task':task_id,
                          'workflow':meta['review_workflow_id'],
                          'head':meta['pr_head_sha'],'status':task['status'],
                          'duplicate_delivery_attached':True}),flush=True)


asyncio.run(main())