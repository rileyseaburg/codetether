#!/usr/bin/env node
// Scoped simulator-only adapter for live agent discovery and two-turn continuity.
const http = require('node:http');
const fs = require('node:fs');
const crypto = require('node:crypto');
require('node:dns').setDefaultResultOrder('ipv4first');
const uiTest = process.env.WORKBENCH_UI_TEST === '1';
const directory = 'artifacts/agent-workflow-validation/workbench-live' + (uiTest ? '-ui' : '');
fs.mkdirSync(directory, { recursive: true });
if (fs.existsSync(`${directory}/proof.json`)) throw new Error('Prior proof exists; preserve it before rerunning');
const line = fs.readFileSync('/etc/codetether-worker/env', 'utf8').split('\n').find(l => l.startsWith('CODETETHER_TOKEN='));
const token = line?.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
if (!token) throw new Error('Service credential missing');
const targets = [
  { workerId: 'ubuntu-dev-sessions', workspaceId: 'ios-e2e-ubuntu-dev', label: 'local' },
  { workerId: 'a2a-server-harvester-0', workspaceId: 'api-harvester-validation', label: 'harvester' },
].filter(target => !uiTest || target.label === 'local').map(target => ({ ...target, marker: crypto.randomBytes(12).toString('hex'), taskIds: [] }));
const secondPrompt = 'What was the exact code I asked you to remember in my previous message? Reply only with that code. Do not use tools or read files.';
for (const target of targets) target.firstPrompt = `Remember this exact code for this conversation: ${target.marker}. Reply READY. Do not use tools or read files.`;
async function api(route, method = 'GET', body) {
  const started = Date.now();
  const response = await fetch(`https://api.codetether.run${route}`, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  fs.appendFileSync(`${directory}/transport.jsonl`, JSON.stringify({ route, method,
    status: response.status, elapsedMs: Date.now() - started, at: new Date().toISOString() }) + '\n');
  if (!response.ok) throw new Error(`API HTTP ${response.status}`);
  return response.json();
}
function save() { fs.writeFileSync(`${directory}/tasks.json`, JSON.stringify(targets, null, 2)); }
function reply(res, status, body) { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); }
http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (req.method === 'GET' && url.pathname === '/test-config') return reply(res, 200, { targets, secondPrompt });
    if (req.method === 'GET' && url.pathname === '/v1/agent/workers') {
      const data = await api(req.url); const rows = Array.isArray(data) ? data : data.workers;
      return reply(res, 200, rows.filter(row => targets.some(t => t.workerId === row.worker_id)));
    }
    if (req.method === 'GET' && url.pathname === '/v1/agent/workspaces') {
      return reply(res, 200, (await api(req.url)).filter(row => targets.some(t => t.workspaceId === row.id)));
    }
    const target = targets.find(t => url.pathname === `/v1/agent/workspaces/${t.workspaceId}/tasks`);
    if (req.method === 'POST' && target) {
      let raw = ''; for await (const chunk of req) { raw += chunk; if (raw.length > 8000) throw new Error('Request too large'); }
      const body = JSON.parse(raw), metadata = body.metadata || {};
      if (metadata.target_worker_id !== target.workerId || body.model !== 'github-copilot/gpt-5-mini') throw new Error('Wrong worker/model');
      if (target.taskIds.length >= 2) throw new Error('Only two test turns are allowed');
      if (target.taskIds.length === 0) {
        if (body.prompt !== target.firstPrompt || !/^ios-[a-z0-9-]+$/.test(metadata.context_id || '')) throw new Error('Invalid first turn');
        target.contextId = metadata.context_id;
      } else {
        if (body.prompt !== secondPrompt || metadata.context_id !== target.contextId
          || metadata.resume_session_id !== target.contextId) throw new Error('Follow-up did not preserve conversation identity');
      }
      const created = await api(url.pathname, 'POST', body);
      if (!created.task?.id) throw new Error('Task ID missing');
      target.taskIds.push(created.task.id); save();
      return reply(res, 200, created);
    }
    const id = /^\/v1\/agent\/tasks\/([^/]+)$/.exec(url.pathname)?.[1];
    if (req.method === 'GET' && id && targets.some(t => t.taskIds.includes(id))) {
      return reply(res, 200, await api(url.pathname));
    }
    if (req.method === 'GET' && url.pathname === '/verify') {
      const proof = [];
      for (const t of targets) {
        if (t.taskIds.length !== 2) throw new Error('Two turns were not submitted');
        const task = await api(`/v1/agent/tasks/${t.taskIds[1]}`);
        if (task.status !== 'completed' || !String(task.result).includes(t.marker)) throw new Error(`${t.label}: context recall failed`);
        const first = await api(`/v1/agent/tasks/${t.taskIds[0]}`);
        const sessionId = task => task.metadata?.worker_session_id || task.session_id || task.metadata?.session_id;
        if (sessionId(first) !== t.contextId || sessionId(task) !== t.contextId) {
          throw new Error(`${t.label}: server did not confirm the same requested session identity`);
        }
        proof.push({ target: t.label, workerId: t.workerId, taskIds: t.taskIds, contextId: t.contextId, marker: t.marker, remembered: true });
      }
      const report = { targets: proof, simulatorOrigin: true, userLoginTested: false, verifiedAt: new Date().toISOString() };
      fs.writeFileSync(`${directory}/proof.json`, JSON.stringify(report, null, 2));
      return reply(res, 200, report);
    }
    return reply(res, 404, { error: 'Route not permitted' });
  } catch (error) {
    fs.appendFileSync(`${directory}/transport.jsonl`, JSON.stringify({ route: req.url, error: String(error.message).split(token).join('[redacted]'), at: new Date().toISOString() }) + '\n');
    reply(res, 502, { error: String(error.message).split(token).join('[redacted]') });
  }
}).listen(19871, '127.0.0.1', () => console.log('Scoped work-session harness on loopback 19871'));










