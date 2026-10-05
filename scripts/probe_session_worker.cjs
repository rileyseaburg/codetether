#!/usr/bin/env node
// Real API protocol probe, NOT simulator or user-login proof. Tests isolation and continuity.
const fs = require('node:fs');
const crypto = require('node:crypto');
require('node:dns').setDefaultResultOrder('ipv4first');
const target = process.argv[2] || 'local';
if (!['local', 'harvester'].includes(target)) throw new Error('Expected local or harvester');
const workerId = target === 'local' ? 'ubuntu-dev-sessions' : 'a2a-server-harvester-0';
const workerName = target === 'local' ? workerId : 'harvester-a2a-server-harvester-0';
const workspaceId = target === 'local' ? 'ios-e2e-ubuntu-dev' : 'api-harvester-validation';
const token = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
  .find(l => l.startsWith('CODETETHER_TOKEN=')).slice(17).replace(/^["']|["']$/g, '');
const directory = `artifacts/agent-workflow-validation/protocol-${target}-${Date.now()}`;
fs.mkdirSync(directory, { recursive: true });
const evidence = { origin: 'api-smoke', workerId, targets: [], completed: false };
function save() { fs.writeFileSync(`${directory}/proof.json`, JSON.stringify(evidence, null, 2)); }
async function api(route, method = 'GET', body) {
  const response = await fetch('https://api.codetether.run' + route, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`API HTTP ${response.status}`);
  return response.json();
}
const sessionId = task => task.metadata?.worker_session_id || task.session_id || task.metadata?.session_id;
async function turn(context, prompt, resume) {
  const created = await api(`/v1/agent/workspaces/${workspaceId}/tasks`, 'POST', {
    title: 'Work-session protocol validation', prompt, agent_type: 'build', priority: 2,
    model: 'github-copilot/gpt-5-mini', metadata: { target_worker_id: workerId, target_agent_name: workerName,
      context_id: context.id, ...(resume ? { resume_session_id: context.id } : {}), source: 'work-session-protocol-test' },
  });
  if (!created.task?.id) throw new Error('Task ID missing');
  context.tasks.push({ id: created.task.id, stage: resume ? 'recall' : 'remember' }); save();
  const deadline = Date.now() + 240000;
  while (Date.now() < deadline) {
    const task = await api(`/v1/agent/tasks/${created.task.id}`);
    if (['completed', 'failed', 'cancelled'].includes(task.status)) {
      Object.assign(context.tasks.at(-1), { status: task.status, sessionId: sessionId(task),
        result: String(task.result || '').split(token).join('[redacted]'), error: task.error }); save();
      if (task.status !== 'completed') throw new Error(`Worker task ${task.status}`);
      if (sessionId(task) !== context.id) throw new Error('Worker did not report the requested conversation ID');
      return String(task.result || '');
    }
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  throw new Error('Worker timeout');
}
async function main() {
  for (let i = 0; i < 2; i++) {
    const context = { id: `ios-${crypto.randomUUID()}`, marker: crypto.randomBytes(12).toString('hex'), tasks: [] };
    evidence.targets.push(context); save();
    await turn(context, `Remember this exact code for this conversation: ${context.marker}. Reply READY. Do not use tools or read files.`, false);
  }
  for (const context of evidence.targets) {
    const answer = await turn(context, 'What was the exact code I asked you to remember in my previous message? Reply only with that code. Do not use tools or read files.', true);
    if (!answer.includes(context.marker)) throw new Error('Conversation recalled another session or lost context');
  }
  evidence.completed = true; evidence.verifiedAt = new Date().toISOString(); save();
  console.log(JSON.stringify({ target, workerId, artifact: `${directory}/proof.json`, completed: true }));
}
main().catch(error => { evidence.failure = error.message; save(); console.error(error.message, directory); process.exitCode = 1; });
















