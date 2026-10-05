#!/usr/bin/env node
// Preserve issuer verification; use the canonical public HTTPS token endpoint.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function kubectl(args) {
  const result = spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000 });
  if (result.status !== 0) throw new Error('kubectl failed; raw output suppressed');
  return result.stdout;
}
const app = JSON.parse(kubectl(['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
if (app.spec.source.targetRevision !== 'eb2051a212a2c729a7963da8e1dda39a4e958513') {
  throw new Error('Deployment revision changed; re-review before modifying');
}
const parameters = app.spec.source.helm?.parameters || [];
const changes = {
  'env.KEYCLOAK_URL': 'https://auth.quantum-forge.io',
  'env.KEYCLOAK_ISSUER': 'https://auth.quantum-forge.io/realms/quantum-forge',
};
const patch = [{ op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion }];
if (!app.spec.source.helm) patch.push({ op: 'add', path: '/spec/source/helm', value: {} });
if (!app.spec.source.helm?.parameters) patch.push({ op: 'add', path: '/spec/source/helm/parameters', value: [] });
const previous = {};
for (const [name, value] of Object.entries(changes)) {
  const index = parameters.findIndex(parameter => parameter.name === name);
  previous[name] = index >= 0 ? parameters[index].value : null;
  patch.push(index >= 0
    ? { op: 'replace', path: `/spec/source/helm/parameters/${index}`, value: { name, value } }
    : { op: 'add', path: '/spec/source/helm/parameters/-', value: { name, value } });
}
kubectl(['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
const record = { application: 'argocd/codetether-a2a-server', previous, changes,
  reason: 'Internal HTTP token endpoint minted a different issuer from the required public HTTPS issuer',
  changedAt: new Date().toISOString(), issuerValidationDisabled: false };
fs.mkdirSync('artifacts/ios-login-followup-20261005', { recursive: true });
fs.writeFileSync('artifacts/ios-login-followup-20261005/transport-repair.json', JSON.stringify(record, null, 2) + '\n');
console.log(JSON.stringify(record, null, 2));




