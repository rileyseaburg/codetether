"""Publish with the registry's configured administration credential; no ACL changes."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

OUT = Path(__file__).parent
release = json.loads((OUT / 'release.json').read_text())
secret = json.loads(subprocess.check_output(['kubectl', 'get', 'secret', 'harbor-core', '-n', 'container-registry', '-o', 'json'], text=True))
password = base64.b64decode(secret['data']['HARBOR_ADMIN_PASSWORD']).decode()
docker = ['docker', '-H', 'unix:///var/run/docker.sock']
with tempfile.TemporaryDirectory(prefix='ui-harbor-publish-') as temporary:
    env = dict(os.environ, DOCKER_CONFIG=temporary)
    login = subprocess.run(docker + ['login', 'registry.quantum-forge.net', '--username', 'admin', '--password-stdin'], input=password,
                           text=True, capture_output=True, env=env)
    print('registry_login_exit=' + str(login.returncode), flush=True)
    if login.returncode:
        print('Configured Harbor login rejected; no credential values logged.')
        raise SystemExit(login.returncode)
    with (OUT / 'push-harbor.log').open('w') as log:
        pushed = subprocess.run(docker + ['push', release['image']], stdout=log, stderr=subprocess.STDOUT, env=env)
    print('push_exit=' + str(pushed.returncode), flush=True)
    if pushed.returncode: raise SystemExit(pushed.returncode)
    data = json.loads(subprocess.check_output(docker + ['image', 'inspect', release['image']], text=True, env=env))[0]
release.update(imageId=data['Id'], digests=data.get('RepoDigests', []), pullSecret='registry-credentials')
(OUT / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
print(json.dumps({'image': release['image'], 'digests': release['digests']}, indent=2))