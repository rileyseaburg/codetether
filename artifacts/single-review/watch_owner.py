"""Observe the current single-owner review and its exact chunk execution."""
import asyncio
import json
import logging

logging.disable(logging.CRITICAL)
from a2a_server import database as db


async def main():
    owner_id='ce621100-7d32-5bd8-9739-8047e802f049'
    previous=None
    for _ in range(90):
        task=await db.db_get_task(owner_id);meta=task['metadata']
        pool=await db.get_pool()
        async with pool.acquire() as conn:
            chunks=await conn.fetch("SELECT id,status,worker_id,error FROM tasks WHERE metadata->>'review_owner_id'=$1 ORDER BY created_at",owner_id)
        value={'owner':owner_id,'status':task['status'],'head':meta['pr_head_sha'],
               'verdict':meta.get('review_verdict'),'manifest_chunks':len(meta.get('review_manifest') or []),
               'chunks':[dict(r) for r in chunks]}
        encoded=json.dumps(value)
        if encoded!=previous:print(encoded,flush=True);previous=encoded
        if task['status'] in ('completed','failed','cancelled'):
            print('OWNER_RESULT',task.get('result'),flush=True)
            return
        await asyncio.sleep(10)
    raise RuntimeError('review still running after observation window')


asyncio.run(main())