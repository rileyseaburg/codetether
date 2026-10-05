"""Read-only cutover inventory; no credentials or hook secrets are printed."""
import json
import subprocess

import httpx

record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/forgejo/spotlessbinco-agent'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
root='https://forgejo.quantum-forge.io/api/v1/repos/riley/spotlessbinco'
with httpx.Client(timeout=30,auth=(record['username'],record['password']),
                  headers={'User-Agent':'CodeTether-Review-Cutover/1.0'}) as client:
    response=client.get(root+'/hooks');response.raise_for_status()
    print(json.dumps([{'id':h['id'],'active':h['active'],'events':h['events'],
                       'url':h.get('config',{}).get('url')} for h in response.json()]))
    response=client.get(root+'/pulls/5912');response.raise_for_status()
    print('CAPACITY_PR',json.dumps({k:response.json().get(k) for k in ('state','merged','html_url')}))