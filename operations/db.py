import json
import sqlite3
from pathlib import Path
from operations.modules.registry import REGISTRY

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY, modules TEXT, pricing TEXT);
CREATE TABLE IF NOT EXISTS customers(tenant TEXT, id TEXT, name TEXT, branch TEXT, PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS equipment(tenant TEXT,id TEXT,customer TEXT,property TEXT,trade TEXT,name TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS agreements(tenant TEXT,id TEXT,equipment TEXT,property TEXT,trade TEXT,start TEXT,end TEXT,discount INTEGER,terms TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS benefits(tenant TEXT,id TEXT,agreement TEXT,amount INTEGER,source TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS stock(tenant TEXT,id TEXT,name TEXT,on_hand INTEGER,cost INTEGER,price INTEGER,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS movements(tenant TEXT,id TEXT,part TEXT,quantity INTEGER,kind TEXT,job TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS jobs(tenant TEXT,id TEXT,equipment TEXT,property TEXT,trade TEXT,revision INTEGER,status TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS proposals(tenant TEXT,id TEXT,job TEXT,revision INTEGER,state TEXT,payload TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS invoices(tenant TEXT,id TEXT,job TEXT,state TEXT,snapshot TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS audit(tenant TEXT,id TEXT,actor TEXT,at TEXT,reason TEXT,source TEXT,before_value TEXT,after_value TEXT,PRIMARY KEY(tenant,id));
'''
def connect(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    return db

def seed(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        if not db.execute('SELECT 1 FROM tenants WHERE id=?', ('demo',)).fetchone():
            db.execute('INSERT INTO tenants VALUES(?,?,?)', ('demo', json.dumps(list(REGISTRY)), json.dumps({'monthly_cents':100000,'validated':False})))
            db.execute('INSERT INTO customers VALUES(?,?,?,?)', ('demo','customer-1','Morgan Ellis','branch-1'))
            db.executemany('INSERT INTO equipment VALUES(?,?,?,?,?,?)', [('demo','hvac-1','customer-1','124 Oak Lane','HVAC','Upstairs heat pump · Carrier · serial DEMO-001'),('demo','panel-1','customer-1','124 Oak Lane','Electrical','Main electrical panel'),('demo','hvac-2','customer-1','46 Willow Way','HVAC','Guest-house air handler')])
            db.execute('INSERT INTO agreements VALUES(?,?,?,?,?,?,?,?,?)', ('demo','care-v1','hvac-1','124 Oak Lane','HVAC','2026-01-01','2027-12-31',10,'Frozen v1: one remaining HVAC maintenance visit; 10% labor discount; electrical excluded.'))
            db.execute('INSERT INTO benefits VALUES(?,?,?,?,?)', ('demo','opening','care-v1',1,'Fictional opening grant'))
            db.executemany('INSERT INTO stock VALUES(?,?,?,?,?,?)', [('demo','capacitor','Run capacitor',8,1800,4500),('demo','control-board','Replacement control board',0,8500,14000)])
            db.execute('INSERT INTO movements VALUES(?,?,?,?,?,?)', ('demo','issued','capacitor',-2,'issued-to-job','job-1'))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)', ('demo','job-1','hvac-1','124 Oak Lane','HVAC',1,'Awaiting confirmation'))
        db.commit()
    except Exception:
        db.rollback()
        raise
