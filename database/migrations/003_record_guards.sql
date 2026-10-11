SET LOCAL search_path TO goob_foundation,pg_catalog;

CREATE FUNCTION protect_identity() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF NEW.id<>OLD.id OR NEW.created_at<>OLD.created_at OR
    (to_jsonb(NEW)->'organization_id') IS DISTINCT FROM (to_jsonb(OLD)->'organization_id') THEN
   RAISE EXCEPTION 'record identity, tenant and creation timestamp are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION protect_plan_contents() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM agree_agreements WHERE organization_id=NEW.organization_id AND plan_version_id=NEW.plan_version_id) THEN
   RAISE EXCEPTION 'referenced plan version contents are frozen; publish a new version' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER plan_contents BEFORE INSERT ON agree_benefit_definitions FOR EACH ROW EXECUTE FUNCTION protect_plan_contents();

CREATE FUNCTION check_outcome_reference() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
BEGIN
 IF TG_TABLE_NAME='ai_execution_outcomes' THEN
   IF NOT EXISTS(SELECT 1 FROM ai_decisions d JOIN ai_actions a ON a.organization_id=d.organization_id AND a.change_set_id=d.change_set_id
     WHERE d.organization_id=NEW.organization_id AND d.id=NEW.decision_id AND a.id=NEW.action_id
     AND (NEW.status<>'succeeded' OR d.decision='approved')) THEN
     RAISE EXCEPTION 'execution outcome requires matching employee decision' USING ERRCODE='23514';
   END IF;
 ELSIF TG_TABLE_NAME='import_outcomes' THEN
   IF NOT EXISTS(SELECT 1 FROM import_decisions d WHERE d.organization_id=NEW.organization_id AND d.id=NEW.decision_id
      AND d.record_id=NEW.record_id AND d.decision IN ('accept','merge')) THEN
     RAISE EXCEPTION 'import outcome requires matching staff approval' USING ERRCODE='23514';
   END IF;
 ELSIF TG_TABLE_NAME='bill_corrections' THEN
   IF NEW.currency IS DISTINCT FROM (SELECT currency FROM bill_issued_snapshots WHERE organization_id=NEW.organization_id AND id=NEW.issued_snapshot_id) THEN
     RAISE EXCEPTION 'correction currency must match issued invoice' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER execution_decision BEFORE INSERT ON ai_execution_outcomes FOR EACH ROW EXECUTE FUNCTION check_outcome_reference();
CREATE TRIGGER import_decision BEFORE INSERT ON import_outcomes FOR EACH ROW EXECUTE FUNCTION check_outcome_reference();
CREATE TRIGGER correction_currency BEFORE INSERT ON bill_corrections FOR EACH ROW EXECUTE FUNCTION check_outcome_reference();

-- Every scope is a positive, explicit match; overlaps are surfaced for staff review.
CREATE FUNCTION benefit_job_eligible(tenant uuid, account uuid, job uuid, on_day date)
RETURNS boolean LANGUAGE sql STABLE SET search_path=goob_foundation,pg_catalog AS $$
 SELECT EXISTS(
 SELECT 1 FROM agree_benefit_accounts b
 JOIN agree_agreements a ON (a.organization_id,a.id)=(b.organization_id,b.agreement_id)
 JOIN agree_benefit_definitions d ON (d.organization_id,d.id)=(b.organization_id,b.benefit_definition_id)
 JOIN job_jobs j ON j.organization_id=a.organization_id AND j.billing_customer_id=a.customer_id AND j.id=job
 JOIN agree_coverage c ON c.organization_id=a.organization_id AND c.agreement_id=a.id AND c.property_id=j.property_id
 WHERE b.organization_id=tenant AND b.id=account AND b.balance_state='known'
 AND a.status='active' AND a.interpretation_state='approved' AND c.review_state='approved'
 AND on_day BETWEEN a.starts_on AND a.ends_on AND on_day BETWEEN b.period_start AND b.period_end
 AND on_day BETWEEN c.valid_from AND c.valid_until
 AND EXISTS(SELECT 1 FROM job_tasks t JOIN cat_services s ON (s.organization_id,s.id)=(t.organization_id,t.service_id)
 WHERE t.organization_id=j.organization_id AND t.job_id=j.id AND t.status<>'cancelled'
 AND (d.service_scope='all' OR (d.service_scope='specific' AND d.service_id=s.id))
 AND (c.service_scope='all' OR (c.service_scope='specific' AND c.service_id=s.id))
 AND (c.scope_kind='property' OR (c.scope_kind='trade' AND c.trade_id=s.trade_id)
 OR (c.scope_kind='equipment' AND EXISTS(SELECT 1 FROM job_equipment e
 JOIN crm_equipment q ON (q.organization_id,q.id)=(e.organization_id,e.equipment_id)
 JOIN crm_equipment_types et ON (et.organization_id,et.id)=(q.organization_id,q.type_id)
 WHERE e.organization_id=j.organization_id AND e.job_id=j.id AND e.equipment_id=c.equipment_id AND et.trade_id=s.trade_id)))));
$$;

CREATE FUNCTION check_benefit_eligibility() RETURNS trigger LANGUAGE plpgsql
SET search_path=goob_foundation,pg_catalog AS $$
DECLARE local_day date; applicable boolean;
BEGIN
 IF TG_TABLE_NAME='agree_benefit_reservations' THEN
   applicable:=NEW.status='active';
   SELECT (NEW.reserved_at AT TIME ZONE p.timezone)::date INTO local_day FROM job_jobs j JOIN crm_properties p ON (p.organization_id,p.id)=(j.organization_id,j.property_id)
   WHERE j.organization_id=NEW.organization_id AND j.id=NEW.job_id;
 ELSE
   applicable:=NEW.kind='consumption';
   SELECT (NEW.occurred_at AT TIME ZONE p.timezone)::date INTO local_day FROM job_jobs j JOIN crm_properties p ON (p.organization_id,p.id)=(j.organization_id,j.property_id)
   WHERE j.organization_id=NEW.organization_id AND j.id=NEW.job_id;
 END IF;
 IF applicable AND NOT benefit_job_eligible(NEW.organization_id,NEW.account_id,NEW.job_id,local_day) THEN
   RAISE EXCEPTION 'benefit is not eligible for this job/date/scope' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER benefit_eligibility BEFORE INSERT ON agree_benefit_reservations FOR EACH ROW EXECUTE FUNCTION check_benefit_eligibility();
CREATE TRIGGER benefit_eligibility BEFORE INSERT ON agree_benefit_ledger FOR EACH ROW EXECUTE FUNCTION check_benefit_eligibility();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_organizations FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_branches FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_members FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_roles FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_permissions FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_role_permissions FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_member_roles FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_trades FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_modules FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_technicians FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_qualifications FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON org_technician_qualifications FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_customers FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_contacts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_customer_contacts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_addresses FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_properties FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_customer_properties FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_files FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_equipment_types FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_equipment FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_equipment_history FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_notes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON crm_communication_preferences FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_units FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_materials FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_services FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_job_types FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_pricebooks FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_price_versions FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE cat_price_versions ADD CHECK (unit_price <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_labor_rates FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE cat_labor_rates ADD CHECK (hourly_rate <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_checklist_templates FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_checklist_items FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON cat_material_requirements FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE cat_material_requirements ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON import_batches FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON import_field_mappings FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON import_staging_records FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON import_validation_issues FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON import_duplicate_candidates FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE import_duplicate_candidates ADD CHECK (confidence <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON import_decisions FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON import_outcomes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_plans FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_plan_versions FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE agree_plan_versions ADD CHECK (period_price <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_benefit_definitions FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE agree_benefit_definitions ADD CHECK (period_grant <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_agreements FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_coverage FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_benefit_accounts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_changes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_jobs FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_trades FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_equipment FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_tasks FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE job_tasks ADD CHECK (planned_quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON job_appointments FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_assignments FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_availability FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_time_entries FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_status_history FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_confirmed_work FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE job_confirmed_work ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON job_work_evidence FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_return_links FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON job_required_materials FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE job_required_materials ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON job_readiness_checks FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_benefit_ledger FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE agree_benefit_ledger ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_benefit_reservations FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE agree_benefit_reservations ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON agree_planned_visits FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_suppliers FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_supplier_materials FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_locations FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_stock_accounts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_movements FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE inv_movements ADD CHECK (quantity <> 'NaN'::numeric);
ALTER TABLE inv_movements ADD CHECK (unit_cost <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_reservations FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE inv_reservations ADD CHECK (quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON inv_replenishment_policies FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE inv_replenishment_policies ADD CHECK (minimum_quantity <> 'NaN'::numeric);
ALTER TABLE inv_replenishment_policies ADD CHECK (target_quantity <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_quotes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_quote_lines FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_quote_lines ADD CHECK (quantity <> 'NaN'::numeric);
ALTER TABLE bill_quote_lines ADD CHECK (unit_price <> 'NaN'::numeric);
ALTER TABLE bill_quote_lines ADD CHECK (discount_amount <> 'NaN'::numeric);
ALTER TABLE bill_quote_lines ADD CHECK (tax_rate <> 'NaN'::numeric);
ALTER TABLE bill_quote_lines ADD CHECK (tax_amount <> 'NaN'::numeric);
ALTER TABLE bill_quote_lines ADD CHECK (line_total <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_accepted_scopes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_invoices FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_invoices ADD CHECK (subtotal <> 'NaN'::numeric);
ALTER TABLE bill_invoices ADD CHECK (discount_total <> 'NaN'::numeric);
ALTER TABLE bill_invoices ADD CHECK (tax_total <> 'NaN'::numeric);
ALTER TABLE bill_invoices ADD CHECK (total <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_invoice_lines FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_invoice_lines ADD CHECK (quantity <> 'NaN'::numeric);
ALTER TABLE bill_invoice_lines ADD CHECK (unit_price <> 'NaN'::numeric);
ALTER TABLE bill_invoice_lines ADD CHECK (discount_amount <> 'NaN'::numeric);
ALTER TABLE bill_invoice_lines ADD CHECK (tax_rate <> 'NaN'::numeric);
ALTER TABLE bill_invoice_lines ADD CHECK (tax_amount <> 'NaN'::numeric);
ALTER TABLE bill_invoice_lines ADD CHECK (line_total <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_review_flags FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_issued_snapshots FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_issued_snapshots ADD CHECK (total <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_corrections FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_corrections ADD CHECK (amount <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON bill_membership_schedules FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE bill_membership_schedules ADD CHECK (amount <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_runs FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_extracted_terms FOR EACH ROW EXECUTE FUNCTION protect_identity();
ALTER TABLE ai_extracted_terms ADD CHECK (confidence <> 'NaN'::numeric);
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_change_sets FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_actions FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_decisions FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON ai_execution_outcomes FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON audit_events FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON follow_tasks FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON follow_message_drafts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON follow_delivery_attempts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON integrate_connections FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON integrate_record_mappings FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON integrate_sync_attempts FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON integrate_checkpoints FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON integrate_authority FOR EACH ROW EXECUTE FUNCTION protect_identity();
CREATE TRIGGER record_identity BEFORE UPDATE ON report_events FOR EACH ROW EXECUTE FUNCTION protect_identity();
