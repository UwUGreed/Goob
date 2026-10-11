-- Hand-authored database contracts; PostgreSQL 15+; no extensions required.
SET LOCAL search_path TO goob_foundation, pg_catalog;

CREATE FUNCTION demo_reset_allowed(tenant uuid) RETURNS boolean LANGUAGE sql STABLE
SET search_path=pg_catalog AS $$
 SELECT current_setting('goob.demo_reset',true) = tenant::text
    AND current_database() ~ '^goob_dev_[a-z0-9_]+$'
    AND shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()),'pg_database') = 'goob-isolated-development-v1'
$$;

CREATE FUNCTION protect_history() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' AND demo_reset_allowed(OLD.organization_id) THEN RETURN OLD; END IF;
 RAISE EXCEPTION 'posted history is immutable; append a version, reversal or adjustment' USING ERRCODE='23514';
END $$;

CREATE VIEW inv_balances AS
 SELECT a.organization_id,a.id AS account_id,a.location_id,a.material_id,
 COALESCE((SELECT sum(CASE WHEN m.to_account_id=a.id THEN m.quantity ELSE -m.quantity END)
   FROM inv_movements m WHERE m.organization_id=a.organization_id AND (m.to_account_id=a.id OR m.from_account_id=a.id)),0)::numeric(18,4) AS on_hand,
 COALESCE((SELECT sum(r.quantity) FROM inv_reservations r WHERE r.organization_id=a.organization_id AND r.account_id=a.id AND r.status='active'),0)::numeric(18,4) AS reserved,
 (COALESCE((SELECT sum(CASE WHEN m.to_account_id=a.id THEN m.quantity ELSE -m.quantity END)
   FROM inv_movements m WHERE m.organization_id=a.organization_id AND (m.to_account_id=a.id OR m.from_account_id=a.id)),0)
 - COALESCE((SELECT sum(r.quantity) FROM inv_reservations r WHERE r.organization_id=a.organization_id AND r.account_id=a.id AND r.status='active'),0))::numeric(18,4) AS available
 FROM inv_stock_accounts a;

CREATE VIEW agree_balances AS
 SELECT a.organization_id,a.id AS account_id,a.agreement_id,a.balance_state,
 CASE WHEN a.balance_state='known' THEN COALESCE(l.balance,0) END::numeric(18,4) AS remaining,
 COALESCE(r.reserved,0)::numeric(18,4) AS reserved,
 CASE WHEN a.balance_state='known' THEN COALESCE(l.balance,0)-COALESCE(r.reserved,0) END::numeric(18,4) AS available
 FROM agree_benefit_accounts a
 LEFT JOIN LATERAL (SELECT sum(quantity) balance FROM agree_benefit_ledger l WHERE l.organization_id=a.organization_id AND l.account_id=a.id) l ON true
 LEFT JOIN LATERAL (SELECT sum(quantity) reserved FROM agree_benefit_reservations r WHERE r.organization_id=a.organization_id AND r.account_id=a.id AND r.status='active') r ON true;

CREATE VIEW bill_invoice_reconciliation AS
 SELECT i.organization_id,i.id AS invoice_id,i.total AS recorded_total,
 COALESCE(sum(l.line_total),0)::numeric(19,2) AS calculated_total,
 (i.total-COALESCE(sum(l.line_total),0))::numeric(19,2) AS discrepancy
 FROM bill_invoices i LEFT JOIN bill_invoice_lines l ON l.organization_id=i.organization_id AND l.invoice_id=i.id
 GROUP BY i.organization_id,i.id,i.total;

CREATE FUNCTION lock_inventory() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE original inv_movements; a inv_stock_accounts; loc_kind text; row_json jsonb;
BEGIN
 IF TG_OP='DELETE' AND demo_reset_allowed(OLD.organization_id) THEN RETURN OLD; END IF;
 IF TG_TABLE_NAME='inv_movements' THEN
   PERFORM 1 FROM inv_stock_accounts WHERE organization_id=NEW.organization_id
      AND id IN (NEW.from_account_id,NEW.to_account_id) ORDER BY id FOR UPDATE;
   FOR a IN SELECT * FROM inv_stock_accounts WHERE organization_id=NEW.organization_id AND id IN (NEW.from_account_id,NEW.to_account_id) LOOP
     IF a.material_id <> NEW.material_id THEN RAISE EXCEPTION 'movement/account material mismatch' USING ERRCODE='23514'; END IF;
   END LOOP;
   IF NEW.kind='damaged_return' THEN
     SELECT l.kind INTO loc_kind FROM inv_stock_accounts s JOIN inv_locations l ON (l.organization_id,l.id)=(s.organization_id,s.location_id)
       WHERE s.organization_id=NEW.organization_id AND s.id=NEW.to_account_id;
     IF loc_kind IS DISTINCT FROM 'quarantine' THEN RAISE EXCEPTION 'damaged return requires quarantine location' USING ERRCODE='23514'; END IF;
   END IF;
   IF NEW.kind='reversal' THEN
     SELECT * INTO original FROM inv_movements WHERE organization_id=NEW.organization_id AND id=NEW.reverses_id;
     IF NOT FOUND OR original.kind='reversal' OR NEW.quantity<>original.quantity OR NEW.material_id<>original.material_id
        OR NEW.unit_cost<>original.unit_cost OR NEW.currency<>original.currency
        OR NEW.from_account_id IS DISTINCT FROM original.to_account_id OR NEW.to_account_id IS DISTINCT FROM original.from_account_id THEN
       RAISE EXCEPTION 'reversal must exactly invert an original movement' USING ERRCODE='23514';
     END IF;
   END IF;
   IF NEW.work_id IS NOT NULL AND NEW.job_id IS DISTINCT FROM
       (SELECT job_id FROM job_confirmed_work WHERE organization_id=NEW.organization_id AND id=NEW.work_id) THEN
     RAISE EXCEPTION 'movement work/job mismatch' USING ERRCODE='23514';
   END IF;
 ELSE
   PERFORM 1 FROM inv_stock_accounts WHERE organization_id=NEW.organization_id AND id=NEW.account_id FOR UPDATE;
   IF NEW.status='consumed' AND NOT EXISTS(SELECT 1 FROM inv_movements m WHERE m.organization_id=NEW.organization_id
      AND m.id=NEW.consumption_movement_id AND m.from_account_id=NEW.account_id AND m.job_id=NEW.job_id
      AND m.kind='consumption' AND m.quantity=NEW.quantity) THEN
     RAISE EXCEPTION 'reservation consumption mismatch' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER inventory_movement_lock BEFORE INSERT ON inv_movements FOR EACH ROW EXECUTE FUNCTION lock_inventory();
CREATE TRIGGER inventory_reservation_lock BEFORE INSERT OR UPDATE ON inv_reservations FOR EACH ROW EXECUTE FUNCTION lock_inventory();

CREATE FUNCTION check_inventory_balance() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE ids uuid[]; tenant uuid;
BEGIN
 IF TG_OP='DELETE' AND demo_reset_allowed(OLD.organization_id) THEN RETURN NULL; END IF;
 tenant:=NEW.organization_id;
 IF TG_TABLE_NAME='inv_movements' THEN ids:=ARRAY[NEW.from_account_id,NEW.to_account_id]; ELSE ids:=ARRAY[NEW.account_id]; END IF;
 IF EXISTS(SELECT 1 FROM inv_balances WHERE organization_id=tenant AND account_id=ANY(ids) AND (on_hand<0 OR available<0)) THEN
   RAISE EXCEPTION 'insufficient inventory including reservations' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER inventory_balance AFTER INSERT ON inv_movements DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_balance();
CREATE CONSTRAINT TRIGGER inventory_reserved_balance AFTER INSERT OR UPDATE ON inv_reservations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_balance();

CREATE FUNCTION lock_benefit() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE original agree_benefit_ledger; state text;
BEGIN
 SELECT balance_state INTO state FROM agree_benefit_accounts WHERE organization_id=NEW.organization_id AND id=NEW.account_id FOR UPDATE;
 IF TG_TABLE_NAME='agree_benefit_ledger' THEN
   IF NEW.quantity<0 AND state='unknown' THEN RAISE EXCEPTION 'cannot consume unknown balance' USING ERRCODE='23514'; END IF;
   IF NEW.kind='reversal' THEN
     SELECT * INTO original FROM agree_benefit_ledger WHERE organization_id=NEW.organization_id AND id=NEW.reverses_id;
     IF NOT FOUND OR original.kind='reversal' OR NEW.account_id<>original.account_id OR NEW.quantity<>-original.quantity THEN
       RAISE EXCEPTION 'benefit reversal must invert original entry' USING ERRCODE='23514';
     END IF;
   END IF;
   IF NEW.work_id IS NOT NULL AND NEW.job_id IS DISTINCT FROM
       (SELECT job_id FROM job_confirmed_work WHERE organization_id=NEW.organization_id AND id=NEW.work_id) THEN
     RAISE EXCEPTION 'benefit work/job mismatch' USING ERRCODE='23514';
   END IF;
 ELSE
   IF state='unknown' AND NEW.status='active' THEN RAISE EXCEPTION 'cannot reserve unknown balance' USING ERRCODE='23514'; END IF;
   IF NEW.status='consumed' AND NOT EXISTS(SELECT 1 FROM agree_benefit_ledger l WHERE l.organization_id=NEW.organization_id
      AND l.id=NEW.consumption_entry_id AND l.account_id=NEW.account_id AND l.job_id=NEW.job_id
      AND l.kind='consumption' AND l.quantity=-NEW.quantity) THEN
     RAISE EXCEPTION 'benefit reservation consumption mismatch' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER benefit_ledger_lock BEFORE INSERT ON agree_benefit_ledger FOR EACH ROW EXECUTE FUNCTION lock_benefit();
CREATE TRIGGER benefit_reservation_lock BEFORE INSERT OR UPDATE ON agree_benefit_reservations FOR EACH ROW EXECUTE FUNCTION lock_benefit();
CREATE FUNCTION check_benefit_balance() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM agree_balances WHERE organization_id=NEW.organization_id AND account_id=NEW.account_id
    AND (remaining<0 OR available<0 OR (balance_state='unknown' AND reserved>0))) THEN
   RAISE EXCEPTION 'insufficient benefit balance including reservations' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER benefit_balance AFTER INSERT ON agree_benefit_ledger DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_benefit_balance();
CREATE CONSTRAINT TRIGGER benefit_reserved_balance AFTER INSERT OR UPDATE ON agree_benefit_reservations DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_benefit_balance();

CREATE FUNCTION protect_reservation() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' AND demo_reset_allowed(OLD.organization_id) THEN RETURN OLD; END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'release reservation instead of deleting it' USING ERRCODE='23514'; END IF;
 IF OLD.status<>'active' OR NEW.status='active' OR
   (to_jsonb(NEW)-ARRAY['status','resolved_at','resolution_reason','consumption_entry_id','consumption_movement_id']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['status','resolved_at','resolution_reason','consumption_entry_id','consumption_movement_id']) THEN
   RAISE EXCEPTION 'reservation can only transition from active to released/consumed' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER reservation_history BEFORE UPDATE OR DELETE ON inv_reservations FOR EACH ROW EXECUTE FUNCTION protect_reservation();
CREATE TRIGGER reservation_history BEFORE UPDATE OR DELETE ON agree_benefit_reservations FOR EACH ROW EXECUTE FUNCTION protect_reservation();
CREATE TRIGGER stock_account_identity BEFORE UPDATE OR DELETE ON inv_stock_accounts FOR EACH ROW EXECUTE FUNCTION protect_history();

CREATE FUNCTION check_domain_links() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE expected uuid; actual uuid;
BEGIN
 IF TG_TABLE_NAME='agree_benefit_accounts' THEN
   SELECT plan_version_id INTO expected FROM agree_agreements WHERE organization_id=NEW.organization_id AND id=NEW.agreement_id;
   SELECT plan_version_id INTO actual FROM agree_benefit_definitions WHERE organization_id=NEW.organization_id AND id=NEW.benefit_definition_id;
   IF expected IS DISTINCT FROM actual THEN RAISE EXCEPTION 'benefit definition is from another plan version' USING ERRCODE='23514'; END IF;
   IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'balance_state') IS DISTINCT FROM (to_jsonb(OLD)-'balance_state') THEN
     RAISE EXCEPTION 'account identity is immutable' USING ERRCODE='23514';
   END IF;
   IF NEW.balance_state='unknown' AND EXISTS(SELECT 1 FROM agree_benefit_reservations WHERE organization_id=NEW.organization_id AND account_id=NEW.id AND status='active') THEN
     RAISE EXCEPTION 'reserved account cannot become unknown' USING ERRCODE='23514';
   END IF;
 ELSIF TG_TABLE_NAME='agree_agreements' AND TG_OP='UPDATE' THEN
   IF NEW.plan_version_id<>OLD.plan_version_id OR NEW.terms_snapshot<>OLD.terms_snapshot OR NEW.customer_id<>OLD.customer_id THEN
     RAISE EXCEPTION 'agreement terms are frozen; create a renewal/change record' USING ERRCODE='23514';
   END IF;
 ELSIF TG_TABLE_NAME='agree_coverage' THEN
   IF NEW.scope_kind='equipment' AND NEW.property_id IS DISTINCT FROM
      (SELECT property_id FROM crm_equipment WHERE organization_id=NEW.organization_id AND id=NEW.equipment_id) THEN
     RAISE EXCEPTION 'coverage equipment/property mismatch' USING ERRCODE='23514';
   END IF;
   IF NEW.service_scope='specific' AND NEW.scope_kind IN ('equipment','trade') THEN
     SELECT trade_id INTO actual FROM cat_services WHERE organization_id=NEW.organization_id AND id=NEW.service_id;
     IF NEW.scope_kind='equipment' THEN
       SELECT t.trade_id INTO expected FROM crm_equipment e JOIN crm_equipment_types t ON (t.organization_id,t.id)=(e.organization_id,e.type_id)
       WHERE e.organization_id=NEW.organization_id AND e.id=NEW.equipment_id;
     ELSE expected:=NEW.trade_id; END IF;
     IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'coverage service/trade mismatch' USING ERRCODE='23514'; END IF;
   END IF;
 ELSIF TG_TABLE_NAME='job_confirmed_work' THEN
   IF NEW.task_id IS NOT NULL THEN
   IF NOT EXISTS(SELECT 1 FROM job_tasks WHERE organization_id=NEW.organization_id AND id=NEW.task_id AND job_id=NEW.job_id AND service_id=NEW.service_id) THEN
     RAISE EXCEPTION 'confirmed work/task mismatch' USING ERRCODE='23514';
   END IF;
    END IF;
 ELSIF TG_TABLE_NAME='bill_review_flags' THEN
   IF NEW.line_id IS NOT NULL THEN
   IF NOT EXISTS(SELECT 1 FROM bill_invoice_lines WHERE organization_id=NEW.organization_id AND id=NEW.line_id AND invoice_id=NEW.invoice_id) THEN
     RAISE EXCEPTION 'review flag references another invoice line' USING ERRCODE='23514';
   END IF;
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER account_plan BEFORE INSERT OR UPDATE ON agree_benefit_accounts FOR EACH ROW EXECUTE FUNCTION check_domain_links();
CREATE TRIGGER agreement_frozen_terms BEFORE UPDATE ON agree_agreements FOR EACH ROW EXECUTE FUNCTION check_domain_links();
CREATE TRIGGER coverage_scope BEFORE INSERT OR UPDATE ON agree_coverage FOR EACH ROW EXECUTE FUNCTION check_domain_links();
CREATE TRIGGER confirmed_task BEFORE INSERT ON job_confirmed_work FOR EACH ROW EXECUTE FUNCTION check_domain_links();
CREATE TRIGGER flag_invoice BEFORE INSERT OR UPDATE ON bill_review_flags FOR EACH ROW EXECUTE FUNCTION check_domain_links();

CREATE FUNCTION protect_invoice() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE state text; tenant uuid; invoice uuid;
BEGIN
 IF TG_OP='DELETE' AND demo_reset_allowed(OLD.organization_id) THEN RETURN OLD; END IF;
 IF TG_TABLE_NAME='bill_invoices' THEN
   IF TG_OP<>'INSERT' AND OLD.status IN ('issued','void') THEN RAISE EXCEPTION 'issued invoice is immutable; use a correction' USING ERRCODE='23514'; END IF;
 ELSE
   IF TG_OP='DELETE' THEN tenant:=OLD.organization_id;invoice:=OLD.invoice_id; ELSE tenant:=NEW.organization_id;invoice:=NEW.invoice_id; END IF;
   IF TG_OP='UPDATE' AND (NEW.organization_id<>OLD.organization_id OR NEW.invoice_id<>OLD.invoice_id) THEN RAISE EXCEPTION 'cannot reparent invoice line' USING ERRCODE='23514'; END IF;
   SELECT status INTO state FROM bill_invoices WHERE organization_id=tenant AND id=invoice FOR UPDATE;
   IF state IN ('issued','void') THEN RAISE EXCEPTION 'issued invoice lines are immutable' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE TRIGGER issued_header BEFORE UPDATE OR DELETE ON bill_invoices FOR EACH ROW EXECUTE FUNCTION protect_invoice();
CREATE TRIGGER issued_lines BEFORE INSERT OR UPDATE OR DELETE ON bill_invoice_lines FOR EACH ROW EXECUTE FUNCTION protect_invoice();

CREATE FUNCTION validate_issue() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE i bill_invoices; s bill_issued_snapshots; lines jsonb; net numeric; discount numeric; tax numeric;
BEGIN
 IF TG_TABLE_NAME='bill_invoices' THEN
   SELECT * INTO i FROM bill_invoices WHERE organization_id=NEW.organization_id AND id=NEW.id FOR UPDATE;
 ELSE SELECT * INTO i FROM bill_invoices WHERE organization_id=NEW.organization_id AND id=NEW.invoice_id FOR UPDATE; END IF;
 IF i.status<>'issued' THEN
   IF TG_TABLE_NAME='bill_issued_snapshots' THEN RAISE EXCEPTION 'snapshot requires issued invoice' USING ERRCODE='23514'; END IF;
   RETURN NULL;
 END IF;
 SELECT * INTO s FROM bill_issued_snapshots WHERE organization_id=i.organization_id AND invoice_id=i.id;
 SELECT jsonb_agg(to_jsonb(l) ORDER BY position),sum(round(quantity*unit_price,2)),sum(discount_amount),sum(tax_amount)
 INTO lines,net,discount,tax FROM bill_invoice_lines l WHERE organization_id=i.organization_id AND invoice_id=i.id;
 IF s.id IS NULL OR lines IS NULL OR s.lines_snapshot IS DISTINCT FROM lines OR s.currency<>i.currency OR s.total<>i.total
   OR i.subtotal IS DISTINCT FROM net OR i.discount_total IS DISTINCT FROM discount OR i.tax_total IS DISTINCT FROM tax
   OR EXISTS(SELECT 1 FROM bill_review_flags WHERE organization_id=i.organization_id AND invoice_id=i.id AND status='open') THEN
   RAISE EXCEPTION 'issue requires matching immutable snapshot, reconciled lines and resolved flags' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER invoice_issue AFTER INSERT OR UPDATE ON bill_invoices DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_issue();
CREATE CONSTRAINT TRIGGER snapshot_issue AFTER INSERT ON bill_issued_snapshots DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_issue();

-- Precise charge identity; labor can reference its rate without inventing a material.
ALTER TABLE bill_invoice_lines ADD CHECK ((kind='material' AND material_id IS NOT NULL AND service_id IS NULL) OR (kind='service' AND service_id IS NOT NULL AND material_id IS NULL) OR (kind='labor' AND material_id IS NULL));
ALTER TABLE bill_quote_lines ADD CHECK ((kind='material' AND material_id IS NOT NULL AND service_id IS NULL) OR (kind='service' AND service_id IS NOT NULL AND material_id IS NULL) OR (kind='labor' AND material_id IS NULL));
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON crm_equipment_history FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON cat_price_versions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON cat_labor_rates FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON cat_checklist_templates FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON cat_checklist_items FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON import_decisions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON import_outcomes FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON agree_plan_versions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON agree_benefit_definitions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON agree_changes FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON job_status_history FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON job_confirmed_work FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON job_work_evidence FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON job_readiness_checks FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON agree_benefit_ledger FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON inv_movements FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON bill_accepted_scopes FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON bill_issued_snapshots FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON bill_corrections FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON ai_extracted_terms FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON ai_actions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON ai_decisions FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON ai_execution_outcomes FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON follow_delivery_attempts FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON integrate_sync_attempts FOR EACH ROW EXECUTE FUNCTION protect_history();
CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON report_events FOR EACH ROW EXECUTE FUNCTION protect_history();

CREATE UNIQUE INDEX ON inv_reservations (organization_id,consumption_movement_id) WHERE consumption_movement_id IS NOT NULL;
CREATE UNIQUE INDEX ON agree_benefit_reservations (organization_id,consumption_entry_id) WHERE consumption_entry_id IS NOT NULL;
