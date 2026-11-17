const {chromium}=require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict');
const c=JSON.parse(fs.readFileSync('tmp/security-staging.json'));
assert.equal(c.project_ref,'mgfzfgvlrxwyyftwukwf');
const out='docs/double-booking-capacity';
function totp(secret){let bits='';for(const v of secret.replace(/=+$/,''))bits+='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'.indexOf(v).toString(2).padStart(5,'0');const bytes=[];for(let i=0;i+8<=bits.length;i+=8)bytes.push(parseInt(bits.slice(i,i+8),2));const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));const h=crypto.createHmac('sha1',Buffer.from(bytes)).update(counter).digest(),o=h[19]&15;return String((h.readUInt32BE(o)&0x7fffffff)%1000000).padStart(6,'0')}
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});const results=[];
 try{for(const [index,role]of ['employee','manager','admin'].entries()){
 const context=await browser.newContext({viewport:{width:390,height:900}}),p=await context.newPage();p.setDefaultTimeout(60000);let token='';
 p.on('request',r=>{if(r.url().startsWith('http://localhost:8004'))token=r.headers().authorization||token});
 const button=name=>p.getByRole('button',{name,exact:true});
 await p.goto('http://localhost:8084');await p.getByLabel('Username',{exact:true}).fill(role+'@'+c.email_domain);await p.getByLabel('Password',{exact:true}).fill(c.passwords[role]);await button('Log in').click();
 if(role!=='employee'){await p.getByLabel('Authenticator code',{exact:true}).fill(totp(c.factors[role].secret));await button('Verify code').click()}
 await p.getByRole('tab',{name:'Jobs',exact:true}).waitFor();assert(token);
 async function request(path,body){const r=await p.request[body?'post':'get']('http://localhost:8004/api/v1/staff/'+path,{headers:{Authorization:token,'Idempotency-Key':crypto.randomUUID()},...(body?{data:body}:{})});return {status:r.status(),body:await r.json()}}
 await p.getByRole('tab',{name:'Jobs',exact:true}).click();await p.getByRole('tab',{name:'Calendar',exact:true}).click();await button('+ Book a Wash').click();await p.getByLabel('Appointment date',{exact:true}).fill('2026-11-30');
 const cat=(await request('calendar-bookings/catalogue')).body,s=cat.services.find(x=>x.customer_bookable),price=s.prices[0];
 for(let n=0;n<7;n++){if(n)await button('Add another vehicle').click();await p.getByRole('button',{name:s.name,exact:true}).last().click();await p.getByRole('button',{name:price.vehicle_type.replaceAll('_',' '),exact:true}).last().click()}
 await p.getByText('No available times for this date',{exact:true}).waitFor();assert.equal(await p.getByRole('button',{name:/^\d{1,2}:\d{2} [AP]M$/}).count(),0);await p.getByText('No available times for this date',{exact:true}).scrollIntoViewIfNeeded();await p.screenshot({path:`${out}/${role}-empty.png`});
 for(let n=0;n<6;n++)await p.getByRole('button',{name:'Remove vehicle',exact:true}).last().click();await p.getByRole('button',{name:'9:00 AM',exact:true}).waitFor();
 results.push({role,no_times_message:true,no_time_buttons:true,vehicle_change_recalculates:true});console.log(role+' empty/recalculation PASS');await context.close();
 }}finally{fs.writeFileSync(out+'/staging-empty-results.json',JSON.stringify(results,null,2));await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
