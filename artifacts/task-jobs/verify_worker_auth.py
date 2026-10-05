"""Verify revocation with status codes only; never emit credential values."""
import base64
import json
import subprocess
from pathlib import Path
import httpx

def read(*args):
    return json.loads(subprocess.run(['vault','kv','get','-format=json',*args],capture_output=True,text=True,check=True).stdout)['data']
latest=read('secret/codetether/a2a-server/auth')
assert 'legacy-worker-rotating:' not in latest['data']['A2A_AUTH_TOKENS']
previous=read('-version='+str(latest['metadata']['version']-1),'secret/codetether/a2a-server/auth')
old=next(p.split(':',1)[1] for p in previous['data']['A2A_AUTH_TOKENS'].split(',') if p.startswith('legacy-worker-rotating:'))
secret=json.loads(subprocess.check_output(['kubectl','-n','a2a-system','get','secret','a2a-server-worker-token','-o','json']))
new=base64.b64decode(secret['data']['CODETETHER_TOKEN']).decode()
url='https://api.codetether.run/v1/worker/connected'
with httpx.Client(timeout=30) as client:
    denied=client.get(url,headers={'Authorization':'Bearer '+old})
    accepted=client.get(url,headers={'Authorization':'Bearer '+new})
result={'old_status':denied.status_code,'new_status':accepted.status_code,'old_credential_removed':True}
print(json.dumps(result))
Path('artifacts/task-jobs/worker-token-rotation.json').write_text(json.dumps(result,indent=2)+'\n')
assert denied.status_code in (401,403) and accepted.status_code==200