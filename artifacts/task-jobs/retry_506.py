"""Retry only the failed native request, through Forgejo's canonical control API."""
import asyncio
import json
import logging
import os

logging.disable(logging.CRITICAL)
from a2a_server.forgejo_webhooks import forgejo_json

async def main():
    base=os.environ['FORGEJO_API_URL'];root='/repos/riley/spotlessbinco'
    task=await forgejo_json('GET',base,root+'/agent/tasks/506')
    assert task['status']=='failed' and task['issue_index']==5960 and task['operation']=='fix'
    issue=await forgejo_json('GET',base,root+'/issues/5960')
    assert issue['state']=='open'
    result=await forgejo_json('POST',base,root+'/agent/tasks/506/retry',{})
    print(json.dumps({'native_task':506,'issue':5960,'result_fields':list(result) if isinstance(result,dict) else [],'retry_requested':True}))

asyncio.run(main())