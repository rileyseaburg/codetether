"""Observe recovery admission and reclassify the measured empty PR via its owner."""
import asyncio
import json
import logging

logging.disable(logging.CRITICAL)
from a2a_server import database as db
from a2a_server.forgejo_review_owner import ensure_review
from a2a_server.forgejo_review_owner.recovery import ensure_recovery
from a2a_server.temporal.config import get_temporal_client


async def main():
    for number in (5909,5921):
        try:owner_id=await ensure_review('riley/spotlessbinco',number)
        except RuntimeError as error:
            if str(error)=='review_pr_closed':
                print(json.dumps({'pr':number,'state':'closed'}),flush=True);continue
            raise
        owner=await db.db_get_task(owner_id)
        if number==5921:
            meta=owner['metadata']
            if meta.get('review_error_reason')=='review_diff_size_out_of_bounds':
                client=await get_temporal_client()
                await client.get_workflow_handle(meta['review_workflow_id']).signal('retry',int(meta.get('review_attempt',1))+1)
                print(json.dumps({'pr':number,'owner':owner_id,'empty_diff_reclassification_requested':True}),flush=True)
        else:
            recovery=await ensure_recovery(owner_id)
            fresh=await db.db_get_task(owner_id)
            print(json.dumps({'pr':number,'owner':owner_id,'recovery_task':recovery,
                              'blocker':fresh['metadata'].get('recovery_blocker')}),flush=True)


asyncio.run(main())