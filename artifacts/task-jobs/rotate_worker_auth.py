"""Stage a replacement worker credential, then revoke legacy access after drain."""
import base64
import json
import secrets
import subprocess
import sys
import time

def kubectl(*args):return subprocess.check_output(['kubectl',*args])
stored=json.loads(subprocess.run(['vault','kv','get','-format=json','secret/codetether/a2a-server/auth'],capture_output=True,text=True,check=True).stdout)['data']
data=stored['data'];raw=data['A2A_AUTH_TOKENS'];parts=raw.split(',')
if sys.argv[1]=='stage':
    worker=json.loads(kubectl('-n','a2a-system','get','secret','a2a-server-worker-token','-o','json'))
    old=base64.b64decode(worker['data']['CODETETHER_TOKEN']).decode()
    assert any(p.split(':',1)[-1].strip()==old for p in parts)
    assert not any(p.startswith('legacy-worker-rotating:') for p in parts)
    new=secrets.token_hex(32)
    parts=['legacy-worker-rotating:'+old if p.split(':',1)[-1].strip()==old else p for p in parts]
    parts.append('worker-jobs:'+new)
else:
    assert sys.argv[1]=='revoke'
    assert any(p.startswith('legacy-worker-rotating:') for p in parts)
    parts=[p for p in parts if not p.startswith('legacy-worker-rotating:')]
replacement={**data,'A2A_AUTH_TOKENS':','.join(parts)}
result=subprocess.run(['vault','kv','put','-cas='+str(stored['metadata']['version']),'secret/codetether/a2a-server/auth','-'],input=json.dumps(replacement),capture_output=True,text=True)
assert result.returncode==0,'Auth credential CAS failed'
if sys.argv[1]=='stage':
    patch={'data':{'CODETETHER_TOKEN':base64.b64encode(new.encode()).decode()}}
    # Feed the patch on stdin rather than placing credential data in process argv.
    subprocess.run(['kubectl','-n','a2a-system','patch','secret','a2a-server-worker-token','--type=merge','--patch-file=/dev/stdin'],input=json.dumps(patch),text=True,capture_output=True,check=True)
subprocess.run(['kubectl','-n','a2a-system','annotate','externalsecret','a2a-server-auth-tokens','force-sync='+str(int(time.time())),'--overwrite'],capture_output=True,check=True)
for _ in range(30):
    current=json.loads(kubectl('-n','a2a-system','get','secret','a2a-server-auth-tokens','-o','json'))
    if base64.b64decode(current['data']['A2A_AUTH_TOKENS']).decode()==replacement['A2A_AUTH_TOKENS']:break
    time.sleep(2)
else:raise RuntimeError('Auth projection refresh not observed')
print(json.dumps({'phase':sys.argv[1],'vault_updated':True,'kubernetes_auth_projected':True,'credentials_printed':False}))