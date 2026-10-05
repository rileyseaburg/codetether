#!/usr/bin/env node
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function run(command, args, input) {
  const r = spawnSync(command, args, { input, encoding: 'utf8', timeout: 30000, maxBuffer: 16 * 1024 * 1024 });
  if (r.status !== 0) throw new Error(`${command} failed; raw output suppressed`);
  return r.stdout;
}
const app = JSON.parse(run('kubectl', ['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const args = ['template', 'a2a-server', 'chart/a2a-server', '-n', 'a2a-system', '-f', '-', '--show-only', 'templates/harvester-statefulset.yaml'];
for (const p of app.spec.source.helm.parameters || []) args.push('--set', `${p.name}=${p.value}`);
const yaml = run('helm', args, JSON.stringify(app.spec.source.helm.valuesObject));
const desired = JSON.parse(run('kubectl', ['create', '--dry-run=client', '-f', '-', '-o', 'json'], yaml));
const live = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'statefulset', 'a2a-server-harvester', '-o', 'json']));
const diffs = [];
function compare(a, b, location) {
  if (JSON.stringify(a) === JSON.stringify(b)) return;
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) compare(a[key], b[key], `${location}/${key}`);
  } else {
    const safe = /updateStrategy|volumeClaimTemplates|revisionHistoryLimit|podManagementPolicy|terminationGracePeriodSeconds|dnsPolicy|restartPolicy|schedulerName|securityContext|imagePullPolicy/.test(location);
    diffs.push({ path: location, ...(safe ? { desired: a, live: b } : { valuesSuppressed: true }) });
  }
}
compare(desired.spec, live.spec, '/spec');
fs.mkdirSync('artifacts/agent-workflow-validation', { recursive: true });
fs.writeFileSync('artifacts/agent-workflow-validation/harvester-drift.json', JSON.stringify(diffs, null, 2));
console.log(JSON.stringify(diffs, null, 2));











