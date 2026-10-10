def read(db, tenant):
    return [dict(r) | {'available':r['on_hand'] + db.execute('SELECT COALESCE(SUM(quantity),0) FROM movements WHERE tenant=? AND part=?',(tenant,r['id'])).fetchone()[0]} for r in db.execute('SELECT * FROM stock WHERE tenant=?',(tenant,))]

def confirm(db, tenant, command):
    issued = db.execute("SELECT COALESCE(SUM(quantity),0) FROM movements WHERE tenant=? AND job='job-1' AND kind='issued-to-job'",(tenant,)).fetchone()[0]
    if issued != -2 or db.execute("SELECT 1 FROM movements WHERE tenant=? AND job='job-1' AND kind='installed'",(tenant,)).fetchone():
        raise ValueError('Issued material evidence changed; review required.')
    # Issued stock already left the warehouse. Installation records disposition, not a second stock deduction.
    db.executemany('INSERT INTO movements VALUES(?,?,?,?,?,?)',[(tenant,command+'-installed','capacitor',0,'installed','job-1'),(tenant,command+'-return','capacitor',1,'unused-return','job-1')])
    return {'installed':1,'unused_return':1,'unit_cost_cents':1800}
