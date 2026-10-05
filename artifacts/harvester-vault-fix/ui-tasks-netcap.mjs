// Capture the raw /v1/agent/tasks response the Tasks page receives.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER, pass = process.env.SMOKE_PASS;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
await ctx.addInitScript(() => { try { window.localStorage.setItem('codetether.workspaceWizardDismissed', '1'); } catch {} });
const page = await ctx.newPage();
const seen = [];
page.on('response', async (r) => {
  if (/\/v1\/agent\/tasks(\?|$)/.test(r.url()) && r.request().method() === 'GET') {
    let body = ''; try { body = await r.text(); } catch {}
    let n = null; try { const j = JSON.parse(body); n = Array.isArray(j) ? j.length : (j.tasks || []).length; } catch {}
    seen.push({ url: r.url(), status: r.status(), tenantHeader: r.request().headers()['x-tenant-id'] || null, auth: !!r.request().headers()['authorization'], count: n, head: body.slice(0, 200) });
  }
});
await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
if (page.url().includes('/login')) {
  await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
  await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
  await page.fill('#username', user); await page.fill('#password', pass); await page.click('#kc-login');
  await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
  await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
}
await page.waitForTimeout(25000);
fs.writeFileSync(`${out}/tasks-page-netcap.json`, JSON.stringify(seen, null, 2));
console.log(JSON.stringify(seen, null, 1));
await ctx.close(); await browser.close();
