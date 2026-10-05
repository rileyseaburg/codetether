#!/usr/bin/env node
// Sanitized API readiness/OOM diagnostics: no raw logs, query strings, or env values.
const fs = require('node:fs');
const { spawnSync } = require('node:child_process');
function command(args) {
  return spawnSync('kubectl', args, { encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 });
}
const pods = command(['-n', 'a2a-system', 'get', 'pods', '-o', 'json']);
if (pods.status !== 0) throw new Error('Pod query failed; output suppressed');
const selected = JSON.parse(pods.stdout).items.filter(p => p.metadata.name.startsWith('a2a-server-deployment-green-'));
const report = { capturedAt: new Date().toISOString(), pods: [] };
for (const pod of selected) {
  const item = { name: pod.metadata.name, node: pod.spec.nodeName,
    containers: pod.status.containerStatuses.map(c => ({ name: c.name, ready: c.ready,
      restarts: c.restartCount, previousReason: c.lastState?.terminated?.reason,
      previousExit: c.lastState?.terminated?.exitCode, startedAt: c.state?.running?.startedAt })),
    logs: [] };
  for (const previous of [true, false]) {
    const args = ['-n', 'a2a-system', 'logs', pod.metadata.name, '--tail=300', '--timestamps'];
    if (previous) args.push('--previous');
    const logs = command(args);
    if (logs.status !== 0) { item.logs.push({ previous, available: false }); continue; }
    const requests = [];
    const errors = [];
    const authErrors = [];
    for (const line of logs.stdout.split('\n')) {
      const request = /"(GET|POST|PUT|PATCH|DELETE) ([^ ?"]+)(?:\?[^ "]*)? HTTP\/[^\"]+" (\d{3})/.exec(line);
      if (request) requests.push({ method: request[1], path: request[2], status: Number(request[3]) });
      const type = /\b([a-zA-Z_.]+(?:Error|Exception))\b/.exec(line)?.[1];
      if (type) errors.push(type);
      if (/Token validation failed|Token rejected|Login error|Refresh error/.test(line)) {
        const category = ['Invalid issuer', 'Signature has expired', 'audience', 'key not found',
          'Unable to find an algorithm', 'not JSON serializable', 'connection'].find(value => line.toLowerCase().includes(value.toLowerCase())) || 'unclassified';
        authErrors.push({ category, timestamp: line.split(' ')[0] });
      }
    }
    item.logs.push({ previous, available: true, requests: requests.slice(-35), authRequests: requests.filter(r => r.path.startsWith('/v1/auth/')),
      authErrors, errorTypes: [...new Set(errors)] });
  }
  report.pods.push(item);
}
const directory = 'artifacts/ios-login-followup-20261005';
fs.mkdirSync(directory, { recursive: true });
const file = `${directory}/api-health-${Date.now()}.json`;
fs.writeFileSync(file, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ artifact: file, ...report }, null, 2));









