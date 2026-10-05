"""Enable only PR review events; leave native issue intake as its sole owner."""
import json
import subprocess

import httpx

pods=json.loads(subprocess.check_output(['kubectl','-n','a2a-system','get','pods',
    '-l','app.kubernetes.io/component=server,color=green','-o','json']))['items']
pod=next(p['metadata']['name'] for p in pods if not p['metadata'].get('deletionTimestamp')
         and any(c.get('type')=='Ready' and c.get('status')=='True' for c in p['status'].get('conditions',[])))
enabled=subprocess.check_output(['kubectl','-n','a2a-system','exec',pod,'--','python3','-c','import os; print(os.environ["FORGEJO_SINGLE_REVIEW_REPOS"])'],text=True).strip()
assert enabled=='riley/spotlessbinco'
secret=subprocess.check_output(['kubectl','-n','a2a-system','exec',pod,'--','python3','-c','import os; print(os.environ["FORGEJO_WEBHOOK_SECRET"])'],text=True).strip()
assert len(secret)>=16
record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/forgejo/spotlessbinco-agent'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
root='https://forgejo.quantum-forge.io/api/v1/repos/riley/spotlessbinco'
events=['pull_request_only','pull_request_sync','pull_request_review_request']
expected_events={'pull_request','pull_request_sync','pull_request_review_request'}
with httpx.Client(timeout=30,auth=(record['username'],record['password']),
                  headers={'User-Agent':'CodeTether-Review-Cutover/1.0'}) as client:
    r=client.get(root+'/hooks/2');r.raise_for_status();hook=r.json()
    assert hook['config']['url']=='https://api.codetether.run/v1/webhooks/forgejo'
    r=client.patch(root+'/hooks/2',json={'active':True,'events':events,
        'config':{**hook['config'],'secret':secret}})
    r.raise_for_status()
    r=client.get(root+'/hooks/2');r.raise_for_status();hook=r.json()
    print(json.dumps({'observed_hook':hook['id'],'active':hook['active'],'events':hook['events']}))
    assert hook['active'] and set(hook['events'])==expected_events
    print(json.dumps({'hook':2,'active':True,'events':hook['events']}))