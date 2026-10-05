"""Route only explicitly marked production-host smoke traffic to the candidate."""
import copy
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).parent
release = json.loads((OUT / 'release.json').read_text())
if not release.get('digests'): raise RuntimeError('Candidate image is not published')
live = json.loads(subprocess.check_output(['kubectl', 'get', 'deployment', 'codetether-marketing', '-n', 'a2a-server', '-o', 'json'], text=True))
pod = copy.deepcopy(live['spec']['template']['spec'])
container = pod['containers'][0]
container['image'] = release['image']
container['env'] = [e for e in container.get('env', []) if e['name'] not in ['AUTH_URL', 'NEXTAUTH_URL']]
labels = {'app': 'codetether-marketing-canary'}
meta = {'name': 'codetether-marketing-canary', 'namespace': 'a2a-server'}
resources = [
  {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': meta,
   'spec': {'replicas': 1, 'selector': {'matchLabels': labels}, 'template': {'metadata': {'labels': labels}, 'spec': pod}}},
  {'apiVersion': 'v1', 'kind': 'Service', 'metadata': meta,
   'spec': {'selector': labels, 'ports': [{'port': 3000, 'targetPort': 3000}]}},
  {'apiVersion': 'networking.k8s.io/v1', 'kind': 'Ingress', 'metadata': {**meta, 'annotations': {
    'nginx.ingress.kubernetes.io/canary': 'true',
    'nginx.ingress.kubernetes.io/canary-by-header': 'X-CodeTether-Release',
    'nginx.ingress.kubernetes.io/canary-by-header-value': release['commit'],
  }}, 'spec': {'ingressClassName': 'nginx',
    'tls': [{'hosts': ['codetether.run'], 'secretName': 'codetether-marketing-tls'}],
    'rules': [{'host': 'codetether.run', 'http': {'paths': [{'path': '/', 'pathType': 'Prefix', 'backend': {'service': {'name': meta['name'], 'port': {'number': 3000}}}}]}}]}}
]
manifest = {'apiVersion': 'v1', 'kind': 'List', 'items': resources}
(OUT / 'canary.json').write_text(json.dumps(manifest, indent=2))
subprocess.run(['kubectl', 'apply', '-f', str(OUT / 'canary.json')], check=True)
subprocess.run(['kubectl', 'rollout', 'status', 'deployment/codetether-marketing-canary', '-n', 'a2a-server', '--timeout=180s'], check=True)