#!/usr/bin/env node
// Read-only log check: emit only allowlisted event metadata, never raw log lines.
const { spawnSync } = require('node:child_process');
const result = spawnSync('kubectl', [
  'logs', '-n', 'keycloak', 'keycloak-0', '--since=12h', '--tail=20000', '--timestamps',
], { encoding: 'utf8', timeout: 30000, maxBuffer: 16 * 1024 * 1024 });
if (result.status !== 0) {
  console.error('Keycloak log read failed; raw output suppressed');
  process.exit(1);
}
const events = [];
const target = process.argv[2]?.toLowerCase();
for (const line of result.stdout.split('\n')) {
  if (!/\bLOGIN_ERROR\b/.test(line) || !/clientId="?a2a-monitor(?:"|,|\s)/.test(line)) continue;
  const username = /\busername="?([^",\s]+)/.exec(line)?.[1]?.toLowerCase();
  if (target && username !== target) continue;
  const error = /\berror="?([a-z0-9_]+)(?:"|,|\s)/i.exec(line)?.[1];
  const timestamp = /^(\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?)/.exec(line)?.[1];
  const grantType = /\bgrant_type="?([a-z_]+)(?:"|,|\s)/.exec(line)?.[1];
  const authMethod = /\bauth_method="?([a-z-]+)(?:"|,|\s)/.exec(line)?.[1];
  if (error) events.push({ timestamp, type: 'LOGIN_ERROR', client: 'a2a-monitor', error,
    grantType: ['password', 'authorization_code', 'refresh_token'].includes(grantType) ? grantType : undefined,
    authMethod: ['openid-connect', 'saml'].includes(authMethod) ? authMethod : undefined });
}
console.log(JSON.stringify({
  namespace: 'keycloak', pod: 'keycloak-0', window: 'last 12h, at most 20000 lines',
  matchedCount: events.length, events: events.slice(-10),
  scope: target ? 'Requested username matched in server event metadata' : 'Client-scoped event metadata only',
  limitation: 'Historical server events, not a newly attempted login.',
}, null, 2));

