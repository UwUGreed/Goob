-- Run as the schema owner with psql -v app_role=YOUR_EXISTING_APP_ROLE -f grants.sql.
-- Provision a LOGIN role/password outside this file. Never make the runtime role
-- a superuser, schema owner, or member of the migration role.
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT, UPDATE ON
  tenants_v1, branches_v1, memberships_v1, records_v1, agreements_v1,
  balances_v1, reservations_v1, proposals_v1, imports_v1, outbox_v1, invoices_v1
  TO :"app_role";
GRANT SELECT, INSERT ON
  terms_v1, benefits_v1, movements_v1, notes_v1, events_v1, commands_v1
  TO :"app_role";
GRANT SELECT ON alembic_version TO :"app_role";
REVOKE UPDATE, DELETE ON
  terms_v1, benefits_v1, movements_v1, notes_v1, events_v1, commands_v1
  FROM :"app_role";
-- Independent drafts can be edited through authenticated revision/idempotency checks.
-- Legacy proposal invoices and finalized snapshots remain immutable in domain logic.
REVOKE DELETE ON invoices_v1 FROM :"app_role";
GRANT USAGE, SELECT ON SEQUENCE invoice_number_v1 TO :"app_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON view_preferences_v1 TO :"app_role";
