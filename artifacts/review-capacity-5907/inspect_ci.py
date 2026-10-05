"""Inspect current-head review lifecycle and size diagnostics without changing it."""
import json
import subprocess

import httpx

record=json.loads(subprocess.run([
    'vault','kv','get','-format=json','kv/codetether/harvester/forgejo-review',
],capture_output=True,text=True,check=True).stdout)['data']['data']
root=record['api_base']+'/repos/'+record['repo']
with httpx.Client(timeout=40,headers={
    'Authorization':'token '+record['token'],
    'User-Agent':'CodeTether-Review-Capacity/1.0',
}) as client:
    r=client.get(root+'/pulls/5907');r.raise_for_status();pr=r.json()
    print('HEAD',pr['head']['sha'])
    r=client.get(root+'/actions/runs',params={'head_sha':pr['head']['sha'],'page':1,'limit':10})
    r.raise_for_status()
    for run in r.json().get('workflow_runs',[]):
        if run.get('workflow_id')!='codetether-pr-review.yml':continue
        print('RUN',json.dumps({k:run.get(k) for k in ('id','index_in_repo','status','html_url')}))
        path=root+'/actions/runs/'+str(run['id'])
        r=client.get(path+'/jobs');r.raise_for_status()
        print('JOBS',json.dumps([{'id':j['id'],'status':j.get('status'),
                                'runner':j.get('runner_name'),
                                'conclusion':j.get('conclusion'),
                                'steps':[{k:s.get(k) for k in ('name','status','conclusion')}
                                         for s in j.get('steps',[])]} for j in r.json()['jobs']]))
        r=client.get(path+'/jobs/1/logs')
        if r.status_code==200:
            for line in r.text.splitlines():
                if any(key in line for key in ('Review commit range:', 'Complete PR diff',
                    'Complete diff payload bytes:', 'Reviewing exact diff chunk',
                    'exceeding safe review limit', 'refusing partial review')):
                    print(line[:1000])