// Browser-only synthetic API fixtures. Never imported by application code.
const day = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Dubai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const at = hour => `${day}T${hour}:00:00+04:00`;
const job = {id:'job-1',booking_id:'booking-1',booking_reference:'TF-1042',version:1,assigned_staff_id:'staff-1',assigned_staff_name:'Alex Morgan',assigned_team_id:'team-1',assigned_team_name:'Team One',assignment_source:'manual',assigned_at:at('08'),assigned_by_staff_id:'manager-1',expected_duration_minutes:60,status:'assigned',scheduled_start:at('10'),scheduled_end:at('11'),en_route_at:null,estimated_arrival_at:null,arrived_at:null,started_at:null,completed_at:null,customer_name:'Sam Taylor',customer_phone:'+971500000000',customer_email:'sam@example.test',written_address:'Villa 12, Khalifa City, Abu Dhabi',location_url:'https://maps.google.com',latitude:null,longitude:null,location_instructions:'Use the side gate',payment_status:'unpaid',payment_method:null,total_amount_minor:7000,currency_code:'AED',vehicles:[{make:'Toyota',model:'Camry',year:2024,vehicle_type:'sedan',colour:'White',plate_number:'TEST 123',notes:null,service_name:'Standard',amount_minor:7000}],timeline:[],consumption:null,direct_expenses:[],direct_expenses_total_minor:0};
const jobs=[job,{...job,id:'job-2',booking_id:'booking-2',booking_reference:'TF-1043',customer_name:'ليلى أحمد',scheduled_start:at('13'),scheduled_end:at('14'),status:'in_progress',started_at:at('13')},{...job,id:'job-3',booking_id:'booking-3',booking_reference:'TF-1044',customer_name:'Jamie Lee',scheduled_start:at('16'),scheduled_end:at('17'),assigned_team_id:null,assigned_team_name:null,assigned_staff_id:null,assigned_staff_name:null}];
const profile = role => ({id:'staff-1',display_name:'Alex Morgan',username:'ux.test',phone:'+971500000001',role,is_active:true,must_change_password:false,teams:[{id:'team-1',name:'Team One'}]});
const settings={currency_code:'AED',timezone:'Asia/Dubai',slot_duration_minutes:60,turnaround_buffer_minutes:15,operating_hours:Array.from({length:7},(_,weekday)=>({weekday,is_open:true,opening_time:'08:00:00',closing_time:'20:00:00'})),cancellation_cutoff_hours:4,minimum_mobile_booking_minor:0,automatic_inventory_deduction_enabled:true};
const catalogue={services:[{id:'service-1',name:'Standard',description:'Exterior and interior clean',customer_bookable:true,is_active:true,sort_order:1,expected_duration_minutes:60,prices:[{vehicle_type:'sedan',price_minor:7000},{vehicle_type:'suv',price_minor:10000}],addons:[]}],addons:[],settings,policy_revision:'ux-fixture-v1',public_web_url:'https://example.test'};
async function installFixtures(context, role) {
 const requests=[],unknown=[];
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),p=url.pathname;
  if(url.hostname==='localhost'||url.hostname==='127.0.0.1') return route.continue();
  let data;
  if(p.includes('/auth/v1/')) {
   if(p.endsWith('/token')) data={access_token:`eyJhbGciOiJIUzI1NiJ9.${Buffer.from(JSON.stringify({sub:'staff-1',exp:Math.floor(Date.now()/1000)+7200,aal:'aal2'})).toString('base64url')}.fixture`,refresh_token:'synthetic-refresh',token_type:'bearer',expires_in:7200,user:{id:'staff-1',aud:'authenticated',role:'authenticated',email:'ux@example.test',app_metadata:{},user_metadata:{},created_at:new Date().toISOString()}};
   else if(p.endsWith('/user')) data={id:'staff-1',aud:'authenticated',role:'authenticated',factors:[]};
   else data={};
  } else if(p.startsWith('/api/v1/')) {
   requests.push({method:request.method(),path:p,body:request.postDataJSON()});
   if(p.endsWith('/context')) data={staff_id:'staff-1',business_id:'business-1',business_name:'Trifecta',role,timezone:'Asia/Dubai',display_name:'Alex Morgan',username:'ux.test',phone:null,must_change_password:false};
   else if(p.endsWith('/sync-state')) data={jobs:1,workforce:1,schedule:1,finance:1,inventory:1,customers:1};
   else if(p.endsWith('/dashboard')) data={date:day,currency_code:'AED',metrics:[{key:'jobs',label:'Appointments today',value:3},{key:'completed',label:'Completed',value:0},{key:'active',label:'In progress',value:1},{key:'unassigned',label:'Unassigned',value:1}],attention:[{kind:'unassigned_jobs',count:1,label:'Unassigned appointments'}],active_jobs:[jobs[1]]};
   else if(p.endsWith('/jobs/calendar')) data={jobs:jobs.map(j=>({job_id:j.id,version:1,can_double_book:true,scheduled_start:j.scheduled_start,scheduled_end:j.scheduled_end,local_date:day,status:j.status,team_id:j.assigned_team_id,team_short_name:j.assigned_team_name,vehicle_label:'Toyota Camry',service_label:'Standard'}))};
   else if(p.endsWith('/jobs')) {const view=url.searchParams.get('view');data={jobs:view==='unassigned'?[jobs[2]]:view==='history'||view==='rescheduling'?[]:jobs,total:3,next_offset:null};}
   else if(/\/jobs\/[^/]+$/.test(p)) data=jobs.find(j=>p.endsWith('/'+j.id))||job;
   else if(p.endsWith('/quality')) data={job_id:'job-1',inspection:null,checklist:[],photos:[],issues:[],complaints:[],required_completed:0,required_total:0,before_photo_count:0,after_photo_count:0,issue_count:0,can_complete:true};
   else if(p.endsWith('/communications')) data=[];
   else if(p.endsWith('/cash-payment')) {const j=jobs.find(j=>p.includes(j.id))||job;j.payment_status='paid';const cash=request.postDataJSON();data={job:j,amount_applied_minor:7000,tendered_minor:cash.tendered_minor,change_minor:cash.change_minor};}
   else if(p.endsWith('/assignment-options')) data=[{team_id:'team-1',team_name:'Team One',status:'available',reason:null,same_day_job_count:2,assigned_minutes:120}];
   else if(p.endsWith('/reschedule-options')) data=[{team_id:'team-1',team_name:'Team One',status:'available',reason:null,same_day_job_count:2,assigned_minutes:120}];
   else if(p.endsWith('/calendar-bookings/catalogue')||p.endsWith('/catalogue')) data=catalogue;
   else if(p.endsWith('/availability')) data={slots:[{time:'15:00:00',available:true,starts_at:at('15'),ends_at:at('16')}]};
   else if(p.endsWith('/calendar-bookings')) data={job_id:'new-job',reference:'TF-TEST-1050',scheduled_start:at('15'),capacity_exception:!!request.postDataJSON()?.overlap};
   else if(/\/bookings\/[^/]+\/reschedule$/.test(p)) {data={...job,scheduled_start:at('15'),scheduled_end:at('16'),version:2};}
   else if(p.endsWith('/business-settings')) data=settings;
   else if(p.endsWith('/attendance/overview')) data=[{staff_id:'staff-1',staff_name:'Alex Morgan',shift_name:'Day shift',status:'present',clock_in_at:at('08'),clock_out_at:null,late_minutes:0}];
   else if(p.endsWith('/shift-assignments')) data=[{id:'shift-assignment-1',staff_id:'staff-1',staff_name:'Alex Morgan',start_time:'08:00:00',end_time:'18:00:00',team_name:'Team One',date:day}];
   else if(p.endsWith('/finance/cash/mine')) data={currency_code:'AED',collected_today_minor:14000,awaiting_handover_minor:7000};
   else if(p.endsWith('/profile')) data=profile(role);
   else if(p.endsWith('/users')) data=[profile('employee')];
   else if(p.endsWith('/teams')) data=[{id:'team-1',name:'Team One',is_active:true,member_count:1,jobs_today:2,active_job_reference:'TF-1043',active_job_status:'in_progress'}];
   else if(p.endsWith('/customers')) data={items:[],customers:[],total:0,next_offset:null};
   else if(p.endsWith('/reports/v2')) data={summary:{bookings:3,completed_washes:0,outstanding_minor:7000,average_booking_value_minor:7000,booked_sales_minor:21000,collected_revenue_minor:14000,currency_code:'AED'},series:[],staff_performance:[],service_mix:[],payment_mix:[],team_performance:[]};
   else if(p.endsWith('/inventory/overview')) data={active_item_count:0,low_stock_count:0,out_of_stock_count:0,needs_review_count:0,locations:[]};
   else if(p.endsWith('/loyalty/settings')) data={enabled:true,credits_required:9,reward_service_id:'service-1'};
   else if(p.endsWith('/finance/overview')) data={currency_code:'AED',booked_sales_minor:21000,collected_revenue_minor:14000,outstanding_minor:7000,expenses_minor:0,operational_profit_minor:14000,margin_percent:100,cash_pending_minor:7000,cash_short_over_minor:0,expense_categories:[],team_contributions:[],series:[]};
   else if(p.endsWith('/coupons')) data={items:[]};
   else if(p.endsWith('/finance/expenses')) data={items:[],next_cursor:null,total_minor:0};
   else if(['/complaints','/inventory/locations','/shifts','/leave','/cancellations','/attendance','/finance/cash/pending','/finance/cash/reconciliations'].some(end=>p.endsWith(end))) data=[];
   else if(p.includes('/inventory/')&&/items|attention|movements|stock/.test(p)) data={items:[],next_offset:null};
   else if(/\/jobs\/[^/]+\/(start-trip|arrive|start|complete|reschedule)$/.test(p)) {const j=jobs.find(j=>p.includes(j.id))||job;Object.assign(j,{status:p.endsWith('/start-trip')?'en_route':p.endsWith('/arrive')?'arrived':p.endsWith('/complete')?'completed':'in_progress'});data=j;}
   else if(p.endsWith('/holds')) data={hold_token:'synthetic-hold',expires_at:at('23')};
   else {data=[];unknown.push(p);}
  } else return route.abort();
  return route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(data)});
 });
 return {requests,unknown};
}
module.exports={installFixtures,day,jobs};
