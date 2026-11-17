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
 const cat=(await request('calendar-bookings/catalogue')).body,s=cat.services.find(x=>x.customer_bookable),price=s.prices[0],day=`2026-11-${24+index}`;
 const body={date:day,time:'09:00',contact:{first_name:'Synthetic capacity verification',phone:'+971500000000'},location:{written_address:'Synthetic capacity verification villa'},vehicles:[{service_id:s.id,vehicle_type:price.vehicle_type}],expected_amount_minor:price.price_minor,policy_revision:cat.policy_revision,policy_delivery:'provided'};
 const receipts=[];for(let n=0;n<10;n++){const r=await request('calendar-bookings',body);if(r.status===409)break;assert.equal(r.status,201,JSON.stringify(r));receipts.push(r.body)}
 const rejected=await request('calendar-bookings',body);assert.equal(rejected.status,409);
 let slots=(await request(`calendar-bookings/availability?date=${day}&service_id=${s.id}`)).body.slots;assert(!slots.some(x=>x.time==='09:00:00'));
 await p.getByRole('tab',{name:'Jobs',exact:true}).click();await p.getByRole('tab',{name:'Calendar',exact:true}).click();await button('+ Book a Wash').click();
 await p.getByLabel('Appointment date',{exact:true}).fill(day);await button(s.name).click();await button(price.vehicle_type.replaceAll('_',' ')).click();
 await p.getByText('Checking team capacity…',{exact:true}).waitFor({state:'hidden'});assert.equal(await button('9:00 AM').count(),0);await p.screenshot({path:`${out}/${role}-normal.png`});
 await button('Close').click();await p.getByRole('button',{name:new RegExp('^'+day)}).click();await p.getByRole('button',{name:/^Double-book this time · 9:00 AM/}).first().click();
 await button(s.name).click();await button(price.vehicle_type.replaceAll('_',' ')).click();for(const [label,value]of [['Customer name','Synthetic deliberate overlap'],['Customer phone','+971500000000'],['Written service address','Synthetic overlap villa']])await p.getByLabel(label,{exact:true}).fill(value);
 await button('I provided the policies to the customer').click();await button('Review appointment').click();await button('Double-book this time').click();await p.getByRole('alertdialog',{name:'Double-book this time?',exact:true}).waitFor();await p.screenshot({path:`${out}/${role}-confirmation.png`});
 const response=p.waitForResponse(r=>/\/calendar-bookings\/[^/]+\/double-book$/.test(new URL(r.url()).pathname)&&r.request().method()==='POST');await button('Confirm double-booking').click();const created=await response;assert.equal(created.status(),201,await created.text());const extra=await created.json();await p.getByText('Both appointments remain independently confirmed.',{exact:true}).waitFor();
 const cal=await request(`jobs/calendar?start_date=${day}&end_date=${day}`);assert.equal(cal.status,200);const jobs=cal.body.jobs;assert(jobs.some(x=>x.job_id===extra.job_id&&x.status==='assigned'));for(const r of receipts)assert(jobs.some(x=>x.job_id===r.job_id&&x.status==='assigned'));
 results.push({role,day,normal_api:rejected.status,occupied_time_hidden:true,explicit_api:created.status(),originals:receipts,extra,calendar_jobs:jobs.map(x=>({job_id:x.job_id,status:x.status}))});fs.writeFileSync(out+'/staging-browser-results.json',JSON.stringify(results,null,2));console.log(role+' PASS');await context.close();
 }}finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
