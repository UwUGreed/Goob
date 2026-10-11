"""Database-only schema specification; no application imports or ORM.

Generate SQL/docs with python -m database.generate. Published migrations are
immutable: future changes must go into a new numbered migration.
"""
TABLES = {}


def table(name, columns='', refs=None, checks=(), unique=(), history=False, note=''):
    fields = {'organization_id': 'uuid NOT NULL', 'id': 'uuid NOT NULL DEFAULT gen_random_uuid()',
              'created_at': 'timestamptz NOT NULL DEFAULT now()'}
    for line in columns.strip().splitlines():
        if line.strip():
            key, value = line.strip().split(' ', 1)
            fields[key] = value
    refs = refs or {}
    references = {}
    for key, target in refs.items():
        optional = key.endswith('?')
        key = key.rstrip('?')
        fields[key] = 'uuid' + ('' if optional else ' NOT NULL')
        references[key] = target
    TABLES[name] = dict(columns=fields, refs=references, checks=list(checks),
                        unique=list(unique), history=history, note=note,
                        owner=name.split('_')[0])


table('org_organizations', '''
name text NOT NULL CHECK (length(trim(name)) > 0)
slug text NOT NULL UNIQUE
is_demo boolean NOT NULL DEFAULT false
archived_at timestamptz
''', note='Tenant root; archive instead of deleting operational history.')
TABLES['org_organizations']['columns'].pop('organization_id')
table('org_branches', 'name text NOT NULL\ntimezone text NOT NULL\narchived_at timestamptz', unique=[('organization_id','name')])
table('org_members', '''
auth_provider text NOT NULL
auth_subject text NOT NULL
display_name text NOT NULL
status text NOT NULL CHECK (status IN ('active','invited','inactive'))
''', {'branch_id?':'org_branches'}, unique=[('organization_id','auth_provider','auth_subject')], note='Opaque references to an external identity provider; no passwords or auth accounts.')
table('org_roles', 'name text NOT NULL', unique=[('organization_id','name')])
table('org_permissions', 'code text NOT NULL', unique=[('organization_id','code')])
table('org_role_permissions', refs={'role_id':'org_roles','permission_id':'org_permissions'}, unique=[('organization_id','role_id','permission_id')])
table('org_member_roles', refs={'member_id':'org_members','role_id':'org_roles'}, unique=[('organization_id','member_id','role_id')])
table('org_trades', 'code text NOT NULL\nname text NOT NULL\nenabled boolean NOT NULL DEFAULT true', unique=[('organization_id','code')])
table('org_modules', "code text NOT NULL\nenabled boolean NOT NULL DEFAULT false\nsettings jsonb NOT NULL DEFAULT '{}'::jsonb", unique=[('organization_id','code')])
table('org_technicians', 'employee_number text NOT NULL\nactive boolean NOT NULL DEFAULT true', {'member_id':'org_members'}, unique=[('organization_id','member_id'),('organization_id','employee_number')])
table('org_qualifications', 'code text NOT NULL\nname text NOT NULL', {'trade_id':'org_trades'}, unique=[('organization_id','code')])
table('org_technician_qualifications', 'valid_from date NOT NULL\nvalid_until date\ncredential_reference text', {'technician_id':'org_technicians','qualification_id':'org_qualifications'}, checks=['valid_until IS NULL OR valid_until >= valid_from'], unique=[('organization_id','technician_id','qualification_id','valid_from')])

table('crm_customers', "kind text NOT NULL CHECK (kind IN ('residential','commercial'))\ndisplay_name text NOT NULL\narchived_at timestamptz")
table('crm_contacts', 'given_name text NOT NULL\nfamily_name text NOT NULL\nemail text\nphone text\narchived_at timestamptz')
table('crm_customer_contacts', "relationship text NOT NULL\nis_primary boolean NOT NULL DEFAULT false", {'customer_id':'crm_customers','contact_id':'crm_contacts'}, unique=[('organization_id','customer_id','contact_id','relationship')])
table('crm_addresses', 'line1 text NOT NULL\nline2 text\ncity text NOT NULL\nregion text NOT NULL\npostal_code text NOT NULL\ncountry_code text NOT NULL CHECK (country_code ~ \'^[A-Z]{2}$\')')
table('crm_properties', 'name text NOT NULL\ntimezone text NOT NULL\narchived_at timestamptz', {'address_id':'crm_addresses'})
table('crm_customer_properties', "relationship text NOT NULL CHECK (relationship IN ('owner','tenant','manager','billing'))\nvalid_from date NOT NULL\nvalid_until date", {'customer_id':'crm_customers','property_id':'crm_properties'}, checks=['valid_until IS NULL OR valid_until >= valid_from'], unique=[('organization_id','customer_id','property_id','relationship','valid_from')])
table('crm_files', 'storage_reference text NOT NULL\nfilename text NOT NULL\ncontent_type text NOT NULL\nbyte_size bigint NOT NULL CHECK (byte_size >= 0)\nsha256 text NOT NULL CHECK (sha256 ~ \'^[0-9a-f]{64}$\')', note='Metadata only. Storage reference contains an object key, never credentials or file bytes.')
table('crm_equipment_types', 'name text NOT NULL', {'trade_id':'org_trades'}, unique=[('organization_id','trade_id','name')])
table('crm_equipment', '''
name text NOT NULL
make text
model text
serial_number text
installed_on date
warranty_until date
warranty_terms text
archived_at timestamptz
''', {'type_id':'crm_equipment_types','property_id':'crm_properties','warranty_document_id?':'crm_files'}, checks=['warranty_until IS NULL OR installed_on IS NULL OR warranty_until >= installed_on'], note='Current location projection; relocations and replacements remain in history; trade is derived from equipment type.')
table('crm_equipment_history', "kind text NOT NULL CHECK (kind IN ('installed','relocated','replaced','retired'))\neffective_at timestamptz NOT NULL\nreason text NOT NULL", {'equipment_id':'crm_equipment','from_property_id?':'crm_properties','to_property_id?':'crm_properties','replacement_equipment_id?':'crm_equipment','evidence_id?':'crm_files'}, checks=["kind <> 'relocated' OR (from_property_id IS NOT NULL AND to_property_id IS NOT NULL AND from_property_id <> to_property_id)","kind <> 'replaced' OR (replacement_equipment_id IS NOT NULL AND replacement_equipment_id <> equipment_id)"], history=True)
table('crm_notes', 'body text NOT NULL', {'author_id':'org_members','customer_id?':'crm_customers','property_id?':'crm_properties','equipment_id?':'crm_equipment','attachment_id?':'crm_files'}, checks=['num_nonnulls(customer_id,property_id,equipment_id) = 1'])
table('crm_communication_preferences', "channel text NOT NULL CHECK (channel IN ('email','sms','phone','postal'))\npurpose text NOT NULL\nallowed boolean NOT NULL\nrecorded_at timestamptz NOT NULL\nsource text NOT NULL", {'contact_id':'crm_contacts'}, unique=[('organization_id','contact_id','channel','purpose')])

table('cat_units', 'code text NOT NULL\ndimension text NOT NULL', unique=[('organization_id','code')])
table('cat_materials', 'sku text NOT NULL\nname text NOT NULL\nactive boolean NOT NULL DEFAULT true', {'unit_id':'cat_units'}, unique=[('organization_id','sku')])
table('cat_services', 'code text NOT NULL\nname text NOT NULL\nactive boolean NOT NULL DEFAULT true', {'trade_id':'org_trades'}, unique=[('organization_id','code')])
table('cat_job_types', 'code text NOT NULL\nname text NOT NULL', unique=[('organization_id','code')])
table('cat_pricebooks', 'name text NOT NULL\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')')
table('cat_price_versions', 'version integer NOT NULL CHECK (version > 0)\nvalid_from date NOT NULL\nvalid_until date\nunit_price numeric(19,4) NOT NULL CHECK (unit_price >= 0)', {'pricebook_id':'cat_pricebooks','unit_id':'cat_units','material_id?':'cat_materials','service_id?':'cat_services'}, checks=['num_nonnulls(material_id,service_id) = 1','valid_until IS NULL OR valid_until >= valid_from'], unique=[('organization_id','pricebook_id','material_id','version'),('organization_id','pricebook_id','service_id','version')], history=True)
table('cat_labor_rates', 'name text NOT NULL\nvalid_from date NOT NULL\nvalid_until date\nhourly_rate numeric(19,4) NOT NULL CHECK (hourly_rate >= 0)\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')', {'trade_id':'org_trades'}, checks=['valid_until IS NULL OR valid_until >= valid_from'], history=True)
table('cat_checklist_templates', 'name text NOT NULL\nversion integer NOT NULL CHECK (version > 0)', {'service_id':'cat_services'}, unique=[('organization_id','service_id','version')], history=True)
table('cat_checklist_items', 'position integer NOT NULL CHECK (position > 0)\ninstruction text NOT NULL\nrequired boolean NOT NULL DEFAULT true', {'template_id':'cat_checklist_templates'}, unique=[('organization_id','template_id','position')], history=True)
table('cat_material_requirements', 'quantity numeric(18,4) NOT NULL CHECK (quantity > 0)', {'service_id':'cat_services','material_id':'cat_materials'}, unique=[('organization_id','service_id','material_id')], note='Quantity uses the material base unit; no implicit unit conversions.')

table('import_batches', "source_system text NOT NULL\nidempotency_key text NOT NULL\nstatus text NOT NULL CHECK (status IN ('staged','review','approved','applied','rejected'))\nstarted_at timestamptz NOT NULL", {'source_file_id':'crm_files','requested_by':'org_members'}, unique=[('organization_id','idempotency_key')])
table('import_field_mappings', 'source_field text NOT NULL\ntarget_table text NOT NULL\ntarget_field text NOT NULL\ntransform_description text NOT NULL', {'batch_id':'import_batches'}, unique=[('organization_id','batch_id','source_field','target_table','target_field')])
table('import_staging_records', "source_identifier text NOT NULL\noriginal_values jsonb NOT NULL\nnormalized_values jsonb NOT NULL DEFAULT '{}'::jsonb\nstatus text NOT NULL CHECK (status IN ('pending','uncertain','approved','rejected','applied'))", {'batch_id':'import_batches'}, unique=[('organization_id','batch_id','source_identifier')])
table('import_validation_issues', "field_name text NOT NULL\nseverity text NOT NULL CHECK (severity IN ('warning','error'))\ncode text NOT NULL\ndescription text NOT NULL", {'record_id':'import_staging_records'})
table('import_duplicate_candidates', 'candidate_table text NOT NULL\ncandidate_id uuid NOT NULL\nreason text NOT NULL\nconfidence numeric(5,4) CHECK (confidence BETWEEN 0 AND 1)', {'record_id':'import_staging_records'}, note='Candidate is untrusted staging evidence, not an authoritative domain FK.')
table('import_decisions', "decision text NOT NULL CHECK (decision IN ('accept','reject','merge','defer'))\nreason text NOT NULL\ndecided_at timestamptz NOT NULL", {'record_id':'import_staging_records','reviewer_id':'org_members'}, history=True)
table('import_outcomes', 'idempotency_key text NOT NULL\ntarget_table text NOT NULL\ntarget_id uuid\noutcome text NOT NULL\nexecuted_at timestamptz NOT NULL', {'record_id':'import_staging_records','decision_id':'import_decisions'}, unique=[('organization_id','idempotency_key')], history=True)

table('agree_plans', 'code text NOT NULL\nname text NOT NULL\nactive boolean NOT NULL DEFAULT true', unique=[('organization_id','code')])
table('agree_plan_versions', 'version integer NOT NULL CHECK (version > 0)\nterms text NOT NULL\npublished_at timestamptz NOT NULL\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')\nperiod_price numeric(19,2) NOT NULL CHECK (period_price >= 0)', {'plan_id':'agree_plans','source_file_id?':'crm_files'}, unique=[('organization_id','plan_id','version')], history=True)
table('agree_benefit_definitions', "code text NOT NULL\nname text NOT NULL\nunit text NOT NULL\nservice_scope text NOT NULL CHECK (service_scope IN ('all','specific'))\nperiod_grant numeric(18,4) NOT NULL CHECK (period_grant >= 0)\neligibility_description text NOT NULL\nrequires_approval boolean NOT NULL DEFAULT true", {'plan_version_id':'agree_plan_versions','service_id?':'cat_services'}, checks=["(service_scope='all' AND service_id IS NULL) OR (service_scope='specific' AND service_id IS NOT NULL)"], unique=[('organization_id','plan_version_id','code')], history=True)
table('agree_agreements', '''
agreement_number text NOT NULL
starts_on date NOT NULL
ends_on date NOT NULL
status text NOT NULL CHECK (status IN ('draft','active','expired','cancelled','review'))
renewal_mode text NOT NULL CHECK (renewal_mode IN ('manual','automatic','none'))
renewal_notice_days integer NOT NULL DEFAULT 30 CHECK (renewal_notice_days >= 0)
interpretation_state text NOT NULL CHECK (interpretation_state IN ('unreviewed','approved','ambiguous','rejected'))
interpretation_approved_at timestamptz
terms_snapshot text NOT NULL
''', {'customer_id':'crm_customers','plan_version_id':'agree_plan_versions','source_file_id?':'crm_files','interpretation_reviewer_id?':'org_members'}, checks=['ends_on >= starts_on',"interpretation_state <> 'approved' OR (interpretation_reviewer_id IS NOT NULL AND interpretation_approved_at IS NOT NULL)"], unique=[('organization_id','agreement_number')], note='Frozen terms and version references; lifecycle dates/status may change only with change history.')
table('agree_coverage', '''
scope_kind text NOT NULL CHECK (scope_kind IN ('property','equipment','trade'))
service_scope text NOT NULL CHECK (service_scope IN ('all','specific'))
valid_from date NOT NULL
valid_until date NOT NULL
review_state text NOT NULL CHECK (review_state IN ('approved','ambiguous','rejected'))
''', {'agreement_id':'agree_agreements','property_id':'crm_properties','equipment_id?':'crm_equipment','trade_id?':'org_trades','service_id?':'cat_services'}, checks=["(scope_kind='property' AND equipment_id IS NULL AND trade_id IS NULL) OR (scope_kind='equipment' AND equipment_id IS NOT NULL AND trade_id IS NULL) OR (scope_kind='trade' AND trade_id IS NOT NULL AND equipment_id IS NULL)","(service_scope='all' AND service_id IS NULL) OR (service_scope='specific' AND service_id IS NOT NULL)",'valid_until >= valid_from'], note='Every scope names a property. Explicit all/specific service scope; NULL never means wildcard on its own.')
table('agree_benefit_accounts', "balance_state text NOT NULL CHECK (balance_state IN ('known','unknown'))\nperiod_start date NOT NULL\nperiod_end date NOT NULL", {'agreement_id':'agree_agreements','benefit_definition_id':'agree_benefit_definitions','source_record_id?':'import_staging_records'}, checks=['period_end >= period_start'], unique=[('organization_id','agreement_id','benefit_definition_id','period_start')])
table('agree_changes', 'kind text NOT NULL\neffective_at timestamptz NOT NULL\nreason text NOT NULL\nbefore_values jsonb NOT NULL\nafter_values jsonb NOT NULL', {'agreement_id':'agree_agreements','approved_by':'org_members','renewal_agreement_id?':'agree_agreements'}, history=True)

table('job_jobs', "job_number text NOT NULL\nstatus text NOT NULL CHECK (status IN ('draft','scheduled','in_progress','completed','cancelled','return_required'))\nplanned_scope text NOT NULL\nversion integer NOT NULL DEFAULT 1 CHECK (version > 0)", {'billing_customer_id':'crm_customers','property_id':'crm_properties','branch_id':'org_branches','job_type_id':'cat_job_types'}, unique=[('organization_id','job_number')])
table('job_trades', refs={'job_id':'job_jobs','trade_id':'org_trades'}, unique=[('organization_id','job_id','trade_id')])
table('job_equipment', refs={'job_id':'job_jobs','equipment_id':'crm_equipment'}, unique=[('organization_id','job_id','equipment_id')])
table('job_tasks', 'description text NOT NULL\nplanned_quantity numeric(18,4) NOT NULL CHECK (planned_quantity > 0)\nstatus text NOT NULL CHECK (status IN (\'planned\',\'cancelled\',\'confirmed\'))', {'job_id':'job_jobs','service_id':'cat_services','checklist_template_id?':'cat_checklist_templates'})
table('job_appointments', 'starts_at timestamptz NOT NULL\nends_at timestamptz NOT NULL\nstatus text NOT NULL CHECK (status IN (\'scheduled\',\'completed\',\'cancelled\'))', {'job_id':'job_jobs'}, checks=['ends_at > starts_at'])
table('job_assignments', refs={'appointment_id':'job_appointments','technician_id':'org_technicians'}, unique=[('organization_id','appointment_id','technician_id')])
table('job_availability', 'starts_at timestamptz NOT NULL\nends_at timestamptz NOT NULL\nkind text NOT NULL CHECK (kind IN (\'available\',\'unavailable\'))\nreason text NOT NULL', {'technician_id':'org_technicians'}, checks=['ends_at > starts_at'])
table('job_time_entries', 'starts_at timestamptz NOT NULL\nends_at timestamptz NOT NULL\nkind text NOT NULL CHECK (kind IN (\'labor\',\'travel\',\'break\'))', {'job_id':'job_jobs','technician_id':'org_technicians','approved_by?':'org_members'}, checks=['ends_at > starts_at'])
table('job_status_history', 'from_status text\nto_status text NOT NULL\nchanged_at timestamptz NOT NULL\nreason text NOT NULL', {'job_id':'job_jobs','actor_id':'org_members'}, history=True)
table('job_confirmed_work', 'description text NOT NULL\nquantity numeric(18,4) NOT NULL CHECK (quantity > 0)\nconfirmed_at timestamptz NOT NULL\nidempotency_key text NOT NULL', {'job_id':'job_jobs','task_id?':'job_tasks','service_id':'cat_services','unit_id':'cat_units','confirmed_by':'org_members'}, unique=[('organization_id','idempotency_key')], history=True)
table('job_work_evidence', 'description text NOT NULL', {'work_id':'job_confirmed_work','file_id':'crm_files'}, unique=[('organization_id','work_id','file_id')], history=True)
table('job_return_links', 'reason text NOT NULL', {'original_job_id':'job_jobs','return_job_id':'job_jobs'}, checks=['original_job_id <> return_job_id'], unique=[('organization_id','original_job_id','return_job_id')])
table('job_required_materials', 'quantity numeric(18,4) NOT NULL CHECK (quantity > 0)', {'job_id':'job_jobs','material_id':'cat_materials'}, unique=[('organization_id','job_id','material_id')])
table('job_readiness_checks', "checked_at timestamptz NOT NULL\nresult text NOT NULL CHECK (result IN ('ready','blocked','unknown'))\nrule_code text NOT NULL\nreason text NOT NULL", {'job_id':'job_jobs','material_id?':'cat_materials','evidence_file_id?':'crm_files'}, history=True)

table('agree_benefit_ledger', '''
kind text NOT NULL CHECK (kind IN ('grant','consumption','expiration','reversal','adjustment'))
quantity numeric(18,4) NOT NULL CHECK (quantity <> 0)
occurred_at timestamptz NOT NULL
idempotency_key text NOT NULL
reason text NOT NULL
''', {'account_id':'agree_benefit_accounts','job_id?':'job_jobs','work_id?':'job_confirmed_work','source_record_id?':'import_staging_records','reverses_id?':'agree_benefit_ledger','approved_by':'org_members'}, checks=["(kind='grant' AND quantity>0) OR (kind IN ('consumption','expiration') AND quantity<0) OR kind IN ('reversal','adjustment')","(kind='reversal') = (reverses_id IS NOT NULL)","kind <> 'consumption' OR work_id IS NOT NULL"], unique=[('organization_id','idempotency_key'),('organization_id','reverses_id')], history=True)
table('agree_benefit_reservations', "quantity numeric(18,4) NOT NULL CHECK (quantity > 0)\nstatus text NOT NULL CHECK (status IN ('active','released','consumed'))\nreserved_at timestamptz NOT NULL\nresolved_at timestamptz\nresolution_reason text\nidempotency_key text NOT NULL", {'account_id':'agree_benefit_accounts','job_id':'job_jobs','consumption_entry_id?':'agree_benefit_ledger'}, checks=["(status='active' AND resolved_at IS NULL) OR (status<>'active' AND resolved_at IS NOT NULL AND resolution_reason IS NOT NULL)","(status='consumed') = (consumption_entry_id IS NOT NULL)"], unique=[('organization_id','idempotency_key')])
table('agree_planned_visits', 'due_from date NOT NULL\ndue_until date NOT NULL\nstatus text NOT NULL CHECK (status IN (\'planned\',\'scheduled\',\'completed\',\'cancelled\'))', {'agreement_id':'agree_agreements','property_id':'crm_properties','service_id':'cat_services','job_id?':'job_jobs','completed_work_id?':'job_confirmed_work'}, checks=['due_until >= due_from',"status <> 'completed' OR completed_work_id IS NOT NULL"])

table('inv_suppliers', 'name text NOT NULL\nexternal_reference text')
table('inv_supplier_materials', 'supplier_sku text NOT NULL\nlead_days integer CHECK (lead_days >= 0)', {'supplier_id':'inv_suppliers','material_id':'cat_materials'}, unique=[('organization_id','supplier_id','supplier_sku')])
table('inv_locations', "code text NOT NULL\nname text NOT NULL\nkind text NOT NULL CHECK (kind IN ('warehouse','truck','quarantine','other'))\nactive boolean NOT NULL DEFAULT true", {'branch_id':'org_branches','technician_id?':'org_technicians'}, unique=[('organization_id','code')])
table('inv_stock_accounts', refs={'location_id':'inv_locations','material_id':'cat_materials'}, unique=[('organization_id','location_id','material_id')], note='Lock row before changing movements/reservations; on-hand is derived, not an editable opening quantity.')
table('inv_movements', '''
kind text NOT NULL CHECK (kind IN ('opening','receipt','transfer','consumption','usable_return','damaged_return','adjustment','reversal'))
quantity numeric(18,4) NOT NULL CHECK (quantity > 0)
unit_cost numeric(19,4) NOT NULL CHECK (unit_cost >= 0)
currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')
occurred_at timestamptz NOT NULL
idempotency_key text NOT NULL
reason text NOT NULL
''', {'material_id':'cat_materials','from_account_id?':'inv_stock_accounts','to_account_id?':'inv_stock_accounts','job_id?':'job_jobs','work_id?':'job_confirmed_work','source_record_id?':'import_staging_records','reverses_id?':'inv_movements','approved_by':'org_members'}, checks=['num_nonnulls(from_account_id,to_account_id) >= 1','from_account_id IS NULL OR to_account_id IS NULL OR from_account_id <> to_account_id',"kind <> 'transfer' OR (from_account_id IS NOT NULL AND to_account_id IS NOT NULL)","kind NOT IN ('opening','receipt','usable_return','damaged_return') OR (from_account_id IS NULL AND to_account_id IS NOT NULL)","kind <> 'consumption' OR (from_account_id IS NOT NULL AND to_account_id IS NULL AND work_id IS NOT NULL)","(kind='reversal') = (reverses_id IS NOT NULL)","kind <> 'opening' OR source_record_id IS NOT NULL"], unique=[('organization_id','idempotency_key'),('organization_id','reverses_id')], history=True, note='Single row stores both legs of a transfer; equal quantity/cost by construction. Posted entries are append-only.')
table('inv_reservations', "quantity numeric(18,4) NOT NULL CHECK (quantity > 0)\nstatus text NOT NULL CHECK (status IN ('active','released','consumed'))\nreserved_at timestamptz NOT NULL\nresolved_at timestamptz\nresolution_reason text\nidempotency_key text NOT NULL", {'account_id':'inv_stock_accounts','job_id':'job_jobs','consumption_movement_id?':'inv_movements'}, checks=["(status='active' AND resolved_at IS NULL) OR (status<>'active' AND resolved_at IS NOT NULL AND resolution_reason IS NOT NULL)","(status='consumed') = (consumption_movement_id IS NOT NULL)"], unique=[('organization_id','idempotency_key')])
table('inv_replenishment_policies', 'minimum_quantity numeric(18,4) NOT NULL CHECK (minimum_quantity >= 0)\ntarget_quantity numeric(18,4) NOT NULL CHECK (target_quantity >= minimum_quantity)', {'account_id':'inv_stock_accounts','preferred_supplier_id?':'inv_suppliers'}, unique=[('organization_id','account_id')])

table('bill_quotes', 'quote_number text NOT NULL\nstatus text NOT NULL CHECK (status IN (\'draft\',\'accepted\',\'rejected\',\'expired\'))\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')\nvalid_until date NOT NULL', {'customer_id':'crm_customers','property_id':'crm_properties','job_id?':'job_jobs'}, unique=[('organization_id','quote_number')])
LINE = '''
position integer NOT NULL CHECK (position > 0)
kind text NOT NULL CHECK (kind IN ('service','labor','material'))
description text NOT NULL
quantity numeric(18,4) NOT NULL CHECK (quantity > 0)
unit_price numeric(19,4) NOT NULL CHECK (unit_price >= 0)
discount_amount numeric(19,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0)
tax_rate numeric(9,6) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 1)
tax_jurisdiction text NOT NULL
tax_amount numeric(19,2) NOT NULL CHECK (tax_amount >= 0)
line_total numeric(19,2) NOT NULL CHECK (line_total >= 0)
'''
table('bill_quote_lines', LINE, {'quote_id':'bill_quotes','unit_id':'cat_units','service_id?':'cat_services','material_id?':'cat_materials','price_version_id?':'cat_price_versions','labor_rate_id?':'cat_labor_rates'}, checks=['discount_amount <= round(quantity*unit_price,2)','tax_amount = round((round(quantity*unit_price,2)-discount_amount)*tax_rate,2)','line_total = round(quantity*unit_price,2)-discount_amount+tax_amount'], unique=[('organization_id','quote_id','position')])
table('bill_accepted_scopes', 'accepted_at timestamptz NOT NULL\naccepted_name text NOT NULL\nscope_snapshot jsonb NOT NULL\nquote_snapshot jsonb NOT NULL', {'quote_id':'bill_quotes','recorded_by':'org_members','evidence_id?':'crm_files'}, unique=[('organization_id','quote_id')], history=True)
table('bill_invoices', '''
invoice_number text NOT NULL
status text NOT NULL CHECK (status IN ('draft','review','issued','void'))
currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')
subtotal numeric(19,2) NOT NULL CHECK (subtotal >= 0)
discount_total numeric(19,2) NOT NULL CHECK (discount_total >= 0)
tax_total numeric(19,2) NOT NULL CHECK (tax_total >= 0)
total numeric(19,2) NOT NULL CHECK (total >= 0)
version integer NOT NULL DEFAULT 1 CHECK (version > 0)
''', {'billing_customer_id':'crm_customers','job_id?':'job_jobs','accepted_scope_id?':'bill_accepted_scopes'}, checks=['total = subtotal-discount_total+tax_total'], unique=[('organization_id','invoice_number')])
table('bill_invoice_lines', LINE, {'invoice_id':'bill_invoices','unit_id':'cat_units','service_id?':'cat_services','material_id?':'cat_materials','price_version_id?':'cat_price_versions','labor_rate_id?':'cat_labor_rates','work_id?':'job_confirmed_work','benefit_entry_id?':'agree_benefit_ledger'}, checks=['discount_amount <= round(quantity*unit_price,2)','tax_amount = round((round(quantity*unit_price,2)-discount_amount)*tax_rate,2)','line_total = round(quantity*unit_price,2)-discount_amount+tax_amount'], unique=[('organization_id','invoice_id','position')])
table('bill_review_flags', "code text NOT NULL\nreason text NOT NULL\nstatus text NOT NULL CHECK (status IN ('open','resolved','dismissed'))\nresolution text\nresolved_at timestamptz", {'invoice_id':'bill_invoices','line_id?':'bill_invoice_lines','evidence_file_id?':'crm_files','evidence_work_id?':'job_confirmed_work','reviewer_id?':'org_members'}, checks=["status = 'open' OR (resolution IS NOT NULL AND resolved_at IS NOT NULL AND reviewer_id IS NOT NULL)"])
table('bill_issued_snapshots', 'issued_at timestamptz NOT NULL\ncustomer_snapshot jsonb NOT NULL\naddress_snapshot jsonb NOT NULL\nlines_snapshot jsonb NOT NULL CHECK (jsonb_typeof(lines_snapshot)=\'array\')\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')\ntotal numeric(19,2) NOT NULL CHECK (total >= 0)\nidempotency_key text NOT NULL', {'invoice_id':'bill_invoices','issued_by':'org_members'}, unique=[('organization_id','invoice_id'),('organization_id','idempotency_key')], history=True)
table('bill_corrections', "kind text NOT NULL CHECK (kind IN ('credit','correction'))\namount numeric(19,2) NOT NULL CHECK (amount <> 0)\ncurrency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$')\nreason text NOT NULL\nissued_at timestamptz NOT NULL\nline_snapshot jsonb NOT NULL\nidempotency_key text NOT NULL", {'issued_snapshot_id':'bill_issued_snapshots','approved_by':'org_members'}, unique=[('organization_id','idempotency_key')], history=True)
table('bill_membership_schedules', 'period_start date NOT NULL\nperiod_end date NOT NULL\ndue_on date NOT NULL\namount numeric(19,2) NOT NULL CHECK (amount >= 0)\ncurrency text NOT NULL CHECK (currency ~ \'^[A-Z]{3}$\')\nstatus text NOT NULL CHECK (status IN (\'planned\',\'billed\',\'cancelled\'))', {'agreement_id':'agree_agreements'}, checks=['period_end >= period_start'], unique=[('organization_id','agreement_id','period_start')])

table('ai_runs', 'provider text NOT NULL\nmodel text NOT NULL\nprompt_version text NOT NULL\nstarted_at timestamptz NOT NULL\nfinished_at timestamptz\nstatus text NOT NULL CHECK (status IN (\'proposed\',\'completed\',\'failed\'))\ninput_digest text NOT NULL\nmetadata jsonb NOT NULL DEFAULT \'{}\'::jsonb', {'requested_by':'org_members'}, checks=['finished_at IS NULL OR finished_at >= started_at'])
table('ai_extracted_terms', 'field_name text NOT NULL\nproposed_value jsonb NOT NULL\nsource_locator text NOT NULL\nevidence_excerpt text NOT NULL\nconfidence numeric(5,4) CHECK (confidence BETWEEN 0 AND 1)', {'run_id':'ai_runs','source_file_id':'crm_files'}, history=True)
table('ai_change_sets', 'status text NOT NULL CHECK (status IN (\'proposed\',\'approved\',\'rejected\',\'executed\',\'failed\'))\nsummary text NOT NULL\nidempotency_key text NOT NULL', {'run_id':'ai_runs'}, unique=[('organization_id','idempotency_key')])
table('ai_actions', 'position integer NOT NULL CHECK (position > 0)\naction_type text NOT NULL\ntarget_table text NOT NULL\ntarget_id uuid\nexpected_version integer\nproposed_values jsonb NOT NULL', {'change_set_id':'ai_change_sets','evidence_term_id?':'ai_extracted_terms'}, unique=[('organization_id','change_set_id','position')], history=True, note='Non-authoritative proposal only; target is an untrusted suggestion, not a command.')
table('ai_decisions', 'decision text NOT NULL CHECK (decision IN (\'approved\',\'rejected\'))\nreason text NOT NULL\ndecided_at timestamptz NOT NULL', {'change_set_id':'ai_change_sets','reviewer_id':'org_members'}, history=True)
table('ai_execution_outcomes', 'status text NOT NULL CHECK (status IN (\'succeeded\',\'failed\',\'skipped\'))\nrecord_table text\nrecord_id uuid\nerror_code text\nexecuted_at timestamptz NOT NULL\nidempotency_key text NOT NULL', {'action_id':'ai_actions','decision_id':'ai_decisions'}, unique=[('organization_id','idempotency_key')], history=True)
table('audit_events', "actor_kind text NOT NULL CHECK (actor_kind IN ('employee','system','import'))\noccurred_at timestamptz NOT NULL\nrecord_table text NOT NULL\nrecord_id uuid NOT NULL\naction text NOT NULL\nbefore_values jsonb\nafter_values jsonb\nreason text NOT NULL\nidempotency_key text NOT NULL", {'actor_id?':'org_members'}, checks=["actor_kind <> 'employee' OR actor_id IS NOT NULL"], unique=[('organization_id','idempotency_key')], history=True, note='Record pointer deliberately survives deletions/archival; structured tenant and actor FK; no automatic application event producer.')

table('follow_tasks', 'title text NOT NULL\ndue_at timestamptz NOT NULL\nstatus text NOT NULL CHECK (status IN (\'open\',\'done\',\'cancelled\'))\nremind_at timestamptz', {'assigned_to':'org_members','customer_id?':'crm_customers','job_id?':'job_jobs'})
table('follow_message_drafts', 'channel text NOT NULL CHECK (channel IN (\'email\',\'sms\'))\nsubject text\nbody text NOT NULL\nstatus text NOT NULL CHECK (status IN (\'draft\',\'approved\',\'cancelled\'))', {'contact_id':'crm_contacts','created_by':'org_members','task_id?':'follow_tasks','approved_by?':'org_members'}, checks=["status <> 'approved' OR approved_by IS NOT NULL"])
table('follow_delivery_attempts', 'attempt integer NOT NULL CHECK (attempt > 0)\nattempted_at timestamptz NOT NULL\nstatus text NOT NULL CHECK (status IN (\'pending\',\'succeeded\',\'failed\'))\nprovider_reference text\nerror_code text\nretry_after timestamptz', {'draft_id':'follow_message_drafts'}, unique=[('organization_id','draft_id','attempt')], history=True)
table('integrate_connections', 'provider text NOT NULL\nsecret_reference text NOT NULL\nenabled boolean NOT NULL DEFAULT false', unique=[('organization_id','provider')], note='Secret-manager reference only; no access tokens or plaintext credentials.')
table('integrate_record_mappings', 'entity_type text NOT NULL\nlocal_record_id uuid NOT NULL\nexternal_id text NOT NULL', {'connection_id':'integrate_connections'}, unique=[('organization_id','connection_id','entity_type','external_id'),('organization_id','connection_id','entity_type','local_record_id')])
table('integrate_sync_attempts', 'started_at timestamptz NOT NULL\nfinished_at timestamptz\nstatus text NOT NULL CHECK (status IN (\'pending\',\'succeeded\',\'failed\'))\nerror_code text\nerror_detail text\nretry_after timestamptz\nidempotency_key text NOT NULL', {'connection_id':'integrate_connections'}, unique=[('organization_id','idempotency_key')], history=True)
table('integrate_checkpoints', 'stream text NOT NULL\ncursor_value text NOT NULL\nupdated_at timestamptz NOT NULL', {'connection_id':'integrate_connections'}, unique=[('organization_id','connection_id','stream')])
table('integrate_authority', "entity_type text NOT NULL\nauthority text NOT NULL CHECK (authority IN ('goob','provider'))\nconflict_policy text NOT NULL CHECK (conflict_policy IN ('manual','authoritative_wins'))", {'connection_id':'integrate_connections'}, unique=[('organization_id','connection_id','entity_type')], note='Optional Ply source-of-truth configuration only; no integration execution.')
table('report_events', "event_type text NOT NULL CHECK (event_type IN ('job_status','readiness','inventory','billing_exception','billing_resolution'))\noccurred_at timestamptz NOT NULL\nidempotency_key text NOT NULL\nis_fictional boolean NOT NULL DEFAULT false\npayload jsonb NOT NULL DEFAULT '{}'::jsonb", {'job_id?':'job_jobs','movement_id?':'inv_movements','invoice_id?':'bill_invoices'}, unique=[('organization_id','idempotency_key')], history=True, note='Optional ordinary PostgreSQL reporting projection. No retention policy or hypertable; authoritative records are elsewhere.')


def ordered_tables():
    result = []
    pending = dict(TABLES)
    while pending:
        ready = [name for name, spec in pending.items()
                 if all(ref in result or ref == name for ref in spec['refs'].values())
                 and (name == 'org_organizations' or 'org_organizations' in result)]
        if not ready:
            raise ValueError('Circular table dependencies: ' + ','.join(pending))
        for name in ready:
            result.append(name)
            pending.pop(name)
    return result
