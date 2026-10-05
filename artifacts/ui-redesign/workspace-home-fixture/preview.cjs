// Render the actual component DOM from the local fixture test. No network.
const fs = require('node:fs')
const path = require('node:path')
const root = path.resolve(__dirname, '../../../marketing-site')
const postcss = require(require.resolve('postcss', { paths: [root] }))
const tailwind = require(require.resolve('@tailwindcss/postcss', { paths: [root] }))
const { chromium } = require(require.resolve('playwright', { paths: [root] }))

;(async () => {
  const source = path.join(root, 'src/styles/tailwind.css')
  const css = await postcss([tailwind({ base: root })]).process(fs.readFileSync(source, 'utf8'), { from: source })
  const body = fs.readFileSync(path.join(__dirname, 'preview-body.html'), 'utf8')
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell' })
  const page = await browser.newPage()
  await page.route('**/*', route => route.abort())
  const results = []
  for (const [name, width, height, dark] of [['desktop', 1280, 960, false], ['desktop-dark', 1280, 960, true], ['mobile', 390, 1000, false]]) {
    await page.setViewportSize({ width, height })
    await page.setContent(`<!doctype html><html class="${dark ? 'dark' : ''}"><head><meta charset="utf-8"><style>${css.css}</style><style>body{margin:0;padding:24px;font-family:Arial,sans-serif;background:${dark ? '#090f1a' : '#f5f7fa'}}@media(max-width:600px){body{padding:16px}}</style></head><body><p style="font-size:11px;color:#64748b;margin:0 auto 18px;max-width:1152px">LOCAL DESIGN PREVIEW · SAMPLE DATA · 1,611 REGISTRATIONS</p>${body}</body></html>`)
    await page.screenshot({ path: path.join(__dirname, `preview-${name}.png`), fullPage: true })
    results.push({ name, width, documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
      workspaceButtons: await page.getByRole('list', { name: 'Available workspaces' }).getByRole('button').count(),
      launchVisible: await page.getByRole('button', { name: 'Start agent', exact: true }).isVisible(),
      discovery: await page.locator('#workspace-discovery-title').boundingBox(),
      launcher: await page.locator('#workspace-launcher').boundingBox(),
      advancedVisible: await page.locator('#workspace-advanced-controls').isVisible(),
      monitorVisible: await page.locator('#swarm-monitor').isVisible() })
  }
  fs.writeFileSync(path.join(__dirname, 'preview-results.json'), JSON.stringify({ level: 'mocked local', results }, null, 2))
  console.log(JSON.stringify(results, null, 2))
  await browser.close()
})().catch(error => { console.error(error); process.exitCode = 1 })