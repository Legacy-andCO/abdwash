const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {installFixtures,day}=require('./fixtures.cjs');
const fs=require('node:fs');
const path=require('node:path');
const stage=process.argv[2]||'before';
const out=path.resolve('docs/ux-review',stage); fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 for(const role of ['manager','employee']) {
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const fixtures=await installFixtures(context,role); const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://localhost:8082');
  await page.getByRole('textbox',{name:'Username',exact:true}).fill('ux.test');
  await page.getByRole('textbox',{name:'Password',exact:true}).fill('synthetic-password');
  await page.getByRole('button',{name:'Log in',exact:true}).click();
  await page.getByRole('tab',{name:'Today',exact:true}).waitFor(); await page.waitForTimeout(1600);
  await page.screenshot({path:path.join(out,`${role}-today-mobile.png`)});
  await page.setViewportSize({width:1280,height:900}); await page.screenshot({path:path.join(out,`${role}-today-desktop.png`)});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('tab',{name:'Jobs',exact:true}).click();await page.waitForTimeout(450);
  await page.screenshot({path:path.join(out,`${role}-jobs-mobile.png`)});
  await page.getByRole('tab',{name:'Calendar',exact:true}).click();await page.waitForTimeout(450);
  await page.screenshot({path:path.join(out,`${role}-calendar-mobile.png`)});
  await page.getByRole('button',{name:'+ Book a Wash',exact:true}).click();await page.waitForTimeout(400);
  await page.screenshot({path:path.join(out,`${role}-booking-mobile.png`)});
  await page.getByRole('button',{name:'Close',exact:true}).click();
  fs.writeFileSync(path.join(out,`${role}-capture.json`),JSON.stringify({errors,unknown:fixtures.unknown,requests:fixtures.requests.map(({method,path})=>({method,path}))},null,2));
  await context.close();
 }
 await browser.close();console.log('Captured '+stage);
})().catch(e=>{console.error(e);process.exitCode=1;});
