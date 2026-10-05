"""Observe CI for the exact capacity-change commit; never merge or alter statuses."""
import json
import subprocess
import time
from pathlib import Path

import httpx

publication=json.loads((Path(__file__).parent/'publication.json').read_text())
credential=json.loads(subprocess.run([
    'vault','kv','get','-format=json','kv/codetether/harvester/forgejo-review',
],capture_output=True,text=True,check=True).stdout)['data']['data']
root=credential['api_base']+'/repos/'+credential['repo']
with httpx.Client(timeout=40,headers={
    'Authorization':'token '+credential['token'],'User-Agent':'CodeTether-Review-Capacity/1.0',
}) as client:
    previous=None
    for _ in range(35):
        r=client.get(root+'/pulls/'+str(publication['number']));r.raise_for_status()
        assert r.json()['head']['sha']==publication['head'], 'Capacity PR head advanced'
        r=client.get(root+'/actions/runs',params={'head_sha':publication['head'],'limit':10,'page':1})
        r.raise_for_status();runs=r.json().get('workflow_runs') or []
        state=[{k:x.get(k) for k in ('id','index_in_repo','workflow_id','status','html_url')}
               for x in runs]
        encoded=json.dumps(state)
        if encoded!=previous:
            print(encoded,flush=True);previous=encoded
            (Path(__file__).parent/'capacity-ci.json').write_text(json.dumps(state,indent=2)+'\n')
        if runs and all(x.get('status') in ('success','failure','cancelled','skipped') for x in runs):
            break
        time.sleep(30)