#!/usr/bin/env node
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
async function main() {
  const line = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n').find(l => l.startsWith('CODETETHER_TOKEN='));
  const token = line.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
  const report = { observedAt: new Date().toISOString(), requests: [] };
  for (let i = 0; i < 3; i++) {
    for (const route of ['/v1/agent/workers?online_only=true', '/v1/agent/workspaces']) {
      const start = Date.now();
      const response = await fetch('https://api.codetether.run' + route, { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(15000) });
      const bytes = Buffer.from(await response.arrayBuffer());
      if (response.status !== 200) throw new Error(`API ${response.status}`);
      const data = JSON.parse(bytes.toString());
      report.requests.push({ route, status: response.status, elapsedMs: Date.now() - start, responseBytes: bytes.length, rows: Array.isArray(data) ? data.length : null });
    }
  }
  const pods = spawnSync('kubectl', ['-n', 'a2a-system', 'get', 'pods', '-l', 'color=green', '-o', 'json'], { encoding: 'utf8' });
  const pod = JSON.parse(pods.stdout).items.find(p => p.status.containerStatuses?.[0]?.ready);
  if (!pod) throw new Error('API not ready');
  const sql = spawnSync('kubectl', ['-n', 'a2a-system', 'exec', '-i', pod.metadata.name, '--', 'python', '/dev/stdin'], {
    input: fs.readFileSync('scripts/check_bounded_worker_query.py'), encoding: 'utf8', timeout: 30000 });
  if (sql.status !== 0) throw new Error('Bounded-query check failed');
  report.database = JSON.parse(sql.stdout);
  report.pod = { name: pod.metadata.name, restarts: pod.status.containerStatuses[0].restartCount };
  fs.writeFileSync('artifacts/agent-workflow-validation/registry-hotfix/proof.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });












