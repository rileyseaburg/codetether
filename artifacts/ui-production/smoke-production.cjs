// Real production browser verification. Credentials stay in memory, no HAR/trace.
const { chromium } = require('../../marketing-site/node_modules/playwright');
const { execFileSync } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const OUT = __dirname;
const canary = process.env.PRODUCTION_CANARY === '1';
const resultName = canary ? 'canary-browser.json' : 'production-browser.json';
const release = JSON.parse(fs.readFileSync(path.join(OUT, 'release.json')));
const record = { level: 'live deployment/Argo', mode: canary ? 'production-host canary' : 'production', commit: release.commit, image: release.image, checks: [], mutations: [] };
let browser, adminToken, userId;
const username = `ui-release-${release.commit.slice(0, 8)}-${crypto.randomBytes(3).toString('hex')}@example.com`;
const password = crypto.randomBytes(36).toString('base64url');
const secrets = [username, password];
const save = () => fs.writeFileSync(path.join(OUT, resultName), JSON.stringify(record, null, 2));
const kube = (...args) => JSON.parse(execFileSync('kubectl', [...args, '-o', 'json'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }));
function safe(text) {
  let result = String(text || '');
  for (const secret of secrets) if (secret) result = result.split(secret).join('[REDACTED]');
  return result.replace(/(?:Bearer\s+\S+|eyJ[A-Za-z0-9_.-]+)/g, '[REDACTED]').replace(/https?:\/\/[^\s"<>]+/g, value => {
    try { const u = new URL(value); return u.origin + u.pathname; } catch { return '[URL]'; }
  });
}
async function admin(method, endpoint, body) {
  const response = await fetch('http://127.0.0.1:18080/admin/realms/quantum-forge' + endpoint, {
    method, headers: { Authorization: 'Bearer ' + adminToken, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Keycloak admin ${method} ${endpoint.split('?')[0]} returned ${response.status}`);
  const text = await response.text();
  return { data: text ? JSON.parse(text) : null, location: response.headers.get('location'), status: response.status };
}
(async () => {
  const env = kube('get', 'statefulset', 'keycloak', '-n', 'keycloak').spec.template.spec.containers[0].env;
  const adminName = env.find(e => e.name === 'KEYCLOAK_ADMIN').value;
  const ref = env.find(e => e.name === 'KEYCLOAK_ADMIN_PASSWORD').valueFrom.secretKeyRef;
  const adminPassword = Buffer.from(kube('get', 'secret', ref.name, '-n', 'keycloak').data[ref.key], 'base64').toString();
  secrets.push(adminName, adminPassword);
  const tokenResponse = await fetch('http://127.0.0.1:18080/realms/master/protocol/openid-connect/token', {
    method: 'POST', body: new URLSearchParams({ grant_type: 'password', client_id: 'admin-cli', username: adminName, password: adminPassword }),
  });
  if (!tokenResponse.ok) throw new Error('Configured Keycloak admin authentication failed');
  adminToken = (await tokenResponse.json()).access_token; secrets.push(adminToken);
  const created = await admin('POST', '/users', {
    username, email: username, firstName: 'UI', lastName: 'Release check', enabled: true, emailVerified: true,
    attributes: { ui_release_check: [release.commit] }, credentials: [{ type: 'password', value: password, temporary: false }],
  });
  userId = created.location.split('/').pop(); record.testUserId = userId; save();
  const role = (await admin('GET', '/roles/editor')).data;
  await admin('POST', `/users/${userId}/role-mappings/realm`, [{ id: role.id, name: role.name }]);
  browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell' });
  for (const host of (canary ? ['codetether.run'] : ['codetether.run', 'quantum-forge.codetether.run'])) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ...(canary ? { extraHTTPHeaders: { 'X-CodeTether-Release': release.commit } } : {}) });
    const page = await context.newPage();
    const entry = { host, requests: [] }; record.checks.push(entry); save();
    page.on('response', response => {
      const u = new URL(response.url());
      if (response.status() >= 400 || u.pathname.includes('/v1/') || u.pathname.startsWith('/api/auth/')) entry.requests.push({ host: u.host, path: u.pathname, status: response.status() });
    });
    if (host === 'codetether.run') {
      const versionResponse = await page.goto(`https://${host}/api/ui-version?release=${release.commit.slice(0, 12)}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
      const version = await versionResponse.json();
      entry.versionStatus = versionResponse.status(); entry.revision = version.revision; save();
      if (version.revision !== release.commit) throw new Error(`Wrong production revision at ${host}`);
    } else {
      // This alias sends /api (except /api/auth) to the API service. Its root
      // UI uses the same marketing Service via codetether-marketing-bridge.
      entry.versionSource = 'shared codetether-marketing Service; authenticated UI checked below';
    }
    entry.stage = 'sign-in'; save();
    await page.goto(`https://${host}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.getByRole('button', { name: 'Continue with Quantum Forge SSO' }).click({ timeout: 45000 });
    await page.waitForURL(u => u.hostname === 'auth.quantum-forge.io', { timeout: 45000 });
    const oauth = new URL(page.url());
    entry.callback = oauth.searchParams.get('redirect_uri'); entry.pkce = oauth.searchParams.get('code_challenge_method');
    if (entry.callback !== `https://${host}/api/auth/callback/keycloak`) throw new Error(`Callback origin mismatch at ${host}`);
    entry.stage = 'callback'; save();
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await page.locator('#kc-login').click();
    await page.waitForURL(u => u.host === host && u.pathname.startsWith('/dashboard'), { timeout: 60000 });
    entry.stage = 'dashboard'; save();
    await page.getByRole('heading', { name: 'Workspaces', exact: true }).waitFor({ timeout: 45000 });
    const nav = page.getByRole('navigation', { name: 'Dashboard', exact: true });
    entry.navigation = (await nav.getByRole('link').allTextContents()).map(text => text.trim());
    if (entry.navigation.length > 9) throw new Error('Old overloaded navigation is still served');
    entry.moreToolsCollapsed = await nav.getByRole('button', { name: 'More tools' }).getAttribute('aria-expanded') === 'false';
    await page.getByRole('searchbox', { name: 'Search workspaces' }).waitFor();
    await page.screenshot({ path: path.join(OUT, `${host}-workspaces.png`), fullPage: true });
    await page.goto(`https://${host}/dashboard/tasks`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Tasks', exact: true }).waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(OUT, `${host}-tasks.png`), fullPage: true });
    await page.goto(`https://${host}/dashboard/sessions`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: 'Sessions', exact: true }).waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(OUT, `${host}-sessions.png`), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: 'Open navigation menu' }).click();
    await page.getByRole('dialog', { name: 'Dashboard navigation' }).waitFor();
    await page.screenshot({ path: path.join(OUT, `${host}-mobile.png`), fullPage: true });
    await page.keyboard.press('Escape');
    entry.mobileFits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    entry.authenticatedDashboard = true; save();
    await context.close();
  }
  record.success = true; save();
})().catch(error => { record.error = safe(error.message); record.success = false; save(); console.error(record.error); process.exitCode = 1; })
  .finally(async () => {
    if (browser) await browser.close();
    if (adminToken && userId) {
      try { await admin('PUT', `/users/${userId}`, { enabled: false }); await admin('POST', `/users/${userId}/logout`); record.testUserDisabled = true; }
      catch (error) { record.cleanupError = safe(error.message); process.exitCode = 1; }
    }
    save(); console.log(JSON.stringify({ success: record.success, hosts: record.checks.map(c => ({ host: c.host, revision: c.revision, authenticated: c.authenticatedDashboard })), disabledTestUser: record.testUserDisabled }, null, 2));
  });