#!/usr/bin/env node
// Inspect routing fields and lifecycle metadata for the specific reported failed call.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
async function main() {
  const id = '3541aeb2-304e-4010-9685-f920c39a515e';
  const token = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
    .find(line => line.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
  const r = await fetch(`https://api.codetether.run/v1/agent/tasks/${id}`, {
    headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000) });
  if (!r.ok) throw new Error(`Task lookup HTTP ${r.status}`);
  const task = await r.json();
  const selected = {};
  function visit(value, path = '') {
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      const name = path ? path + '.' + key : key;
      if (/model|provider|target_worker|target_agent|personality/.test(key) && (typeof child === 'string' || child === null)) selected[name] = child;
      else if (key === 'metadata' || key === 'routing') visit(child, name);
    }
  }
  visit(task);
  const journal = spawnSync('journalctl', ['--user', '-u', 'codetether-work-session-worker',
    '--since', '2026-10-07 10:20:00 UTC', '--until', '2026-10-07 10:25:00 UTC', '-o', 'cat', '--no-pager'],
    { encoding: 'utf8', timeout: 15000, maxBuffer: 4000000 });
  const checkpoints = (journal.stdout || '').replace(/\u001b\[[0-9;]*m/g, '').split('\n')
    .filter(line => line.includes(id) && /checkpoint="(?:claimed|model_selected|session_ready|workspace_ready)"/.test(line))
    .map(line => ({ checkpoint: /checkpoint="([^"]+)"/.exec(line)?.[1], detail: /detail="([^"]+)"/.exec(line)?.[1] }));
  const report = { taskId: id, requestedAndStoredRouting: selected, checkpoints, journalExit: journal.status };
  fs.writeFileSync('artifacts/agent-workflow-validation/app-api-repair/reported-task-routing.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });