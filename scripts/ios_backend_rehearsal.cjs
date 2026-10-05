#!/usr/bin/env node
// A real service-originated rehearsal, NEVER a claim of iPhone-originated work.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const evidence = path.resolve(__dirname, '../artifacts/ios-login-e2e-20261005/backend-rehearsal');
const output = path.resolve(__dirname, '../artifacts/ios-e2e-web/backend-rehearsal');
const receiptFile = path.join(evidence, 'receipt.json');
const marker = 'ios-backend-rehearsal-20261005';
const url = 'http://192.168.50.101:8768/';
const workerId = 'wrk_1791203157_35195f4f7b97da0a';
async function main() {
  const mode = process.argv[2] || 'poll';
  if (!['submit', 'poll', 'verify', 'diagnose', 'retry', 'correct'].includes(mode)) throw new Error('Use submit, poll, verify, diagnose, retry, or correct');
  fs.mkdirSync(evidence, { recursive: true });
  const line = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n')
    .find(line => line.startsWith('CODETETHER_TOKEN='));
  if (!line) throw new Error('Service credential unavailable');
  const token = line.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
  async function request(route, method = 'GET', body) {
    const response = await fetch(`https://api.codetether.run${route}`, {
      method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) throw new Error(`Task API HTTP ${response.status}`);
    return response.json();
  }
  let retryOf;
  const requestedModel = ['retry', 'correct'].includes(mode) ? process.argv[3] : undefined;
  if (['retry', 'correct'].includes(mode)) {
    if (!requestedModel) throw new Error('Specify an explicitly discovered retry model');
    const old = JSON.parse(fs.readFileSync(receiptFile, 'utf8'));
    const failed = await request(`/v1/agent/tasks/${old.taskId}`);
    if (failed.status !== (mode === 'correct' ? 'completed' : 'failed')) throw new Error('Unexpected prior task state');
    retryOf = old.taskId;
    fs.copyFileSync(receiptFile, path.join(evidence, `receipt-${old.taskId}.json`));
    fs.copyFileSync(path.join(evidence, 'latest-task.json'), path.join(evidence, `${mode === 'correct' ? 'unverified' : 'failed'}-${old.taskId}.json`));
  }
  if ((mode === 'submit' && !fs.existsSync(receiptFile)) || ['retry', 'correct'].includes(mode)) {
    const prompt = `This is a BACKEND-ONLY REHEARSAL, not a phone-submitted task.
Work only in ${output}; create that directory as needed. Do not alter other files.
Your workspace CWD is ${path.dirname(output)}. Use relative paths backend-rehearsal/..., NOT artifacts/ios-e2e-web/backend-rehearsal/... again.
${mode === 'correct' ? `This is a corrective follow-up to ${retryOf}: earlier files were placed under ${path.dirname(output)}/artifacts/ios-e2e-web/backend-rehearsal. Copy them into the exact requested directory; preserve the old files as evidence. You may stop and replace ONLY the existing codetether-ios-backend-rehearsal.service to run the corrected absolute server.js path.` : ''}
${mode === 'correct' ? `If port 8768 is held by an orphan Node process from THIS rehearsal, verify its /proc/PID/cmdline equals /usr/bin/node ${output}/server.js. You are authorized to terminate ONLY that matching rehearsal-owned PID, without stopping the worker service. For the latest observed run that PID was 886898; verify the current identity first. A transient unit started while the orphan holds the port exits immediately with EADDRINUSE, so release this rehearsal's port before starting its unit. Do not rewrite the already-correct files unnecessarily.` : ''}
After starting the unit, require systemctl --user show codetether-ios-backend-rehearsal.service
to report ActiveState=active and MainPID matching the listening process. Merely invoking
systemd-run is NOT evidence that the unit stays running. Fix failures before reporting success.
Create site/index.html titled "A2A backend rehearsal", visibly containing marker ${marker},
the current UTC time, and an explicit statement that this was NOT submitted from an iPhone.
Create a small Node HTTP server serving ONLY that index page on / and /index.html,
with text/html content type, and rejecting other paths with 404. Bind 192.168.50.101:8768.
Start it as user service codetether-ios-backend-rehearsal with systemd-run --user.
If necessary, set XDG_RUNTIME_DIR=/run/user/$(id -u) for the user bus.
The user bus exists at /run/user/1000/bus. Explicitly run service commands with
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus.
Use /usr/bin/node with the absolute ${output}/server.js path and systemd-run --user --collect.
Do not conclude success or stop at a partial result until the exact HTTP URL is serving the file.
Do not stop unrelated services; if the port or service already exists, inspect its identity first.
Verify GET ${url} returns HTTP 200 and the marker. Compute SHA-256 of the HTML file.
Reply with the absolute HTML path, URL, HTTP status, SHA-256, and service/process identity.
Do not read credentials, environment secret files, memory, histories, or other projects.
Do not spawn subagents. Do not claim an authenticated phone interaction occurred.`;
    const response = await request('/v1/agent/workspaces/ios-e2e-ubuntu-dev/tasks', 'POST', {
      title: '[BACKEND ONLY] iOS HTML hosting rehearsal', prompt, agent_type: 'build', priority: 2,
      ...(requestedModel ? { model: requestedModel } : {}),
      metadata: { target_worker_id: workerId, source: 'ios-backend-rehearsal', phone_origin: false },
    });
    if (!response.task?.id) throw new Error('Submission response had no task ID');
    fs.writeFileSync(receiptFile, JSON.stringify({ taskId: response.task.id, workerId,
      workspaceId: 'ios-e2e-ubuntu-dev', submittedAt: new Date().toISOString(),
      phoneOrigin: false, output, url, marker, requestedModel, retryOf }, null, 2) + '\n');
  }
  if (!fs.existsSync(receiptFile)) throw new Error('No rehearsal receipt; submit first');
  const receipt = JSON.parse(fs.readFileSync(receiptFile, 'utf8'));
  if (mode === 'diagnose') {
    const list = spawnSync('kubectl', ['-n', 'a2a-system', 'get', 'pods', '-o', 'json'], { encoding: 'utf8' });
    if (list.status !== 0) throw new Error('Pod listing failed');
    const pods = JSON.parse(list.stdout).items.filter(pod => pod.metadata.name.startsWith('a2a-server-deployment-green-'));
    for (const pod of pods) {
      const logs = spawnSync('kubectl', ['-n', 'a2a-system', 'logs', pod.metadata.name, '--since=10m', '--tail=3000'],
        { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
      if (logs.status !== 0) continue;
      const lines = logs.stdout.split('\n').filter(line => line.includes(receipt.taskId))
        .map(line => line.split(token).join('[redacted]').replace(/Bearer\s+\S+/gi, 'Bearer [redacted]').slice(0, 1000)).slice(-12);
      console.log(JSON.stringify({ pod: pod.metadata.name, taskId: receipt.taskId, lines }));
    }
    return;
  }
  const task = await request(`/v1/agent/tasks/${encodeURIComponent(receipt.taskId)}`);
  const safe = value => typeof value === 'string' ? value.split(token).join('[redacted]') : value;
  const state = { taskId: task.id, status: task.status, result: safe(task.result), error: safe(task.error),
    phoneOrigin: false, observedAt: new Date().toISOString(),
    workspaceId: task.workspace_id || task.codebase_id,
    assignedWorker: task.assigned_worker_id || task.worker_id,
    targetWorker: task.metadata?.target_worker_id, model: task.model,
    modelRef: task.metadata?.model_ref, targetAgent: task.metadata?.target_agent_name };
  fs.writeFileSync(path.join(evidence, 'latest-task.json'), JSON.stringify(state, null, 2) + '\n');
  console.log(JSON.stringify({ taskId: task.id, status: task.status, phoneOrigin: false }));
  if (task.status === 'pending') {
    const pending = await request(`/v1/agent/tasks?status=pending&worker_id=${workerId}`);
    const rows = Array.isArray(pending) ? pending : pending.tasks || [];
    const match = rows.find(item => item.id === task.id);
    console.log(JSON.stringify({ visibleInWorkerQueue: Boolean(match),
      workspaceId: match?.workspace_id, codebaseId: match?.codebase_id,
      targetWorker: match?.metadata?.target_worker_id,
      model: match?.model, modelRef: match?.metadata?.model_ref,
    }));
  }
  if (mode !== 'verify') return;
  if (task.status !== 'completed') throw new Error('Rehearsal task is not completed');
  const file = path.join(output, 'site/index.html');
  const html = fs.readFileSync(file);
  const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  const served = Buffer.from(await response.arrayBuffer());
  if (response.status !== 200 || !served.equals(html) || !served.toString().includes(marker)) {
    throw new Error('Hosted page did not match local artifact');
  }
  const indexResponse = await fetch(new URL('/index.html', url), { signal: AbortSignal.timeout(10000) });
  const rejected = await fetch(new URL('/__out_of_scope__', url), { signal: AbortSignal.timeout(10000) });
  const indexBytes = Buffer.from(await indexResponse.arrayBuffer());
  if (indexResponse.status !== 200 || !indexBytes.equals(html) || rejected.status !== 404) {
    throw new Error('Static server route restrictions failed');
  }
  if (!String(response.headers.get('content-type')).startsWith('text/html')) {
    throw new Error('Static server did not return HTML content type');
  }
  const sha256 = crypto.createHash('sha256').update(html).digest('hex');
  const resultText = String(task.result || '');
  if (!resultText.includes(url.replace(/\/$/, '')) || !resultText.includes(file) || !resultText.includes(sha256)) {
    throw new Error('Agent response did not correlate URL, file, and SHA-256');
  }
  const unit = 'codetether-ios-backend-rehearsal.service';
  const service = spawnSync('systemctl', ['--user', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'WorkingDirectory'], { encoding: 'utf8' });
  if (service.status !== 0) throw new Error('Hosting service inspection failed');
  const properties = Object.fromEntries(service.stdout.trim().split('\n').map(line => {
    const separator = line.indexOf('='); return [line.slice(0, separator), line.slice(separator + 1)];
  }));
  const pid = Number(properties.MainPID);
  if (properties.ActiveState !== 'active' || !Number.isSafeInteger(pid) || pid <= 1) {
    throw new Error('Hosting service is not active');
  }
  const args = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
  if (!args.some(arg => arg.startsWith(output + '/'))) throw new Error('Hosting process is outside rehearsal directory');
  if (!resultText.includes(unit) || !resultText.includes(String(pid))) {
    throw new Error('Agent response did not identify the active hosting process');
  }
  const proof = { taskId: task.id, phoneOrigin: false, file, url, status: response.status,
    sha256, service: { unit, pid, state: properties.ActiveState }, responseMatchesArtifact: true,
    indexStatus: indexResponse.status, otherPathStatus: rejected.status,
    contentType: response.headers.get('content-type'), verifiedAt: new Date().toISOString() };
  fs.writeFileSync(path.join(evidence, 'http-proof.json'), JSON.stringify(proof, null, 2) + '\n');
  console.log(JSON.stringify(proof));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });