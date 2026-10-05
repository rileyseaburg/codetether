"""Inspect only non-secret token restrictions before same-scope rotation."""
import json
import subprocess
import httpx

def secret(path):
    return json.loads(subprocess.run(['vault','kv','get','-format=json',path],
        capture_output=True,text=True,check=True).stdout)['data']['data']

record=secret('kv/codetether/harvester/forgejo-review')
operator=secret('kv/forgejo/spotlessbinco-agent')
with httpx.Client(timeout=30,auth=(operator['username'],operator['password']),
                  headers={'User-Agent':'CodeTether-Credential-Rotation/1.0'}) as client:
    r=client.get(record['api_base']+'/users/'+record['username']+'/tokens');r.raise_for_status()
    matches=[t for t in r.json() if t['name']==record['token_name']]
    assert len(matches)==1
    token=matches[0]
    print('TOKEN_FIELDS',sorted(token))
    print('TOKEN_METADATA',{k:token.get(k) for k in ('id','name','scopes','scoped_repositories')})
    r=client.get('https://forgejo.quantum-forge.io/swagger.v1.json');r.raise_for_status()
    print('CREATE_SCHEMA',json.dumps(r.json()['definitions']['CreateAccessTokenOption']))