#!/usr/bin/env node
// Inspect or provision an isolated iOS test identity; never print credentials.
const { spawnSync } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const origin = process.env.KEYCLOAK_ADMIN_URL || 'https://auth.quantum-forge.io';
const endpoint = new URL(origin);
if (endpoint.protocol !== 'https:' &&
    !(endpoint.protocol === 'http:' && endpoint.hostname === '127.0.0.1')) {
  throw new Error('Use HTTPS or a loopback Kubernetes port-forward');
}
const username = 'codetether-ios-e2e';
const credentialPath = 'secret/codetether/ios-e2e-user';
function command(program, args, input) {
  const r = spawnSync(program, args, { input, encoding: 'utf8', timeout: 30000 });
  if (r.status !== 0) throw new Error(`${program} failed; output suppressed`);
  return r.stdout;
}
async function main() {
  const mode = process.argv[2] || 'inspect';
  if (!['inspect', 'provision', 'diagnose-user', 'issuer-check'].includes(mode)) throw new Error('Use inspect, provision, diagnose-user, or issuer-check');
  const secret = JSON.parse(command('kubectl', [
    'get', 'secret', '-n', 'a2a-system', 'codetether-identity-provisioner', '-o', 'json',
  ])).data;
  const value = name => Buffer.from(secret[name], 'base64').toString('utf8');
  const realm = value('KEYCLOAK_AGENT_REALM');
  if (realm !== 'quantum-forge') throw new Error('Unexpected managed realm');
  const tokenResponse = await fetch(`${origin}/realms/${value('KEYCLOAK_PROVISIONER_REALM')}/protocol/openid-connect/token`, {
    method: 'POST', signal: AbortSignal.timeout(20000),
    body: new URLSearchParams({ grant_type: 'client_credentials',
      client_id: value('KEYCLOAK_PROVISIONER_CLIENT_ID'),
      client_secret: value('KEYCLOAK_PROVISIONER_CLIENT_SECRET') }),
  });
  if (!tokenResponse.ok) throw new Error(`Provisioner authentication HTTP ${tokenResponse.status}`);
  const token = (await tokenResponse.json()).access_token;
  if (!token) throw new Error('Provisioner returned no access token');
  if (mode === 'issuer-check') {
    const claims = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
    console.log(JSON.stringify({ transport: origin, tokenIssuer: claims.iss,
      client: claims.azp, note: 'Service-client token metadata only; no user login attempted.' }));
    return;
  }
  async function admin(path, method = 'GET', body) {
    const r = await fetch(`${origin}/admin/realms/${realm}/${path}`, {
      method, signal: AbortSignal.timeout(20000),
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!r.ok) throw new Error(`Keycloak ${method} ${path.split('?')[0]} HTTP ${r.status}`);
    return r.status === 204 || r.status === 201 ? null : r.json();
  }
  if (mode === 'diagnose-user') {
    const requestedUser = process.argv[3];
    if (!requestedUser || requestedUser.length > 254) throw new Error('Specify the login email');
    const matches = await admin(`users?username=${encodeURIComponent(requestedUser)}&exact=true`);
    if (!matches.length) {
      console.log(JSON.stringify({ found: false, username: requestedUser }));
      return;
    }
    for (const user of matches) {
      const credentials = await admin(`users/${user.id}/credentials`);
      console.log(JSON.stringify({ found: true, username: user.username,
        enabled: user.enabled, emailVerified: user.emailVerified,
        requiredActions: user.requiredActions || [],
        credentialTypes: credentials.map(c => c.type),
        note: 'Read-only account metadata; no password or login attempt.' }));
      try {
        const events = await admin(`events?type=LOGIN_ERROR&user=${encodeURIComponent(user.id)}&client=a2a-monitor&max=3`);
        console.log(JSON.stringify({ recentErrors: events.map(event => ({
          time: event.time, type: event.type, error: event.error,
        })) }));
      } catch {
        console.log(JSON.stringify({ recentErrors: null, note: 'Login events not available to provisioner' }));
      }
    }
    return;
  }
  const realmSettings = await admin('');
  console.log(JSON.stringify({ loginWithEmailAllowed: realmSettings.loginWithEmailAllowed,
    registrationEmailAsUsername: realmSettings.registrationEmailAsUsername,
    verifyEmail: realmSettings.verifyEmail }));
  const clients = await admin('clients?clientId=a2a-monitor');
  console.log(JSON.stringify({ realm, clients: clients.map(c => ({
    clientId: c.clientId, enabled: c.enabled, directAccessGrantsEnabled: c.directAccessGrantsEnabled,
    standardFlowEnabled: c.standardFlowEnabled, publicClient: c.publicClient,
  })) }));
  let users = await admin(`users?username=${username}&exact=true`);
  if (!users.length) {
    users = await admin(`users?email=${encodeURIComponent(username + '@example.invalid')}&exact=true`);
  }
  if (mode === 'provision' && !users.length) {
    const password = randomBytes(32).toString('base64url');
    // Store first: a failed Keycloak call never leaves an unrecoverable password.
    command('vault', ['kv', 'put', '-cas=0', credentialPath, '-'],
      JSON.stringify({ username, password, realm, purpose: 'Riley iPhone native app end-to-end test' }));
    await admin('users', 'POST', { username, enabled: true,
      email: `${username}@example.invalid`, emailVerified: false,
      firstName: 'CodeTether', lastName: 'iOS Test', requiredActions: [],
      attributes: { purpose: ['ios-e2e'], managed_by: ['codetether-user-request'] },
      credentials: [{ type: 'password', value: password, temporary: false }],
    });
    users = await admin(`users?username=${username}&exact=true`);
    if (!users.length) {
      users = await admin(`users?email=${encodeURIComponent(username + '@example.invalid')}&exact=true`);
    }
  }
  if (users.length > 1) throw new Error('Unexpected duplicate test users');
  let user = users[0];
  if (mode === 'provision' && !user) {
    throw new Error('Creation not confirmed by read-back; do not repeat provisioning');
  }
  if (user && user.attributes?.purpose?.[0] !== 'ios-e2e') {
    throw new Error('Existing username is not our managed test user; refusing changes');
  }
  if (mode === 'provision' && user) {
    // Only this marked, non-delivering synthetic identity is pre-verified.
    // Never weaken the realm's verification policy or grant administrator roles.
    if (user.email !== `${username}@example.invalid`) throw new Error('Unexpected test email');
    await admin(`users/${user.id}`, 'PUT', { ...user, emailVerified: true });
    const editor = await admin('roles/editor');
    await admin(`users/${user.id}/role-mappings/realm`, 'POST', [editor]);
    command('vault', ['kv', 'patch', credentialPath, `username=${user.username}`]);
    user = await admin(`users/${user.id}`);
    const roles = await admin(`users/${user.id}/role-mappings/realm`);
    if (!user.emailVerified || !roles.some(r => r.name === 'editor')) {
      throw new Error('Test account readiness read-back failed');
    }
    console.log(JSON.stringify({ roles: roles.map(r => r.name) }));
  }
  console.log(JSON.stringify({ mode, username: user?.username || username, userId: user?.id || null,
    enabled: user?.enabled ?? null, requiredActions: user?.requiredActions || [],
    emailVerified: user?.emailVerified ?? null,
    credentialPath: user ? credentialPath : null,
    note: 'No end-user login attempted; credentials remain in Vault.' }));
}
main().catch(error => {
  // No raw upstream responses, tokens, command output, or credential values.
  console.error(error.message);
  process.exitCode = 1;
});