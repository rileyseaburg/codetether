const fs = require('node:fs')
const path = require('node:path')
const esbuild = require('../../marketing-site/node_modules/esbuild')
const postcss = require('../../marketing-site/node_modules/postcss')
const projectRequire = require('node:module').createRequire(path.join(__dirname, '../../marketing-site/package.json'))
const tailwind = projectRequire('@tailwindcss/postcss')
const { chromium } = require('../../marketing-site/node_modules/playwright')
const root = path.resolve(__dirname, '../../marketing-site')
let browser
const errors = []
;(async () => {
  const bundle = await esbuild.build({
    absWorkingDir: root, entryPoints: [path.join(__dirname, 'preview.cjs')], bundle: true, write: false,
    platform: 'browser', format: 'iife', jsx: 'automatic', nodePaths: [path.join(root, 'node_modules')],
    alias: { '@': path.join(root, 'src') }, define: { 'process.env.NODE_ENV': '"development"', 'process.env': '{}' },
    plugins: [{ name: 'fixture-controls', setup(build) {
      build.onResolve({ filter: /(?:\/ModelSelector|\/SessionActions|\/VoiceChatButton)$/ }, args => ({ path: args.path, namespace: 'fixture' }))
      build.onLoad({ filter: /.*/, namespace: 'fixture' }, args => {
        const body = args.path.endsWith('ModelSelector')
          ? "export function ModelSelector(p) {return React.createElement('label',null,p.label,React.createElement('select',{className:'block rounded-lg border-gray-300',disabled:p.disabled},React.createElement('option',null,'Default model')))}"
          : args.path.endsWith('SessionActions') ? "export function SessionActions(p) {return React.createElement('div',{className:'flex gap-2'},React.createElement('button',{onClick:p.onResume},'Resume'),React.createElement('button',{onClick:p.onRefresh},'Refresh'))}"
          : "export default function Voice() {return React.createElement('button',null,'Voice')}"
        return { contents: "import React from 'react';" + body, loader: 'js', resolveDir: root }
      })
    } }],
  })
  const cssPath = path.join(root, 'src/styles/tailwind.css')
  const css = await postcss([tailwind({ base: root })]).process(fs.readFileSync(cssPath, 'utf8'), { from: cssPath })
  fs.writeFileSync(path.join(__dirname, 'preview.css'), css.css)
  browser = await chromium.launch({ headless: true, executablePath: '/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell' })
  const page = await browser.newPage()
  page.on('pageerror', error => { errors.push(error.message); console.error(error.message) })
  await page.route('**/*', route => route.abort())
  await page.setViewportSize({ width: 1180, height: 850 })
  await page.setContent('<html><head></head><body style="margin:0"><div id="root"></div></body></html>')
  await page.addStyleTag({ content: css.css })
  await page.addScriptTag({ content: bundle.outputFiles[0].text })
  await page.getByRole('heading', { name: 'Plan the next release' }).waitFor()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(__dirname, 'desktop-conversation.png') })
  await page.getByText('Conversation settings & actions').click()
  await page.screenshot({ path: path.join(__dirname, 'desktop-settings-open.png') })
  await page.getByText('Conversation settings & actions').click()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(__dirname, 'mobile-conversation.png') })
  await page.getByRole('button', { name: 'Back to sessions' }).click()
  await page.screenshot({ path: path.join(__dirname, 'mobile-session-list.png') })
  fs.writeFileSync(path.join(__dirname, 'preview-results.json'), JSON.stringify({ level: 'mocked local', network: 'all requests blocked; no server', errors, screenshots: 4 }, null, 2))
  await browser.close()
  if (errors.length) throw new Error(errors.join('\n'))
  console.log('mocked local: four fixture screenshots captured; no page exceptions')
})().catch(error => { console.error(error, errors); process.exitCode = 1 }).finally(async () => { if (browser) await browser.close() })