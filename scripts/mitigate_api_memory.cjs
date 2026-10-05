#!/usr/bin/env node
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
function kubectl(args) {
  const r = spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error('kubectl failed; output suppressed');
  return r.stdout;
}
const app = JSON.parse(kubectl(['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const values = app.spec.source.helm.valuesObject;
const resources = { limits: { cpu: '4000m', memory: '6Gi' }, requests: { cpu: '1000m', memory: '3Gi' } };
const patch = [
  { op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion },
  { op: 'replace', path: '/spec/source/helm/valuesObject/blueGreen/replicas/green', value: 1 },
  { op: 'replace', path: '/spec/source/helm/valuesObject/resources', value: resources },
];
kubectl(['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
const record = { previous: { replicas: values.blueGreen.replicas.green, resources: values.resources },
  current: { replicas: 1, resources }, namespace: 'a2a-system', deployment: 'a2a-server-deployment-green',
  reason: 'Repeated OOMKilled and API timeouts; RWO local storage pins replicas to one constrained node',
  permanentMemoryRootCauseFixed: false, time: new Date().toISOString() };
fs.writeFileSync('artifacts/agent-workflow-validation/api-memory-mitigation.json', JSON.stringify(record, null, 2));
console.log(JSON.stringify(record));


