"""Run the changed UI with real Keycloak/API credentials, without logging secrets."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('LIVE_EVIDENCE_DIR', str(Path(__file__).parent)))
OUT.mkdir(parents=True, exist_ok=True)
result = subprocess.run(
    ['kubectl', 'get', 'secret', 'keycloak-client-secret', '-n', 'a2a-server', '-o', 'json'],
    check=True, capture_output=True, text=True,
)
secret = json.loads(result.stdout)['data']
env = dict(os.environ)
env.update({
    'AUTH_URL': 'http://localhost:3001',
    'NEXTAUTH_URL': 'http://localhost:3001',
    'AUTH_SECRET': secrets.token_urlsafe(48),
    'NEXTAUTH_SECRET': '',
    'AUTH_TRUST_HOST': 'true',
    'KEYCLOAK_CLIENT_ID': 'a2a-monitor',
    'KEYCLOAK_CLIENT_SECRET': base64.b64decode(secret['KEYCLOAK_CLIENT_SECRET']).decode(),
    'KEYCLOAK_ISSUER': 'https://auth.quantum-forge.io/realms/quantum-forge',
    'KEYCLOAK_URL': 'https://auth.quantum-forge.io',
    'NEXT_PUBLIC_API_URL': os.environ.get('LIVE_API_URL', 'https://api.codetether.run'),
    'A2A_API_BACKEND': os.environ.get('LIVE_API_BACKEND', 'https://api.codetether.run'),
})
files = set()
for args in (['diff', '--name-only', '--', 'marketing-site', 'a2a_server/tenant_service.py'],
             ['ls-files', '--others', '--exclude-standard', '--', 'marketing-site']):
    files.update(subprocess.check_output(['git', *args], cwd=ROOT, text=True).splitlines())
manifest = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(files) if (ROOT / p).is_file()}
(OUT / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
proc = subprocess.Popen(['./node_modules/.bin/next', 'dev', '--webpack', '--hostname', '127.0.0.1', '-p', '3001'],
                        cwd=ROOT / 'marketing-site', env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
(OUT / 'server.pid').write_text(str(proc.pid) + '\n')
# Whitelist progress lines only. Auth/library diagnostics can contain credentials.
with (OUT / 'server-progress.log').open('a') as log:
    for line in proc.stdout:
        text = line.strip()
        if text.startswith(('✓ Ready', '○ Compiling', '▲ Next.js')):
            print(text, flush=True)
            log.write(text + '\n')
            log.flush()
status = proc.wait()
print(f'ui_server_exit={status}', flush=True)
raise SystemExit(status)