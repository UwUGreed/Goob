import json
import sqlite3
from pathlib import Path
from operations.modules.registry import REGISTRY

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY, modules TEXT, pricing TEXT);
CREATE TABLE IF NOT EXISTS customers(tenant TEXT, id TEXT, name TEXT, branch TEXT, PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS equipment(tenant TEXT,id TEXT,customer TEXT,property TEXT,trade TEXT,name TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS agreements(tenant TEXT,id TEXT,equipment TEXT,property TEXT,trade TEXT,start TEXT,"end" TEXT,discount INTEGER,terms TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS benefits(tenant TEXT,id TEXT,agreement TEXT,amount INTEGER,source TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS stock(tenant TEXT,id TEXT,name TEXT,on_hand INTEGER,cost INTEGER,price INTEGER,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS movements(tenant TEXT,id TEXT,part TEXT,quantity INTEGER,kind TEXT,job TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS jobs(tenant TEXT,id TEXT,equipment TEXT,property TEXT,trade TEXT,revision INTEGER,status TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS proposals(tenant TEXT,id TEXT,job TEXT,revision INTEGER,state TEXT,payload TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS invoices(tenant TEXT,id TEXT,job TEXT,state TEXT,snapshot TEXT,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS audit(tenant TEXT,id TEXT,actor TEXT,at TEXT,reason TEXT,source TEXT,before_value TEXT,after_value TEXT,PRIMARY KEY(tenant,id));
'''
TABLES = ('tenants', 'customers', 'equipment', 'agreements', 'benefits',
          'stock', 'movements', 'jobs', 'proposals', 'invoices', 'audit')


class PostgresConnection:
    """Small adapter for the existing operations SQL and SQLite row contract.

    SQL is internal and uses ? placeholders (never user-supplied SQL).
    The write lock preserves BEGIN IMMEDIATE's serialization across workers.
    """
    def __init__(self, url):
        import psycopg2
        from psycopg2.extras import DictCursor
        self.raw = psycopg2.connect(url, connect_timeout=10, sslmode='require',
                                   application_name='goob-operations',
                                   cursor_factory=DictCursor)
        self.raw.autocommit = True
        with self.raw.cursor() as cursor:
            cursor.execute('SET search_path TO goob, public')
            cursor.execute("SET statement_timeout TO '30s'")
            cursor.execute("SET lock_timeout TO '10s'")

    def execute(self, sql, params=()):
        cursor = self.raw.cursor()
        try:
            if sql == 'BEGIN IMMEDIATE':
                cursor.execute('BEGIN')
                cursor.execute('LOCK TABLE ' + ','.join(TABLES) +
                               ' IN SHARE ROW EXCLUSIVE MODE')
            else:
                cursor.execute(sql.replace('?', '%s'), params or None)
            return cursor
        except Exception:
            cursor.close()
            self.rollback()
            raise

    def executemany(self, sql, rows):
        with self.raw.cursor() as cursor:
            cursor.executemany(sql.replace('?', '%s'), rows)

    def commit(self):
        with self.raw.cursor() as cursor:
            cursor.execute("COMMIT")

    def rollback(self):
        with self.raw.cursor() as cursor:
            cursor.execute("ROLLBACK")

    def close(self):
        self.raw.close()

    def initialize(self):
        try:
            with self.raw.cursor() as cursor:
                cursor.execute('BEGIN')
                cursor.execute('SELECT pg_advisory_xact_lock(90148001)')
                cursor.execute('CREATE SCHEMA IF NOT EXISTS goob')
                cursor.execute('CREATE TABLE IF NOT EXISTS goob.schema_migrations '
                               '(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())')
                cursor.execute('SELECT version FROM goob.schema_migrations WHERE version=1')
                if not cursor.fetchone():
                    cursor.execute(SCHEMA)
                    cursor.execute('INSERT INTO goob.schema_migrations(version) VALUES(1)')
            self.commit()
        except Exception:
            self.rollback()
            raise


def connect(path, initialize=True):
    if str(path).startswith(('postgres://', 'postgresql://')):
        db = PostgresConnection(path)
        try:
            if initialize:
                db.initialize()
            return db
        except Exception:
            db.close()
            raise

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
