"""Deterministic fictional domain records and conservative manifest-based reset."""
import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid5
from psycopg2 import sql
from psycopg2.extras import Json
from database.model import TABLES, ordered_tables
from database.connection import lock_tooling

NAMESPACE=UUID('763563ce-8ec0-48f8-9ec5-353673d6c502')

def identifier(table,key): return str(uuid5(NAMESPACE,table+':'+key))
DEMO_ID=identifier('org_organizations','demo')

def fixture_rows(as_of):
    rows=[]
    stamp=as_of.isoformat()+'T00:00:00+00:00'
    def day(delta): return (as_of+timedelta(days=delta)).isoformat()
    def at(delta,hour=12): return day(delta)+f'T{hour:02}:00:00+00:00'
    def add(table,key,**values):
        row={'id':identifier(table,key),'created_at':stamp,**values}
        if table!='org_organizations': row['organization_id']=DEMO_ID
        for col,target in TABLES[table]['refs'].items():
            if col in row and row[col] is not None: row[col]=identifier(target,row[col])
        rows.append((table,row))
    add('org_organizations','demo',name='Goob Demo Services',slug='goob-demo-services',is_demo=True)
    add('org_branches','main',name='Fictional Central Branch',timezone='America/New_York')
    for who,name in [('office','Avery Office'),('hvac','Jamie Vale'),('electric','Casey Pine'),('plumber','Taylor Reed')]:
        add('org_members',who,auth_provider='fictional-no-provider',auth_subject='demo:'+who,display_name=name,status='active',branch_id='main')
    for role in ['owner','technician']: add('org_roles',role,name=role)
    for perm in ['database.review','work.confirm']:
        add('org_permissions',perm,code=perm)
        add('org_role_permissions',perm,role_id='owner',permission_id=perm)
    add('org_role_permissions','tech',role_id='technician',permission_id='work.confirm')
    add('org_member_roles','office',member_id='office',role_id='owner')
    for who in ['hvac','electric','plumber']:
        add('org_member_roles',who,member_id=who,role_id='technician')
        add('org_technicians',who,member_id=who,employee_number='DEMO-'+who,active=True)
    for key,name in [('hvac','Mechanical / HVAC'),('electrical','Electrical'),('plumbing','Plumbing')]:
        add('org_trades',key,code=key,name=name,enabled=True)
        add('org_qualifications',key,code='demo-'+key,name='Fictional '+name+' qualification',trade_id=key)
    for who,trade in [('hvac','hvac'),('electric','electrical'),('electric','hvac'),('plumber','plumbing')]:
        add('org_technician_qualifications',who+trade,technician_id=who,qualification_id=trade,valid_from=day(-90),valid_until=day(365),credential_reference='FICTIONAL-NOT-A-LICENSE')
    for mod in ['crm','agreements','jobs','inventory','billing']:
        add('org_modules',mod,code=mod,enabled=True,settings={'fixture':True})
    for key,name,kind in [('avery','Avery Chen','residential'),('rowan','Rowan Brooks','residential'),('juniper','Juniper Workshop LLC (fictional)','commercial')]:
        add('crm_customers',key,display_name=name,kind=kind)
        add('crm_contacts',key,given_name=name.split()[0],family_name='Demo',email=key+'@example.com')
        add('crm_customer_contacts',key,customer_id=key,contact_id=key,relationship='billing',is_primary=True)
        add('crm_communication_preferences',key,contact_id=key,channel='email',purpose='service',allowed=True,recorded_at=stamp,source='Fictional seed consent; never send')
    for key,customer,street in [('home','avery','100 Example Lane'),('cottage','avery','200 Example Lane'),('rowan','rowan','300 Example Lane'),('shop','juniper','400 Example Lane')]:
        add('crm_addresses',key,line1=street,city='Exampleville',region='SC',postal_code='00000',country_code='US')
        add('crm_properties',key,name='Fictional '+key,address_id=key,timezone='America/New_York')
        add('crm_customer_properties',key,customer_id=customer,property_id=key,relationship='owner',valid_from=day(-365))
    for key in ['terms','evidence','import']:
        add('crm_files',key,storage_reference='demo://not-uploaded/'+key,filename=key+'.txt',content_type='text/plain',byte_size=0,sha256='0'*64)
    for key,name in [('hvac','Heat pump'),('electrical','Electrical panel'),('plumbing','Water heater')]:
        add('crm_equipment_types',key,name=name,trade_id=key)
    for key,prop,typ in [('heat','home','hvac'),('cottageheat','cottage','hvac'),('panel','rowan','electrical'),('heater','shop','plumbing')]:
        add('crm_equipment',key,name='Fictional '+key,property_id=prop,type_id=typ,make='Example Make',model='Demo 100',serial_number='DEMO-'+key,installed_on=day(-300),warranty_until=day(500),warranty_terms='Fictional parts-only warranty',warranty_document_id='terms')
        add('crm_equipment_history',key,equipment_id=key,kind='installed',to_property_id=prop,effective_at=at(-300),reason='Fictional installation history',evidence_id='evidence')
    add('crm_notes','home',body='Fictional location note',author_id='office',property_id='home',attachment_id='evidence')
    for unit,dimension in [('each','count'),('hour','time'),('visit','count')]:add('cat_units',unit,code=unit,dimension=dimension)
    for key,name in [('capacitor','Example capacitor'),('board','Example control board'),('wire','Example wire spool')]:add('cat_materials',key,sku='DEMO-'+key,name=name,unit_id='each')
    for key,trade in [('maintenance','hvac'),('panelcheck','electrical'),('watercheck','plumbing')]:add('cat_services',key,code=key,name='Fictional '+key,trade_id=trade)
    add('cat_job_types','service',code='service',name='Service visit')
    add('cat_pricebooks','standard',name='Fictional standard pricing',currency='USD')
    add('cat_price_versions','capacitor',pricebook_id='standard',material_id='capacitor',unit_id='each',version=1,valid_from=day(-30),unit_price=45)
    add('cat_price_versions','maintenance',pricebook_id='standard',service_id='maintenance',unit_id='visit',version=1,valid_from=day(-30),unit_price=120)
    add('cat_labor_rates','hvac',name='Fictional HVAC labor',trade_id='hvac',valid_from=day(-30),hourly_rate=100,currency='USD')
    add('cat_checklist_templates','maintenance',name='Maintenance v1',service_id='maintenance',version=1)
    add('cat_checklist_items','maintenance',template_id='maintenance',position=1,instruction='Record fictional equipment inspection',required=True)
    add('cat_material_requirements','maintenance',service_id='maintenance',material_id='capacitor',quantity=1)
    add('import_batches','opening',source_system='fictional-fixture',idempotency_key='demo-opening-v1',status='approved',started_at=stamp,source_file_id='import',requested_by='office')
    add('import_field_mappings','balance',batch_id='opening',source_field='remaining_visits',target_table='agree_benefit_accounts',target_field='balance_state',transform_description='Blank is unknown, never zero')
    add('import_staging_records','stock',batch_id='opening',source_identifier='opening-stock',original_values={'quantity':20,'fictional':True},normalized_values={'quantity':20},status='approved')
    add('import_staging_records','benefits',batch_id='opening',source_identifier='opening-benefits',original_values={'active_visits':3,'expired_visits':2,'fictional':True},normalized_values={'active_visits':3,'expired_visits':2},status='approved')
    add('import_staging_records','uncertain',batch_id='opening',source_identifier='uncertain-membership',original_values={'remaining_visits':None,'terms':'possibly two units','fictional':True},normalized_values={'balance_state':'unknown'},status='uncertain')
    add('import_validation_issues','uncertain',record_id='uncertain',field_name='remaining_visits',severity='error',code='UNKNOWN_BALANCE',description='Fictional ambiguous source requires staff reconciliation')
    add('import_duplicate_candidates','uncertain',record_id='uncertain',candidate_table='crm_customers',candidate_id=identifier('crm_customers','avery'),reason='Fictional possible duplicate',confidence=0.6)
    add('import_decisions','stock',record_id='stock',reviewer_id='office',decision='accept',reason='Approved fictional opening quantities',decided_at=stamp)
    add('import_decisions','benefits',record_id='benefits',reviewer_id='office',decision='accept',reason='Approved fictional opening visit quantities',decided_at=stamp)
    add('import_decisions','uncertain',record_id='uncertain',reviewer_id='office',decision='defer',reason='Do not guess missing balance',decided_at=stamp)
    add('agree_plans','care',code='care',name='Fictional Home Care')
    add('agree_plan_versions','care-v1',plan_id='care',version=1,terms='Fictional v1: three HVAC maintenance visits; explicit coverage only.',published_at=at(-60),currency='USD',period_price=300,source_file_id='terms')
    add('agree_benefit_definitions','visits',plan_version_id='care-v1',code='visits',name='Maintenance visits',unit='visit',service_scope='specific',period_grant=3,eligibility_description='Approved coverage, matching property/equipment/trade/service and effective dates',service_id='maintenance')
    for key,status,start,end,interpretation in [('active','active',-30,335,'approved'),('expired','expired',-400,-35,'approved'),('ambiguous','review',-10,355,'ambiguous')]:
        kwargs={'interpretation_reviewer_id':'office','interpretation_approved_at':stamp} if interpretation=='approved' else {}
        add('agree_agreements',key,agreement_number='DEMO-'+key,customer_id='avery',plan_version_id='care-v1',starts_on=day(start),ends_on=day(end),status=status,renewal_mode='manual',interpretation_state=interpretation,source_file_id='terms',terms_snapshot='Fictional preserved care v1 terms',**kwargs)
        add('agree_coverage',key,agreement_id=key,property_id='home' if key!='ambiguous' else 'cottage',scope_kind='equipment' if key!='ambiguous' else 'property',equipment_id='heat' if key!='ambiguous' else None,service_scope='specific' if key!='ambiguous' else 'all',service_id='maintenance' if key!='ambiguous' else None,valid_from=day(start),valid_until=day(end),review_state='approved' if interpretation=='approved' else 'ambiguous')
        add('agree_benefit_accounts',key,agreement_id=key,benefit_definition_id='visits',balance_state='unknown' if key=='ambiguous' else 'known',period_start=day(start),period_end=day(end),source_record_id='uncertain' if key=='ambiguous' else 'benefits')
    add('agree_coverage','trade',agreement_id='active',property_id='cottage',scope_kind='trade',trade_id='hvac',service_scope='specific',service_id='maintenance',valid_from=day(-30),valid_until=day(335),review_state='approved')
    add('agree_changes','renewal-review',agreement_id='active',kind='renewal_review',effective_at=stamp,reason='Fictional annual review',before_values={'renewal_mode':'manual'},after_values={'renewal_mode':'manual'},approved_by='office')
    for key,status,customer,prop in [('completed','completed','avery','home'),('scheduled','scheduled','avery','cottage'),('return','return_required','avery','home'),('electrical','scheduled','rowan','rowan'),('plumbing','scheduled','juniper','shop')]:
        add('job_jobs',key,job_number='DEMO-'+key,status=status,planned_scope='Fictional '+key+' scope',billing_customer_id=customer,property_id=prop,branch_id='main',job_type_id='service')
        trade='electrical' if key=='electrical' else 'plumbing' if key=='plumbing' else 'hvac'
        service='panelcheck' if key=='electrical' else 'watercheck' if key=='plumbing' else 'maintenance'
        add('job_trades',key,job_id=key,trade_id=trade)
        add('job_equipment',key,job_id=key,equipment_id={'completed':'heat','scheduled':'cottageheat','return':'heat','electrical':'panel','plumbing':'heater'}[key])
        add('job_tasks',key,job_id=key,service_id=service,description='Fictional planned task',planned_quantity=1,status='confirmed' if key=='completed' else 'planned')
        delta=-1 if key=='completed' else 1
        add('job_appointments',key,job_id=key,starts_at=at(delta),ends_at=at(delta,14),status='completed' if key=='completed' else 'scheduled')
        tech='electric' if key=='electrical' else 'plumber' if key=='plumbing' else 'hvac'
        add('job_assignments',key,appointment_id=key,technician_id=tech)
    add('job_assignments','helper',appointment_id='completed',technician_id='electric')
    add('job_trades','multi',job_id='return',trade_id='electrical')
    add('job_availability','hvac',technician_id='hvac',starts_at=at(1,8),ends_at=at(1,17),kind='available',reason='Fictional schedule')
    add('job_time_entries','completed',job_id='completed',technician_id='hvac',starts_at=at(-1),ends_at=at(-1,13),kind='labor',approved_by='office')
    add('job_status_history','completed',job_id='completed',actor_id='office',from_status='in_progress',to_status='completed',changed_at=at(-1,14),reason='Fictional completion')
    add('job_confirmed_work','maintenance',job_id='completed',task_id='completed',service_id='maintenance',unit_id='visit',confirmed_by='office',description='Fictional confirmed maintenance',quantity=1,confirmed_at=at(-1,14),idempotency_key='demo-work-maintenance')
    add('job_work_evidence','maintenance',work_id='maintenance',file_id='evidence',description='Fictional evidence reference')
    add('job_return_links','return',original_job_id='completed',return_job_id='return',reason='Control board unavailable')
    add('job_required_materials','return',job_id='return',material_id='board',quantity=1)
    add('job_required_materials','scheduled',job_id='scheduled',material_id='capacitor',quantity=1)
    add('job_readiness_checks','return',job_id='return',material_id='board',checked_at=stamp,result='blocked',rule_code='MATERIAL_NOT_RESERVED',reason='Fictional board required; no reservation or stock')
    for key,account,kind,quantity in [('grant','active','grant',3),('consume','active','consumption',-1),('expired-grant','expired','grant',2),('expire','expired','expiration',-2)]:
        add('agree_benefit_ledger',key,account_id=account,kind=kind,quantity=quantity,occurred_at=at(-1) if kind=='consumption' else stamp,idempotency_key='demo-benefit-'+key,reason='Fictional '+kind,approved_by='office',source_record_id='benefits',**({'job_id':'completed','work_id':'maintenance'} if kind=='consumption' else {}))
    add('agree_benefit_reservations','scheduled',account_id='active',job_id='scheduled',quantity=1,status='active',reserved_at=stamp,idempotency_key='demo-benefit-reservation')
    add('agree_benefit_reservations','released',account_id='active',job_id='return',quantity=1,status='released',reserved_at=at(-2),resolved_at=at(-1),resolution_reason='Fictional release',idempotency_key='demo-benefit-release')
    add('agree_planned_visits','scheduled',agreement_id='active',property_id='cottage',service_id='maintenance',job_id='scheduled',due_from=day(0),due_until=day(30),status='scheduled')
    add('agree_planned_visits','completed',agreement_id='active',property_id='home',service_id='maintenance',job_id='completed',completed_work_id='maintenance',due_from=day(-5),due_until=day(0),status='completed')
    add('inv_suppliers','example',name='Fictional Parts Supply',external_reference='DEMO-NO-PROVIDER')
    add('inv_supplier_materials','board',supplier_id='example',material_id='board',supplier_sku='DEMO-BOARD',lead_days=3)
    for key,kind in [('warehouse','warehouse'),('truck-a','truck'),('truck-b','truck'),('quarantine','quarantine')]:
        add('inv_locations',key,code=key,name='Fictional '+key,kind=kind,branch_id='main',**({'technician_id':'hvac' if key=='truck-a' else 'electric'} if kind=='truck' else {}))
        add('inv_stock_accounts',key,location_id=key,material_id='capacitor')
    add('inv_stock_accounts','board',location_id='warehouse',material_id='board')
    for key,kind,qty,source,target in [('opening','opening',20,None,'warehouse'),('transfer','transfer',4,'warehouse','truck-a'),('installed','consumption',2,'truck-a',None),('unused','usable_return',1,None,'truck-a')]:
        add('inv_movements',key,kind=kind,quantity=qty,unit_cost=18,currency='USD',occurred_at=stamp,idempotency_key='demo-inventory-'+key,reason='Fictional '+key,material_id='capacitor',from_account_id=source,to_account_id=target,approved_by='office',source_record_id='stock',**({'job_id':'completed','work_id':'maintenance'} if key in ['installed','unused'] else {}))
    add('inv_reservations','scheduled',account_id='truck-a',job_id='scheduled',quantity=1,status='active',reserved_at=stamp,idempotency_key='demo-stock-reservation')
    add('inv_replenishment_policies','board',account_id='board',minimum_quantity=1,target_quantity=3,preferred_supplier_id='example')
    add('bill_quotes','completed',quote_number='DEMO-Q1',status='accepted',currency='USD',valid_until=day(30),customer_id='avery',property_id='home',job_id='completed')
    line=dict(position=1,kind='service',description='Fictional maintenance',quantity=1,unit_price=120,discount_amount=0,tax_rate=0,tax_jurisdiction='Fictional no-tax snapshot',tax_amount=0,line_total=120,unit_id='visit',service_id='maintenance',price_version_id='maintenance')
    add('bill_quote_lines','maintenance',quote_id='completed',**line)
    add('bill_accepted_scopes','completed',quote_id='completed',recorded_by='office',accepted_at=at(-2),accepted_name='Fictional Avery Chen',scope_snapshot={'service':'maintenance'},quote_snapshot={'currency':'USD','total':120},evidence_id='evidence')
    add('bill_invoices','discrepancy',invoice_number='DEMO-I1',status='review',currency='USD',subtotal=240,discount_total=0,tax_total=0,total=240,billing_customer_id='avery',job_id='completed',accepted_scope_id='completed')
    add('bill_invoice_lines','maintenance',invoice_id='discrepancy',work_id='maintenance',benefit_entry_id='consume',**line)
    material_line=dict(position=2,kind='material',description='Fictional overbilled capacitor quantity',quantity=3,unit_price=45,discount_amount=0,tax_rate=0,tax_jurisdiction='Fictional no-tax snapshot',tax_amount=0,line_total=135,unit_id='each',material_id='capacitor',price_version_id='capacitor',work_id='maintenance')
    add('bill_invoice_lines','material',invoice_id='discrepancy',**material_line)
    for key,reason,line_key in [('covered-service','Service charged despite benefit consumption','maintenance'),('material-count','Billed three, installed two, unused return one','material'),('header-mismatch','Header 240 differs from line sum 255',None)]:
        add('bill_review_flags',key,invoice_id='discrepancy',line_id=line_key,code=key,reason='Fictional discrepancy: '+reason,status='open',evidence_work_id='maintenance',evidence_file_id='evidence')
    add('bill_membership_schedules','care',agreement_id='active',period_start=day(-30),period_end=day(335),due_on=day(0),amount=300,currency='USD',status='planned')
    add('ai_runs','terms',provider='fictional-no-api',model='fixture',prompt_version='v1',started_at=stamp,finished_at=stamp,status='proposed',input_digest='0'*64,requested_by='office',metadata={'fictional':True})
    add('ai_extracted_terms','terms',run_id='terms',source_file_id='terms',field_name='remaining_visits',proposed_value={'unknown':True},source_locator='fictional page 1',evidence_excerpt='Balance is illegible in this fictional record',confidence=0.2)
    add('ai_change_sets','terms',run_id='terms',status='rejected',summary='Fictional unknown balance proposal',idempotency_key='demo-ai-proposal')
    add('ai_actions','terms',change_set_id='terms',evidence_term_id='terms',position=1,action_type='review_balance',target_table='agree_benefit_accounts',target_id=identifier('agree_benefit_accounts','ambiguous'),expected_version=1,proposed_values={'balance_state':'unknown'})
    add('ai_decisions','terms',change_set_id='terms',reviewer_id='office',decision='rejected',reason='Fictional evidence insufficient; no execution',decided_at=stamp)
    add('ai_execution_outcomes','terms',action_id='terms',decision_id='terms',status='skipped',error_code='REJECTED_PROPOSAL',executed_at=stamp,idempotency_key='demo-ai-outcome')
    add('audit_events','fixture',actor_kind='employee',actor_id='office',occurred_at=stamp,record_table='job_confirmed_work',record_id=identifier('job_confirmed_work','maintenance'),action='fictional-confirmation',before_values={},after_values={'confirmed':True},reason='Fictional audit fixture, not app execution',idempotency_key='demo-audit')
    add('follow_tasks','return',assigned_to='office',job_id='return',customer_id='avery',title='Fictional return visit readiness review',due_at=at(1),remind_at=at(1,10),status='open')
    add('follow_message_drafts','return',contact_id='avery',created_by='office',task_id='return',channel='email',subject='Fictional draft only',body='Never send: fictional return visit draft',status='draft')
    add('integrate_connections','ply',provider='ply',secret_reference='unconfigured://fictional-placeholder',enabled=False)
    add('integrate_authority','ply',connection_id='ply',entity_type='inventory',authority='goob',conflict_policy='manual')
    for key,kind,job in [('complete','job_status','completed'),('blocked','readiness','return'),('stock','inventory','completed'),('billing','billing_exception','completed')]:
        add('report_events',key,event_type=kind,occurred_at=stamp,idempotency_key='demo-event-'+key,is_fictional=True,payload={'fictional':True,'description':key},job_id=job,**({'movement_id':'installed'} if kind=='inventory' else {}),**({'invoice_id':'discrepancy'} if kind=='billing_exception' else {}))
    order={name:i for i,name in enumerate(ordered_tables())}
    return sorted(rows,key=lambda pair:order[pair[0]])


def dumps(value): return json.dumps(value,default=lambda x:float(x) if isinstance(x,Decimal) else str(x),sort_keys=True)

def lock_tables(cur):
    cur.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(sql.SQL(',').join(sql.Identifier('goob_foundation',t) for t in ordered_tables())))


def seed(db,as_of):
    lock_tooling(db)
    records=fixture_rows(as_of)
    conflicts=[]; skipped=0; new=[]
    with db.cursor() as cur:
        lock_tables(cur)
        for table,row in records:
            tenant_clause = '' if table=='org_organizations' else ' AND organization_id=%s'
            cur.execute(sql.SQL('SELECT to_jsonb(t) AS data FROM goob_foundation.{} t WHERE id=%s'+tenant_clause).format(sql.Identifier(table)),(row['id'],) if not tenant_clause else (row['id'],DEMO_ID))
            found=cur.fetchall()
            cur.execute('SELECT row_snapshot,as_of FROM goob_db_meta.fixture_rows WHERE organization_id=%s AND table_name=%s AND record_id=%s',(DEMO_ID,table,row['id']))
            manifest=cur.fetchone()
            if not found and not manifest: new.append((table,row));continue
            expected=json.loads(dumps(row))
            if len(found)!=1 or not manifest or manifest['as_of']!=as_of or found[0]['data']!=manifest['row_snapshot'] or any(found[0]['data'].get(k)!=v for k,v in expected.items()):
                conflicts.append({'table':table,'id':row['id']})
            else: skipped+=1
        if conflicts:
            db.rollback()
            return {'created':0,'skipped':skipped,'conflicting':len(conflicts),'conflicts':conflicts}
        for table,row in new:
            cols=list(row)
            values=[Json(row[c],dumps=dumps) if isinstance(row[c],(dict,list)) else row[c] for c in cols]
            cur.execute(sql.SQL('INSERT INTO goob_foundation.{} ({}) VALUES ({}) RETURNING to_jsonb({}.*) AS data').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols),sql.Identifier(table)),values)
            snapshot=cur.fetchone()['data']
            cur.execute('INSERT INTO goob_db_meta.fixture_rows VALUES(%s,%s,%s,%s,%s)',(DEMO_ID,table,row['id'],Json(snapshot,dumps=dumps),as_of))
    db.commit()
    return {'created':len(new),'skipped':skipped,'conflicting':0,'as_of':as_of.isoformat()}


def reset(db):
    lock_tooling(db)
    with db.cursor() as cur:
        lock_tables(cur)
        cur.execute('SELECT * FROM goob_db_meta.fixture_rows WHERE organization_id=%s',(DEMO_ID,))
        manifests={(r['table_name'],str(r['record_id'])):r['row_snapshot'] for r in cur.fetchall()}
        actual={}
        for table in ordered_tables():
            key='id' if table=='org_organizations' else 'organization_id'
            cur.execute(sql.SQL('SELECT id,to_jsonb(t) AS data FROM goob_foundation.{} t WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(key)),(DEMO_ID,))
            for row in cur.fetchall():actual[(table,str(row['id']))]=row['data']
        if actual!=manifests: raise ValueError('Demo rows differ from fixture manifest; reset refused without deleting anything.')
        if not actual: db.rollback();return {'deleted':0}
        root=actual.get(('org_organizations',DEMO_ID),{})
        if root.get('name')!='Goob Demo Services' or root.get('is_demo') is not True: raise ValueError('Known demo organization identity mismatch.')
        cur.execute("SELECT set_config('goob.demo_reset',%s,true)",(DEMO_ID,))
        # Delete only individually verified IDs; table order reverses the dependency graph.
        for table in reversed(ordered_tables()):
            ids=[record for t,record in manifests if t==table]
            # Self-references (reversals/renewals) are deleted together in one statement.
            if ids:
                clause='' if table=='org_organizations' else ' AND organization_id=%s'
                cur.execute(sql.SQL('DELETE FROM goob_foundation.{} WHERE id=ANY(%s::uuid[])'+clause).format(sql.Identifier(table)),(ids,) if not clause else (ids,DEMO_ID))
        cur.execute('DELETE FROM goob_db_meta.fixture_rows WHERE organization_id=%s',(DEMO_ID,))
    db.commit()
    return {'deleted':len(actual),'organization_id':DEMO_ID}
