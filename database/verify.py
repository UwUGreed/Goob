"""Database-only verification against the known demo tenant in isolated development."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4
from psycopg2 import Error, sql
from psycopg2.extras import Json
from database.connection import connect, require_development, lock_tooling
from database.fixtures import DEMO_ID, identifier as I, seed, reset
from database.model import TABLES


def verify(db):
    require_development(db)
    passed=[]
    def read(query,args=()):
        with db.cursor() as cur:cur.execute(query,args);return cur.fetchall()
    def check(name,condition):
        if not condition:raise ValueError('Verification failed: '+name)
        passed.append(name)
    def reject(name,query,args=(),code='23514'):
        try:
            with db.cursor() as cur:
                cur.execute(query,args)
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        except Error as error:
            db.rollback()
            check(name,error.pgcode==code)
        else:
            db.rollback();raise ValueError('Invalid database operation accepted: '+name)
    baseline=read('SELECT DISTINCT as_of FROM goob_db_meta.fixture_rows WHERE organization_id=%s',(DEMO_ID,))
    if len(baseline)!=1:raise ValueError('Seed the known demo organization before verifying.')
    as_of=baseline[0]['as_of'];db.rollback()
    result=seed(db,as_of)
    check('seed_rerun_safe',result['created']==0 and result['conflicting']==0 and result['skipped']>0)
    result=seed(db,as_of.replace(year=as_of.year+1))
    check('changed_as_of_refused_without_writes',result['created']==0 and result['conflicting']>0)
    constraints=read("SELECT count(*) AS n FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='goob_foundation' AND c.contype='f'")[0]['n']
    check('foreign_keys_present',constraints>200)
    n=read("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema='goob_foundation' AND table_type='BASE TABLE'")[0]['n']
    check('all_business_tables_present',n==len(TABLES))
    reject('required_customer_name','INSERT INTO crm_customers(organization_id,kind) VALUES(%s,\'residential\')',(DEMO_ID,),'23502')
    reject('duplicate_tenant_key','INSERT INTO org_trades(organization_id,code,name) VALUES(%s,\'hvac\',\'duplicate\')',(DEMO_ID,),'23505')
    other=str(uuid4())
    with db.cursor() as cur:
        cur.execute("INSERT INTO org_organizations(id,name,slug) VALUES(%s,'Other verification tenant',%s)",(other,'verify-'+other))
    reject('cross_tenant_reference','INSERT INTO crm_customer_contacts(organization_id,customer_id,contact_id,relationship) VALUES(%s,%s,%s,\'invalid\')',(other,I('crm_customers','avery'),I('crm_contacts','avery')),'23503')
    reject('posted_inventory_immutable','UPDATE inv_movements SET quantity=999 WHERE organization_id=%s AND id=%s',(DEMO_ID,I('inv_movements','opening')))
    reject('posted_benefit_immutable','DELETE FROM agree_benefit_ledger WHERE organization_id=%s AND id=%s',(DEMO_ID,I('agree_benefit_ledger','grant')))
    reject('plan_version_immutable','UPDATE agree_plan_versions SET period_price=1 WHERE organization_id=%s',(DEMO_ID,))
    reject('tenant_identity_immutable','UPDATE crm_customers SET id=gen_random_uuid() WHERE organization_id=%s',(DEMO_ID,))
    reject('finite_exact_amounts',"UPDATE bill_invoice_lines SET unit_price='NaN'::numeric WHERE organization_id=%s",(DEMO_ID,))
    reject('frozen_agreement_terms','UPDATE agree_agreements SET terms_snapshot=\'changed\' WHERE organization_id=%s',(DEMO_ID,))
    reject('invalid_coverage_scope',"UPDATE agree_coverage SET equipment_id=NULL WHERE organization_id=%s AND scope_kind='equipment'",(DEMO_ID,))
    reject('wrong_coverage_property',"UPDATE agree_coverage SET property_id=%s WHERE organization_id=%s AND id=%s",(I('crm_properties','cottage'),DEMO_ID,I('agree_coverage','active')))
    reject('bad_invoice_rounding','UPDATE bill_invoice_lines SET tax_amount=0.01 WHERE organization_id=%s',(DEMO_ID,))
    reject('issue_without_reconciled_snapshot',"UPDATE bill_invoices SET status='issued' WHERE organization_id=%s",(DEMO_ID,))
    reject('duplicate_movement_idempotency',"INSERT INTO inv_movements SELECT organization_id,gen_random_uuid(),created_at,kind,quantity,unit_cost,currency,occurred_at,idempotency_key,reason,material_id,from_account_id,to_account_id,job_id,work_id,source_record_id,reverses_id,approved_by FROM inv_movements WHERE organization_id=%s AND id=%s",(DEMO_ID,I('inv_movements','opening')),'23505')
    reject('transfer_requires_two_legs',"INSERT INTO inv_movements(organization_id,kind,quantity,unit_cost,currency,occurred_at,idempotency_key,reason,material_id,from_account_id,approved_by) VALUES(%s,'transfer',1,18,'USD',now(),%s,'verification',%s,%s,%s)",(DEMO_ID,str(uuid4()),I('cat_materials','capacitor'),I('inv_stock_accounts','warehouse'),I('org_members','office')))
    reject('movement_material_mismatch',"INSERT INTO inv_movements(organization_id,kind,quantity,unit_cost,currency,occurred_at,idempotency_key,reason,material_id,to_account_id,approved_by) VALUES(%s,'receipt',1,18,'USD',now(),%s,'verification',%s,%s,%s)",(DEMO_ID,str(uuid4()),I('cat_materials','board'),I('inv_stock_accounts','warehouse'),I('org_members','office')))
    reservation_sql="INSERT INTO {table}(organization_id,account_id,job_id,quantity,status,reserved_at,idempotency_key) VALUES(%s,%s,%s,%s,'active','"+as_of.isoformat()+"T12:00:00+00:00',%s)"
    reject('inventory_overreservation',reservation_sql.format(table='inv_reservations'),(DEMO_ID,I('inv_stock_accounts','truck-a'),I('job_jobs','return'),100,str(uuid4())))
    reject('benefit_overreservation',reservation_sql.format(table='agree_benefit_reservations'),(DEMO_ID,I('agree_benefit_accounts','active'),I('job_jobs','return'),100,str(uuid4())))
    reject('unknown_benefit_not_zero_or_spendable',reservation_sql.format(table='agree_benefit_reservations'),(DEMO_ID,I('agree_benefit_accounts','ambiguous'),I('job_jobs','return'),1,str(uuid4())))
    reject('expired_benefit_cannot_be_reserved',reservation_sql.format(table='agree_benefit_reservations'),(DEMO_ID,I('agree_benefit_accounts','expired'),I('job_jobs','return'),1,str(uuid4())))
    reject('reservation_cannot_be_erased','DELETE FROM inv_reservations WHERE organization_id=%s',(DEMO_ID,))
    reject('reservation_quantity_cannot_be_silently_edited','UPDATE inv_reservations SET quantity=2 WHERE organization_id=%s',(DEMO_ID,))
    # Issue a fully reconciled invoice in a transaction; verify immutability, then roll back.
    with db.cursor() as cur:
        cur.execute("UPDATE bill_review_flags SET status='resolved',resolution='Verification only',resolved_at=now(),reviewer_id=%s WHERE organization_id=%s",(I('org_members','office'),DEMO_ID))
        cur.execute("UPDATE bill_invoices SET subtotal=255,total=255,status='issued' WHERE organization_id=%s",(DEMO_ID,))
        cur.execute("""INSERT INTO bill_issued_snapshots(organization_id,invoice_id,issued_by,issued_at,customer_snapshot,address_snapshot,lines_snapshot,currency,total,idempotency_key)
          SELECT i.organization_id,i.id,%s,now(),'{}','{}',
          (SELECT jsonb_agg(to_jsonb(l) ORDER BY position) FROM bill_invoice_lines l WHERE l.organization_id=i.organization_id AND l.invoice_id=i.id),
          i.currency,i.total,%s FROM bill_invoices i WHERE i.organization_id=%s""",(I('org_members','office'),str(uuid4()),DEMO_ID))
        cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    check('reconciled_invoice_can_be_issued',True)
    reject('issued_prices_immutable','UPDATE bill_invoice_lines SET unit_price=0 WHERE organization_id=%s',(DEMO_ID,))
    # Matching reversal keeps original history. Roll back the verification row.
    with db.cursor() as cur:
        cur.execute("INSERT INTO inv_movements(organization_id,kind,quantity,unit_cost,currency,occurred_at,idempotency_key,reason,material_id,from_account_id,reverses_id,approved_by) VALUES(%s,'reversal',1,18,'USD',now(),%s,'verification',%s,%s,%s,%s)",(DEMO_ID,str(uuid4()),I('cat_materials','capacitor'),I('inv_stock_accounts','truck-a'),I('inv_movements','unused'),I('org_members','office')))
        cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    check('traceable_reversal_accepted',True);db.rollback()
    with db.cursor() as cur:
        cur.execute('UPDATE crm_customers SET display_name=\'User-edited fixture\' WHERE organization_id=%s AND id=%s',(DEMO_ID,I('crm_customers','avery')))
        # Seed preflight sees the edit in this transaction and rolls it back, never overwrites it.
    result=seed(db,as_of)
    check('edited_fixture_conflict_detected',result['conflicting']==1 and result['created']==0)
    # Reset must refuse both edited and unregistered tenant records.
    with db.cursor() as cur:
        cur.execute("INSERT INTO crm_customers(organization_id,display_name,kind) VALUES(%s,'Not a fixture','residential')",(DEMO_ID,))
    try: reset(db)
    except ValueError: db.rollback();check('reset_refuses_unregistered_demo_rows',True)
    else: raise ValueError('Reset accepted unregistered demo records.')
    # True concurrent commits on the same balance; one must fail at commit.
    # Runs a compensating cleanup in a finally block; no test rows remain after success.
    for table,account,quantity in [('inv_reservations',I('inv_stock_accounts','truck-a'),2),('agree_benefit_reservations',I('agree_benefit_accounts','active'),1)]:
        keys=['verify-'+str(uuid4()) for _ in range(2)]
        barrier=Barrier(2)
        def reserve(key):
            conn=connect(True)
            try:
                require_development(conn)
                barrier.wait(timeout=10)
                with conn.cursor() as cur:cur.execute(reservation_sql.format(table=table),(DEMO_ID,account,I('job_jobs','return'),quantity,key))
                conn.commit();return 'committed'
            except Error as exc:
                conn.rollback();return exc.pgcode
            finally:conn.close()
        db.rollback()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(reserve,keys))
            check(table+'_concurrent_capacity',sorted(outcomes)==['23514','committed'])
        finally:
            with db.cursor() as cur:
                cur.execute("SELECT set_config('goob.demo_reset',%s,true)",(DEMO_ID,))
                cur.execute(sql.SQL('DELETE FROM {} WHERE organization_id=%s AND idempotency_key=ANY(%s)').format(sql.Identifier(table)),(DEMO_ID,keys))
            db.commit()
    reports={}
    for path in sorted((Path(__file__).parent/'reports').glob('*.sql')):
        reports[path.stem]=read(path.read_text())
    inventory=reports['01_inventory']
    truck=next(r for r in inventory if r['location']=='truck-a')
    check('inventory_fixture_reconciles',(truck['on_hand'],truck['reserved'],truck['available'])==(3,1,2))
    warehouse=next(r for r in inventory if r['location']=='warehouse' and r['sku']=='DEMO-capacitor')
    check('transfer_conserves_quantity',warehouse['on_hand']==16 and sum(r['on_hand'] for r in inventory if r['sku']=='DEMO-capacitor')==19)
    active=next(r for r in reports['02_benefits'] if r['agreement_number']=='DEMO-active')
    unknown=next(r for r in reports['02_benefits'] if r['agreement_number']=='DEMO-ambiguous')
    expired=next(r for r in reports['02_benefits'] if r['agreement_number']=='DEMO-expired')
    check('benefit_fixture_reconciles',(active['remaining'],active['reserved'],active['available'])==(2,1,1))
    check('unknown_balance_preserved',unknown['remaining'] is None and unknown['available'] is None and not unknown['agreement_eligible_as_of'])
    check('expired_not_eligible',not expired['agreement_eligible_as_of'] and expired['remaining']==0)
    check('return_visit_shortage_calculated',next(r for r in reports['03_readiness'] if r['job_number']=='DEMO-return')['shortage']==1)
    check('billing_discrepancy_calculated',reports['04_billing'][0]['discrepancy']==-15 and reports['04_billing'][0]['open_flags']==3)
    check('fictional_event_report',sum(r['event_count'] for r in reports['05_events'])==4)
    check('explicit_scope_query',next(r for r in reports['06_coverage'] if r['job_number']=='DEMO-scheduled')['approved_agreement_candidates']==1)
    db.rollback()
    result=seed(db,as_of)
    check('verification_leaves_fixtures_unchanged',result['created']==0 and result['conflicting']==0)
    return {'passed':len(passed),'checks':passed,'reports':{name:len(rows) for name,rows in reports.items()}}
