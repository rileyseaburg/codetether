"""Close only the superseded capacity workaround, preserving branch and evidence."""
import json
import subprocess

import httpx

record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/forgejo/codetether-bot'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
root='https://forgejo.quantum-forge.io/api/v1/repos/riley/spotlessbinco'
with httpx.Client(timeout=30,headers={'Authorization':'token '+record['token'],
                                       'User-Agent':'CodeTether-Review-Cutover/1.0'}) as client:
    r=client.get(root+'/pulls/5912');r.raise_for_status();pr=r.json()
    assert pr['head']['ref']=='fix/codetether-review-capacity-5907'
    r=client.get(root+'/pulls/5912/files',params={'limit':50});r.raise_for_status()
    paths={row['filename'] for row in r.json()}
    expected={'.forgejo/workflows/codetether-pr-review.yml',
              'scripts/codetether-review/chunk_pipeline.sh','scripts/codetether-review/chunk_worker.sh'}
    assert paths==expected,'Workaround contains other changes; preserve it for its author'
    if pr['state']=='open':
        r=client.patch(root+'/pulls/5912',json={'state':'closed'});r.raise_for_status()
        print(json.dumps({'pr':5912,'state':r.json()['state'],'branch_preserved':True}))
        r=client.post(root+'/issues/5912/comments',json={'body':
            'Superseded by the single-owner webhook/Temporal harvester review implementation in riley/codetether#47. The duplicate CI AI reviewer has been disabled; builds and scans remain. This capacity-only workaround is not being merged. Its branch and evidence are preserved.'})
        r.raise_for_status()
    else:print(json.dumps({'pr':5912,'state':pr['state'],'branch_preserved':True}))