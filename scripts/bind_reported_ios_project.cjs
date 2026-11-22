#!/usr/bin/env node
// Bind only the reported local project to the verified interactive worker.
const fs = require('node:fs');
require('node:dns').setDefaultResultOrder('ipv4first');
async function main() {
  const token = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
    .find(line => line.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
  async function api(route, method = 'GET', body) {
    const r = await fetch('https://api.codetether.run' + route, { method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(20000) });
    if (!r.ok) throw new Error(`API HTTP ${r.status}`);
    return r.json();
  }
  const workerId = 'ubuntu-dev-sessions', workspaceId = '7547cf73', expectedPath = '/home/riley/spotlessbinco';
  const workers = await api('/v1/agent/workers?online_only=true');
  const worker = workers.find(w => w.worker_id === workerId);
  if (!worker?.capabilities?.includes('session-context') || !worker.workspaces?.includes(expectedPath)) {
    throw new Error('Interactive worker does not advertise the reported project');
  }
  const project = await api(`/v1/agent/workspaces/${workspaceId}`);
  if (project.path !== expectedPath || !fs.statSync(expectedPath).isDirectory()) throw new Error('Project path mismatch');
  if (project.worker_id && project.worker_id !== workerId && workers.some(w => w.worker_id === project.worker_id)) {
    throw new Error('Project still belongs to an online worker; no handoff attempted');
  }
  const running = await api(`/v1/agent/tasks?workspace_id=${workspaceId}&status=running`);
  if (!Array.isArray(running) || running.length) throw new Error('Project has active work; no handoff attempted');
  await api('/v1/agent/workspaces', 'POST', {
    workspace_id: workspaceId, name: project.name, path: project.path, worker_id: workerId,
    description: project.description, agent_config: project.agent_config,
    git_url: project.git_url, git_branch: project.git_branch,
  });
  const after = await api(`/v1/agent/workspaces/${workspaceId}`);
  if (after.worker_id !== workerId || after.path !== expectedPath) throw new Error('Handoff not visible');
  const report = { workspaceId, path: expectedPath, previousWorkerId: project.worker_id,
    workerId, noProjectFilesModified: true, at: new Date().toISOString() };
  fs.writeFileSync('artifacts/agent-workflow-validation/app-api-repair/project-binding.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });