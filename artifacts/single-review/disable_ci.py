"""Retire the duplicate AI workflow through Forgejo's own configuration route."""
import json
import subprocess

import httpx

record=json.loads(subprocess.run(['vault','kv','get','-format=json','kv/forgejo/spotlessbinco-agent'],
    capture_output=True,text=True,check=True).stdout)['data']['data']
base='https://forgejo.quantum-forge.io'
with httpx.Client(timeout=30,headers={'User-Agent':'CodeTether-Review-Cutover/1.0'}) as client:
    page=client.get(base+'/user/login');page.raise_for_status()
    response=client.post(base+'/user/login',data={'user_name':record['username'],'password':record['password']},
                         headers={'Origin':base,'Referer':base+'/user/login'})
    assert response.status_code in (302,303),'Operator login failed'
    path='/riley/spotlessbinco/actions'
    response=client.post(base+path+'/disable',data={'workflow':'codetether-pr-review.yml'},
                         headers={'Origin':base,'Referer':base+path})
    response.raise_for_status()
    page=client.get(base+path,params={'workflow':'codetether-pr-review.yml'})
    page.raise_for_status()
    assert '/actions/enable' in page.text,'Disabled-workflow confirmation missing'
    print(json.dumps({'repository':'riley/spotlessbinco','workflow':'codetether-pr-review.yml',
                      'disabled':True,'status':response.status_code}))