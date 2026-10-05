// Full end-to-end through the real dashboard in a real Chromium:
// Keycloak login -> quick-create Container workspace -> select openai-codex model
// -> Trigger Agent -> wait for the task to complete and read the result in the UI.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER;
const pass = process.env.SMOKE_PASS;
if (!user || !pass) throw new Error('SMOKE_USER/SMOKE_PASS required');
const MODEL = 'openai-codex/gpt-5.6-luna';
const PROMPT = 'Reply with exactly the single word PONG and nothing else. Do not use any tools. (UI E2E smoke 2026-09-04)';

const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
const page = await ctx.newPage();
const evidence = { steps: [], network: [] };
const step = async (name, extra = {}) => {
  await page.screenshot({ path: `${out}/e2e-${name}.png` });
  evidence.steps.push({ name, url: page.url(), at: new Date().toISOString(), ...extra });
  console.log(`[${name}]`, JSON.stringify(extra));
};
page.on('response', async (r) => {
  const u = r.url();
  if (/\/v1\/agent\/workspaces(\/[^/]+\/trigger)?$/.test(u) && r.request().method() === 'POST') {
    let body = null; try { body = await r.json(); } catch {}
    evidence.network.push({ method: 'POST', url: u.replace(/^https?:\/\/[^/]+/, ''), status: r.status(), body });
    console.log('[net]', r.request().method(), u.replace(/^https?:\/\/[^/]+/, ''), r.status(), JSON.stringify(body).slice(0, 400));
  }
});

// Suppress the first-run workspace wizard modal (the app persists this key itself).
await ctx.addInitScript(() => { try { window.localStorage.setItem('codetether.workspaceWizardDismissed', '1'); } catch {} });

// 1. Login through Keycloak
await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
await page.fill('#username', user);
await page.fill('#password', pass);
await page.click('#kc-login');
await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(4000);
await step('01-logged-in', { loginError: page.url().includes('error=') });

// Dismiss the first-run wizard if it is showing (it persists the dismissal itself).
const dismiss = page.getByRole('button', { name: /Dismiss tips/i });
if (await dismiss.count()) { await dismiss.first().click(); await page.waitForTimeout(800); }
await page.locator('div.fixed.inset-0.z-50').waitFor({ state: 'detached', timeout: 10000 }).catch(() => {});
await step('01b-wizard-dismissed', { overlay: await page.locator('div.fixed.inset-0.z-50').count() });

// 2. Quick-create a Container workspace (uses an SSE-connected worker)
page.on('console', (m) => { if (m.type() === 'error') console.log('[console.error]', m.text().slice(0, 300)); });
page.on('framenavigated', (f) => { if (f === page.mainFrame()) console.log('[nav]', f.url()); });
await page.getByRole('button', { name: /^Container$/ }).click();
await page.waitForTimeout(500);
const createBtn = page.getByRole('button', { name: /Create Container Workspace/i });
console.log('[create-btn] count', await createBtn.count(), 'disabled', await createBtn.first().isDisabled().catch(() => 'n/a'));
await createBtn.first().click();
await page.waitForTimeout(1500);
await step('02a-after-click', { url: page.url() });
await page.waitForTimeout(6000);
console.log('[body-after]', (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ').slice(0, 300));
const quickMsg = await page.evaluate(() => (document.body.innerText.match(/(workspace created[^\n]*|No connected worker[^\n]*|creation failed[^\n]*)/i) || [null])[0]);
await step('02-workspace-created', { quickMsg });
if (!quickMsg || !/created/i.test(quickMsg)) throw new Error('workspace not created: ' + quickMsg);

// 3. Advanced controls -> select the model via the provider pill
await page.getByRole('button', { name: /Show Advanced Controls/i }).click();
const box = page.locator('input[data-cy="model-selector-input"]').first();
await box.scrollIntoViewIfNeeded();
await box.click();
await page.waitForTimeout(1200);
const menu = page.locator('div.fixed.z-\\[90\\]').first();
await menu.locator('button', { hasText: /^openai-codex\s*\d+$/ }).first().click();
await page.waitForTimeout(800);
await menu.locator('button', { hasText: /^gpt-5\.6-luna/ }).first().click();
await page.waitForTimeout(800);
const modelValue = await box.inputValue();
await step('03-model-selected', { modelValue });
if (modelValue !== MODEL) throw new Error('unexpected model ' + modelValue);

// 4. Prompt + Trigger Agent
const promptBox = page.getByPlaceholder(/Enter your instructions for the AI agent/i).first();
await promptBox.scrollIntoViewIfNeeded();
await promptBox.fill(PROMPT);
await step('04-prompt-filled');
const runBtn = page.getByRole('button', { name: /Run Agent|Trigger Agent/ }).first();
console.log('[run-btn]', await runBtn.innerText(), 'disabled', await runBtn.isDisabled());
await runBtn.click();
await page.waitForTimeout(6000);
const triggerResp = evidence.network.find((n) => /trigger$/.test(n.url));
await step('05-triggered', { triggerStatus: triggerResp?.status, taskId: triggerResp?.body?.task_id || triggerResp?.body?.session_id, model: triggerResp?.body?.model || triggerResp?.body?.routing?.model_ref });

// 5. Watch the UI for completion (runtime context / task list updates)
let finalText = null;
for (let i = 0; i < 24; i++) {
  await page.waitForTimeout(10000);
  const txt = await page.evaluate(() => document.body.innerText);
  const m = txt.match(/(Status|status)[:\s]+(completed|failed|running|queued|in_progress)[^\n]*/);
  const pong = /\bPONG\b/.test(txt);
  console.log(`[poll ${i}]`, m ? m[0].slice(0, 80) : 'no status text', 'PONG visible:', pong);
  if (pong || (m && /completed|failed/.test(m[2]))) { finalText = { status: m ? m[2] : null, pong }; break; }
}
await step('06-final', finalText || { timedOut: true });

// 6. Open the Tasks page and look for our task
await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
await page.waitForTimeout(4000);
const tasksText = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ');
const hit = tasksText.match(/.{0,120}UI E2E smoke.{0,200}/);
await step('07-tasks-page', { tasksHit: hit ? hit[0] : null });

fs.writeFileSync(`${out}/e2e-evidence.json`, JSON.stringify(evidence, null, 2));
await ctx.close();
await browser.close();
