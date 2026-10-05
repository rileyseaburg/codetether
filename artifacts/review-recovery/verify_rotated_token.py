"""Verify the current Vault projection without printing authentication values."""
import json
import subprocess
from pathlib import Path
import httpx

def read(path):
    return json.loads(subprocess.run(['vault','kv','get','-format=json',path],capture_output=True,text=True,check=True).stdout)['data']['data']

r=read('kv/codetether/harvester/forgejo-review');o=read('kv/forgejo/spotlessbinco-agent')
with httpx.Client(timeout=30,auth=(o['username'],o['password'])) as c:
    response=c.get(r['api_base']+'/users/'+r['username']+'/tokens');response.raise_for_status()
    tokens=response.json();new=next(t for t in tokens if t['name']==r['token_name'])
with httpx.Client(timeout=30,headers={'Authorization':'token '+r['token'],'User-Agent':'CodeTether-Review-Diagnostics/1.0'}) as c:
    good=c.get(r['api_base']+'/repos/riley/spotlessbinco')
    outside=c.get(r['api_base']+'/repos/riley/codetether')
public=httpx.get(r['api_base']+'/repos/riley/codetether',timeout=30)
result={'old_token_id':35,'old_token_absent':not any(t['id']==35 for t in tokens),
        'outside_repo_public':public.status_code==200,
        'new_token_id':new['id'],'new_http':good.status_code,'outside_repo_http':outside.status_code,
        'scopes':new['scopes'],'repositories':new['repositories']}
print(json.dumps(result))
Path('artifacts/review-recovery/token-rotation.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['old_token_absent'] and good.status_code==200
assert set(new['scopes'])=={'read:issue','read:repository'}
assert [x['full_name'] for x in new['repositories']]==['riley/spotlessbinco']