"""Read callback allowlists using configured admin credentials; never print secrets."""
import base64
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

def kube(*args):
    return json.loads(subprocess.check_output(['kubectl', *args, '-o', 'json'], text=True))
env = kube('get', 'statefulset', 'keycloak', '-n', 'keycloak')['spec']['template']['spec']['containers'][0]['env']
admin = next(e['value'] for e in env if e['name'] == 'KEYCLOAK_ADMIN')
ref = next(e['valueFrom']['secretKeyRef'] for e in env if e['name'] == 'KEYCLOAK_ADMIN_PASSWORD')
password = base64.b64decode(kube('get', 'secret', ref['name'], '-n', 'keycloak')['data'][ref['key']]).decode()
base = 'http://127.0.0.1:18080'
body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli', 'username': admin, 'password': password}).encode()
with urllib.request.urlopen(urllib.request.Request(base + '/realms/master/protocol/openid-connect/token', data=body), timeout=20) as response:
    token = json.load(response)['access_token']
request = urllib.request.Request(base + '/admin/realms/quantum-forge/clients?clientId=a2a-monitor', headers={'Authorization': 'Bearer ' + token})
with urllib.request.urlopen(request, timeout=20) as response:
    clients = json.load(response)
evidence = [{'clientId': c['clientId'], 'redirectUris': c.get('redirectUris'), 'webOrigins': c.get('webOrigins')} for c in clients]
Path(__file__).with_name('keycloak-redirects.json').write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence, indent=2))