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
 const cat=(await request('calendar-bookings/catalogue')).body,s=cat.services.find(x=>x.customer_bookable),price=s.prices[0],day=`2026-12-0${1+index}`;
 await p.getByRole('tab',{name:'Jobs',exact:true}).click();await p.getByRole('tab',{name:'Calendar',exact:true}).click();await button('+ Book a Wash').click();await p.getByLabel('Appointment date',{exact:true}).fill(day);await button(s.name).click();await button(price.vehicle_type.replaceAll('_',' ')).click();await button('9:00 AM').click();
 for(const [label,value]of [['Customer name','Synthetic stale selection'],['Customer phone','+971500000000'],['Written service address','Synthetic stale selection villa']])await p.getByLabel(label,{exact:true}).fill(value);await button('I provided the policies to the customer').click();await button('Review appointment').click();
 const body={date:day,time:'09:00',contact:{first_name:'Synthetic competing booking',phone:'+971500000000'},location:{written_address:'Synthetic competing villa'},vehicles:[{service_id:s.id,vehicle_type:price.vehicle_type}],expected_amount_minor:price.price_minor,policy_revision:cat.policy_revision,policy_delivery:'provided'};
 for(let n=0;n<10;n++){const r=await request('calendar-bookings',body);if(r.status===409)break;assert.equal(r.status,201)}
 const response=p.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/staff/calendar-bookings'&&r.request().method()==='POST');await button('Confirm booking').click();assert.equal((await response).status(),409);
 const error=p.getByText('This time is no longer available. Please choose another available time.',{exact:true});await error.waitFor();await p.getByText('Checking team capacity…',{exact:true}).waitFor({state:'hidden'});await button('9:00 AM').waitFor({state:'hidden'});await error.scrollIntoViewIfNeeded();await p.screenshot({path:`${out}/${role}-stale.png`});
 results.push({role,stale_submission_status:409,recovery_message:true,occupied_time_removed:true});console.log(role+' stale selection PASS');await context.close();
 }}finally{fs.writeFileSync(out+'/staging-stale-results.json',JSON.stringify(results,null,2));await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
