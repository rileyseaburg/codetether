// Inspect why the ModelSelector input is hidden on /dashboard for this user.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, storageState: `${out}/.ui-storage-state.json` });
const page = await ctx.newPage();
await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(3000);
await page.screenshot({ path: `${out}/ui-05-dashboard-full.png`, fullPage: true });
const info = await page.evaluate(() => {
  const inp = document.querySelector('input[placeholder*="Search by provider"]');
  if (!inp) return { found: false };
  const chain = [];
  let e = inp;
  while (e && e !== document.body) {
    const cs = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    if (cs.display === 'none' || cs.visibility === 'hidden' || r.width === 0 || r.height === 0) {
      chain.push({ tag: e.tagName, cls: (e.className || '').toString().slice(0, 120), display: cs.display, vis: cs.visibility, w: r.width, h: r.height });
    }
    e = e.parentElement;
  }
  const r = inp.getBoundingClientRect();
  return { found: true, inputRect: { x: r.x, y: r.y, w: r.width, h: r.height }, hiddenAncestors: chain.slice(0, 6), nearbyHeading: (inp.closest('section,form,div')?.querySelector('h2,h3,label')?.textContent || '').trim() };
});
console.log(JSON.stringify(info, null, 1));
const headings = await page.evaluate(() => [...document.querySelectorAll('h2,h3')].map((h) => h.textContent.trim()).slice(0, 30));
console.log('HEADINGS:', headings);
await ctx.close();
await browser.close();
