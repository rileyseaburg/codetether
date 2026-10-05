#!/usr/bin/env node
// A user-owned, version-pinned interactive worker. Leaves the legacy system worker untouched.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
function run(command, args) {
  const r = spawnSync(command, args, { encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error(`${command} failed; raw output suppressed`);
  return r.stdout.trim();
}
const home = process.env.HOME;
const source = path.join(home, '.cargo/bin/codetether');
const version = run(source, ['--version']);
if (version !== 'codetether 4.7.6-dev.24') throw new Error('Unexpected candidate version');
const binary = path.join(home, '.local/lib/codetether/session-worker-4.7.6-dev.24');
fs.mkdirSync(path.dirname(binary), { recursive: true });
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
if (fs.existsSync(binary) && hash(binary) !== hash(source)) throw new Error('Pinned binary collision');
if (!fs.existsSync(binary)) fs.copyFileSync(source, binary);
fs.chmodSync(binary, 0o755);
const state = path.join(home, '.local/share/codetether-session-worker');
fs.mkdirSync(state, { recursive: true });
let env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
for (const [key, value] of Object.entries({ CODETETHER_WORKER_ID: 'ubuntu-dev-sessions',
  CODETETHER_WORKER_CAPABILITIES: 'persistent,persistent-workspace,session-context',
  CODETETHER_WORKER_TARGETED_ONLY: '1', CODETETHER_AGENT_HOME: state, CODETETHER_HOME: state,
  XDG_DATA_HOME: path.join(state, 'data'), XDG_CACHE_HOME: path.join(state, 'cache'),
  CODETETHER_DEFAULT_MODEL: 'github-copilot/gpt-5-mini' })) {
  const regex = new RegExp(`^${key}=.*$`, 'm');
  env = regex.test(env) ? env.replace(regex, `${key}=${value}`) : env.trimEnd() + `\n${key}=${value}\n`;
}
const config = path.join(home, '.config/codetether/session-worker.env');
fs.mkdirSync(path.dirname(config), { recursive: true });
fs.writeFileSync(config, env, { mode: 0o600 });
fs.chmodSync(config, 0o600);
const unit = path.join(home, '.config/systemd/user/codetether-work-session-worker.service');
const content = `[Unit]\nDescription=CodeTether interactive work-session worker\nAfter=network-online.target\n[Service]\nEnvironmentFile=${config}\nWorkingDirectory=/home/riley/A2A-Server-MCP\nExecStart=${binary} worker --server https://api.codetether.run --name ubuntu-dev-sessions --workspaces /home/riley/A2A-Server-MCP --port 18880 --max-concurrent-tasks 2 --auto-approve all\nRestart=on-failure\nRestartSec=5\n[Install]\nWantedBy=default.target\n`;
if (fs.existsSync(unit) && !fs.readFileSync(unit, 'utf8').includes('CodeTether interactive work-session worker')) throw new Error('Service name collision');
fs.writeFileSync(unit, content);
run('systemctl', ['--user', 'daemon-reload']);
run('systemctl', ['--user', 'enable', '--now', 'codetether-work-session-worker.service']);
const proof = { version, sha256: hash(binary), binary, workerId: 'ubuntu-dev-sessions',
  unit: 'codetether-work-session-worker.service', stateDirectory: state, credentialsPrinted: false };
fs.writeFileSync('artifacts/agent-workflow-validation/session-worker-install.json', JSON.stringify(proof, null, 2));
console.log(JSON.stringify(proof));








