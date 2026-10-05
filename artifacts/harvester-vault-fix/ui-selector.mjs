// Post-login: exercise the real ModelSelector on the dashboard and record
// which providers/models it renders. Reuses the saved storage state.
import { chromium } from '/home/riley/A2A-Server-MCP/marketing-site/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const out = '/home/riley/A2A-Server-MCP/artifacts/harvester-vault-fix';
const browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, storageState: `${out}/.ui-storage-state.json` });
const page = await ctx.newPage();

await page.goto('https://quantum-forge.codetether.run/dashboard', { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(3000);
if (page.url().includes('/login')) throw new Error('session not carried: ' + page.url());

await page.getByRole('button', { name: /Show Advanced Controls/i }).click();
await page.waitForTimeout(800);
const box = page.locator('input[data-cy="model-selector-input"]').first();
await box.scrollIntoViewIfNeeded();

const menu = page.locator('div.fixed.z-\\[90\\]');
const readMenu = async () => {
  if (!(await menu.count())) return { open: false };
  const text = (await menu.first().innerText()).replace(/\s+/g, ' ');
  const options = await menu.first().locator('button span.font-medium').allInnerTexts();
  const providerPills = await menu.first().locator('button').allInnerTexts();
  return { open: true, optionCount: options.length, options: options.slice(0, 40), pills: providerPills.filter((t) => t && t.length < 30).slice(0, 40), noMatch: /No models matching/.test(text) };
};

const results = {};
// 1. Just focus: what does the menu show by default?
await box.click();
await page.waitForTimeout(1500);
results.onFocus = await readMenu();
await page.screenshot({ path: `${out}/ui-05-selector-open.png` });

// 2. Type real keystrokes for each query.
for (const q of ['openai-codex', 'gpt-5.6-luna', 'cerebras']) {
  await box.click();
  await box.press('Control+a');
  await box.press('Backspace');
  await box.pressSequentially(q, { delay: 40 });
  await page.waitForTimeout(1500);
  results[q] = await readMenu();
  await page.screenshot({ path: `${out}/ui-06-search-${q.replace(/[^a-z0-9]/gi, '_')}.png` });
}

// 3. Select the exact model the review pipeline uses and confirm the selection sticks.
await box.click();
await box.press('Control+a');
await box.press('Backspace');
await box.pressSequentially('gpt-5.6-luna', { delay: 40 });
await page.waitForTimeout(1200);
const target = menu.first().locator('button', { hasText: /gpt-5\.6-luna/ }).first();
let selected = null;
if (await target.count()) {
  await target.click();
  await page.waitForTimeout(800);
  selected = { inputValue: await box.inputValue(), pageMention: await page.evaluate(() => { const m = document.body.innerText.match(/openai-codex\/gpt-5\.6-luna[^\s]*/); return m ? m[0] : null; }) };
  await page.screenshot({ path: `${out}/ui-07-selected.png` });
}

const summary = { url: page.url(), results, selected };
fs.writeFileSync(`${out}/ui-selector-result.json`, JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 1));
await ctx.close();
await browser.close();
