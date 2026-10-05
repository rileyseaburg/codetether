// Inspect the Tasks page DOM: what rows render and what the empty-state says.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER, pass = process.env.SMOKE_PASS;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1400 } });
await ctx.addInitScript(() => { try { window.localStorage.setItem('codetether.workspaceWizardDismissed', '1'); } catch {} });
const page = await ctx.newPage();
const errs = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 200)));
await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
if (page.url().includes('/login')) {
  await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
  await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
  await page.fill('#username', user); await page.fill('#password', pass); await page.click('#kc-login');
  await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
  await page.goto('https://quantum-forge.codetether.run/dashboard/tasks', { waitUntil: 'networkidle', timeout: 60000 });
}
await page.waitForTimeout(30000);
const info = await page.evaluate(() => {
  const main = document.querySelector('main') || document.body;
  const text = main.innerText.replace(/\s+/g, ' ');
  return { mainText: text.slice(0, 1200), hasPong: /PONG/.test(text), hasE2E: /UI E2E/.test(text), rows: document.querySelectorAll('main .divide-y > *').length };
});
await page.screenshot({ path: `${out}/e2e-09-tasks-page-full.png`, fullPage: true });
const r = { url: page.url(), ...info, errs: errs.slice(0, 5) };
fs.writeFileSync(`${out}/tasks-page-dom.json`, JSON.stringify(r, null, 2));
console.log(JSON.stringify(r, null, 1));
await ctx.close(); await browser.close();
