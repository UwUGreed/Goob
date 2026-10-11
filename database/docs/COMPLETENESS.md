# Requirement-to-table completeness matrix

All 97 business tables have concrete SQL types/nullability, primary keys, tenant ownership, foreign keys, constraints and indexes in migration 001 and TABLES.md. Migrations 002–003 add cross-row guards and immutability rules. “Records only” means schema exists without implementing application behavior.

| Requested area | Implemented tables / artifacts | Boundary or deferred rule |
|---|---|---|
| Organizations, branches | org_organizations, org_branches | Trusted tenant selection and timezone catalog validation at integration |
| Existing auth identity references, employee membership | org_members (provider/opaque subject), org_member_roles | No auth accounts/passwords/session flows; legacy header role is not trusted identity |
| Roles/permissions | org_roles, org_permissions, org_role_permissions | Runtime authorization and RLS deferred |
| Technicians, qualifications, enabled trades | org_technicians, org_qualifications, org_technician_qualifications, org_trades | Expiration/qualification eligibility enforced by later scheduling commands |
| Module enablement/settings | org_modules | Dependency closure and runtime feature gating deferred; no universal module engine |
| Residential/commercial customers, contacts | crm_customers, crm_contacts, crm_customer_contacts | Contact normalization/deduplication is a future command |
| Multiple properties, billing vs service | crm_addresses, crm_properties, crm_customer_properties; job_jobs.billing_customer_id/property_id | Effective dates structured; overlapping ownership/management intervals need review |
| Equipment types, trade, make/model/serial/install/warranty | crm_equipment_types, crm_equipment; type owns trade FK | Serial numbers are not assumed globally unique |
| Relocation/replacement history | crm_equipment_history | Later command must update current location and re-review coverage atomically |
| Notes, attachments, preferences | crm_notes, crm_files, crm_communication_preferences | Metadata/object references only; no bytes/uploads/messages |
| Extensible MEP catalog, services/job types | org_trades, cat_services, cat_job_types | No dispatch algorithm |
| Pricebooks/versioned prices/labor | cat_pricebooks, cat_price_versions, cat_labor_rates | Immutable versions and copied billing prices; selecting an effective price/overlap resolution deferred |
| Materials/units/checklists/requirements | cat_materials, cat_units, cat_checklist_templates, cat_checklist_items, cat_material_requirements | Unit conversion and task checklist completion capture are future enhancements |
| Plans and frozen plan versions | agree_plans, agree_plan_versions, agree_benefit_definitions | New versions for term/benefit changes; no additions to a referenced version |
| Customer agreements/renewals | agree_agreements, agree_changes | Renewal mode/notice fields and history; no automatic renewer |
| Explicit property/equipment/trade/service coverage | agree_coverage; benefit_job_eligible() | Explicit scope discriminators; overlapping valid agreements require staff selection |
| Source interpretation approval | agree_agreements reviewer/time/state/source_file_id; ai_extracted_terms | Unknown/ambiguous interpretation blocks eligibility; no document AI calls |
| Benefit accounts and all ledger types | agree_benefit_accounts, agree_benefit_ledger | Grants, consumption, expiration, reversal, adjustment; approved_by is an identity FK, not permission enforcement |
| Reservations/releases and four-way balance separation | agree_benefit_reservations, agree_balances view, eligibility function | Unknown remains NULL; locking/deferred checks protect quantity; plan-specific eligibility beyond structured scope remains future |
| Planned visits/completed service links | agree_planned_visits, job_confirmed_work | Records only; no automatic schedule |
| Jobs/trades/equipment/planned scope | job_jobs, job_trades, job_equipment, job_tasks | Multiple trades/equipment per job; no rewriting legacy dispatch |
| Appointments/multiple technicians/availability/time | job_appointments, job_assignments, job_availability, job_time_entries | Overlap, routing, availability matching, timesheet policy deferred |
| Status history, confirmed work/evidence | job_status_history, job_confirmed_work, job_work_evidence | Planned versus confirmed records separate; future commands emit histories/audit |
| Return visits/material needs/readiness | job_return_links, job_required_materials, job_readiness_checks | SQL shortage report implemented; no application readiness engine |
| Suppliers/warehouse/trucks | inv_suppliers, inv_supplier_materials, inv_locations, inv_stock_accounts | Purchasing, supplier invoices and reconciliation deferred |
| Traceable opening/receipt/transfer/consumption/returns/adjustments | inv_movements with kind and source record; composite FKs | Balanced single-row transfer, immutable history, exact reversals; return quantity reconciliation remains future |
| Inventory reservations/replenishment/costs | inv_reservations, inv_replenishment_policies, inv_balances; movement unit_cost/currency | Standard snapshot costing documented; FIFO/weighted average deferred |
| Quotes/accepted scope | bill_quotes, bill_quote_lines, bill_accepted_scopes | Immutable acceptance snapshot; capture/validate actual consent in future application |
| Draft invoices/lines/prices/discounts/tax | bill_invoices, bill_invoice_lines, bill_invoice_reconciliation | Exact numeric/rounding enforced; draft discrepancy allowed/reported; no tax engine |
| Work/benefit links and review evidence | bill_invoice_lines work/benefit FKs; bill_review_flags | Semantic billing review and required charge coverage still need command-level rules |
| Issued snapshots/corrections/credits | bill_issued_snapshots, bill_corrections | Issuance reconciliation/frozen lines enforced; cumulative credit limits and official numbering policy deferred |
| Membership billing separate from jobs | bill_membership_schedules | No payment processor, card data or billing automation |
| AI metadata/extractions/actions/decisions/outcomes | ai_runs, ai_extracted_terms, ai_change_sets, ai_actions, ai_decisions, ai_execution_outcomes | Proposals never execute; successful outcomes must reference matching approved decisions |
| Actor/time/tenant/affected-record/change audit | audit_events | Append-only storage; no application audit producers were added |
| Import files/batches/mappings/staging/originals | import_batches, import_field_mappings, import_staging_records, crm_files | Fictional fixtures only; no real customer migration |
| Issues/duplicates/reconciliation/approval/outcomes | import_validation_issues, import_duplicate_candidates, import_decisions, import_outcomes | Approved outcome relation enforced; deduplication heuristics/import executor deferred |
| Provenance/idempotency/opening ledger evidence | source_record_id on stock and benefit records; unique batch/outcome/movement keys | Exact source-field provenance via staging/mappings; unknown values require review |
| Follow-up/reminder/message/delivery records | follow_tasks, follow_message_drafts, follow_delivery_attempts | Records only, no sends, scheduler or background tasks |
| Integration secrets/mappings/sync/checkpoints/retry | integrate_connections, integrate_record_mappings, integrate_sync_attempts, integrate_checkpoints | Secret references only; external credential storage and provider calls absent |
| Optional Ply source of truth | integrate_authority, disabled demo connection | Explicit entity authority/conflict policy, no Ply connection |
| Operational reporting | report_events and reports/01–06 SQL | Ordinary PostgreSQL; idempotent fictional events, no hypertable/retention/aggregation service |
| Additive versioned migration safety | migrations/001–003, cli.py, connection.py | Checksummed transactions; unknown/shared/production targets refused |
| Seed idempotency, as-of, edit conflicts | fixtures.py; goob_db_meta.fixture_rows | Stable IDs; all-or-nothing writes; no overwriting edits |
| Explicit safe reset | cli.py reset --confirm-demo-reset, fixtures.reset | Isolated marker and exact verified tenant manifest required; no truncation |
| Standalone connection check | cli.py check | Read-only, TLS-aware, no startup hooks or secret logs |
| Database validation | verify.py, isolated test schemas, SQL reports | Disposable migrations, constraints, reruns, concurrency, immutability, reports, tenant-safe reset |
| ERD/dictionary/integration guidance | docs/ERD.md, TABLES.md, ARCHITECTURE.md, INTEGRITY.md, INTEGRATION.md | Application implementation intentionally excluded |
