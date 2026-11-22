#!/usr/bin/env node
// Compare Argo's actual desired manifests, not a different local chart revision.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const dir = 'artifacts/agent-workflow-validation';
function run(command, args, env = process.env, input) {
  const result = spawnSync(command, args, { encoding: 'utf8', env, input, timeout: 90000, maxBuffer: 16000000 });
  if (result.status !== 0) throw new Error(`${command} failed; unfiltered output withheld`);
  return result.stdout;
}
function main() {
  const env = { ...process.env, KUBECONFIG: `${process.cwd()}/${dir}/kube-namespace-overlay.json:${process.env.KUBECONFIG || `${process.env.HOME}/.kube/config`}` };
  const source = run('argocd', ['app', 'manifests', 'codetether-a2a-server', '--core', '--source', 'git'], env);
  const document = source.split(/^---\s*$/m).find(doc => /^kind:\s*StatefulSet\s*$/m.test(doc)
    && /^  name:\s*a2a-server-harvester\s*$/m.test(doc));
  if (!document) throw new Error('Harvester document missing from Argo desired manifests');
  const manifests = [JSON.parse(run('kubectl', ['create', '--dry-run=client', '--validate=false', '-f', '-', '-o', 'json'], process.env, document))];
  const desired = manifests.find(doc => doc?.kind === 'StatefulSet' && doc.metadata?.name === 'a2a-server-harvester');
  if (!desired) throw new Error('No desired harvester manifest');
  const live = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'statefulset', 'a2a-server-harvester', '-o', 'json']));
  const differences = [];
  function compare(a, b, path) {
    if (JSON.stringify(a) === JSON.stringify(b)) return;
    if (a && b && typeof a === 'object' && typeof b === 'object') {
      for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) compare(a[key], b[key], `${path}.${key}`);
      return;
    }
    const safe = /replicas|storage|volumeMode|updateStrategy|apiVersion|\.kind$|serviceName/.test(path);
    differences.push({ path, desiredPresent: a !== undefined, livePresent: b !== undefined,
      ...(safe ? { desired: a, live: b } : {}) });
  }
  compare(desired.spec, live.spec, 'spec');
  const report = { checkedAt: new Date().toISOString(), source: 'Argo desired manifests', differences };
  fs.writeFileSync(`${dir}/argo-harvester-manifest-diff.json`, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }