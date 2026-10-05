"""Watch the exact recovery run, emitting only non-sensitive lifecycle evidence."""
import asyncio
import json
import logging
import os

import httpx

logging.disable(logging.CRITICAL)


async def main():
    base = os.environ['FORGEJO_API_URL']
    path = '/repos/riley/spotlessbinco/actions/runs/10179/jobs'
    previous = None
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(50):
            response = await client.get(base+path, headers={
                'Authorization':'token '+os.environ['FORGEJO_TOKEN'],
            })
            response.raise_for_status()
            rows = response.json()['jobs']
            state = [{'job':r['id'],'runner':r.get('runner_id'),
                      'runner_name':r.get('runner_name'),'status':r.get('status'),
                      'conclusion':r.get('conclusion'),
                      'steps':[{k:s.get(k) for k in ('name','status','conclusion')}
                               for s in r.get('steps',[])]} for r in rows]
            encoded = json.dumps(state)
            if encoded != previous:
                print(encoded,flush=True)
                previous = encoded
            if rows and all(r.get('status')=='completed' for r in rows):
                return
            await asyncio.sleep(30)
        raise RuntimeError('Review still running after observation window')


asyncio.run(main())