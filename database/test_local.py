"""Full isolated PostgreSQL test. Requires Docker; removes its own container on exit."""
import argparse
import sys
import tempfile
from pathlib import Path
import json
import os
import secrets
import subprocess
import time
from datetime import date
from uuid import uuid4
from psycopg2 import sql, OperationalError
from database.connection import connect, MARKER, require_development
from database.cli import migrate
from database.fixtures import seed, reset, DEMO_ID, identifier
from database.verify import verify


def run(postgres_version=17):
    name='goob-db-test-'+uuid4().hex[:12]
    password=secrets.token_urlsafe(24)
    env={**os.environ,'POSTGRES_PASSWORD':password}
    proc=subprocess.run(['docker','run','--detach','--rm','--name',name,'--label','goob.database-test=true',
        '-e','POSTGRES_PASSWORD','-e','POSTGRES_USER=goob_dev','-e','POSTGRES_DB=goob_dev_foundation',
        '-p','127.0.0.1::5432',f'postgres:{postgres_version}-alpine'],env=env,capture_output=True,text=True)
    if proc.returncode:raise RuntimeError('Could not start disposable PostgreSQL container; check Docker availability.')
    db=None
    try:
        binding=subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip()
        port=binding.rsplit(':',1)[1]
        os.environ.update(GOOB_DATABASE_URL=f'postgresql://goob_dev:{password}@127.0.0.1:{port}/goob_dev_foundation?sslmode=disable',GOOB_DB_ENV='development',GOOB_DB_EXPECTED_DATABASE='goob_dev_foundation')
        for attempt in range(80):
            try:db=connect(True);break
            except OperationalError:time.sleep(.25)
        if db is None:raise RuntimeError('Disposable PostgreSQL did not become ready.')
        # An unmarked database must be rejected before any schema writes.
        try:require_development(db)
        except ValueError: db.rollback()
        else:raise AssertionError('Unmarked database accepted')
        with db.cursor() as cur:
            cur.execute(sql.SQL('COMMENT ON DATABASE goob_dev_foundation IS {}').format(sql.Literal(MARKER)))
        db.commit()
        # Exercise non-UTC server defaults through a fresh connection.
        with db.cursor() as cur:cur.execute("ALTER DATABASE goob_dev_foundation SET timezone='America/New_York'")
        db.commit();db.close();db=connect(True)
        with db.cursor() as cur:
            cur.execute('SHOW timezone');assert cur.fetchone()['TimeZone']=='UTC'
        db.rollback()
        before=migrate(db,False);assert len(before['pending'])==3
        db.rollback()
        first=migrate(db,True);assert len(first['applied_now'])==3
        second=migrate(db,True);assert second['applied_now']==[]
        created=seed(db,date(2026,10,10));assert created['created']==206
        results=verify(db)
        # Run the documented public CLI, including failure paths, in separate processes.
        cli_checks=[]
        def cli(*arguments, expected=0):
            result=subprocess.run([sys.executable,'-m','database.cli',*arguments],capture_output=True,text=True)
            assert password not in result.stdout+result.stderr
            assert result.returncode==expected, ('CLI exit status',arguments,result.returncode,result.stderr)
            cli_checks.append(' '.join(arguments))
            return json.loads(result.stdout) if result.returncode==0 else None
        assert cli('check')['writes'] is False
        assert cli('migrate','--dry-run')['pending']==[]
        assert cli('seed','--as-of','2026-10-10')['skipped']==206
        assert len(cli('report'))==6
        cli('reset',expected=1)
        cli('seed','--as-of','invalid',expected=2)
        with tempfile.TemporaryDirectory() as temp:
            cli('--env-file',str(Path(temp)/'missing.env'),'check',expected=1)
        original=os.environ['GOOB_DB_EXPECTED_DATABASE']
        os.environ['GOOB_DB_EXPECTED_DATABASE']='goob_dev_wrong_target'
        try:cli('migrate','--apply',expected=1)
        finally:os.environ['GOOB_DB_EXPECTED_DATABASE']=original

        # Applied migration tampering fails closed, without modifying domain records.
        with db.cursor() as cur:cur.execute("UPDATE goob_db_meta.migrations SET sha256='tampered' WHERE version='001_foundation'")
        try:migrate(db,True)
        except ValueError:db.rollback()
        else:raise AssertionError('Checksum mismatch was accepted')
        # A different tenant can use the same composite child id and must survive demo reset.
        other=str(uuid4());child=identifier('crm_customers','avery')
        with db.cursor() as cur:
            cur.execute("INSERT INTO org_organizations(id,name,slug) VALUES(%s,'Other test organization',%s)",(other,'other-'+other))
            cur.execute("INSERT INTO crm_customers(organization_id,id,display_name,kind) VALUES(%s,%s,'Other tenant customer','residential')",(other,child))
        db.commit()
        deleted=reset(db);assert deleted['deleted']==206
        with db.cursor() as cur:
            cur.execute('SELECT count(*) AS n FROM crm_customers WHERE organization_id=%s AND id=%s',(other,child));assert cur.fetchone()['n']==1
        db.rollback()
        assert reset(db)['deleted']==0
        assert seed(db,date(2027,3,15))['created']==206
        results_future=verify(db)
        assert reset(db)['deleted']==206
        print(json.dumps({'status':'passed','database':f'disposable PostgreSQL {postgres_version}','migrations':first['applied_now'],
            'cli_checks':len(cli_checks),'non_utc_server_default':'passed','fixture_records':created['created'],'checks_per_as_of':results['passed'],'as_of_dates':['2026-10-10','2027-03-15'],
            'additional_checks':['unmarked database rejected','migration dry-run','migration rerun','migration checksum tampering rejected','reset only demo tenant','same child ID in another tenant preserved','reset rerun','reseed with changed as-of'],
            'container_removed_on_exit':True},indent=2))
    finally:
        if db:db.close()
        subprocess.run(['docker','stop',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-version',type=int,choices=[17,18],default=17)
    run(parser.parse_args().postgres_version)
