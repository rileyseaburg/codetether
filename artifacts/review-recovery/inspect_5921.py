"""Measure the real current-head diff without exposing credentials or contents."""
import json
import subprocess
from pathlib import Path

import httpx

record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/codetether/harvester/forgejo-review'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
root=record['api_base']+'/repos/'+record['repo']
with httpx.Client(timeout=90,headers={'Authorization':'token '+record['token'],
                                      'User-Agent':'CodeTether-Review-Diagnostics/1.0'}) as client:
    r=client.get(root+'/pulls/5921');r.raise_for_status();pr=r.json()
    size=0;complete=True
    with client.stream('GET',root+'/pulls/5921.diff') as response:
        response.raise_for_status()
        for part in response.iter_bytes():
            size+=len(part)
            if size>30_000_000:complete=False;break
    r=client.get(root+'/pulls/5921');r.raise_for_status()
    assert r.json()['head']['sha']==pr['head']['sha'],'Head changed during measurement'
    result={'pr':5921,'state':pr['state'],'head':pr['head']['sha'],
            'base':pr['base']['sha'],'changed_files':pr.get('changed_files'),
            'additions':pr.get('additions'),'deletions':pr.get('deletions'),
            'diff_bytes':size,'measurement_complete':complete,
            'configured_limit':20_000_000,'empty':size==0}
    Path('artifacts/review-recovery/pr-5921-diff.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))