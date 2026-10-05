"""Commit a production Application manifest, then let Argo reconcile it."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
release = json.loads((OUT / 'release.json').read_text())
if not release.get('digests'):
    raise RuntimeError('Refusing promotion without a pushed image digest')
canary = json.loads((OUT / 'canary-browser.json').read_text())
if not canary.get('success') or canary.get('commit') != release['commit']:
    raise RuntimeError('Refusing promotion without matching successful canary evidence')
before = json.loads((OUT / 'argo-before.json').read_text())
source = copy.deepcopy(before['source'])
source['targetRevision'] = release['commit']
values = source['helm']['valuesObject']
repository, tag = release['image'].rsplit(':', 1)
values['image'].update(repository=repository, tag=tag, pullPolicy='IfNotPresent')
values['imagePullSecrets'] = [{'name': 'registry-credentials'}]
# Both production hosts are registered with Keycloak. Infer the initiating
# HTTPS origin instead of sending root-host callbacks to a different domain.
values.get('env', {}).pop('AUTH_URL', None)
values.get('env', {}).pop('NEXTAUTH_URL', None)
values['env']['AUTH_TRUST_HOST'] = 'true'
manifest = yaml.safe_load((ROOT / 'deploy/argocd/marketing.yaml').read_text())
manifest['spec']['source'] = source
manifest['spec']['destination'] = before['destination']
manifest['spec']['syncPolicy'] = before['syncPolicy']
text = yaml.safe_dump(manifest, sort_keys=False)
(OUT / 'production-application.yaml').write_text(text)
(ROOT / 'deploy/argocd/marketing.yaml').write_text(text)

def git(*args, env=None, input=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, input=input, text=True).strip()
with tempfile.TemporaryDirectory(prefix='ui-promotion-index-') as temporary:
    env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
    git('read-tree', release['commit'], env=env)
    git('add', '--', 'deploy/argocd/marketing.yaml', env=env)
    tree = git('write-tree', env=env)
    promotion = git('commit-tree', tree, '-p', release['commit'], input='chore(deploy): promote redesigned production UI through ArgoCD\n')
git('update-ref', 'refs/heads/' + release['branch'], promotion, release['commit'])
git('push', 'origin', 'refs/heads/' + release['branch'])
release['promotionCommit'] = promotion
(OUT / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
# Replace only the Application source; preserve unrelated live metadata/state.
patch = json.dumps([{'op': 'replace', 'path': '/spec/source', 'value': source}])
subprocess.run(['kubectl', 'patch', 'application', 'codetether-marketing', '-n', 'argocd', '--type=json', '-p', patch], check=True)
subprocess.run(['kubectl', 'annotate', 'application', 'codetether-marketing', '-n', 'argocd', 'argocd.argoproj.io/refresh=hard', '--overwrite'], check=True)
print(json.dumps({'promotionCommit': promotion, 'app': 'argocd/codetether-marketing', 'image': release['image']}, indent=2))