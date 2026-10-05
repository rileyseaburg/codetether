const { chromium } = require('../../marketing-site/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
 const browser = await chromium.launch({headless:true,executablePath:'/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell'});
 const context = await browser.newContext({viewport:{width:1440,height:900},extraHTTPHeaders:{'x-cypress-test':'true'}});
 const evidence={level:'mocked local',errors:[],checks:[]};
 await context.route('**/*', async route=>{
  const u=new URL(route.request().url());
  if(u.pathname==='/api/auth/session')return route.fulfill({json:{user:{name:'Audit User',email:'audit@example.invalid'},expires:'2099-01-01T00:00:00.000Z',accessToken:'audit-fixture'}});
  if(u.hostname!=='127.0.0.1'||u.pathname.startsWith('/api/'))return route.fulfill({status:503,json:{detail:'UI audit: backend intentionally unavailable'}});
  return route.continue();
 });
 const page=await context.newPage();
 page.on('pageerror',e=>evidence.errors.push(e.message));
 await page.goto('http://127.0.0.1:3107/dashboard/settings',{timeout:120000,waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:'A Audit User'}).waitFor({timeout:60000});
 await page.screenshot({path:path.join(__dirname,'desktop.png'),fullPage:true});
 evidence.checks.push({name:'desktop layout',...await page.evaluate(()=>{const side=document.querySelector('div.md\\:fixed');const main=document.querySelector('div.absolute.inset-0');return {sidebar:side?.getBoundingClientRect().toJSON(),content:main?.getBoundingClientRect().toJSON()}})});
 await page.getByRole('button',{name:'A Audit User'}).click();
 const menu=page.getByText(/Signed in as/);
 evidence.checks.push({name:'user menu bounds',box:await menu.locator('..').boundingBox(),viewport:page.viewportSize()});
 await page.screenshot({path:path.join(__dirname,'desktop-user-menu.png'),fullPage:true});
 await page.keyboard.press('Escape');
 evidence.checks.push({name:'user menu closes on Escape',closed:!(await menu.isVisible())});
 await page.setViewportSize({width:390,height:844});
 await page.reload({waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:'A',exact:true}).waitFor();
 await page.waitForTimeout(500);
 await page.evaluate(()=>document.activeElement?.blur());
 const tabs=[];
 for(let i=0;i<6;i++) {await page.keyboard.press('Tab');tabs.push(await page.evaluate(()=>{const e=document.activeElement;return {tag:e.tagName,text:e.textContent?.trim().slice(0,60),label:e.getAttribute('aria-label'),rect:e.getBoundingClientRect().toJSON()}}));}
 evidence.checks.push({name:'mobile first six Tab stops with sidebar closed',tabs});
 await page.screenshot({path:path.join(__dirname,'mobile.png'),fullPage:true});
 evidence.checks.push({name:'unnamed dashboard buttons',buttons:await page.locator('button').evaluateAll(bs=>bs.filter(b=>!b.textContent.trim()&&!b.getAttribute('aria-label')&&!b.getAttribute('aria-labelledby')&&!b.getAttribute('title')).map(b=>({html:b.outerHTML.slice(0,350),box:b.getBoundingClientRect().toJSON()})))});
 await page.setViewportSize({width:1440,height:900});
 await page.goto('http://127.0.0.1:3107/privacy',{waitUntil:'domcontentloaded'});
 await page.locator('header').getByRole('link',{name:'Pricing',exact:true}).click();
 evidence.checks.push({name:'pricing navigation from privacy',url:page.url(),targetExists:await page.locator('#pricing').count()});
 await page.goto('http://127.0.0.1:3107/',{waitUntil:'domcontentloaded'});
 for(const width of [1440,768,390]) {
  await page.setViewportSize({width,height:900});
  await page.screenshot({path:path.join(__dirname,`home-${width}.png`),fullPage:true});
  evidence.checks.push({name:'homepage width',width,...await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth}))});
 }
 fs.writeFileSync(path.join(__dirname,'results.json'),JSON.stringify(evidence,null,2));

 console.log(JSON.stringify(evidence,null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});