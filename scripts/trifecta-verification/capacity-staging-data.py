import asyncio,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/scripts'),str(ROOT/'backend')]
from security_staging_api import configure
settings=configure()
from security_staging_probe import Probe
from app.core.database import create_engine,create_session_factory
from app.models.entities import Booking,Job,Payment,Business,NotificationOutbox
from sqlalchemy import select
import httpx
async def main():
 engine=create_engine(settings);sessions=create_session_factory(engine);proof={'records':[],'capacity':[]}
 async with sessions() as db:
  assert all(b.name.startswith('Synthetic') for b in await db.scalars(select(Business)))
  for row in json.loads((ROOT/'docs/double-booking-capacity/staging-browser-results.json').read_text()):
   for receipt in [*row['originals'],row['extra']]:
    b=await db.get(Booking,uuid.UUID(receipt['id']));j=await db.get(Job,uuid.UUID(receipt['job_id']));p=await db.scalar(select(Payment).where(Payment.booking_id==b.id))
    assert b.status=='confirmed' and j.status=='assigned' and b.version==1 and p.amount_minor==b.total_amount_minor and p.status=='unpaid'
    proof['records'].append({'role':row['role'],'booking_id':str(b.id),'status':b.status,'version':b.version,'payment':p.status,'amount_minor':p.amount_minor})
 probe=Probe(ROOT/'docs/double-booking-capacity/staging-auth.json')
 async with httpx.AsyncClient(base_url='http://localhost:8004',timeout=60) as client:
  for i,role in enumerate(['employee','manager','admin']):
   auth=await probe.login(role);token=auth['access_token']
   if role!='employee':
    factor=probe.config['factors'][role]
    r,_=await probe.verify(token,factor['id'],factor['secret']);assert r.status_code==200;token=r.json()['access_token']
   headers={'Authorization':'Bearer '+token}
   async def post(body):return await client.post('/api/v1/staff/calendar-bookings',json=body,headers={**headers,'Idempotency-Key':str(uuid.uuid4())})
   cat=(await client.get('/api/v1/staff/calendar-bookings/catalogue',headers=headers)).json();s=next(s for s in cat['services'] if s['customer_bookable']);price=s['prices'][0];day=f'2038-03-{10+i:02d}'
   body={'date':day,'time':'09:00','contact':{'first_name':'Synthetic multivehicle race','phone':'+971500000000'},'location':{'written_address':'Synthetic race test villa'},'vehicles':[{'service_id':s['id'],'vehicle_type':price['vehicle_type']}]*2,'expected_amount_minor':price['price_minor']*2,'policy_revision':cat['policy_revision'],'policy_delivery':'provided'}
   # Management can access two synthetic teams; occupy one before the race.
   if role!='employee':assert (await post(body)).status_code==201
   raced=await asyncio.gather(post(body),post(body));assert sorted(r.status_code for r in raced)==[201,409],[(r.status_code,r.text)for r in raced]
   partial=await post({**body,'time':'11:00'});assert partial.status_code==409
   query=[('date',day),('service_id',s['id']),('service_id',s['id'])]
   available=(await client.get('/api/v1/staff/calendar-bookings/availability',params=query,headers=headers)).json()
   assert not any(s['time'] in ['09:00:00','11:00:00','19:00:00'] for s in available['slots'])
   close=await post({**body,'time':'19:00'});assert close.status_code==409
   invalid=await post({**body,'capacity_exception':True});assert invalid.status_code==422
   proof['capacity'].append({'role':role,'date':day,'concurrent_statuses':sorted(r.status_code for r in raced),'partial_overlap':partial.status_code,'closing_time':close.status_code,'override_flag':invalid.status_code})
   print(role+' staging duration/race PASS',flush=True)
 await probe.client.aclose();await engine.dispose()
 (ROOT/'docs/double-booking-capacity/staging-data-results.json').write_text(json.dumps(proof,indent=2))
asyncio.run(main())
