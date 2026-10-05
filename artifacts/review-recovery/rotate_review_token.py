"""Revoke the reported scoped credential and replace it with identical access."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

def read(path):
    return json.loads(subprocess.run(['vault','kv','get','-format=json',path],
        capture_output=True,text=True,check=True).stdout)['data']

stored=read('kv/codetether/harvester/forgejo-review')
record=stored['data'];operator=read('kv/forgejo/spotlessbinco-agent')['data']
assert record['token_name']=='codetether-harvester-review-read-20260908'
base=record['api_base'];user=record['username']
with httpx.Client(timeout=30,auth=(operator['username'],operator['password']),
                  headers={'User-Agent':'CodeTether-Credential-Rotation/1.0'}) as admin:
    response=admin.get(base+'/users/'+user+'/tokens');response.raise_for_status()
    old=next(t for t in response.json() if t['name']==record['token_name'])
    assert old['id']==35 and set(old['scopes'])=={'read:issue','read:repository'}
    repositories=[{'owner':r['owner'],'name':r['name']} for r in old['repositories']]
    assert repositories==[{'owner':'riley','name':'spotlessbinco'}]
    response=admin.delete(base+'/users/'+user+'/tokens/35');response.raise_for_status()
    print('REVOKED_TOKEN_ID 35',flush=True)
    name='codetether-harvester-review-read-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    response=admin.post(base+'/users/'+user+'/tokens',json={
        'name':name,'scopes':old['scopes'],'repositories':repositories})
    response.raise_for_status();new=response.json()
    replacement={**record,'token':new['sha1'],'token_name':name}
    result=subprocess.run(['vault','kv','put','-cas='+str(stored['metadata']['version']),
        'kv/codetether/harvester/forgejo-review','-'],input=json.dumps(replacement),
        capture_output=True,text=True)
    if result.returncode:
        admin.delete(base+'/users/'+user+'/tokens/'+str(new['id']))
        raise RuntimeError('Vault update rejected; replacement revoked, operator recovery required')
    with httpx.Client(timeout=30) as probe:
        revoked=probe.get(base+'/repos/riley/spotlessbinco',headers={'Authorization':'token '+record['token']})
        working=probe.get(base+'/repos/riley/spotlessbinco',headers={'Authorization':'token '+new['sha1']})
        outside=probe.get(base+'/repos/riley/codetether',headers={'Authorization':'token '+new['sha1']})
    assert revoked.status_code in (401,403)
    assert working.status_code==200 and outside.status_code in (403,404)
    evidence={'old_token_id':35,'old_http':revoked.status_code,'new_token_id':new['id'],
              'new_http':working.status_code,'outside_repo_http':outside.status_code,
              'scopes':old['scopes'],'repositories':repositories,'vault_cas_updated':True}
    Path('artifacts/review-recovery/token-rotation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))