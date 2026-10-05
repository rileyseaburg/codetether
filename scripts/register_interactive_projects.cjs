#!/usr/bin/env node
// Hand off only these verified local project registrations to the interactive worker.
const fs = require('node:fs');
require('node:dns').setDefaultResultOrder('ipv4first');
const workerId = 'ubuntu-dev-sessions';
const legacy = 'wrk_1791203157_35195f4f7b97da0a';
const token = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
  .find(l => l.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
async function api(route, method = 'GET', body) {
  const response = await fetch('https://api.codetether.run' + route, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error(`API HTTP ${response.status}`);
  return response.json();
}
async function main() {
  const workers = await api('/v1/agent/workers?online_only=true');
  const worker = workers.find(w => w.worker_id === workerId && w.capabilities?.includes('session-context'));
  if (!worker) throw new Error('Interactive worker not registered');
  const projects = [
    { workspace_id: 'local-codetether-agent', name: 'CodeTether Agent', path: '/home/riley/A2A-Server-MCP/codetether-agent' },
    { workspace_id: 'local-a2a-server-mcp', name: 'A2A Server', path: '/home/riley/A2A-Server-MCP' },
    { workspace_id: 'ios-e2e-ubuntu-dev', name: 'iOS Validation', path: '/home/riley/A2A-Server-MCP/artifacts/ios-e2e-web' },
  ];
  const all = await api('/v1/agent/workspaces');
  for (const project of projects) {
    const prior = all.find(p => p.id === project.workspace_id);
    if (!fs.statSync(project.path).isDirectory()) throw new Error('Local project is not a directory');
    if (prior && (prior.path !== project.path || ![legacy, workerId].includes(prior.worker_id))) throw new Error('Project ownership differs; refusing handoff');
    await api('/v1/agent/workspaces', 'POST', { ...project, worker_id: workerId,
      description: 'Interactive CLI-style native work-session project' });
  }
  const check = await api('/v1/agent/workspaces');
  for (const project of projects) {
    if (!check.some(p => p.id === project.workspace_id && p.worker_id === workerId)) throw new Error('Project handoff not visible');
  }
  const report = { workerId, projects, formerWorkerId: legacy, noFilesModified: true, at: new Date().toISOString() };
  fs.writeFileSync('artifacts/agent-workflow-validation/interactive-projects.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });








