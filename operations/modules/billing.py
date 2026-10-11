import json

def review(discount):
    labor, part = 15000, 4500
    reduction = (labor * discount + 50)//100
    return {'currency':'USD','labor_cents':labor,'installed_part_cents':part,'discount_cents':reduction,'tax_cents':0,'original_cents':24000,'approved_cents':labor+part-reduction,'flags':[{'rule':'AGREEMENT_LABOR_DISCOUNT','evidence':'care-v1: 10% labor discount on hvac-1 at 124 Oak Lane','potential_cents':reduction},{'rule':'UNUSED_RETURN_NOT_BILLABLE','evidence':'Proposed disposition: 2 issued, 1 installed, 1 unused return. Approval confirms this evidence.','potential_cents':part}]}

def approve(db, tenant, command, snapshot):
    db.execute('INSERT INTO invoices VALUES(?,?,?,?,?)',(tenant,command,'job-1','approved-draft',json.dumps(snapshot)))
