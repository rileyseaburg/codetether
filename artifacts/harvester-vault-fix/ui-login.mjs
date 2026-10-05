// Log into the real dashboard through Keycloak in a real Chromium and record
// what the model selector renders. Credentials come from env, never argv.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER;
const pass = process.env.SMOKE_PASS;
if (!user || !pass) throw new Error('SMOKE_USER/SMOKE_PASS required');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
const page = await ctx.newPage();
const net = [];
page.on('response', (r) => {
  const u = r.url();
  if (/agent\/(models|workers)/.test(u)) net.push({ url: u.slice(0, 120), status: r.status() });
});
const step = async (name) => {
  await page.screenshot({ path: `${out}/ui-${name}.png` });
  console.log(`[${name}]`, page.url());
};

await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
await step('02-login');
await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
await step('03-keycloak');
await page.fill('#username', user);
await page.fill('#password', pass);
await page.click('#kc-login');
await page.waitForURL(/codetether\.run/, { timeout: 60000 });
await page.waitForLoadState('networkidle').catch(() => {});
await page.waitForTimeout(5000);
await step('04-after-login');

const body = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ');
console.log('BODY:', body.slice(0, 500));

// Find the model selector wherever it lives on this page.
const candidates = await page.evaluate(() => [...document.querySelectorAll('input,button,[role=combobox],select')]
  .map((e) => ({ tag: e.tagName, text: (e.getAttribute('placeholder') || e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 60) }))
  .filter((e) => /model|provider|codex|claude|gpt/i.test(e.text)).slice(0, 20));
console.log('MODEL-ISH CONTROLS:', JSON.stringify(candidates));

fs.writeFileSync(`${out}/ui-login-result.json`, JSON.stringify({ url: page.url(), body: body.slice(0, 2000), candidates, net }, null, 2));
await ctx.storageState({ path: `${out}/.ui-storage-state.json` });
await ctx.close();
await browser.close();
