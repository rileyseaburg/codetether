#!/usr/bin/env node
// Favor durable workspace ownership over stale per-replica caches; preserve fallback data.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const dir = 'artifacts/agent-workflow-validation/workspace-hotfix-v2';
fs.mkdirSync(dir, { recursive: true });
function run(command, args, input) {
  const r = spawnSync(command, args, { input, encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
  if (r.status !== 0) {
    if (args.includes('--patch')) fs.writeFileSync(`${dir}/patch-error.txt`, r.stderr || r.error?.message || 'Unknown error');
    throw new Error(`${command} failed; output suppressed`);
  }
  return r.stdout;
}
const pods = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'pods', '-l', 'color=green', '-o', 'json']));
const pod = pods.items.find(p => p.status.containerStatuses?.[0]?.ready);
if (!pod || pod.spec.containers[0].image !== 'registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:main-eb2051a212a2') throw new Error('Unexpected API image');
const original = run('kubectl', ['-n', 'a2a-system', 'exec', '-i', pod.metadata.name, '--', 'python', '/dev/stdin'],
  fs.readFileSync('scripts/read_deployed_monitor.py', 'utf8'));
let modified = original;
for (const name of ['redis_workspaces', 'db_workspaces']) {
  const before = `for cb in ${name}:\n        cid = cb.get('id')\n        if cid and cid not in merged:\n            merged[cid] = cb`;
  const after = `for cb in ${name}:\n        cid = cb.get('id')\n        if cid:\n            merged[cid] = {**merged.get(cid, {}), **cb}`;
  if (modified.includes(before)) modified = modified.replace(before, after);
  else if (modified.split(after).length !== 2) {
    throw new Error('Expected original or repaired merge block not found exactly once');
  }
}
// These endpoints otherwise reported cancellation without executing the coroutine.
const cancellation = 'success = bridge.cancel_task(task_id)';
if (modified.split(cancellation).length === 3) {
  modified = modified.replaceAll(cancellation, 'success = await bridge.cancel_task(task_id)');
} else if (modified.split('success = await bridge.cancel_task(task_id)').length !== 3) {
  throw new Error('Unexpected cancellation sites');
}
const detailMerge = `        for source in (db_workspace, redis_workspace):`;
const authoritativeDetail = `        # Match list-workspace precedence: durable path/ownership wins.
        workspace_dict = {
            **workspace_dict,
            **(redis_workspace or {}),
            **(db_workspace or {}),
        }
${detailMerge}`;
if (modified.split(detailMerge).length !== 2) throw new Error('Unexpected workspace detail merge sites');
if (!modified.includes(authoritativeDetail)) modified = modified.replace(detailMerge, authoritativeDetail);
fs.writeFileSync(`${dir}/monitor.before.py`, original);
fs.writeFileSync(`${dir}/monitor.after.py`, modified);
run('.venv/bin/python', ['-m', 'py_compile', `${dir}/monitor.after.py`]);
const name = 'workspace-registry-consistency';
const map = 'codetether-workspace-registry-v2-20261005';
run('kubectl', ['apply', '--server-side', '--field-manager=codetether-workspace-repair', '-f', '-'], JSON.stringify({ apiVersion: 'v1', kind: 'ConfigMap',
  metadata: { name: map, namespace: 'a2a-system' }, data: { 'monitor_api.py': modified } }));
const app = JSON.parse(run('kubectl', ['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const patch = [{ op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion }];
for (const [key, value] of Object.entries({
  volumes: { name, configMap: { name: map, items: [{ key: 'monitor_api.py', path: 'monitor_api.py' }] } },
  volumeMounts: { name, mountPath: '/app/a2a_server/monitor_api.py', subPath: 'monitor_api.py', readOnly: true },
})) {
  const items = app.spec.source.helm.valuesObject[key] || [];
  const index = items.findIndex(item => item.name === name);
  if (!app.spec.source.helm.valuesObject[key]) patch.push({ op: 'add', path: `/spec/source/helm/valuesObject/${key}`, value: [] });
  patch.push({ op: index < 0 ? 'add' : 'replace', path: `/spec/source/helm/valuesObject/${key}/${index < 0 ? '-' : index}`, value });
}
run('kubectl', ['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
const sha = text => crypto.createHash('sha256').update(text).digest('hex');
const record = { namespace: 'a2a-system', configMap: map, beforeSha256: sha(original), afterSha256: sha(modified),
  precedence: ['local fallback', 'Redis', 'PostgreSQL'], detailPrecedenceFixed: true, cancellationAwaited: true, repositoryFileModified: false };
fs.writeFileSync(`${dir}/deployment.json`, JSON.stringify(record, null, 2));
console.log(JSON.stringify(record));

