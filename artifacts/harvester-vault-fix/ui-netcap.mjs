// Capture what the dashboard actually gets from /v1/worker/connected and /v1/agent/workers.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const user = process.env.SMOKE_USER, pass = process.env.SMOKE_PASS;
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
const page = await ctx.newPage();
page.on('response', async (r) => {
  const u = r.url();
  if (/worker\/connected|agent\/workers|tenant/.test(u)) {
    let b = ''; try { b = (await r.text()).slice(0, 300); } catch {}
    console.log('[net]', r.request().method(), r.status(), u.replace(/^https?:\/\/[^/]+/, '').slice(0, 90), '| auth:', !!r.request().headers()['authorization'], '| tenant:', r.request().headers()['x-tenant-id'] || '-', '|', b.replace(/\s+/g, ' '));
  }
});
await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
if (page.url().includes('/login')) {
  await page.getByRole('button', { name: /Continue with Quantum Forge SSO/i }).click();
  await page.waitForURL(/auth\.quantum-forge\.io/, { timeout: 30000 });
  await page.fill('#username', user); await page.fill('#password', pass); await page.click('#kc-login');
  await page.waitForURL(/quantum-forge\.codetether\.run\/dashboard/, { timeout: 60000 });
}
await page.waitForTimeout(8000);
await ctx.storageState({ path: `${out}/.ui-storage-state.json` });
await ctx.close(); await browser.close();
