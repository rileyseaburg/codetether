"""Exercise the targeted safe-only worker without starting a PR review."""
import asyncio
import json
import logging
import os

logging.disable(logging.CRITICAL)
from a2a_server import database as db
from a2a_server.persistent_worker_pool import create_and_dispatch_task


async def main():
    task_id=await create_and_dispatch_task(
        workspace_id='global',title='Single-review safe worker readiness',
        prompt='Do not use tools. Reply exactly: SINGLE_REVIEW_WORKER_READY',
        agent_type='plan',model_ref=os.environ['GITHUB_APP_MODEL_REF'],
        task_timeout_seconds=120,metadata={
            'source':'single-review-readiness','target_agent_name':'harvester-pr-review',
            'required_capabilities':['review-readonly'],'max_steps':2,
        })
    print('CANARY_TASK',task_id,flush=True)
    for _ in range(40):
        task=await db.db_get_task(task_id)
        if task['status'] in ('completed','failed','cancelled'):
            print(json.dumps({'task':task_id,'status':task['status'],
                              'worker':task.get('worker_id'),'result':task.get('result'),
                              'error':task.get('error')}),flush=True)
            assert task['status']=='completed'
            assert 'SINGLE_REVIEW_WORKER_READY' in str(task.get('result'))
            return
        await asyncio.sleep(5)
    raise RuntimeError('safe reviewer canary did not finish')


asyncio.run(main())