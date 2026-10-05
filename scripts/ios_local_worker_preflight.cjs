#!/usr/bin/env node
// Targeted, read-only configuration inspection. Never print token/env contents.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
function selectedArguments(text) {
  const args = text.split(/\s+|\0/).filter(Boolean);
  const allowed = new Set(['--port', '--host', '--bind', '--name', '--worker-id',
    '--worker-name', '--server', '--server-url', '--a2a-server', '--a2a-server-url',
    '--codebase', '--codebases', '--workspace', '--config', '--url', '--hostname']);
  const values = {};
  for (let i = 0; i < args.length; i++) {
    const [flag, inline] = args[i].split('=', 2);
    if (!allowed.has(flag)) continue;
    const value = inline || args[i + 1];
    if (value && !value.startsWith('--')) {
      values[flag] = value.replace(/(https?:\/\/)[^/@\s]+:[^/@\s]+@/g, '$1[redacted]@');
    }
  }
  return { flags: args.filter(x => x.startsWith('--')).map(x => x.split('=')[0]), values };
}
for (const file of ['/etc/systemd/system/codetether-ubuntu-dev.service',
  path.join(process.env.HOME, '.config/systemd/user/codetether-public-tunnel.service')]) {
  try {
    const text = fs.readFileSync(file, 'utf8');
    const exec = text.split('\n').find(line => line.startsWith('ExecStart=')) || '';
    console.log(JSON.stringify({ file, entrypoint: exec.split(/\s+/)[0], ...selectedArguments(exec) }));
    const config = selectedArguments(exec).values['--config'];
    if (config && config.endsWith('.yml')) {
      const yaml = fs.readFileSync(config, 'utf8');
      console.log(JSON.stringify({ ingress: yaml.split('\n')
        .filter(line => /^\s*(-\s*)?(hostname|service):/.test(line))
        .map(line => line.replace(/(https?:\/\/)[^/@\s]+:[^/@\s]+@/g, '$1[redacted]@')) }));
    }
  } catch (error) {
    console.log(JSON.stringify({ file, error: error.code || 'unreadable' }));
  }
}
const servicePid = Number(spawnSync('systemctl', ['show', 'codetether-ubuntu-dev.service', '-p', 'MainPID', '--value'], { encoding: 'utf8' }).stdout.trim());
if (!Number.isSafeInteger(servicePid) || servicePid <= 1) throw new Error('Worker service has no running process');
const args = fs.readFileSync(`/proc/${servicePid}/cmdline`, 'utf8');
console.log(JSON.stringify({ process: servicePid, ...selectedArguments(args) }));
console.log(JSON.stringify({ subcommands: args.split('\0').filter(arg => ['worker', 'serve', 'a2a'].includes(arg)) }));
const env = fs.readFileSync('/etc/codetether-worker/env', 'utf8');
console.log(JSON.stringify({ workerEnvironmentKeys: env.split('\n')
  .map(line => /^([A-Za-z_][A-Za-z0-9_]*)=/.exec(line)?.[1]).filter(Boolean) }));
const environment = Object.fromEntries(env.split('\n').filter(line => /^[A-Z_]+=/.test(line))
  .map(line => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1).replace(/^["']|["']$/g, '')]));
console.log(JSON.stringify({ workerConfiguration: Object.fromEntries(
  ['HOME', 'XDG_CONFIG_HOME', 'VAULT_ADDR', 'CODETETHER_DEFAULT_MODEL'].map(key => [key, environment[key]])),
  sameVaultTokenAsCaller: environment.VAULT_TOKEN === process.env.VAULT_TOKEN }));
if (environment.VAULT_ADDR && environment.VAULT_TOKEN) {
  fetch(`${environment.VAULT_ADDR}/v1/auth/token/lookup-self`, { headers: { 'X-Vault-Token': environment.VAULT_TOKEN }, signal: AbortSignal.timeout(10000) })
    .then(response => console.log(JSON.stringify({ workerVaultLookupStatus: response.status })))
    .catch(() => console.log(JSON.stringify({ workerVaultLookupStatus: 'unreachable' })));
}
async function inspectRegistry() {
  const tunnel = spawnSync('journalctl', ['--user', '-u', 'codetether-public-tunnel.service', '--since', '5 days ago', '-n', '2000', '--no-pager', '-o', 'cat'], { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 });
  let ingress = null;
  if (tunnel.status === 0) {
    for (const match of tunnel.stdout.matchAll(/config=("(?:\\.|[^"\\])*")/g)) {
      try {
        const config = JSON.parse(JSON.parse(match[1]));
        ingress = config.ingress?.map(rule => ({ hostname: rule.hostname, path: rule.path,
          service: String(rule.service || '').replace(/[?#].*$/, '') }));
      } catch { /* Never echo unparsed configuration or log output. */ }
    }
  }
  console.log(JSON.stringify({ tunnelIngress: ingress }));
  const journal = spawnSync('journalctl', ['-u', 'codetether-ubuntu-dev.service', '--since', '1 hour ago', '-n', '300', '--no-pager', '-o', 'cat'], { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
  if (journal.status === 0) {
    const raw = journal.stdout;
    const terms = ['401', '403', '404', 'registered', 'heartbeat', 'connection refused'];
    const counts = Object.fromEntries(terms.map(term => [term, raw.toLowerCase().split(term).length - 1]));
    const ids = [...new Set(raw.match(/\bwrk_[a-zA-Z0-9_]+\b/g) || [])].slice(-5);
    console.log(JSON.stringify({ journalWindow: 'last hour, at most 300 records', counts, workerIds: ids }));
    const errors = raw.split('\n').filter(line => /stream error|failed to fetch|forbidden/i.test(line)).slice(-3);
    console.log(JSON.stringify({ transportErrors: errors.map(line => ({
      codes: [...new Set(line.match(/\b[45][0-9]{2}\b/g) || [])],
      paths: [...line.matchAll(/https?:\/\/[^\s/()]+(\/[^?\s()"]*)/g)].map(match => match[1]),
      invalidToken: /invalid token/i.test(line), missingBearer: /missing bearer/i.test(line),
      streamError: /stream error/i.test(line),
    })) }));
    const receiptPath = path.resolve(__dirname, '../artifacts/ios-login-e2e-20261005/backend-rehearsal/receipt.json');
    const currentTask = fs.existsSync(receiptPath) ? JSON.parse(fs.readFileSync(receiptPath, 'utf8')).taskId : '';
    const selected = raw.split('\n').filter(line => /Resolved server-side workspace IDs|No server-side workspace IDs|Found pending tasks|Task skipped.*scope|403 Forbidden|Vault.*fail|Vault.*error|Registered.*providers/.test(line) || (currentTask && line.includes(currentTask)));
    const secretValues = env.split('\n').filter(line => /^[A-Z_]*(TOKEN|PASSWORD|SECRET)[A-Z_]*=/.test(line))
      .map(line => line.slice(line.indexOf('=') + 1)).filter(value => value.length > 8);
    const diagnostics = [...selected.filter(line => /403 Forbidden/.test(line)).slice(-2), ...selected.slice(-6)];
    console.log(JSON.stringify({ rehearsalDiagnostics: diagnostics.map(line => {
      let safe = line.replace(/\u001b\[[0-9;]*m/g, '');
      for (const value of secretValues) safe = safe.split(value).join('[redacted]');
      return safe.replace(/Bearer\s+\S+/gi, 'Bearer [redacted]').slice(0, 1000);
    }) }));
  } else {
    console.log(JSON.stringify({ journal: 'unavailable' }));
  }
  const line = env.split('\n').find(value => value.startsWith('CODETETHER_TOKEN='));
  if (!line) throw new Error('Service token is not configured');
  let token = line.slice('CODETETHER_TOKEN='.length).replace(/^["']|["']$/g, '');
  if (process.argv.includes('--vault-worker-credential')) {
    const read = spawnSync('vault', ['kv', 'get', '-format=json', 'secret/codetether/a2a-server/auth'], { encoding: 'utf8', timeout: 30000 });
    if (read.status !== 0) throw new Error('Vault read failed; output suppressed');
    const configured = JSON.parse(read.stdout).data.data.A2A_AUTH_TOKENS;
    const entry = configured.split(',').find(value => value.trim().startsWith('worker-jobs:'));
    if (!entry) throw new Error('Dedicated worker-jobs credential unavailable');
    token = entry.slice(entry.indexOf(':') + 1).trim();
    console.log(JSON.stringify({ credentialSource: 'Vault worker-jobs; read-only probe, no persisted changes' }));
  }
  if (process.argv.includes('--cluster-worker-credential')) {
    const read = spawnSync('kubectl', ['get', 'secret', '-n', 'a2a-system', 'a2a-server-auth-tokens', '-o', 'json'], { encoding: 'utf8', timeout: 30000 });
    if (read.status !== 0) throw new Error('Cluster credential read failed; output suppressed');
    const configured = Buffer.from(JSON.parse(read.stdout).data.A2A_AUTH_TOKENS, 'base64').toString();
    const entry = configured.split(',').find(value => value.trim().startsWith('worker-jobs:'));
    if (!entry) throw new Error('Dedicated cluster worker credential unavailable');
    const active = entry.slice(entry.indexOf(':') + 1).trim();
    console.log(JSON.stringify({ matchesPreviousCredential: token === active, credentialSource: 'cluster worker-jobs, read-only' }));
    token = active;
  }
  const origin = process.env.IOS_REGISTRY_ORIGIN || 'https://api.codetether.run';
  if (origin !== 'https://api.codetether.run' && origin !== 'http://127.0.0.1:18889') {
    throw new Error('Unexpected registry origin');
  }
  for (const route of ['workers', 'workspaces']) {
    const response = await fetch(`${origin}/v1/agent/${route}`, {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = String(data.detail || '').toLowerCase();
      const reason = ['not configured', 'authentication required', 'invalid token', 'missing bearer svid', 'missing bearer token'].find(value => detail.includes(value)) || 'unclassified';
      console.log(JSON.stringify({ route, status: response.status, reason }));
      continue;
    }
    const data = await response.json();
    const rows = Array.isArray(data) ? data : (data[route] || []);
    const matches = rows.filter(row => route === 'workspaces'
      ? row.path === '/home/riley/A2A-Server-MCP'
        || String(row.path || '').startsWith('/home/riley/A2A-Server-MCP/artifacts/ios-e2e-web')
      : [row.name, row.worker_name, row.hostname, row.agent_name]
        .some(value => typeof value === 'string' && value.includes('ubuntu-dev')));
    console.log(JSON.stringify({ route, status: response.status, count: rows.length,
      fields: Object.keys(rows[0] || {}), matches: matches.map(row => ({
        id: row.id, worker_id: row.worker_id, name: row.name, worker_name: row.worker_name,
        hostname: row.hostname, path: row.path, status: row.status, codebases: row.codebases,
        workspaces: row.workspaces, global_workspace_id: row.global_workspace_id,
        capabilities: row.capabilities,
      })) }));
  }
}
inspectRegistry().catch(error => {
  console.error(error instanceof Error ? error.message : 'Registry check failed');
  process.exitCode = 1;
});
for (const pid of [742248, 3748592]) {
  try {
    const command = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
    console.log(JSON.stringify({ pid, executable: command[0],
      scriptPaths: command.filter(arg => arg.startsWith('/') && /\.[cm]?js$/.test(arg)) }));
  } catch { console.log(JSON.stringify({ pid, available: false })); }
}