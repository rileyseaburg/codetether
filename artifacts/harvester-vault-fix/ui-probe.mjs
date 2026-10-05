// Drive the real Chromium (CDP on :9333) through the dashboard and record
// what the model selector actually renders. Writes screenshots + JSON here.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const target = process.argv[2] || 'https://codetether.run/dashboard';
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = browser.contexts()[0] || (await browser.newContext());
const page = await ctx.newPage();
const netlog = [];
page.on('response', (r) => {
  const u = r.url();
  if (/\/v1\/agent\/(models|workers)|\/api\/(v1\/)?agent\/(models|workers)/.test(u)) {
    netlog.push({ url: u, status: r.status() });
  }
});
page.on('console', (m) => {
  if (m.type() === 'error') netlog.push({ console: m.text().slice(0, 200) });
});

await page.goto(target, { waitUntil: 'networkidle', timeout: 60000 }).catch((e) => netlog.push({ gotoError: String(e) }));
await page.waitForTimeout(4000);
const title = await page.title();
const url = page.url();
const bodyText = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ').slice(0, 800);
await page.screenshot({ path: `${out}/ui-01-landing.png`, fullPage: false });

// Look for a model selector / provider text on the page.
const probe = await page.evaluate(() => {
  const txt = document.body.innerText;
  const hits = ['openai-codex', 'cerebras', 'openrouter', 'bedrock', 'Sign in', 'Login', 'Keycloak', 'model'].map((k) => [k, txt.toLowerCase().includes(k.toLowerCase())]);
  const inputs = [...document.querySelectorAll('input,button,[role=combobox]')].map((e) => (e.getAttribute('placeholder') || e.getAttribute('aria-label') || e.textContent || '').trim()).filter(Boolean).slice(0, 40);
  return { hits: Object.fromEntries(hits), inputs };
});

fs.writeFileSync(`${out}/ui-probe.json`, JSON.stringify({ target, url, title, bodyText, probe, netlog }, null, 2));
console.log(JSON.stringify({ url, title, hits: probe.hits, netlog }, null, 1));
console.log('BODY:', bodyText.slice(0, 400));
console.log('CONTROLS:', probe.inputs.slice(0, 25));
await page.close();
await browser.close();
