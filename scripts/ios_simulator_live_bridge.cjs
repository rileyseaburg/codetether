#!/usr/bin/env node
// Temporary loopback test harness. No user login bypass and no credentials in iOS.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
require('node:dns').setDefaultResultOrder('ipv4first');
const root = path.resolve(__dirname, '..');
const dir = path.join(root, 'artifacts/ios-simulator-delivery');
fs.mkdirSync(dir, { recursive: true });
const configFile = path.join(dir, 'config.json');
const receiptFile = path.join(dir, 'simulator-task.json');
const proofFile = path.join(dir, 'live-proof.json');
const marker = `ios-simulator-${Date.now()}`;
const workerId = 'wrk_1791203157_35195f4f7b97da0a';
const workspaceId = 'ios-e2e-ubuntu-dev';
const site = path.join(root, 'artifacts/ios-e2e-web/simulator-live/site/index.html');
const url = 'http://192.168.50.101:8769/';
const unit = 'codetether-ios-simulator-live.service';
if (fs.existsSync(receiptFile)) throw new Error('Existing simulator receipt: preserve and review it before another run');
const env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
const raw = env.split('\n').find(line => line.startsWith('CODETETHER_TOKEN='));
if (!raw) throw new Error('Existing worker credential unavailable');
const token = raw.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
const config = { marker, workerId, workspaceId, url, site, unit,
  title: '[SIMULATOR LIVE] A2A Monitor task proof', model: 'github-copilot/gpt-5-mini',
  prompt: `A real iOS Simulator integration test submitted this task. It did NOT test user login or a physical phone.
Your workspace is ${path.dirname(path.dirname(path.dirname(site)))}. Use correct absolute paths.
Create ${site} with title A2A Simulator Live Proof, marker ${marker}, UTC creation time, and a visible statement that this is simulator-originated, not physical-phone proof.
Create the sibling ../server.js using Node HTTP, serving only / and /index.html as text/html, other routes 404, on 192.168.50.101:8769.
Start it as user unit ${unit} using systemd-run --user --collect and an ABSOLUTE /usr/bin/node script path.
Use XDG_RUNTIME_DIR=/run/user/1000 and DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus explicitly.
Do not modify the earlier backend-rehearsal directory, port8768, or any unrelated service/file. Do not read credentials or histories; do not spawn subagents.
If a rehearsal-owned process is blocking8769, verify its exact script identity before replacing it. Do not report success until systemctl shows active with a positive MainPID and HTTP GET ${url} returns200 and the marker.
Reply with exact HTML path, URL, SHA-256, unit name, MainPID, and observed HTTP status. Preserve prior evidence.` };
fs.writeFileSync(configFile, JSON.stringify(config, null, 2) + '\n');
let taskId;
async function upstream(route, method, body) {
  const response = await fetch(`https://api.codetether.run${route}`, { method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Upstream HTTP ${response.status}`);
  return response.json();
}
function reply(res, status, value) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(value));
}
const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/test-config') return reply(res, 200, config);
    if (req.method === 'POST' && req.url === `/v1/agent/workspaces/${workspaceId}/tasks`) {
      if (taskId) return reply(res, 409, { error: 'Task already submitted' });
      let data = '';
      for await (const chunk of req) { data += chunk; if (data.length > 16000) throw new Error('Request too large'); }
      const body = JSON.parse(data);
      if (body.prompt !== config.prompt || body.title !== config.title || body.model !== config.model
        || body.metadata?.target_worker_id !== workerId || body.agent_type !== 'build') {
        return reply(res, 403, { error: 'Request differs from the scoped test configuration' });
      }
      const created = await upstream(req.url, 'POST', body);
      if (!created.task?.id) throw new Error('Missing real task ID');
      taskId = created.task.id;
      fs.writeFileSync(receiptFile, JSON.stringify({ taskId, simulatorOrigin: true,
        userLoginTested: false, physicalPhone: false, marker, submittedAt: new Date().toISOString() }, null, 2));
      return reply(res, 200, created);
    }
    if (taskId && req.method === 'GET' && req.url === `/v1/agent/tasks/${taskId}`) {
      return reply(res, 200, await upstream(req.url, 'GET'));
    }
    if (taskId && req.method === 'GET' && req.url === '/verify') {
      const task = await upstream(`/v1/agent/tasks/${taskId}`, 'GET');
      if (task.status !== 'completed') throw new Error('Task not completed');
      const file = fs.readFileSync(site);
      const page = await fetch(url, { signal: AbortSignal.timeout(10000) });
      const bytes = Buffer.from(await page.arrayBuffer());
      const hash = crypto.createHash('sha256').update(file).digest('hex');
      if (page.status !== 200 || !bytes.equals(file) || !bytes.toString().includes(marker)) throw new Error('Page verification failed');
      const result = String(task.result || '');
      if (![site, url, hash, unit].every(value => result.includes(value))) throw new Error('Returned result does not match artifact');
      const status = spawnSync('systemctl', ['--user', 'show', unit, '-p', 'ActiveState', '-p', 'MainPID'], { encoding: 'utf8' });
      const pid = Number(/MainPID=(\d+)/.exec(status.stdout)?.[1]);
      if (!status.stdout.includes('ActiveState=active') || !pid) throw new Error('Hosting unit is not active');
      const args = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
      if (!args.some(arg => arg.startsWith(path.dirname(path.dirname(site)) + '/'))) throw new Error('Hosting process path mismatch');
      const proof = { taskId, marker, simulatorOrigin: true, physicalPhone: false, userLoginTested: false,
        url, file: site, sha256: hash, httpStatus: page.status, unit, pid, verifiedAt: new Date().toISOString() };
      fs.writeFileSync(proofFile, JSON.stringify(proof, null, 2) + '\n');
      return reply(res, 200, proof);
    }
    reply(res, 404, { error: 'Route not allowed' });
  } catch (error) {
    reply(res, 502, { error: String(error.message).split(token).join('[redacted]') });
  }
});
server.listen(18771, '127.0.0.1', () => console.log('Scoped live-test harness listening on loopback 18771'));
process.on('SIGTERM', () => server.close());









