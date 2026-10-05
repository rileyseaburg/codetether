#!/usr/bin/env node
// Select Argo's namespace without changing the user's kubeconfig or copying credentials.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const current = spawnSync('kubectl', ['config', 'view', '--minify', '-o', 'json'], { encoding: 'utf8' });
if (current.status !== 0) throw new Error('Cannot inspect context names');
const view = JSON.parse(current.stdout);
const context = view.contexts[0];
const overlay = { apiVersion: 'v1', kind: 'Config', 'current-context': view['current-context'], contexts: [{
  name: context.name, context: { cluster: context.context.cluster, user: context.context.user, namespace: 'argocd' },
}] };
const file = path.resolve('artifacts/agent-workflow-validation/kube-namespace-overlay.json');
fs.writeFileSync(file, JSON.stringify(overlay), { mode: 0o600 });
const kubeconfig = process.env.KUBECONFIG || path.join(process.env.HOME, '.kube/config');
const result = spawnSync('argocd', ['app', 'diff', 'codetether-a2a-server', '--core', '--refresh'], {
  encoding: 'utf8', timeout: 60000, maxBuffer: 8 * 1024 * 1024,
  env: { ...process.env, KUBECONFIG: `${file}:${kubeconfig}` },
});
fs.writeFileSync('artifacts/agent-workflow-validation/argo-diff.txt', result.stdout || '');
console.log(JSON.stringify({ exit: result.status, artifact: 'artifacts/agent-workflow-validation/argo-diff.txt' }));
console.log(result.stdout || '');
const diagnosticLines = String(result.stderr || '').split('\n').filter(line =>
  /^(@@|---|\+\+\+|[+-]\s)/.test(line));
fs.writeFileSync('artifacts/agent-workflow-validation/argo-diff-diagnostic.txt', diagnosticLines.join('\n'));
console.log(diagnosticLines.join('\n'));
if (![0, 1].includes(result.status)) { console.error('Argo diff unavailable; raw diagnostic suppressed'); process.exitCode = 1; }


