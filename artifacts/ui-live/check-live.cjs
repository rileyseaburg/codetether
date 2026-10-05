const { chromium } = require('../../marketing-site/node_modules/playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const OUT = process.env.LIVE_EVIDENCE_DIR || __dirname;
fs.mkdirSync(OUT, { recursive: true });
const BASE = 'http://localhost:3001';
const API = process.env.LIVE_API_URL || 'https://api.codetether.run';
const authOnly = process.env.LIVE_AUTH_ONLY === '1';
const readApiOnly = process.env.LIVE_READ_API_ONLY === '1';
const signupMode = process.env.LIVE_SIGNUP === '1';
const suffix = process.env.LIVE_CREDENTIAL_PATH?.split('/').pop().replace('ui-live-', '') || crypto.randomUUID().slice(0, 8);
const credentials = signupMode && !process.env.LIVE_CREDENTIAL_PATH ? {
  PLAYWRIGHT_AGENT_USERNAME: `ui-live-${suffix}@example.com`,
  PLAYWRIGHT_AGENT_PASSWORD: crypto.randomBytes(32).toString('base64url'),
} : JSON.parse(execFileSync('vault', ['kv', 'get', '-format=json', process.env.LIVE_CREDENTIAL_PATH || 'kv/codetether/playwright/agent-keycloak-auth'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })).data.data;
const username = credentials.PLAYWRIGHT_AGENT_USERNAME;
const password = credentials.PLAYWRIGHT_AGENT_PASSWORD;
const RUN = process.env.LIVE_RUN || 'read-only';
const secrets = [username, password];
const evidence = { level: 'live deployment/Argo', mode: 'changed local UI with real services; no frontend deployment change', base: BASE, api: API,
  backend: { namespace: process.env.LIVE_BACKEND_NAMESPACE || 'a2a-server', service: process.env.LIVE_BACKEND_SERVICE || 'codetether-a2a-server' },
  started: new Date().toISOString(), stage: 'launch', checks: [], requests: [] };
let browser;
let page;
function safe(text) {
  let value = String(text || '');
  for (const secret of secrets) if (secret) value = value.split(secret).join('[REDACTED]');
  value = value.replace(/(?:Bearer\s+\S+|eyJ[A-Za-z0-9_.-]+|sk-[A-Za-z0-9_-]{12,}|hvs\.[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+)/g, '[REDACTED CREDENTIAL]');
  return value.replace(/https?:\/\/[^\s"<>]+/g, raw => {
    try { const url = new URL(raw); return url.origin + url.pathname; } catch { return '[URL]'; }
  });
}
function save() { fs.writeFileSync(path.join(OUT, `${RUN}-results.json`), JSON.stringify(evidence, null, 2)); }
async function shot(name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: true,
    mask: [page.locator('input[type=password], input[name=username], input[name=email]')] });
}
async function api(url, method = 'GET', body) {
  return page.evaluate(async ({ target, method, body }) => {
    const session = await fetch('/api/auth/session').then(response => response.json());
    const response = await fetch(target, { method, headers: { Authorization: `Bearer ${session.accessToken}`, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined });
    let data;
    try { data = await response.json(); } catch { data = null; }
    return { status: response.status, data };
  }, { target: url, method, body });
}
(async () => {
  browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  page = await context.newPage();
  page.on('requestfailed', request => {
    const url = new URL(request.url());
    evidence.requests.push({ origin: url.origin, path: url.pathname, method: request.method(), failure: safe(request.failure()?.errorText) });
    save();
  });
  // No route mocks, test-bypass headers, HAR, traces, or persisted auth state.
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.pathname.includes('/v1/') || url.pathname.startsWith('/api/auth/') || url.pathname.includes('/protocol/openid-connect/')) {
      evidence.requests.push({ origin: url.origin, path: url.pathname, method: response.request().method(), status: response.status() });
    }
  });
  evidence.stage = 'open-login'; save();
  if (signupMode) {
    const credentialPath = `kv/codetether/playwright/ui-live-${suffix}`;
    if (!process.env.LIVE_CREDENTIAL_PATH) execFileSync('vault', ['kv', 'put', '-format=json', credentialPath, '-'], {
      input: JSON.stringify({ ...credentials, purpose: 'User-requested live UI integration validation', created_at: evidence.started }),
      encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'],
    });
    evidence.testIdentityCredentialPath = credentialPath;
    evidence.stage = 'real-workspace-signup'; save();
    await page.goto(BASE + '/register', { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.locator('[name=org_name]').fill(`UI Integration ${suffix}`);
    await page.locator('[name=email]').fill(username);
    await page.locator('[name=password]').fill(password);
    const responsePromise = page.waitForResponse(response => response.url().includes('/v1/tenants/signup') && response.request().method() === 'POST', { timeout: 180000 });
    await page.locator('button[type=submit]').click();
    evidence.stage = 'awaiting-signup-response';
    evidence.submissionPage = { origin: new URL(page.url()).origin, path: new URL(page.url()).pathname, queryKeys: [...new URL(page.url()).searchParams.keys()] };
    save();
    const response = await responsePromise;
    const result = await response.json();
    evidence.checks.push({ check: 'real workspace signup', status: response.status(), result });
    evidence.createdTenant = result.tenant_id ? { tenant_id: result.tenant_id, realm_name: result.realm_name, instance_url: result.instance_url } : null;
    save();
    if (!response.ok()) throw new Error(`Workspace signup rejected: ${response.status()} ${safe(JSON.stringify(result))}`);
    await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  } else {
    await page.goto(BASE + '/login' + (authOnly || readApiOnly ? '?callbackUrl=%2Fprivacy' : ''), { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.getByRole('button', { name: 'Continue with Quantum Forge SSO' }).click({ timeout: 45000 });
  }
  await page.waitForURL(url => url.hostname === 'auth.quantum-forge.io', { timeout: 45000 });
  const authorization = new URL(page.url());
  evidence.checks.push({ check: 'real OAuth authorization', origin: authorization.origin, path: authorization.pathname,
    clientId: authorization.searchParams.get('client_id'), redirectUri: authorization.searchParams.get('redirect_uri'),
    pkce: authorization.searchParams.get('code_challenge_method') === 'S256', statePresent: authorization.searchParams.has('state') });
  evidence.stage = 'keycloak-login'; save();
  await page.locator('#username').fill(username, { timeout: 20000 });
  await page.locator('#password').fill(password);
  await page.locator('#kc-login').click();
  await page.waitForTimeout(2000);
  if (new URL(page.url()).hostname === 'auth.quantum-forge.io') {
    evidence.identityProviderText = safe(await page.locator('body').innerText());
    save();
  }
  await page.waitForURL(url => ['localhost', '127.0.0.1'].includes(url.hostname) && (authOnly || readApiOnly ? url.pathname === '/privacy' : url.pathname.startsWith('/dashboard')), { timeout: 60000 });
  const session = await page.evaluate(() => fetch('/api/auth/session').then(response => response.json()));
  if (session.accessToken) secrets.push(session.accessToken);
  if (session.refreshToken) secrets.push(session.refreshToken);
  if (session.idToken) secrets.push(session.idToken);
  evidence.checks.push({ check: 'real session', authenticated: Boolean(session.user && session.accessToken),
    hasRefreshToken: Boolean(session.refreshToken), tenantId: session.tenantId || null, error: session.error || null });
  if (!session.user || !session.accessToken) throw new Error('No authenticated API session returned');
  if (process.env.LIVE_DESIGN_PREVIEW === '1') {
    await require('../ui-redesign/capture.cjs')({ page, api, apiBase: API, evidence, save, safe, out: OUT });
    evidence.stage = 'design-preview-captured'; save();
    console.log(JSON.stringify({ stage: evidence.stage, preview: evidence.preview }, null, 2));
    return;
  }
  if (authOnly) {
    const claims = JSON.parse(Buffer.from(session.accessToken.split('.')[1], 'base64url'));
    const waitSeconds = Math.max(1, claims.exp - Math.floor(Date.now() / 1000) - 55);
    evidence.stage = 'waiting-for-real-token-refresh';
    evidence.checks.push({ check: 'token lifetime', issuedAt: claims.iat, expiresAt: claims.exp, waitSeconds }); save();
    if (waitSeconds > 1200) throw new Error('Token lifetime exceeds the bounded twenty-minute refresh validation window');
    await page.waitForTimeout(waitSeconds * 1000);
    const renewedResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/session' && response.status() === 200, { timeout: 45000 });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 45000 });
    const renewed = await (await renewedResponse).json();
    if (renewed.accessToken) secrets.push(renewed.accessToken);
    if (renewed.refreshToken) secrets.push(renewed.refreshToken);
    if (renewed.idToken) secrets.push(renewed.idToken);
    const newClaims = renewed.accessToken ? JSON.parse(Buffer.from(renewed.accessToken.split('.')[1], 'base64url')) : {};
    const success = Boolean(renewed.user && renewed.accessToken !== session.accessToken && newClaims.exp > claims.exp && newClaims.sub === claims.sub && !renewed.error);
    evidence.checks.push({ check: 'real automatic token refresh', success, previousExpiry: claims.exp, newExpiry: newClaims.exp, sameIdentity: newClaims.sub === claims.sub, error: renewed.error || null });
    evidence.stage = success ? 'real-signin-and-refresh-finished' : 'token-refresh-failed'; save();
    await shot(`${RUN}-authenticated.png`);
    if (!success) throw new Error('Real session refresh did not return a renewed access token');
    console.log(JSON.stringify({ stage: evidence.stage, checks: evidence.checks }, null, 2));
    return;
  }
  evidence.stage = 'live-read-only-api'; save();
  for (const endpoint of ['/v1/agent/workspaces/list', '/v1/agent/workers', '/v1/worker/connected', '/v1/billing/subscription', '/v1/billing/usage']) {
    const result = await api(API + endpoint);
    const data = result.data;
    let summary;
    if (endpoint.endsWith('/workspaces/list')) {
      const items = Array.isArray(data) ? data : data?.workspaces || [];
      // Only identify the user-designated repository; do not inspect other workspaces.
      summary = { count: items.length, currentRepository: items.filter(item => String(item.path || '').includes('A2A-Server-MCP')).map(item => ({ id: item.id, name: item.name, worker_id: item.worker_id, status: item.status })) };
    } else if (endpoint.endsWith('/agent/workers')) {
      const items = Array.isArray(data) ? data : [];
      summary = items.map(item => ({ worker_id: item.worker_id, name: item.name, status: item.status, models: item.models, codebases: item.codebases }));
    } else if (endpoint.endsWith('/worker/connected')) {
      summary = { workers: (data?.workers || []).map(item => ({ worker_id: item.worker_id, agent_name: item.agent_name })) };
    } else {
      summary = data ? { keys: Object.keys(data), ...Object.fromEntries(['tier', 'tier_name', 'tasks_used', 'tasks_limit', 'detail'].filter(key => key in data).map(key => [key, data[key]])),
        plan: typeof data.plan === 'string' ? data.plan : data.plan ? Object.fromEntries(['name', 'id', 'tasks_per_month', 'max_concurrent_tasks', 'max_task_runtime_seconds'].filter(key => key in data.plan).map(key => [key, data.plan[key]])) : null,
        subscriptionKeys: data.subscription ? Object.keys(data.subscription) : [] } : null;
    }
    evidence.checks.push({ check: endpoint, status: result.status, summary }); save();
  }
  if (process.env.LIVE_MUTATIONS === '1') {
    await require('./mutations.cjs')({ page, api, apiBase: API, evidence, save, safe, out: OUT });
  }
  if (process.env.LIVE_FINAL_CHECKS === '1') {
    await require('./final-checks.cjs')({ page, api, apiBase: API, evidence, save, safe, out: OUT });
  }
  if (readApiOnly) {
    evidence.stage = 'public-read-only-finished'; save();
    console.log(JSON.stringify({ stage: evidence.stage, checks: evidence.checks }, null, 2)); return;
  }
  for (const route of ['/dashboard/settings', '/dashboard/billing', '/dashboard/tasks', '/dashboard/sessions']) {
    evidence.stage = route; save();
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.getByRole('main').waitFor({ timeout: 20000 });
    await page.waitForTimeout(1500);
    evidence.checks.push({ check: 'real page', route, headings: await page.locator('h1').allTextContents(),
      alerts: (await page.getByRole('alert').allTextContents()).map(safe) });
    await shot(route.split('/').pop() + '.png'); save();
  }
  evidence.stage = 'read-only-phase-finished'; save();
  console.log(JSON.stringify({ stage: evidence.stage, checks: evidence.checks }, null, 2));
})().catch(async error => {
  evidence.error = { name: error.name, message: safe(error.message) };
  if (page) {
    evidence.page = safe(page.url());
    evidence.alerts = (await page.locator('#kc-error-message, [role=alert]').allTextContents().catch(() => [])).map(safe);
    if (new URL(page.url()).hostname === 'auth.quantum-forge.io') evidence.identityProviderText = safe(await page.locator('body').innerText().catch(() => ''));
    if (new URL(page.url()).pathname === '/register') evidence.registrationText = safe(await page.locator('main').innerText().catch(() => ''));
    await shot(`${RUN}-failure.png`).catch(() => {});
  }
  save(); console.error(JSON.stringify({ stage: evidence.stage, error: evidence.error, alerts: evidence.alerts })); process.exitCode = 1;
}).finally(async () => { if (browser) await browser.close(); });