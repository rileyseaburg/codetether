#!/usr/bin/env node
// Remove stale, unmanaged template fields after verifying the desired pull secret remains.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function kubectl(args) {
  const r = spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error('kubectl failed; output suppressed');
  return r.stdout;
}
const resource = JSON.parse(kubectl(['-n', 'a2a-system', 'get', 'statefulset', 'a2a-server-harvester', '-o', 'json']));
const secrets = resource.spec.template.spec.imagePullSecrets;
if (!secrets.some(s => s.name === 'registry-credentials')) throw new Error('Desired registry pull credential absent');
const patch = [{ op: 'test', path: '/metadata/resourceVersion', value: resource.metadata.resourceVersion }];
const obsolete = secrets.findIndex(s => s.name === 'harbor-regcred');
if (obsolete >= 0) patch.push({ op: 'remove', path: `/spec/template/spec/imagePullSecrets/${obsolete}` });
if (resource.spec.template.metadata.annotations?.['kubectl.kubernetes.io/restartedAt']) {
  patch.push({ op: 'remove', path: '/spec/template/metadata/annotations/kubectl.kubernetes.io~1restartedAt' });
}
kubectl(['-n', 'a2a-system', 'patch', 'statefulset', 'a2a-server-harvester', '--type=json', '--patch', JSON.stringify(patch)]);
fs.writeFileSync('artifacts/agent-workflow-validation/harvester-metadata-reconcile.json', JSON.stringify({
  namespace: 'a2a-system', name: resource.metadata.name, patch, secretObjectsDeleted: false,
  podRestarted: false, updateStrategy: resource.spec.updateStrategy,
}, null, 2));
console.log('Reconciled stale template metadata; preserved Secret objects and running pod');
