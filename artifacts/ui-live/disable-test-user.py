"""Disable and log out only the marked test identity, preserving its evidence."""
import base64
import json
import os
import sys
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

OUT = Path(__file__).parent
OUT = Path(os.environ.get('LIVE_EVIDENCE_DIR', str(OUT)))
OUT.mkdir(parents=True, exist_ok=True)
enable_preview = '--enable-preview' in sys.argv
BASE = 'http://127.0.0.1:18080'
USER_ID = '28d1d4f6-59a1-48b4-bbaa-ce5b839d90c9'
def kube(*args):
    return json.loads(subprocess.check_output(['kubectl', *args, '-o', 'json'], text=True))
env = kube('get', 'statefulset', 'keycloak', '-n', 'keycloak')['spec']['template']['spec']['containers'][0]['env']
admin = next(item['value'] for item in env if item['name'] == 'KEYCLOAK_ADMIN')
ref = next(item['valueFrom']['secretKeyRef'] for item in env if item['name'] == 'KEYCLOAK_ADMIN_PASSWORD')
password = base64.b64decode(kube('get', 'secret', ref['name'], '-n', 'keycloak')['data'][ref['key']]).decode()
body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli', 'username': admin, 'password': password}).encode()
with urllib.request.urlopen(urllib.request.Request(BASE + '/realms/master/protocol/openid-connect/token', data=body), timeout=20) as response:
    token = json.load(response)['access_token']
evidence = {'level': 'live deployment/Argo', 'service': 'keycloak/keycloak', 'userId': USER_ID, 'operations': []}
def request(method, suffix='', data=None):
    req = urllib.request.Request(BASE + '/admin/realms/quantum-forge/users/' + USER_ID + suffix,
        method=method, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        evidence['operations'].append({'method': method, 'suffix': suffix, 'status': response.status})
        return json.loads(raw) if raw else None
user = request('GET')
if user.get('attributes', {}).get('ui_validation_run') != ['cb1e678f']:
    raise RuntimeError('Refusing cleanup of an unmarked identity')
request('PUT', data={'enabled': enable_preview})
if not enable_preview:
    request('POST', '/logout')
after = request('GET')
evidence['disabled'] = after.get('enabled') is False
subprocess.run(['vault', 'kv', 'patch', '-format=json', 'kv/codetether/playwright/ui-live-cb1e678f', '-'],
    input=json.dumps({'status': 'active_readonly_ui_preview' if enable_preview else 'disabled_after_validation', 'keycloak_user_id': USER_ID}),
    text=True, capture_output=True, check=True)
filename = 'test-user-enabled.json' if enable_preview else 'test-user-cleanup.json'
(OUT / filename).write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps(evidence, indent=2))