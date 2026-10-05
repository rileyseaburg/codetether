import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

OUT = Path(__file__).parent
release = json.loads((OUT / 'release.json').read_text())
image = 'us-central1-docker.pkg.dev/spotlessbinco/codetether/codetether-marketing:ui-' + release['commit'][:12]
docker = ['docker', '-H', 'unix:///var/run/docker.sock']
subprocess.run(docker + ['tag', release['image'], image], check=True)
secret = json.loads(subprocess.check_output(['kubectl', 'get', 'secret', 'gcp-artifact-registry', '-n', 'a2a-server', '-o', 'json'], text=True))
with tempfile.TemporaryDirectory(prefix='ui-gcp-registry-') as temporary:
    file = Path(temporary) / 'config.json'
    file.write_bytes(base64.b64decode(secret['data']['.dockerconfigjson'])); file.chmod(0o600)
    env = dict(os.environ, DOCKER_CONFIG=temporary)
    with (OUT / 'push-gcp.log').open('w') as log:
        result = subprocess.run(docker + ['push', image], stdout=log, stderr=subprocess.STDOUT, env=env)
    print('push_exit=' + str(result.returncode), flush=True)
    if result.returncode: raise SystemExit(result.returncode)
    data = json.loads(subprocess.check_output(docker + ['image', 'inspect', image], text=True, env=env))[0]
release.update(image=image, imageId=data['Id'], digests=data.get('RepoDigests', []), pullSecret='gcp-artifact-registry')
(OUT / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
print(json.dumps({'image': image, 'digests': release['digests']}, indent=2))