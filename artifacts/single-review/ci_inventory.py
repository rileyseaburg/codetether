"""Inventory active legacy reviewer runs; do not touch build/test/scan runs."""
import json
import subprocess

import httpx

record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/forgejo/spotlessbinco-agent'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
url='https://forgejo.quantum-forge.io/api/v1/repos/riley/spotlessbinco/actions/runs'
params=[('workflow_id','codetether-pr-review.yml'),('limit',50),('page',1),
        ('status','waiting'),('status','running'),('status','blocked'),('status','unknown')]
with httpx.Client(timeout=30,auth=(record['username'],record['password']),
                  headers={'User-Agent':'CodeTether-Review-Cutover/1.0'}) as client:
    response=client.get(url,params=params);response.raise_for_status()
    body=response.json();runs=body.get('workflow_runs') or []
    assert all(r['workflow_id']=='codetether-pr-review.yml' for r in runs)
    print(json.dumps({'total':body.get('total_count'),'runs':[
        {k:r.get(k) for k in ('id','index_in_repo','status','commit_sha','html_url')}
        for r in runs]},indent=2))