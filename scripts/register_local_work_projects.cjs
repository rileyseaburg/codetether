#!/usr/bin/env node
// Expose verified local CLI project directories in the app's project picker.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const workerId = 'wrk_1791203157_35195f4f7b97da0a';
const env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
const token = env.split('\n').find(l => l.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
async function api(route, method = 'GET', body) {
  const r = await fetch('https://api.codetether.run' + route, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}
async function main() {
  if (!env.includes(`CODETETHER_WORKER_ID=${workerId}`)) throw new Error('Expected stable local worker identity missing');
  const projects = [
    { workspace_id: 'local-codetether-agent', name: 'CodeTether Agent', path: '/home/riley/A2A-Server-MCP/codetether-agent' },
    { workspace_id: 'local-a2a-server-mcp', name: 'A2A Server', path: '/home/riley/A2A-Server-MCP' },
  ];
  const registered = await api('/v1/agent/workspaces');
  for (const project of projects) {
    if (!fs.statSync(project.path).isDirectory()) throw new Error('Project path is not a directory');
    const existing = registered.find(p => p.id === project.workspace_id);
    if (existing && (existing.path !== project.path || existing.worker_id !== workerId)) throw new Error('Existing project identity differs');
    if (!existing) await api('/v1/agent/workspaces', 'POST', { ...project, worker_id: workerId,
      description: 'Verified local CLI project for native work sessions' });
  }
  const active = await api(`/v1/agent/tasks?status=running&worker_id=${workerId}`);
  if (!Array.isArray(active) || active.length) throw new Error('Projects registered; worker busy, scope reload deferred');
  const state = spawnSync('systemctl', ['show', 'codetether-ubuntu-dev.service', '-p', 'MainPID', '--value'], { encoding: 'utf8' });
  const pid = Number(state.stdout.trim());
  if (!Number.isSafeInteger(pid) || pid <= 1) throw new Error('No local worker process');
  const args = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
  if (!args.includes('worker') || !args.includes('ubuntu-dev')) throw new Error('Process identity mismatch');
  process.kill(pid, 'SIGTERM');
  const report = { workerId, projects, scopeReloadRequested: true, previousPid: pid,
    credentialsPrinted: false, recordedAt: new Date().toISOString() };
  fs.writeFileSync('artifacts/agent-workflow-validation/local-projects.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });












