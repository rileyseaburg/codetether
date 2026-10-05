"""Read-only trusted runner credential probe. Never print authentication values."""
import json
import subprocess
import sys

POD = sys.argv[1] if len(sys.argv) > 1 else 'forgejo-act-runner-dind-59d7674f4c-fcd8d'


def query(command):
    shell = ('export VAULT_ADDR=http://vault.vault.svc.cluster.local:8200; '
             'export VAULT_TOKEN="$(cat /vault/runtime/token)"; ' + command)
    result = subprocess.run([
        'kubectl', '-n', 'forgejo-actions', 'exec', POD, '-c', 'vault-agent',
        '--', 'sh', '-c', shell,
    ], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)['data']


metadata = query('vault token lookup -format=json')
print(json.dumps({'pod': POD, 'ttl': metadata.get('ttl'),
                  'policies': metadata.get('policies'),
                  'renewable': metadata.get('renewable')}))
record = query('vault kv get -format=json kv/forgejo/codetether-bot')['data']
print(json.dumps({'reviewer_credential_readable': bool(record.get('token')),
                  'username': record.get('username')}))