#!/usr/bin/env node
// Current validation-task lifecycle only; never read saved session/memory files.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const targets = JSON.parse(fs.readFileSync('artifacts/agent-workflow-validation/workbench-live-ui/tasks.json'));
const ids = targets.flatMap(t => t.taskIds);
const logs = spawnSync('journalctl', ['--user', '-u', 'codetether-work-session-worker.service', '--since', '2 hours ago', '-n', '5000', '-o', 'cat', '--no-pager'],
  { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, timeout: 30000 });
if (logs.status !== 0) throw new Error('Cannot read worker lifecycle diagnostics');
const events = [];
for (const raw of logs.stdout.split('\n')) {
  const line = raw.replace(/\u001b\[[0-9;]*m/g, '');
  const taskId = ids.find(id => line.includes(id));
  if (!taskId || !line.includes('checkpoint=')) continue;
  const checkpoint = /checkpoint="([a-z_]+)"/.exec(line)?.[1];
  const sessionId = /session_id=([a-zA-Z0-9_-]+)/.exec(line)?.[1];
  const elapsedMs = /elapsed_ms=(\d+)/.exec(line)?.[1];
  const workspace = checkpoint === 'workspace_ready' ? /detail="([^"]+)"/.exec(line)?.[1] : undefined;
  if (checkpoint) events.push({ taskId, checkpoint, sessionId, workspace, elapsedMs: Number(elapsedMs) });
}
const record = { expected: targets.map(t => ({ contextId: t.contextId, taskIds: t.taskIds })), events };
fs.writeFileSync('artifacts/agent-workflow-validation/workbench-live-ui/lifecycle.json', JSON.stringify(record, null, 2));
console.log(JSON.stringify(record, null, 2));


