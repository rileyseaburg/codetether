const { chromium } = require('../../marketing-site/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell' });
  const page = await browser.newPage();
  const evidence = { level: 'live deployment/Argo', mode: 'public endpoint browser probes; no mocks', checks: [] };
  for (const host of ['api.codetether.run', 'quantum-forge.codetether.run']) {
    try {
      const response = await page.goto(`https://${host}/health`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      evidence.checks.push({ url: `https://${host}/health`, status: response.status(),
        server: response.headers().server, body: (await page.locator('body').innerText()).slice(0, 500) });
      await page.screenshot({ path: path.join(__dirname, `public-${host}.png`) });
    } catch (error) {
      evidence.checks.push({ url: `https://${host}/health`, errorType: error.name });
    }
  }
  fs.writeFileSync(path.join(__dirname, 'public-browser-results.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
  await browser.close();
})().catch(error => { console.error(error.name); process.exitCode = 1; });
