#!/usr/bin/env node
// Repair only the existing worker credential wiring. Never print secret values.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
function run(command, args, input) {
  const result = spawnSync(command, args, { input, encoding: 'utf8', timeout: 30000 });
  if (result.status !== 0) {
    const text = String(result.stderr).toLowerCase();
    const category = ['test failed', 'conflict', 'forbidden', 'denied', 'invalid', 'no such file', 'parse', 'timeout']
      .find(value => text.includes(value)) || 'unclassified';
    throw new Error(`${command} ${args.join(' ')} failed (${category}); raw output suppressed`);
  }
  return result.stdout;
}
async function main() {
  const mode = process.argv[2];
  if (!['configure-server', 'refresh-worker', 'refresh-scope', 'refresh-provider', 'refresh-hosting'].includes(mode)) throw new Error('Specify a repair mode');
  const source = JSON.parse(run('kubectl', ['-n', 'a2a-system', 'get', 'secret', 'a2a-server-auth-tokens', '-o', 'json']));
  const configured = Buffer.from(source.data.A2A_AUTH_TOKENS, 'base64').toString();
  const entry = configured.split(',').find(value => value.trim().startsWith('worker-jobs:'));
  if (!entry) throw new Error('Dedicated worker credential missing');
  const token = entry.slice(entry.indexOf(':') + 1).trim();
  if (!token || /[\r\n]/.test(token)) throw new Error('Invalid worker credential format');
  if (mode === 'configure-server') {
    const secretName = 'a2a-server-ios-worker-auth';
    const found = run('kubectl', ['-n', 'a2a-system', 'get', 'secret', secretName, '--ignore-not-found', '-o', 'json']).trim();
    if (found) {
      const existing = JSON.parse(found);
      if (existing.data?.WORKER_AUTH_TOKEN !== Buffer.from(token).toString('base64')) {
        throw new Error('Existing worker secret differs; refusing overwrite');
      }
    } else {
      run('kubectl', ['create', '-f', '-'], JSON.stringify({
        apiVersion: 'v1', kind: 'Secret', type: 'Opaque',
        metadata: { name: secretName, namespace: 'a2a-system',
          labels: { 'app.kubernetes.io/part-of': 'codetether' } },
        data: { WORKER_AUTH_TOKEN: Buffer.from(token).toString('base64') },
      }));
    }
    const app = JSON.parse(run('kubectl', ['-n', 'argocd', 'get', 'application', 'codetether-a2a-server', '-o', 'json']));
    if (app.spec.source.targetRevision !== 'eb2051a212a2c729a7963da8e1dda39a4e958513') {
      throw new Error('Argo revision changed; re-review before editing');
    }
    const parameters = app.spec.source.helm?.parameters || [];
    const existing = parameters.find(p => p.name === 'workerAuth.existingSecret');
    if (existing && existing.value !== secretName) throw new Error('Worker auth override exists; refusing overwrite');
    const patch = [
      { op: 'test', path: '/metadata/resourceVersion', value: app.metadata.resourceVersion },
    ];
    if (!app.spec.source.helm) patch.push({ op: 'add', path: '/spec/source/helm', value: {} });
    if (!app.spec.source.helm?.parameters) {
      patch.push({ op: 'add', path: '/spec/source/helm/parameters', value: [] });
    }
    if (!existing) patch.push({ op: 'add', path: '/spec/source/helm/parameters/-',
      value: { name: 'workerAuth.existingSecret', value: secretName } });
    // This patch contains only a Secret reference and resource version, never credentials.
    run('kubectl', ['-n', 'argocd', 'patch', 'application', 'codetether-a2a-server', '--type=json', '--patch', JSON.stringify(patch)]);
    console.log(JSON.stringify({ mode, application: 'argocd/codetether-a2a-server',
      workerSecret: `a2a-system/${secretName}`, authenticationDisabled: false }));
    return;
  }
  const probe = await fetch('https://api.codetether.run/v1/agent/workers', {
    headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000),
  });
  if (!probe.ok) throw new Error(`API still rejects configured worker credential: HTTP ${probe.status}`);
  const file = '/etc/codetether-worker/env';
  const env = fs.readFileSync(file, 'utf8');
  if ((env.match(/^CODETETHER_TOKEN=/gm) || []).length !== 1) throw new Error('Unexpected worker environment layout');
  const state = run('systemctl', ['show', 'codetether-ubuntu-dev.service', '-p', 'MainPID', '--value']).trim();
  const pid = Number(state);
  if (!Number.isSafeInteger(pid) || pid <= 1) throw new Error('No running worker to refresh');
  const args = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8').split('\0');
  if (!args.includes('worker') || !args.includes('ubuntu-dev')) throw new Error('Worker identity changed');
  let updatedEnv = env.replace(/^CODETETHER_TOKEN=.*$/m, `CODETETHER_TOKEN=${token}`);
  if (['refresh-scope', 'refresh-provider', 'refresh-hosting'].includes(mode)) {
    const receipt = JSON.parse(fs.readFileSync('artifacts/ios-login-e2e-20261005/backend-rehearsal/receipt.json', 'utf8'));
    const workers = await probe.json();
    const rows = Array.isArray(workers) ? workers : workers.workers;
    if (!rows.some(worker => worker.worker_id === receipt.workerId && worker.name === 'ubuntu-dev')) {
      throw new Error('Rehearsal worker identity not found');
    }
    const active = await fetch(`https://api.codetether.run/v1/agent/tasks?status=running&worker_id=${encodeURIComponent(receipt.workerId)}`, {
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20000),
    });
    if (!active.ok) throw new Error('Cannot confirm worker is idle');
    const activeTasks = await active.json();
    if (!Array.isArray(activeTasks) || activeTasks.length) throw new Error('Worker may be busy; refusing restart');
    const stable = env.match(/^CODETETHER_WORKER_ID=(.*)$/m)?.[1];
    if (stable && stable !== receipt.workerId) throw new Error('A different persistent worker identity is configured');
    if (!stable) updatedEnv = updatedEnv.trimEnd() + `\nCODETETHER_WORKER_ID=${receipt.workerId}\n`;
    const oldCaps = updatedEnv.match(/^CODETETHER_WORKER_CAPABILITIES=(.*)$/m)?.[1] || '';
    const caps = [...new Set([...oldCaps.split(/[\s,]+/).filter(Boolean), 'persistent', 'persistent-workspace'])].join(',');
    if (/^CODETETHER_WORKER_CAPABILITIES=/m.test(updatedEnv)) {
      updatedEnv = updatedEnv.replace(/^CODETETHER_WORKER_CAPABILITIES=.*$/m, `CODETETHER_WORKER_CAPABILITIES=${caps}`);
    } else {
      updatedEnv = updatedEnv.trimEnd() + `\nCODETETHER_WORKER_CAPABILITIES=${caps}\n`;
    }
    console.log(JSON.stringify({ scopeReloadWorker: receipt.workerId, runningTasks: activeTasks.length }));
  }
  if (mode === 'refresh-provider') {
    const policyName = 'codetether-ios-worker-models';
    const policy = fs.readFileSync('artifacts/ios-login-e2e-20261005/worker-provider-policy.hcl', 'utf8');
    run('vault', ['policy', 'write', policyName, '-'], policy);
    const issued = JSON.parse(run('vault', ['token', 'create', '-format=json', `-policy=${policyName}`,
      '-ttl=24h', '-explicit-max-ttl=72h', '-orphan', '-display-name=codetether-ios-worker']));
    const providerToken = issued.auth.client_token;
    if (!providerToken || /[\r\n]/.test(providerToken)) throw new Error('Provider token issue failed');
    updatedEnv = updatedEnv.replace(/^VAULT_TOKEN=.*$/m, `VAULT_TOKEN=${providerToken}`);
    console.log(JSON.stringify({ providerPolicy: policyName, ttlSeconds: issued.auth.lease_duration, maxTTL: '72h', administratorTokenCopied: false }));
  }
  if (mode === 'refresh-hosting') {
    const runtime = `/run/user/${process.getuid()}`;
    if (!fs.statSync(`${runtime}/bus`).isSocket()) throw new Error('User bus socket is unavailable');
    for (const [key, value] of Object.entries({ XDG_RUNTIME_DIR: runtime, DBUS_SESSION_BUS_ADDRESS: `unix:path=${runtime}/bus` })) {
      const line = new RegExp(`^${key}=.*$`, 'm');
      updatedEnv = line.test(updatedEnv) ? updatedEnv.replace(line, `${key}=${value}`)
        : updatedEnv.trimEnd() + `\n${key}=${value}\n`;
    }
    console.log(JSON.stringify({ userBusConfigured: true, uid: process.getuid() }));
  }
  fs.writeFileSync(file, updatedEnv, { mode: 0o600 });
  process.kill(pid, 'SIGTERM'); // Restart=always reloads this worker's environment.
  console.log(JSON.stringify({ mode, service: 'codetether-ubuntu-dev.service', oldPid: pid,
    APIProbe: probe.status, credentialPrinted: false }));
}
main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});