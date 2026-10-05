"""Build an exact committed frontend snapshot; keep registry credentials private."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
release = json.loads((OUT / 'release.json').read_text())
subprocess.run(['git', 'push', 'origin', 'refs/heads/' + release['branch']], cwd=ROOT, check=True)
archive = subprocess.check_output(['git', 'archive', release['commit'] + ':marketing-site'], cwd=ROOT)
context = OUT / 'build-context.tar.gz'
excluded_roots = {'node_modules', '.next', '.git', 'certs', 'e2e', 'test-results', 'playwright-report', 'coverage', '.npmrc'}
with tarfile.open(fileobj=io.BytesIO(archive)) as source, tarfile.open(context, 'w:gz') as target:
    for member in source:
        parts = Path(member.name).parts
        if not parts or parts[0] in excluded_roots or any(part.startswith('.env') for part in parts):
            continue
        if member.name.endswith(('.pem', '.key', '.tsbuildinfo', '.log')):
            continue
        target.addfile(member, source.extractfile(member) if member.isfile() else None)
secret = json.loads(subprocess.check_output(['kubectl', 'get', 'secret', 'registry-credentials', '-n', 'a2a-server', '-o', 'json'], text=True))
config = base64.b64decode(secret['data']['.dockerconfigjson'])
with tempfile.TemporaryDirectory(prefix='ui-registry-') as temporary:
    config_path = Path(temporary) / 'config.json'
    config_path.write_bytes(config)
    config_path.chmod(0o600)
    env = dict(os.environ, DOCKER_CONFIG=temporary, DOCKER_BUILDKIT='0')
    docker = ['docker', '-H', 'unix:///var/run/docker.sock']
    with context.open('rb') as stream, (OUT / ('build-' + release['commit'][:12] + '.log')).open('w') as log:
        command = docker + ['build', '--memory=10g', '--build-arg', 'SOURCE_REVISION=' + release['commit'], '-t', release['image'], '-']
        result = subprocess.run(command, stdin=stream, stdout=log, stderr=subprocess.STDOUT, env=env)
    print('build_exit=' + str(result.returncode), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    # Publishing uses push-harbor.py: the deployment pull credential is read-only.
    data = json.loads(subprocess.check_output(docker + ['image', 'inspect', release['image']], env=env, text=True))[0]
    release['digests'] = data.get('RepoDigests', [])
    release['imageId'] = data['Id']
    (OUT / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
    print(json.dumps({key: release[key] for key in ['commit', 'image', 'digests']}, indent=2))