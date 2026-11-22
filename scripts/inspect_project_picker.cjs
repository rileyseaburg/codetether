#!/usr/bin/env node
// Read-only project-discovery diagnostics. Never reads tasks or conversation history.
const fs = require('node:fs');
require('node:dns').setDefaultResultOrder('ipv4first');
async function main() {
  const line = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n').find(value => value.startsWith('CODETETHER_TOKEN='));
  const token = line.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
  async function get(route) {
    const response = await fetch('https://api.codetether.run' + route, {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000) });
    if (response.status !== 200) throw new Error(`Project inspection HTTP ${response.status}`);
    return response.json();
  }
  const [workers, projects] = await Promise.all([get('/v1/agent/workers?online_only=true'), get('/v1/agent/workspaces')]);
  const report = { verificationLevel: 'live deployment/Argo', observedAt: new Date().toISOString(),
    readOnly: true, totalWorkspaces: projects.length, workers: [] };
  for (const worker of workers) {
    const roots = worker.workspaces || [];
    const pathMatch = project => roots.some(root => project.path === root || project.path?.startsWith(root.endsWith('/') ? root : root + '/'));
    const displayed = projects.filter(project => project.worker_id === worker.worker_id || pathMatch(project));
    const proposed = projects.filter(project => project.worker_id === worker.worker_id ||
      (!project.worker_id && roots.includes(project.path)));
    const owners = {};
    for (const project of displayed) owners[project.worker_id || '(unassigned)'] = (owners[project.worker_id || '(unassigned)'] || 0) + 1;
    const counts = {};
    for (const project of displayed) {
      const prefix = project.path?.split('/').slice(0, 6).join('/') || '(no path)';
      counts[prefix] = (counts[prefix] || 0) + 1;
    }
    report.workers.push({ workerId: worker.worker_id, name: worker.name, roots,
      strictDiscoveryCount: proposed.length,
      strictExamples: proposed.slice(0, 8).map(p => ({ name: p.name, path: p.path, owner: p.worker_id })),
      displayedCount: displayed.length, explicitOwnerCount: projects.filter(p => p.worker_id === worker.worker_id).length,
      foreignOwnerCount: displayed.filter(p => p.worker_id && p.worker_id !== worker.worker_id).length,
      exactAdvertisedPathCount: projects.filter(p => roots.includes(p.path)).length,
      owners, pathGroups: Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12),
      examples: displayed.slice(0, 8).map(p => ({ id: p.id, name: p.name, path: p.path,
        workerId: p.worker_id, status: p.status, fields: Object.keys(p) })) });
  }
  const dir = 'artifacts/agent-workflow-validation/project-picker';
  fs.mkdirSync(dir, { recursive: true });
  const output = `${dir}/inspection-${Date.now()}.json`;
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ ...report, artifact: output }, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });