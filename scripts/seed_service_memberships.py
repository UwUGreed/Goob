"""Repeatable connected demo. Only the explicitly demo-labelled account is seeded.
Existing records are retained; stable metadata keys prevent duplicates. No resets.
"""
from datetime import timedelta
from sqlalchemy import select
from operations.domain import desk, service_memberships
from operations.domain.common import Problem, event
from operations.domain.identity import actor_for
from operations.persistence.database import engine_for, sessions
from operations.persistence.models import Record, PortalUser, ServicePlan, Agreement, now


def seed(db, actor):
    branch = actor.branches[0]
    def one(key,kind,name,data,**links):
        r=db.scalar(select(Record).where(Record.tenant_id==actor.tenant,Record.portal_meta['demoKey'].astext==key))
        if not r:
            r=desk.create(db,actor,kind,branch,name,data,**links)
            r.portal_meta={'demoKey':key}
        return r
    c=one('alex-customer','customers','Alex Morgan',{'email':'alex@example.test','phone':'555-0108','account_type':'residential'})
    home=one('alex-home','properties','Home',{'address':'82 Maple Avenue'},parent_id=c.id)
    rental=one('alex-rental','properties','Rental',{'address':'210 Cedar Street'},parent_id=c.id)
    unit=one('alex-hvac','equipment','Home heat pump',{'trade':'HVAC','model':'Demo heat pump','serial':'FICTIONAL-HVAC-01'},parent_id=home.id)
    one('alex-rental-hvac','equipment','Rental air conditioner',{'trade':'HVAC','model':'Demo AC'},parent_id=rental.id)
    if not c.data.get('primary_property_id'):
        c.data=c.data|{'primary_property_id':home.id}
    plan=db.scalar(select(ServicePlan).where(ServicePlan.tenant_id==actor.tenant,ServicePlan.name=='Home HVAC Care'))
    if not plan:
        service_memberships.run(db,actor,{'operation':'plan','values':{'name':'Home HVAC Care','trades':['HVAC'],'termDays':365,'visits':2,'discountRules':[{'kind':'labor','service':'repair','percent':15}]}})
        plan=db.scalar(select(ServicePlan).where(ServicePlan.tenant_id==actor.tenant,ServicePlan.name=='Home HVAC Care'))
    membership=db.scalar(select(Agreement).where(Agreement.tenant_id==actor.tenant,Agreement.equipment_id==unit.id))
    if not membership:
        service_memberships.run(db,actor,{'operation':'enroll','values':{'planId':plan.id,'customerId':c.id,'propertyId':home.id,'equipmentId':unit.id,'starts':(now().date()-timedelta(days=1)).isoformat()}})
    for key,title,site,service,part,lines in [
        ('alex-covered-repair','Covered HVAC repair',home,'repair','Run capacitor',[{'description':'Eligible HVAC labor','kind':'labor','quantity':1,'unit_cents':18000,'discount_eligible':True},{'description':'Separately billable part','kind':'material','quantity':1,'unit_cents':4500,'discount_eligible':False}]),
        ('alex-maintenance','Seasonal HVAC maintenance',home,'maintenance','No parts required',[]),
        ('alex-uncovered-repair','Rental HVAC inspection',rental,'repair','No parts required',[{'description':'Inspection labor','kind':'labor','quantity':1,'unit_cents':18000,'discount_eligible':True}]),
    ]:
        j=db.scalar(select(Record).where(Record.tenant_id==actor.tenant,Record.portal_meta['demoKey'].astext==key))
        if not j:
            from operations.persistence.models import uid
            desk.run(db,actor,{'type':'create','job':{'id':'job-'+uid(),'customerId':c.id,'propertyId':site.id,'title':title,'description':'Connected fictional membership demo. Coverage follows selected property and equipment.','address':site.data['address'],'trade':'HVAC','service':service,'serviceDate':now().date().isoformat(),'part':part,'node':'3-1','time':'Today','urgent':False,'lines':lines}})
            j=db.scalar(select(Record).where(Record.tenant_id==actor.tenant,Record.customer_id==c.id,Record.name==title))
            j.portal_meta=j.portal_meta|{'demoKey':key}
    # One-time classification of records created by the existing verification script.
    # Presentation uses stored metadata, never name-based heuristics.
    for r in db.scalars(select(Record).where(Record.tenant_id==actor.tenant,Record.kind.in_(['customers','jobs']))):
        if r.name=='Verification sink visit' or r.kind=='customers' and r.name.startswith('Verification '):
            if not r.portal_meta.get('verification'):
                r.portal_meta=r.portal_meta|{'verification':True}
                event(db,actor,r.branch_id,'portal.fixture.classified',r.id,{'verification':True,'source':'portal-cloud.spec.ts'})
    jobs=db.scalars(select(Record).where(Record.tenant_id==actor.tenant,Record.kind=="jobs").order_by(Record.created_at,Record.id)).all()
    for n,j in enumerate(jobs,2001):
        if not j.portal_meta.get("displayNumber"):
            j.portal_meta=j.portal_meta|{"displayNumber":str(n)}
    db.flush()


def main():
    with sessions(engine_for())() as db:
        u=db.scalar(select(PortalUser).where(PortalUser.identifier=='goob',PortalUser.demo.is_(True)))
        if not u:
            raise Problem('Provision the dedicated goob demo account first.')
        actor=actor_for(db,u.tenant_id,u.subject)
        # Same conservative lock as API commands keeps provisioning atomic.
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:tenant,0))'),{'tenant':actor.tenant})
        seed(db,actor)
        db.commit()
    print('Connected membership demo retained/created; existing records and balances preserved.')

if __name__=='__main__':
    main()
