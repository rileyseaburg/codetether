"""Rerun the existing trusted review through Forgejo's authenticated UI endpoint."""
import json
import subprocess
from html.parser import HTMLParser

import httpx


class CSRF(HTMLParser):
    def __init__(self):
        super().__init__()
        self.value = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('name') == '_csrf':
            self.value = attrs.get('value') or attrs.get('content')


record = json.loads(subprocess.run(
    ['vault','kv','get','-format=json','kv/forgejo/codetether-bot'],
    capture_output=True, text=True, check=True,
).stdout)['data']['data']
base = 'https://forgejo.quantum-forge.io'
with httpx.Client(timeout=30, headers={'User-Agent':'CodeTether-CI-Recovery/1.0'}) as client:
    pr = client.get(base+'/api/v1/repos/riley/spotlessbinco/pulls/5907',
                    headers={'Authorization':'token '+record['token']})
    pr.raise_for_status()
    assert pr.json()['head']['sha']=='7ba48ee2c92ba7ce0cb313de36759ede4eb91ba0'
    page = client.get(base+'/user/login')
    page.raise_for_status()
    csrf = CSRF(); csrf.feed(page.text)
    form={'user_name':record['username'],'password':record['password']}
    if csrf.value: form['_csrf']=csrf.value
    # Forgejo 15 uses net/http CrossOriginProtection, not hidden CSRF fields.
    response = client.post(base+'/user/login',data=form,
                           headers={'Origin':base,'Referer':base+'/user/login'})
    assert response.status_code in (302,303), f'Login failed: HTTP {response.status_code}'
    run_path = '/riley/spotlessbinco/actions/runs/9264'
    page = client.get(base+run_path)
    if page.status_code in (302,303,307,308):
        location=page.headers['location']
        assert location.startswith(base+'/'), 'Unexpected cross-origin run redirect'
        page=client.get(location)
    page.raise_for_status()
    csrf = CSRF();csrf.feed(page.text)
    headers={'Origin':base,'Referer':base+run_path}
    if csrf.value:headers['X-Csrf-Token']=csrf.value
    response = client.post(base+run_path+'/jobs/0/rerun',
                           data={'_csrf':csrf.value} if csrf.value else {},headers=headers)
    response.raise_for_status()
    print(json.dumps({'review_run':9264,'rerun_http':response.status_code,
                      'url':base+run_path,'body':response.json()}))