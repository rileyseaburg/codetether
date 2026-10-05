// Locate the E2E task row on the Tasks page, click it, and capture the detail pane.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER, pass = process.env.SMOKE_PASS;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
await ctx.addInitScript(() => { try { window.localStorage.setItem('codetether.workspaceWizardDismissed', '1'); } catch {} });
const page = await ctx.newPage();
await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
if (page.url().includes('/login')) {
  await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
  await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
  await page.fill('#username', user); await page.fill('#password', pass); await page.click('#kc-login');
  await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
  await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
}
await page.locator('main .divide-y > *').first().waitFor({ timeout: 45000 });
const rows = page.locator('main .divide-y > *');
const n = await rows.count();
let idx = -1, rowText = null;
for (let i = 0; i < n; i++) {
  const t = (await rows.nth(i).innerText()).replace(/\s+/g, ' ');
  if (/PONG/.test(t)) { idx = i; rowText = t.slice(0, 300); break; }
}
let detail = null;
if (idx >= 0) {
  await rows.nth(idx).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${out}/e2e-10-tasks-row.png` });
  await rows.nth(idx).click();
  await page.waitForTimeout(3000);
  const txt = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ');
  detail = { hasTaskId: /e8c46b6d/.test(txt), hasCompleted: /completed/i.test(txt), hasModel: /openai-codex/.test(txt), hasPongResult: (txt.match(/PONG/g) || []).length };
  await page.screenshot({ path: `${out}/e2e-11-task-detail.png` });
}
const r = { url: page.url(), totalRows: n, rowIndex: idx, rowText, detail };
fs.writeFileSync(`${out}/e2e-tasks-page.json`, JSON.stringify(r, null, 2));
console.log(JSON.stringify(r, null, 1));
await ctx.close(); await browser.close();
