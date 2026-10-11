"""Standalone database tooling; never imported by the application."""
import os
import re
import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

MARKER = 'goob-isolated-development-v1'


def connect(write=False):
    url = os.environ.get('GOOB_DATABASE_URL')
    if not url and not write:
        url = os.environ.get('DATABASE_URL')
    if not url:
        raise ValueError('Set GOOB_DATABASE_URL explicitly for database tooling.')
    params = parse_dsn(url)
    mode = params.get('sslmode', 'require')
    if mode not in ('require','verify-ca','verify-full'):
        raise ValueError('Cloud PostgreSQL requires TLS require/verify-ca/verify-full.')
    db=psycopg2.connect(url, sslmode=mode, connect_timeout=10, application_name='goob-database-tools', cursor_factory=RealDictCursor)
    with db.cursor() as cur:
        cur.execute("SET statement_timeout='30s'")
        cur.execute("SET lock_timeout='10s'")
        cur.execute("SET idle_in_transaction_session_timeout='60s'")
        cur.execute('SET search_path=goob_foundation,pg_catalog')
        # Keep JSON timestamp snapshots deterministic across server/session defaults.
        cur.execute("SET TIME ZONE 'UTC'")
    db.commit()
    if not write:
        db.set_session(readonly=True)
    return db


def require_development(db):
    expected = os.environ.get('GOOB_DB_EXPECTED_DATABASE','')
    if os.environ.get('GOOB_DB_ENV')!='development' or not re.fullmatch(r'goob_dev_[a-z0-9_]+',expected):
        raise ValueError('Writes require GOOB_DB_ENV=development and a goob_dev_* expected database name.')
    with db.cursor() as cur:
        cur.execute("SELECT current_database() AS name, shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()")
        row=cur.fetchone()
    if row['name'] != expected or row['marker'] != MARKER:
        raise ValueError('Database identity/isolated-development marker mismatch; no writes allowed.')


def lock_tooling(db):
    require_development(db)
    with db.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(9014897)')


def lock_deployment(db, expected_host, expected_database):
    """Explicitly authorized schema deployment, never a seed/reset exemption."""
    params=db.get_dsn_parameters()
    if not expected_host or not expected_database or params.get('host')!=expected_host:
        raise ValueError('Deployment host identity mismatch.')
    with db.cursor() as cur:
        cur.execute('SELECT current_database() AS name, ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
        row=cur.fetchone()
        if not row or row['name']!=expected_database or not row['ssl']:
            raise ValueError('Deployment database identity or TLS check failed.')
        cur.execute('SELECT pg_advisory_xact_lock(9014897)')
