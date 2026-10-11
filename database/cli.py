"""Explicit database-only commands: check, migrate, seed, verify, report, reset."""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
from database.connection import connect, lock_tooling, lock_deployment

ROOT=Path(__file__).parent


def migrations():
    return [(p.stem, hashlib.sha256(p.read_bytes()).hexdigest(), p.read_text()) for p in sorted((ROOT/'migrations').glob('*.sql'))]


def applied(db):
    with db.cursor() as cur:
        cur.execute("SELECT to_regclass('goob_db_meta.migrations') AS relation")
        if not cur.fetchone()['relation']: return {}
        cur.execute('SELECT version,sha256 FROM goob_db_meta.migrations')
        return {r['version']:r['sha256'] for r in cur.fetchall()}


def migrate(db, apply=False, deployment_target=None):
    if apply:
        if deployment_target:
            lock_deployment(db,*deployment_target)
        else:
            lock_tooling(db)
    existing=applied(db)
    known={version:digest for version,digest,_ in migrations()}
    if set(existing)-set(known): raise ValueError('Database has migrations not present in this checkout.')
    for version,digest in existing.items():
        if known[version]!=digest: raise ValueError(f'Applied migration checksum mismatch: {version}')
    if not apply:
        return {'applied':list(existing),'pending':[v for v,_,_ in migrations() if v not in existing],'writes':False}
    with db.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS goob_db_meta')
        cur.execute('REVOKE ALL ON SCHEMA goob_db_meta FROM PUBLIC')
        cur.execute('CREATE TABLE IF NOT EXISTS goob_db_meta.migrations(version text PRIMARY KEY,sha256 text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
        cur.execute('''CREATE TABLE IF NOT EXISTS goob_db_meta.fixture_rows(
            organization_id uuid NOT NULL,table_name text NOT NULL,record_id uuid NOT NULL,
            row_snapshot jsonb NOT NULL,as_of date NOT NULL,
            PRIMARY KEY(organization_id,table_name,record_id))''')
        changed=[]
        for version,digest,sql in migrations():
            if version in existing: continue
            cur.execute(sql)
            cur.execute('INSERT INTO goob_db_meta.migrations(version,sha256) VALUES(%s,%s)',(version,digest))
            changed.append(version)
    db.commit()
    return {'applied_now':changed,'already_applied':list(existing)}


def check(db):
    with db.cursor() as cur:
        cur.execute('SELECT current_database() AS database,current_setting(\'server_version\') AS postgres_version')
        result=dict(cur.fetchone())
        cur.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
        row=cur.fetchone();result['tls']=bool(row and row['ssl'])
        cur.execute('SELECT extname,extversion FROM pg_extension ORDER BY extname')
        result['installed_extensions']=cur.fetchall()
        result['writes']=False
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',type=Path,help='Explicit local env file, existing environment values win')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check')
    m=sub.add_parser('migrate'); mode=m.add_mutually_exclusive_group(); mode.add_argument('--apply',action='store_true');mode.add_argument('--dry-run',action='store_true')
    m.add_argument('--deploy-host',help='Explicit authorized deployment host; requires --apply and --deploy-database')
    m.add_argument('--deploy-database',help='Exact authorized database name; schema migrations only')
    s=sub.add_parser('seed');s.add_argument('--as-of',type=date.fromisoformat,required=True)
    sub.add_parser('verify')
    sub.add_parser('report')
    r=sub.add_parser('reset');r.add_argument('--confirm-demo-reset',action='store_true')
    args=p.parse_args()
    if args.command=='migrate' and (args.deploy_host or args.deploy_database):
        if not (args.apply and args.deploy_host and args.deploy_database):
            p.error('Deployment requires --apply, --deploy-host and --deploy-database together.')
    if args.env_file:
        if not args.env_file.is_file():
            print('Explicit environment file does not exist; refusing fallback to another target.',file=sys.stderr)
            return 1
        load_dotenv(args.env_file,override=False)
    write=args.command in ('seed','reset','verify') or (args.command=='migrate' and args.apply)
    db=None
    try:
        db=connect(write=write)
        if args.command=='check': result=check(db)
        elif args.command=='migrate': result=migrate(db,args.apply,(args.deploy_host,args.deploy_database) if args.deploy_host else None)
        elif args.command=='seed':
            from database.fixtures import seed
            result=seed(db,args.as_of)
        elif args.command=='reset':
            from database.fixtures import reset
            if not args.confirm_demo_reset: raise ValueError('Reset requires --confirm-demo-reset.')
            result=reset(db)
        elif args.command=='verify':
            from database.verify import verify
            result=verify(db)
        else:
            result={}
            with db.cursor() as cur:
                for path in sorted((ROOT/'reports').glob('*.sql')):
                    cur.execute(path.read_text());result[path.stem]=cur.fetchall()
        print(json.dumps(result,default=str,indent=2))
        if isinstance(result,dict) and result.get('conflicting',0): return 2
        return 0
    except (ValueError,psycopg2.Error) as exc:
        # Raw server errors can contain row values or a DSN. Never emit them.
        code=exc.pgcode if isinstance(exc,psycopg2.Error) else 'configuration-or-validation'
        print(f'Database command failed ({code}). No credentials or row data logged.',file=sys.stderr)
        if isinstance(exc,ValueError): print(str(exc),file=sys.stderr)
        return 1
    finally:
        if db is not None: db.close()

if __name__=='__main__': raise SystemExit(main())
