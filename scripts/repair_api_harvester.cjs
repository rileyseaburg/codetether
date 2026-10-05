#!/usr/bin/env node
// Enable a targeted API worker without changing finite Forgejo Job routing.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function kubectl(args) {
  const r = spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error('kubectl failed; output suppressed');
  return r.stdout;
}
const app = JSON.parse(kubectl(['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const base = '/spec/source/helm/valuesObject/harvester';
const current = app.spec.source.helm.valuesObject.harvester;
if (!current.enabled) throw new Error('Unexpected disabled harvester chart');
const patch = [
  { op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion },
  { op: 'add', path: base + '/replicaCount', value: 1 },
  { op: 'add', path: base + '/image/tag', value: '4.7.6-dev.24-session-context-2a86d64c' },
  { op: 'add', path: base + '/capabilities', value: [...new Set([...(current.capabilities || ['harvester', 'persistent', 'persistent-workspace', 'persistent_workspace', 'git-clone', 'repo-cache']), 'session-context'])] },
  { op: 'add', path: base + '/tokenSecret', value: { name: 'a2a-server-ios-worker-auth', key: 'WORKER_AUTH_TOKEN' } },
  { op: 'add', path: base + '/workspaceReclaim', value: { ...current.workspaceReclaim, enabled: false } },
];
const extra = current.extraEnv || [];
const index = extra.findIndex(e => e.name === 'CODETETHER_WORKER_TARGETED_ONLY');
if (!current.extraEnv) patch.push({ op: 'add', path: base + '/extraEnv', value: [] });
patch.push({ op: index >= 0 ? 'replace' : 'add', path: base + '/extraEnv/' + (index >= 0 ? index : '-'),
  value: { name: 'CODETETHER_WORKER_TARGETED_ONLY', value: '1' } });
const stableIndex = extra.findIndex(e => e.name === 'CODETETHER_WORKER_ID');
patch.push({ op: stableIndex >= 0 ? 'replace' : 'add', path: base + '/extraEnv/' + (stableIndex >= 0 ? stableIndex : '-'),
  value: { name: 'CODETETHER_WORKER_ID', valueFrom: { fieldRef: { fieldPath: 'metadata.name' } } } });
kubectl(['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
const record = { application: app.metadata.name, previousReplicas: current.replicaCount,
  replicas: 1, targetedOnly: true, taskJobsUnchanged: true, workspaceCleanupDisabled: true,
  tokenSecret: 'a2a-server-ios-worker-auth', changedAt: new Date().toISOString() };
fs.mkdirSync('artifacts/agent-workflow-validation', { recursive: true });
fs.writeFileSync('artifacts/agent-workflow-validation/harvester-repair.json', JSON.stringify(record, null, 2));
console.log(JSON.stringify(record));