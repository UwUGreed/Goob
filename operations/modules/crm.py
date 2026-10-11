def read(db, tenant):
    return {'customers':[dict(r) for r in db.execute('SELECT * FROM customers WHERE tenant=?',(tenant,))], 'equipment':[dict(r) for r in db.execute('SELECT * FROM equipment WHERE tenant=?',(tenant,))]}
