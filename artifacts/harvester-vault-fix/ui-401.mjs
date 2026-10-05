// Find which request returns 401 after login and forces the /login bounce.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
const user = process.env.SMOKE_USER, pass = process.env.SMOKE_PASS;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
const page = await ctx.newPage();
page.on('response', (r) => {
  if (r.status() >= 400) console.log('[http', r.status(), ']', r.request().method(), r.url().replace(/^https?:\/\/[^/]+/, (m) => m.replace('https://', '')).slice(0, 110), '| auth:', (r.request().headers()['authorization'] || '').slice(0, 12));
});
page.on('framenavigated', (f) => { if (f === page.mainFrame()) console.log('[nav]', new Date().toISOString().slice(11, 19), f.url().slice(0, 100)); });
await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
await page.fill('#username', user); await page.fill('#password', pass); await page.click('#kc-login');
await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
console.log('[logged in]', new Date().toISOString().slice(11, 19));
const s = await page.evaluate(async () => { const r = await fetch('/api/auth/session'); return (await r.text()).slice(0, 600); });
console.log('[session]', s);
await page.waitForTimeout(40000);
console.log('[final url]', page.url());
await ctx.close(); await browser.close();
