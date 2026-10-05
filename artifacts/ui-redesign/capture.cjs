const path = require('node:path');
const fs = require('node:fs');
module.exports = async function capture({ page, evidence, save, out }) {
  out = path.join(out, 'light');
  fs.mkdirSync(out, { recursive: true });
  evidence.preview = [];
  for (const [route, name] of [
    ['/dashboard', 'workspaces'],
    ['/dashboard/tasks', 'tasks'],
    ['/dashboard/sessions', 'conversations'],
  ]) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('http://localhost:3001' + route, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.locator('#dashboard-main').waitFor({ timeout: 30000 });
    const lightMode = page.getByRole('button', { name: 'Switch to light mode', exact: true });
    if (await lightMode.count()) await lightMode.click();
    await page.waitForTimeout(2000);
    const nav = page.getByRole('navigation', { name: 'Dashboard', exact: true });
    await nav.waitFor({ timeout: 20000 });
    const more = nav.getByRole('button', { name: 'More tools', exact: true });
    if (await more.getAttribute('aria-expanded') !== 'false') throw new Error('Advanced navigation must be collapsed on primary pages');
    const links = await nav.getByRole('link').allTextContents();
    if (links.length > 9) throw new Error('Primary navigation still exposes too many destinations');
    if (await nav.getByText('New', { exact: true }).count()) throw new Error('Promotional badges still clutter navigation');
    if (await page.getByRole('button', { name: 'Open chat', exact: true }).count()) throw new Error('Marketing chat still overlaps the dashboard');
    const record = { route, theme: 'light', navigation: links.map(text => text.trim()), headings: await page.locator('#dashboard-main h1').allTextContents() };
    await page.screenshot({ path: path.join(out, `${name}-desktop.png`), fullPage: true });
    if (name === 'workspaces') {
      const search = page.getByRole('searchbox', { name: /search workspaces/i });
      if (await search.count()) {
        await search.fill('CodeTether');
        await page.waitForTimeout(500);
        await page.screenshot({ path: path.join(out, 'workspace-search.png'), fullPage: true });
        record.searchAvailable = true;
      }
    }
    if (name === 'tasks') {
      const task = page.getByRole('button', { name: /UI_LIVE_CB1E678F task validation/ });
      if (await task.count()) {
        await task.click();
        await page.waitForTimeout(300);
        await page.screenshot({ path: path.join(out, 'task-result-desktop.png'), fullPage: true });
        record.ownedTaskSelected = true;
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(250);
    record.mobileWidth = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
    if (record.mobileWidth.page > record.mobileWidth.viewport) throw new Error(`${name} overflows the mobile viewport`);
    await page.screenshot({ path: path.join(out, `${name}-mobile.png`), fullPage: true });
    evidence.preview.push(record); save();
  }
};