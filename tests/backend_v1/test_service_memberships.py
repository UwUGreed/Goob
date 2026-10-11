"""Membership coverage, billing, ledger reconciliation and inventory guards."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from operations.domain import desk, service_memberships
from operations.domain.common import Actor
from operations.persistence.database import sessions
from operations.persistence.models import DispatchTechnician, Record, now


def test_explicit_discount_rules_and_rounding():
    lines=[{'description':'Labor','kind':'labor','unit_cents':18000,'quantity':1,'discount_eligible':True},{'description':'Part','kind':'material','unit_cents':4500,'quantity':1}]
    rules=[{'kind':'labor','service':'repair','percent':15}]
    assert service_memberships.charge_proposal(lines,rules,'repair')['totalCents']==19800
    assert service_memberships.charge_proposal(lines,rules,'maintenance')['totalCents']==22500
    assert service_memberships.charge_proposal([lines[0]|{'unit_cents':1}], [{'kind':'labor','service':'repair','percent':50}], 'repair')['totalCents']==0


def setup(api,engine):
    with sessions(engine)() as db:
        actor=Actor(api.tenant,'owner','owner',('a','b'))
        warehouse=desk.create(db,actor,'locations','a','Warehouse',{'location_type':'warehouse'})
        truck=desk.create(db,actor,'locations','a','H-01',{'location_type':'truck'})
        db.add(DispatchTechnician(tenant_id=api.tenant,id='hvac',branch_id='a',name='HVAC Technician',trade='HVAC',location_id=truck.id,node='0-3',status='Available'))
        desk.run(db,actor,{'type':'stock','item':{'id':str(uuid4()),'part':'Run capacitor','sku':str(uuid4()),'trade':'HVAC','truck':'H-01','quantity':4,'threshold':1}})
        from scripts.seed_service_memberships import seed
        seed(db,actor)
        db.commit()
    def change(body,status=200,key=None,role='owner'):
        r=api.client.post('/api/dispatch',json=body,headers=api.headers(role,key))
        assert r.status_code==status,r.text
        return r.json().get('state')
    s=api.client.get('/api/dispatch',headers=api.headers()).json()['state']
    return s,change


def test_connected_membership_and_inventory(api,engine):
    s,change=setup(api,engine)
    c=next(c for c in s['customers'] if c['name']=='Alex Morgan')
    home=next(p for p in s['properties'] if p['customerId']==c['id'] and p['name']=='Home')
    rental=next(p for p in s['properties'] if p['customerId']==c['id'] and p['name']=='Rental')
    repair=next(j for j in s['records'] if j['title']=='Covered HVAC repair')
    maintenance=next(j for j in s['records'] if j['title']=='Seasonal HVAC maintenance')
    uncovered=next(j for j in s['records'] if j['title']=='Rental HVAC inspection')
    m=s['memberships'][0]
    assert repair['coverage']['eligible'] and not uncovered['coverage']['eligible']
    assert repair['chargeProposal']['totalCents']==19800 and m['remaining']==2
    change({'type':'membership','operation':'enroll','values':{'planId':m['planId'],'customerId':c['id'],'propertyId':rental['id'],'equipmentId':m['equipmentId'],'starts':now().date().isoformat()}},422)
    change({'type':'membership','operation':'cancel','values':{'id':m['id'],'revision':m['revision']}},403,role='viewer')
    stock=next(i for i in s['stock'] if i['truck']=='H-01')
    sku,loc=stock['skuId'],stock['locationId']
    warehouse=next(l for l in s['locations'] if l['type']=='warehouse')
    key=str(uuid4())
    movement={'type':'movement','values':{'action':'receive','sku_id':sku,'location_id':warehouse['id'],'quantity':3,'reason':'Shipment'}}
    s=change(movement,key=key)
    assert change(movement,key=key)['stock']==s['stock']
    s=change({'type':'movement','values':{'action':'transfer','sku_id':sku,'location_id':warehouse['id'],'destination_id':loc,'quantity':2,'reason':'Truck restock'}})
    assert next(i for i in s['stock'] if i['locationId']==loc)['quantity']==6
    change({'type':'movement','values':{'action':'adjust','sku_id':sku,'location_id':loc,'quantity':-99,'reason':'Invalid'}},409)
    day=now().date().isoformat()
    from datetime import datetime, timezone
    start=int(datetime.fromisoformat(day+'T10:00:00+00:00').timestamp()*1000)
    def finish(j,offset):
        slot={'date':day,'start':start+offset,'end':start+offset+3600000,'travelStart':start+offset-600000}
        change({'type':'assign','techId':'hvac','jobId':j['id'],'slot':slot})
        for kind in ['start','arrive','work']:
            change({'type':kind,'techId':'hvac'})
        return change({'type':'complete','techId':'hvac'})
    s=finish(repair,0)
    assert s['memberships'][0]['remaining']==2
    change({'type':'complete','techId':'hvac'},409)
    assert sum(m['quantity'] for m in s['movements'] if m['jobId']==repair['id'] and m['kind']=='issue')==1
    s=finish(maintenance,7200000)
    assert s['memberships'][0]['remaining']==1
    # Repeated reconciliation never consumes twice, regardless of request key.
    with sessions(engine)() as db:
        actor=Actor(api.tenant,'owner','owner',('a','b'))
        j=db.get(Record,(api.tenant,maintenance['id']))
        service_memberships.reconcile(db,actor,j,True,'Repeated completion')
        db.commit()
    s=change({'type':'job-review','values':{'id':maintenance['id'],'operation':'reverse','reason':'Incorrect maintenance completion'}})
    assert s['memberships'][0]['remaining']==2
    assert len(s['memberships'][0]['history'])==3
    change({'type':'job-review','values':{'id':repair['id'],'operation':'charges','proposal':{'totalCents':1,'lines':[]}}},409)
    s=change({'type':'job-review','values':{'id':repair['id'],'operation':'charges','proposal':repair['chargeProposal']}})
    assert next(j for j in s['records'] if j['id']==repair['id'])['appliedCharge']['totalCents']==19800
    m=s['memberships'][0]
    s=change({'type':'membership','operation':'renew','values':{'id':m['id'],'revision':m['revision']}})
    assert s['memberships'][0]['remaining']==2  # future grant never changes current term
    m=s['memberships'][0]
    s=change({'type':'membership','operation':'cancel','values':{'id':m['id'],'revision':m['revision']}})
    assert s['memberships'][0]['status']=='canceled'
    assert not next(j for j in s['records'] if j['id']==repair['id'])['coverage']['eligible']

def test_membership_status_dates_equipment_and_plan_snapshots(api,engine):
    s,change=setup(api,engine)
    m=s['memberships'][0]
    repair=next(j for j in s['records'] if j['title']=='Covered HVAC repair')
    s=change({'type':'membership','operation':'edit','values':{'id':m['id'],'revision':m['revision'],'status':'pending','paymentStatus':'paid'}})
    assert s['memberships'][0]['paymentStatus']=='paid'
    assert not next(j for j in s['records'] if j['id']==repair['id'])['coverage']['eligible']
    m=s['memberships'][0]
    s=change({'type':'membership','operation':'edit','values':{'id':m['id'],'revision':m['revision'],'status':'active','paymentStatus':'unpaid'}})
    assert next(j for j in s['records'] if j['id']==repair['id'])['coverage']['eligible']
    plan=s['plans'][0]
    s=change({'type':'membership','operation':'plan','values':plan|{'name':'Changed rules','visits':5,'discountRules':[{'kind':'labor','service':'repair','percent':50}]}})
    assert next(j for j in s['records'] if j['id']==repair['id'])['chargeProposal']['totalCents']==19800
    expired=repair|{'serviceDate':(now().date()+timedelta(days=800)).isoformat()}
    s=change({'type':'edit','job':expired})
    assert not next(j for j in s['records'] if j['id']==repair['id'])['coverage']['eligible']
    change({'type':'membership','operation':'plan','values':plan|{'discountRules':[{'kind':'labor','service':'repair','percent':101}]}},422)
    with sessions(engine)() as db:
        actor=Actor(api.tenant,'owner','owner',('a','b'))
        j=db.get(Record,(api.tenant,repair['id']))
        j.data=j.data|{'service_date':now().date().isoformat(),'billing_mode':'membership'}
        from operations.domain import agreements,billing
        coverage=agreements.coverage(db,actor,j)
        assert billing.review(j,coverage,[])['approved_cents']==19800
        assert agreements.balance(db,actor.tenant,m['id'])==2
        # A second piece of equipment at the covered property is independently uncovered.
        unit=desk.create(db,actor,'equipment','a','Second system',{'trade':'HVAC'},parent_id=j.property_id)
        j.equipment_id=unit.id
        assert not service_memberships.eligibility(db,actor,j)['eligible']
        db.rollback()
