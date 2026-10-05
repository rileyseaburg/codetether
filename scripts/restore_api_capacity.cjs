#!/usr/bin/env node
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
function run(args) {
  const result = spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000 });
  if (result.status !== 0) throw new Error('kubectl failed; output suppressed');
  return result.stdout;
}
const proof = JSON.parse(fs.readFileSync('artifacts/agent-workflow-validation/registry-hotfix/proof.json'));
if (!proof.database.bounded || proof.requests.some(r => r.status !== 200)) throw new Error('Registry fix gate not satisfied');
const previous = JSON.parse(fs.readFileSync('artifacts/agent-workflow-validation/api-memory-mitigation.json')).previous;
const app = JSON.parse(run(['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const patch = [
  { op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion },
  { op: 'replace', path: '/spec/source/helm/valuesObject/resources', value: previous.resources },
  { op: 'replace', path: '/spec/source/helm/valuesObject/blueGreen/replicas/green', value: previous.replicas },
];
const ignored = app.spec.ignoreDifferences || [];
const index = ignored.findIndex(rule => rule.name === 'a2a-server-harvester' && rule.jqPathExpressions?.includes('select(.spec.updateStrategy.type == "OnDelete") | .spec.updateStrategy.rollingUpdate'));
if (index >= 0) patch.push({ op: 'remove', path: `/spec/ignoreDifferences/${index}` });
run(['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
fs.writeFileSync('artifacts/agent-workflow-validation/api-capacity-restored.json', JSON.stringify({
  restored: previous, reason: 'Bounded registry projection removes the large allocation; restore original redundancy',
  inconclusiveDiffNormalizationRemoved: index >= 0, at: new Date().toISOString(),
}, null, 2));
console.log(JSON.stringify({ replicas: previous.replicas, resources: previous.resources }));



