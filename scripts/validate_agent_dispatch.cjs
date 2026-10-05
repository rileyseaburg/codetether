#!/usr/bin/env node
// Real, targeted execution proof. Never use pod readiness as task-success evidence.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const dir = path.resolve(__dirname, '../artifacts/agent-workflow-validation');
fs.mkdirSync(dir, { recursive: true });
const env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
const line = env.split('\n').find(line => line.startsWith('CODETETHER_TOKEN='));
if (!line) throw new Error('Service credential missing');
const token = line.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
async function api(route, method = 'GET', body) {
  const response = await fetch(`https://api.codetether.run${route}`, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`${method} ${route}: HTTP ${response.status}`);
  return response.json();
}
function exec(program, args) {
  const result = spawnSync(program, args, { encoding: 'utf8', timeout: 30000, maxBuffer: 4 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`${program} failed; raw output suppressed`);
  return result.stdout;
}
async function main() {
  const [mode = 'inspect', target = 'local'] = process.argv.slice(2);
  if (!['local', 'harvester'].includes(target)) throw new Error('Choose local or harvester');
  const raw = await api('/v1/agent/workers');
  const workers = Array.isArray(raw) ? raw : raw.workers;
  const selected = workers.filter(w => target === 'local'
    ? ['wrk_1791203157_35195f4f7b97da0a', 'ubuntu-dev-sessions'].includes(w.worker_id)
    : w.name === 'harvester-a2a-server-harvester-0');
  if (mode === 'inspect') {
    console.log(JSON.stringify({ target, workers: selected.map(w => ({ id: w.worker_id, name: w.name,
      status: w.status, lastSeen: w.last_seen, capabilities: w.capabilities,
      models: (w.models || []).filter(m => (typeof m === 'string' ? m : m.id) === 'github-copilot/gpt-5-mini') })) }, null, 2));
    return;
  }
  const receiptFile = path.join(dir, `${target}-receipt.json`);
  selected.sort((a, b) => Number(b.worker_id === 'a2a-server-harvester-0') - Number(a.worker_id === 'a2a-server-harvester-0'));
  if (mode === 'cancel-pending') {
    const prior = JSON.parse(fs.readFileSync(receiptFile));
    const state = await api(`/v1/agent/tasks/${prior.taskId}`);
    if (state.status !== 'pending') throw new Error('Task is no longer pending; refusing cancellation');
    await api(`/v1/agent/tasks/${prior.taskId}/cancel`, 'POST');
    let cancelled = await api(`/v1/agent/tasks/${prior.taskId}`);
    if (cancelled.status === 'pending') {
      await api(`/v1/agent/tasks/${prior.taskId}/status`, 'PUT', { status: 'cancelled',
        worker_id: 'a2a-server-harvester-0', error: 'Operator cancelled unclaimed validation task addressed to a retired worker identity' });
      cancelled = await api(`/v1/agent/tasks/${prior.taskId}`);
    }
    fs.writeFileSync(path.join(dir, `${target}-cancelled-${prior.taskId}.json`), JSON.stringify({ receipt: prior, status: cancelled.status, reason: 'Stale worker identity during controlled restart' }, null, 2));
    if (cancelled.status !== 'cancelled') throw new Error('Cancellation not confirmed');
    fs.renameSync(receiptFile, path.join(dir, `${target}-receipt-${prior.taskId}.json`));
    console.log(JSON.stringify({ taskId: prior.taskId, status: cancelled.status }));
    return;
  }
  if (mode === 'restart-harvester') {
    if (target !== 'harvester') throw new Error('Only the harvester can be restarted here');
    for (const worker of selected) {
      const running = await api(`/v1/agent/tasks?status=running&worker_id=${encodeURIComponent(worker.worker_id)}`);
      if (!Array.isArray(running) || running.length) throw new Error('Harvester may be busy; refusing restart');
    }
    const sts = JSON.parse(exec('kubectl', ['-n', 'a2a-system', 'get', 'statefulset', 'a2a-server-harvester', '-o', 'json']));
    const env = sts.spec.template.spec.containers.find(c => c.name === 'harvester').env;
    if (!env.some(e => e.name === 'CODETETHER_WORKER_ID')) throw new Error('New stable-identity template is not applied');
    exec('kubectl', ['-n', 'a2a-system', 'delete', 'pod', 'a2a-server-harvester-0', '--wait=false']);
    console.log(JSON.stringify({ target, restarted: true, activeTasks: 0 }));
    return;
  }
  if (mode === 'submit' || mode === 'prepare') {
    if (fs.existsSync(receiptFile)) throw new Error('Receipt exists; poll existing task before retrying');
    const worker = selected.find(w => w.status === 'active');
    if (!worker) throw new Error('Target worker is not active in the registry');
    if (mode === 'submit' && target === 'harvester' && worker.worker_id !== 'a2a-server-harvester-0') throw new Error('Waiting for stable harvester identity to register');
    const workspaceId = target === 'local' ? 'ios-e2e-ubuntu-dev' : 'api-harvester-validation';
    const workspacePath = target === 'local'
      ? '/home/riley/A2A-Server-MCP/artifacts/ios-e2e-web'
      : '/var/lib/codetether/repos/api-validation';
    if (target === 'harvester') {
      exec('kubectl', ['-n', 'a2a-system', 'exec', 'a2a-server-harvester-0', '-c', 'harvester', '--', 'mkdir', '-p', workspacePath]);
      await api('/v1/agent/workspaces', 'POST', { workspace_id: workspaceId, name: 'Harvester API Validation',
        path: workspacePath, worker_id: worker.worker_id, description: 'Isolated API-dispatch validation workspace' });
    }
    if (mode === 'prepare') {
      console.log(JSON.stringify({ target, workspaceId, workspacePath, workerId: worker.worker_id, taskSubmitted: false }));
      return;
    }
    const marker = `api-${target}-${crypto.randomBytes(8).toString('hex')}`;
    const file = `${workspacePath}/${marker}.txt`;
    const prompt = `This is a real API routing validation, not a request to modify any project.
Work only in ${workspacePath}. Write EXACTLY ${marker} followed by a newline to ${file}.
Run hostname and sha256sum on that file, then respond with the exact marker, absolute path, SHA-256 and hostname you observed.
Do not read credentials, histories, other projects, or secrets. Do not spawn agents or change any other files.
Remember this marker in this conversation for a subsequent follow-up.`;
    const model = process.argv[4] || 'github-copilot/gpt-5-mini';
    const created = await api(`/v1/agent/workspaces/${workspaceId}/tasks`, 'POST', {
      title: `API validation: ${target}`, prompt, agent_type: 'build', priority: 2, model,
      metadata: { target_worker_id: worker.worker_id, target_agent_name: worker.name, source: 'api-routing-validation' },
    });
    if (!created.task?.id) throw new Error('No actual task ID returned');
    const receipt = { target, taskId: created.task.id, workerId: worker.worker_id, workerName: worker.name,
      workspaceId, workspacePath, file, marker, model, submittedAt: new Date().toISOString() };
    fs.writeFileSync(receiptFile, JSON.stringify(receipt, null, 2) + '\n');
  }
  const receipt = JSON.parse(fs.readFileSync(receiptFile));
  const task = await api(`/v1/agent/tasks/${receipt.taskId}`);
  const safe = value => typeof value === 'string' ? value.split(token).join('[redacted]') : value;
  const state = { taskId: task.id, status: task.status, sessionId: task.session_id,
    result: safe(task.result), error: safe(task.error), targetWorker: task.metadata?.target_worker_id,
    model: task.model, capturedAt: new Date().toISOString() };
  fs.writeFileSync(path.join(dir, `${target}-task.json`), JSON.stringify(state, null, 2) + '\n');
  console.log(JSON.stringify({ target, taskId: task.id, status: task.status, sessionId: task.session_id, error: state.error }));
  if (mode !== 'verify') return;
  if (task.status !== 'completed') throw new Error('Task has not completed');
  const content = target === 'local' ? fs.readFileSync(receipt.file)
    : Buffer.from(exec('kubectl', ['-n', 'a2a-system', 'exec', 'a2a-server-harvester-0', '-c', 'harvester', '--', 'cat', receipt.file]));
  if (content.toString() !== receipt.marker + '\n') throw new Error('Actual artifact differs from requested marker');
  const sha256 = crypto.createHash('sha256').update(content).digest('hex');
  const result = String(task.result || '');
  if (![receipt.marker, receipt.file, sha256].every(value => result.includes(value))) throw new Error('Returned result does not match execution artifact');
  const proof = { ...receipt, sha256, sessionId: task.session_id, status: task.status,
    verifiedAt: new Date().toISOString(), realExecution: true };
  fs.writeFileSync(path.join(dir, `${target}-proof.json`), JSON.stringify(proof, null, 2) + '\n');
  console.log(JSON.stringify(proof, null, 2));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });







