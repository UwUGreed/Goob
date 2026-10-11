def balance(db, tenant, agreement):
    return db.execute('SELECT COALESCE(SUM(amount),0) FROM benefits WHERE tenant=? AND agreement=?',(tenant,agreement)).fetchone()[0]

def eligibility(db, tenant, job, day):
    matches = db.execute('SELECT * FROM agreements WHERE tenant=? AND equipment=? AND property=? AND trade=? AND start<=? AND "end">=?',(tenant,job['equipment'],job['property'],job['trade'],day,day)).fetchall()
    if len(matches) != 1:
        raise ValueError('Coverage missing, expired or overlapping; staff review required.')
    agreement = dict(matches[0])
    if balance(db,tenant,agreement['id']) < 1:
        raise ValueError('No remaining covered maintenance visits.')
    return agreement

def consume(db, tenant, agreement, command):
    if balance(db, tenant, agreement) < 1:
        raise ValueError('Benefit already consumed.')
    db.execute('INSERT INTO benefits VALUES(?,?,?,?,?)',(tenant,command,agreement,-1,'Confirmed job-1 maintenance'))

def read(db, tenant):
    return {'agreements':[dict(r) | {'remaining':balance(db,tenant,r['id'])} for r in db.execute('SELECT * FROM agreements WHERE tenant=?',(tenant,))], 'ledger':[dict(r) for r in db.execute('SELECT * FROM benefits WHERE tenant=?',(tenant,))]}
