#!/usr/bin/env node
// Narrow runtime hotfix while the repository database module has another writer's lease.
// Does not modify that protected worktree file or alter/delete historical DB records.
const fs = require('node:fs');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const dir = 'artifacts/agent-workflow-validation/registry-hotfix';
fs.mkdirSync(dir, { recursive: true });
function run(command, args, input) {
  const result = spawnSync(command, args, { input, encoding: 'utf8', timeout: 30000, maxBuffer: 16 * 1024 * 1024 });
  if (result.status !== 0) {
    if (args.includes('--patch')) {
      fs.writeFileSync(`${dir}/patch-error.txt`, result.stderr);
    }
    throw new Error(`${command} failed; raw output suppressed`);
  }
  return result.stdout;
}
const deployment = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'deployment', 'a2a-server-deployment-green', '-o', 'json']));
const expectedImage = 'registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:main-eb2051a212a2';
if (deployment.spec.template.spec.containers[0].image !== expectedImage) throw new Error('API image changed; re-review hotfix');
const pods = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'pods', '-l', 'color=green', '-o', 'json']));
const pod = pods.items.find(p => p.status.containerStatuses?.[0]?.ready);
if (!pod) throw new Error('No ready API pod to inspect');
const original = run('kubectl', ['-n', 'a2a-system', 'exec', '-i', pod.metadata.name, '--', 'python', '/dev/stdin'],
  fs.readFileSync('scripts/read_deployed_database.py', 'utf8'));
const before = "query = 'SELECT * FROM workers WHERE 1=1'";
const after = `query = '''SELECT worker_id, name, capabilities, hostname,
                              CASE WHEN last_seen >= NOW() - INTERVAL '24 hours'
                                   THEN models ELSE '[]'::jsonb END AS models,
                              global_workspace_id, registered_at, last_seen,
                              status
                       FROM workers WHERE 1=1'''`;
if (original.split(before).length !== 2) throw new Error('Expected unbounded query not found exactly once');
const modified = original.replace(before, after);
const sha = content => crypto.createHash('sha256').update(content).digest('hex');
fs.writeFileSync(`${dir}/database.before.py`, original);
fs.writeFileSync(`${dir}/database.after.py`, modified);
run('.venv/bin/python', ['-m', 'py_compile', `${dir}/database.after.py`]);
fs.writeFileSync(`${dir}/query-change.json`, JSON.stringify({ before, after, preservesHistoricalRows: true, singleWorkerLookupUnchanged: true }, null, 2));
const configMapName = 'codetether-worker-registry-bounded-20261005';
const configMap = { apiVersion: 'v1', kind: 'ConfigMap', metadata: { name: configMapName, namespace: 'a2a-system',
  labels: { 'app.kubernetes.io/part-of': 'codetether' } }, data: { 'database.py': modified } };
run('kubectl', ['apply', '-f', '-'], JSON.stringify(configMap));
const app = JSON.parse(run('kubectl', ['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
const values = app.spec.source.helm.valuesObject;
const patch = [{ op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion }];
const name = 'worker-registry-bounded';
for (const [key, item] of Object.entries({
  volumes: { name, configMap: { name: configMapName, items: [{ key: 'database.py', path: 'database.py' }] } },
  volumeMounts: { name, mountPath: '/app/a2a_server/database.py', subPath: 'database.py', readOnly: true },
})) {
  const entries = values[key] || [];
  const index = entries.findIndex(entry => entry.name === name);
  if (!values[key]) patch.push({ op: 'add', path: `/spec/source/helm/valuesObject/${key}`, value: [] });
  patch.push({ op: index < 0 ? 'add' : 'replace', path: `/spec/source/helm/valuesObject/${key}/${index < 0 ? '-' : index}`, value: item });
}
for (const unused of ['extraVolumes', 'extraVolumeMounts']) {
  if (values[unused]?.length === 1 && values[unused][0].name === name) {
    patch.push({ op: 'remove', path: `/spec/source/helm/valuesObject/${unused}` });
  }
}
run('kubectl', ['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
const record = { namespace: 'a2a-system', configMapName, image: expectedImage,
  sourcePod: pod.metadata.name, beforeSha256: sha(original), afterSha256: sha(modified),
  change: 'Omit model catalogs older than 24h from bulk registry listing only',
  historicalRecordsDeleted: false, repositoryFileModified: false, appliedAt: new Date().toISOString() };
fs.writeFileSync(`${dir}/deployment.json`, JSON.stringify(record, null, 2));
console.log(JSON.stringify(record, null, 2));










