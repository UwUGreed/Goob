# Verification evidence

Run date: 2026-10-10. This file distinguishes local database checks from live Tiger Cloud checks.

## Read-only Tiger Cloud

Command: `.venv/bin/python -m database.cli --env-file .env check`.

Result: connected to the configured `tsdb` service using TLS. It reported PostgreSQL 18.6 and installed TimescaleDB 2.30.2 / Toolkit 1.26.0, alongside existing PostgreSQL extensions. The command ran read-only and did not apply migrations, change roles/policies, seed/reset, enable extensions, or alter existing records. No full connection URL or credential was logged.

## Authorized Tiger Cloud deployment

After the user explicitly requested deployment, all three migrations committed in one transaction to the configured `tsdb` service on 2026-10-10 (America/New_York). Before deployment, a private PostgreSQL custom-format backup of `goob` was written under ignored `backups/`, and its archive listing was verified. Row counts and canonical row hashes were captured for every existing `goob` table.

Post-deployment checks passed: 97 expected business tables, 291 foreign keys, 150 non-internal triggers, all six SQL reports execute, migration checksums match, no pending migrations, and all 12 existing `goob` tables (including migration metadata) retain identical row counts and content hashes. The new foundation is empty: no fictional seed or customer migration was run. See DEPLOYMENT.json for machine-readable results.

The new schema-deployment path requires an explicitly supplied connection plus exact expected host/database and TLS. Wrong-host and wrong-database checks were tested and rejected. The service was not relabeled as development, and development-only seed/reset/verification guards still reject it. Application integration remains unimplemented; cloud deployment does not establish production authentication or RLS.

## Historical disposable PostgreSQL verification

The local launcher used for these historical checks has since been removed.

Commands: `.venv/bin/python -m database.test_local` and `.venv/bin/python -m database.test_local --postgres-version 18`.

The harness provisions only ephemeral local PostgreSQL 17 and 18 containers (one per run), binds a random loopback port, uses a random local password, marks its own dedicated database, and removes the container after testing. It runs the full migration/seed/verification/reset sequence, including two dates: 2026-10-10 and 2027-03-15.

Final run result: **PASS**. All three migrations applied; 206 fictional records; 43 database checks passed for each date on both PostgreSQL 17 and 18, plus eight harness checks and eight public CLI checks per version. The server timezone was deliberately set to America/New_York; the tooling retained deterministic UTC snapshots. After the authorized deployment, a read-only migration inspection reports all three versions applied and no pending migrations. See the command's actual output for the latest run; failures raise and return a nonzero exit code.

Database checks cover:

- Complete table/FK presence, required fields, uniqueness and cross-organization rejection.
- Immutable identities, published plans, agreement terms, inventory/benefit history and issued invoice prices.
- Explicit coverage scope, equipment/property matching, unknown/expired benefit rejection.
- Exact finite decimals, line rounding, invoice issuance refusal without a reconciled snapshot, and successful reconciled issuance.
- Movement idempotency, two-ended transfers, matching materials, traceable reversal.
- Inventory/benefit capacity, reservation lifecycle, and **concurrent committed reservations** in independent connections.
- Seed rerun skip behavior, changed-date refusal, edited fixture conflict detection, reset refusal on additional demo rows.
- Derived inventory/benefit balances, expired/unknown states, return-part shortage, invoice discrepancy, fictional-event aggregates and explicit coverage query.
- Verification leaves fixture snapshots unchanged.

Harness checks additionally cover an unmarked target rejection, migration dry-run/rerun/checksum tampering, exact demo reset, another tenant sharing a child UUID surviving reset, reset rerun and a fresh seed with a changed as-of date. CLI checks cover connection inspection, migration dry-run, seed rerun, all six reports, refusal of reset without confirmation, invalid dates, a missing explicit env file, and a mismatched expected database. Output is checked for accidental credential disclosure. No real customer/import/AI/message/payment/integration side effects occur.

## Scope and artifacts

`python -m database.generate --check` verifies the baseline SQL/dictionary/ERD match the schema definition. Python compilation checks validate database tooling syntax. A before/after content-hash comparison of existing repository files verifies no change outside `database/` except allowed `.env.example` connection placeholders. Existing application edits from the prior task are preserved rather than attributed to this task.

This validates database-level invariants. It does not claim frontend/API correctness, dispatch behavior, real authentication/RLS, external delivery, payment behavior, semantic billing policies, application integration or performance at production scale.
