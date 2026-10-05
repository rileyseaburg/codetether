#!/usr/bin/env node
// Persist only sanitized output from the dedicated read-only checks.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function run(command, args) {
  const result = spawnSync(command, args, { encoding: 'utf8', timeout: 90000, maxBuffer: 8 * 1024 * 1024 });
  if (result.status !== 0) throw new Error('Evidence check failed; raw output suppressed');
  return result.stdout;
}
const logs = JSON.parse(run(process.execPath, ['scripts/check_ios_keycloak_logs.cjs', 'info@evolvingsoftware.io']));
const worker = run(process.execPath, ['scripts/ios_local_worker_preflight.cjs'])
  .trim().split('\n').map(line => JSON.parse(line));
const app = JSON.parse(run('kubectl', ['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const deployment = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'deployment', 'a2a-server-deployment-green', '-o', 'json']));
const report = {
  capturedAt: new Date().toISOString(), logs, worker,
  argo: { application: 'argocd/codetether-a2a-server', sync: app.status.sync.status,
    health: app.status.health.status, revision: app.status.sync.revision,
    workerParameters: app.spec.source.helm.parameters.filter(p => p.name === 'workerAuth.existingSecret'),
    unsynced: app.status.resources.filter(r => r.status !== 'Synced').map(r => ({ kind: r.kind, name: r.name })),
  },
  deployment: { namespace: deployment.metadata.namespace, name: deployment.metadata.name,
    generation: deployment.metadata.generation, ready: deployment.status.readyReplicas,
    updated: deployment.status.updatedReplicas,
    images: deployment.spec.template.spec.containers.map(c => ({ name: c.name, image: c.image })),
  },
  taskSubmitted: false, htmlHosted: false,
};
const file = 'artifacts/ios-login-e2e-20261005/backend-preflight.json';
fs.writeFileSync(file, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ artifact: file, capturedAt: report.capturedAt }));

