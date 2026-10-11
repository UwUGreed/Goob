import json
import uuid
from datetime import datetime, timezone
from operations.modules import agreements, inventory, billing
from operations.modules.registry import guard

def now():
    return datetime.now(timezone.utc).isoformat()

def job(db, tenant):
    result = db.execute("SELECT * FROM jobs WHERE tenant=? AND id='job-1'",(tenant,)).fetchone()
    if not result:
        raise ValueError('Job unavailable in this tenant.')
    return dict(result)

def propose(db, tenant, role):
    guard(db,tenant,role,'workflow','propose')
    current = job(db,tenant)
    if current['status'] == 'Confirmed':
        raise ValueError('Work already confirmed.')
    agreement = agreements.eligibility(db,tenant,current,now()[:10])
    payload = {'provider':'deterministic demo adapter','completed_work':'Maintenance on upstairs heat pump','installed':1,'unused_return':1,'agreement':agreement['id'],'billing':billing.review(agreement['discount'])}
    identifier = str(uuid.uuid4())
    db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',(tenant,identifier,current['id'],current['revision'],'pending',json.dumps(payload)))
    return {'id':identifier, **payload}

def approve(db, tenant, role, identifier):
    db.execute('BEGIN')
    try:
        guard(db,tenant,role,'workflow','approve')
        proposal = db.execute('SELECT * FROM proposals WHERE tenant=? AND id=?',(tenant,identifier)).fetchone()
        if not proposal:
            raise ValueError('Proposal unavailable in this tenant.')
        if proposal['state'] == 'approved':
            db.commit()
            return {'id':identifier,'state':'approved','replayed':True}
        current = job(db,tenant)
        if current['revision'] != proposal['revision']:
            raise ValueError('Proposal is stale. Prepare a fresh proposal.')
        agreement = agreements.eligibility(db,tenant,current,now()[:10])
        payload = json.loads(proposal['payload'])
        snapshot = billing.review(agreement['discount'])
        if agreement['id'] != payload['agreement'] or snapshot != payload['billing']:
            raise ValueError('Coverage or billing changed; prepare a fresh proposal.')
        materials = inventory.confirm(db,tenant,identifier)
        agreements.consume(db,tenant,agreement['id'],identifier)
        billing.approve(db,tenant,identifier,snapshot)
        db.execute("UPDATE jobs SET revision=revision+1,status='Confirmed' WHERE tenant=? AND id='job-1'",(tenant,))
        db.execute("UPDATE proposals SET state='approved' WHERE tenant=? AND id=?",(tenant,identifier))
        after = {'job_status':'Confirmed','materials':materials,'invoice':snapshot,'benefit_consumed':1}
        db.execute('INSERT INTO audit VALUES(?,?,?,?,?,?,?,?)',(tenant,identifier,role,now(),'Employee confirmed proposed work, material disposition and billing corrections','employee approval of deterministic proposal',json.dumps(current),json.dumps(after)))
        db.commit()
        return {'id':identifier,'state':'approved','replayed':False}
    except Exception:
        db.rollback()
        raise
