"""Provision only the marked live-validation user; never reset existing users."""
import base64
import json
from pathlib import Path
import subprocess
import secrets
import urllib.error
import urllib.parse
import urllib.request

OUT = Path(__file__).parent
BASE = 'http://127.0.0.1:18080'
CREDENTIAL_PATH = 'kv/codetether/playwright/ui-live-cb1e678f'
RUN = 'cb1e678f'

def kube(*args):
    return json.loads(subprocess.check_output(['kubectl', *args, '-o', 'json'], text=True))

environment = kube('get', 'statefulset', 'keycloak', '-n', 'keycloak')['spec']['template']['spec']['containers'][0]['env']
admin = next(item['value'] for item in environment if item['name'] == 'KEYCLOAK_ADMIN')
reference = next(item['valueFrom']['secretKeyRef'] for item in environment if item['name'] == 'KEYCLOAK_ADMIN_PASSWORD')
password = base64.b64decode(kube('get', 'secret', reference['name'], '-n', 'keycloak')['data'][reference['key']]).decode()
body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli', 'username': admin, 'password': password}).encode()
with urllib.request.urlopen(urllib.request.Request(BASE + '/realms/master/protocol/openid-connect/token', data=body), timeout=20) as response:
    token = json.load(response)['access_token']
credentials = json.loads(subprocess.check_output(['vault', 'kv', 'get', '-format=json', CREDENTIAL_PATH], text=True))['data']['data']
evidence = {'service': 'keycloak/keycloak', 'realm': 'quantum-forge', 'credentialPath': CREDENTIAL_PATH, 'operations': []}

def api(method, endpoint, data=None):
    request = urllib.request.Request(BASE + '/admin/realms/quantum-forge' + endpoint,
        data=None if data is None else json.dumps(data).encode(), method=method,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read()
        result = json.loads(raw) if raw else None
        evidence['operations'].append({'method': method, 'path': endpoint.split('?')[0], 'status': response.status})
        return result, response.headers

try:
    roles, _ = api('GET', '/roles')
    editor = next((role for role in roles if role['name'] == 'editor'), None)
    if editor is None:
        # This is the existing application policy's non-administrative editor role.
        api('POST', '/roles', {'name': 'editor', 'description': 'CodeTether editor: tasks and sessions; no platform administration'})
        editor, _ = api('GET', '/roles/editor')
    query = urllib.parse.urlencode({'username': credentials['PLAYWRIGHT_AGENT_USERNAME'], 'exact': 'true'})
    existing, _ = api('GET', '/users?' + query)
    if existing:
        user = existing[0]
        if user.get('attributes', {}).get('ui_validation_run') != [RUN]:
            raise RuntimeError('Refusing to modify an existing unmarked user')
        user_id = user['id']
    else:
        credentials['PLAYWRIGHT_AGENT_PASSWORD'] = secrets.token_urlsafe(48)
        subprocess.run(['vault', 'kv', 'patch', '-format=json', CREDENTIAL_PATH, '-'],
                       input=json.dumps({'PLAYWRIGHT_AGENT_PASSWORD': credentials['PLAYWRIGHT_AGENT_PASSWORD'], 'realm_name': 'quantum-forge'}),
                       text=True, capture_output=True, check=True)
        _, headers = api('POST', '/users', {
            'username': credentials['PLAYWRIGHT_AGENT_USERNAME'],
            'email': credentials['PLAYWRIGHT_AGENT_USERNAME'],
            'enabled': True, 'emailVerified': True, 'firstName': 'UI', 'lastName': 'Integration',
            'attributes': {'ui_validation_run': [RUN], 'purpose': ['User-requested live UI verification']},
            'credentials': [{'type': 'password', 'value': credentials['PLAYWRIGHT_AGENT_PASSWORD'], 'temporary': False}],
        })
        user_id = headers['Location'].rstrip('/').split('/')[-1]
    evidence['userId'] = user_id
    (OUT / 'test-user.json').write_text(json.dumps(evidence, indent=2) + '\n')
    api('POST', f'/users/{user_id}/role-mappings/realm', [{'id': editor['id'], 'name': editor['name']}])
    evidence['assignedRole'] = 'editor'
    evidence['adminPrivilegesGranted'] = False
except urllib.error.HTTPError as error:
    evidence['error'] = {'status': error.code, 'operation': 'Keycloak test-user provisioning'}
    raise
finally:
    (OUT / 'test-user.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence, indent=2))