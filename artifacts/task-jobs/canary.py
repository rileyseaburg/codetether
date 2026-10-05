"""Create a finite read-only worker readiness task; no PR or customer data writes."""
import asyncio
import json
import logging
import os

logging.disable(logging.CRITICAL)
from a2a_server.persistent_worker_pool import create_and_dispatch_task
from a2a_server import database as db

async def main():
    task=await create_and_dispatch_task(workspace_id='global',title='Finite Job readiness',
        prompt='Do not use tools. Reply exactly FINITE_JOB_READY.',agent_type='plan',
        model_ref=os.environ['GITHUB_APP_MODEL_REF'],task_timeout_seconds=600,
        metadata={'source':'forgejo-webhook','repo':'riley/spotlessbinco',
                  'workflow_stage':'review_chunk','forgejo_work_key':'finite-job-ready-ee7973a0',
                  'required_capabilities':['review-readonly'],'max_steps':2})
    row=await db.db_get_task(task)
    print(json.dumps({'task':task,'job':row['metadata'].get('job_name'),'status':row['status']}),flush=True)

asyncio.run(main())