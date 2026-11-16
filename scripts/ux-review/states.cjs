const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {installFixtures}=require('./fixtures.cjs');const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:390,height:844},geolocation:{latitude:24.4,longitude:54.3},permissions:['geolocation']});const fixtures=await installFixtures(context,'employee');const page=await context.newPage();page.setDefaultTimeout(10000);const results=[];
 async function test(name,fn){try{await fn();results.push({name,pass:true})}catch(e){results.push({name,pass:false,error:e.message})}}
 await page.goto('http://localhost:8082');await page.getByRole('textbox',{name:'Username',exact:true}).fill('ux.test');await page.getByRole('textbox',{name:'Password',exact:true}).fill('synthetic');await page.getByRole('button',{name:'Log in',exact:true}).click();await page.getByRole('tab',{name:'Today',exact:true}).waitFor();
 await test('Full employee lifecycle: trip, arrival, wash, complete, cash',async()=>{
 await page.getByRole('button',{name:/Open job TF-1042/}).click();await page.getByRole('button',{name:'Start trip',exact:true}).click();await page.getByRole('dialog',{name:'Trip started',exact:true}).getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Arrived at location',exact:true}).click();await page.getByRole('dialog',{name:'Confirm arrival',exact:true}).getByRole('button',{name:'Confirm arrival',exact:true}).click();await page.getByRole('button',{name:'Start wash',exact:true}).click();await page.getByRole('button',{name:'Complete wash',exact:true}).click();await page.getByRole('dialog',{name:'Complete wash?',exact:true}).getByRole('button',{name:'Complete wash',exact:true}).click();
 const dialog=page.locator('dialog[open]');if(await dialog.count())await dialog.getByRole('button').last().click();
 await page.getByRole('button',{name:'Record cash received',exact:true}).click();await page.getByRole('textbox',{name:'Money received',exact:true}).fill('100');await page.getByRole('button',{name:'Complete payment',exact:true}).click();await page.getByRole('dialog',{name:'Payment complete',exact:true}).waitFor();const cash=fixtures.requests.find(r=>r.path.endsWith('/cash-payment'));assert.equal(cash.body.tendered_minor,10000);assert.equal(cash.body.change_minor,3000);assert(fixtures.requests.some(r=>r.path.endsWith('/complete')));await page.getByRole('dialog',{name:'Payment complete',exact:true}).getByRole('button',{name:'OK',exact:true}).click();
 });
 await test('Clock in appears before work for employees starting a shift',async()=>{
 await context.route('**/api/v1/staff/attendance/overview?*',r=>r.fulfill({json:[]}));await page.reload();const clock=page.getByRole('button',{name:'Clock in',exact:true});await clock.waitFor();const jobCard=page.getByRole('button',{name:/Open job TF-1043/});assert((await clock.boundingBox()).y<(await jobCard.boundingBox()).y);
 });
 await test('Empty jobs explain where assignments appear',async()=>{
 await context.route('**/api/v1/staff/jobs?*',r=>r.fulfill({json:{jobs:[],total:0,next_offset:null}}));await page.reload();await page.getByText('No jobs today',{exact:true}).waitFor();assert.match(await page.locator('body').innerText(),/Assigned jobs will appear here/);
 });
 await test('Booking validation retains entered details',async()=>{
 await page.getByRole('button',{name:'Book a wash',exact:true}).click();await page.getByRole('textbox',{name:'Customer name',exact:true}).fill('Test Customer');await page.getByRole('button',{name:'Review appointment',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(await page.getByRole('textbox',{name:'Customer name',exact:true}).inputValue(),'Test Customer');await page.getByRole('button',{name:'Close',exact:true}).click();
 });
 await test('Jobs error offers explicit retry',async()=>{
 await context.route('**/api/v1/staff/jobs?*',r=>r.fulfill({status:503,json:{detail:{code:'SERVICE_UNAVAILABLE',message:'Please try again.'}}}));await page.reload();await page.getByRole('tab',{name:'Jobs',exact:true}).click();await page.getByText('Jobs unavailable',{exact:true}).waitFor({timeout:20000});await page.getByRole('button',{name:'Try again',exact:true}).waitFor();
 });
 fs.writeFileSync('docs/ux-review/after/state-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));await browser.close();if(results.some(r=>!r.pass))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
