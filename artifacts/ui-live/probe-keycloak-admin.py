"""Check the configured Keycloak bootstrap credential without exposing it."""
import base64
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

OUT = Path(__file__).parent
def kubectl(*args):
    return json.loads(subprocess.check_output(['kubectl', *args, '-o', 'json'], text=True))

deployment = kubectl('get', 'statefulset', 'keycloak', '-n', 'keycloak')
environment = deployment['spec']['template']['spec']['containers'][0]['env']
username = next(item['value'] for item in environment if item['name'] == 'KEYCLOAK_ADMIN')
reference = next(item['valueFrom']['secretKeyRef'] for item in environment if item['name'] == 'KEYCLOAK_ADMIN_PASSWORD')
secret = kubectl('get', 'secret', reference['name'], '-n', 'keycloak')['data']
password = base64.b64decode(secret[reference['key']]).decode()
body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli', 'username': username, 'password': password}).encode()
request = urllib.request.Request('http://127.0.0.1:18080/realms/master/protocol/openid-connect/token', data=body)
evidence = {'service': 'keycloak/keycloak', 'transport': 'authenticated Kubernetes port-forward'}
try:
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
        evidence['status'] = response.status
        evidence['authenticated'] = bool(result.get('access_token'))
    # Read only the designated existing test account's metadata.
    test = json.loads(subprocess.check_output(['vault', 'kv', 'get', '-format=json', 'kv/codetether/playwright/agent-keycloak-auth'], text=True))['data']['data']
    query = urllib.parse.urlencode({'username': test['PLAYWRIGHT_AGENT_USERNAME'], 'exact': 'true'})
    request = urllib.request.Request('http://127.0.0.1:18080/admin/realms/quantum-forge/users?' + query,
                                    headers={'Authorization': 'Bearer ' + result['access_token']})
    with urllib.request.urlopen(request, timeout=20) as response:
        users = json.load(response)
    evidence['testUsers'] = [{key: user.get(key) for key in ['id', 'enabled', 'requiredActions']} for user in users]
except urllib.error.HTTPError as error:
    evidence['status'] = error.code
    try:
        data = json.loads(error.read())
        evidence['error'] = {key: data.get(key) for key in ['error', 'error_description']}
    except ValueError:
        evidence['error'] = 'Non-JSON authentication error'
(OUT / 'keycloak-admin-probe.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps(evidence, indent=2))
