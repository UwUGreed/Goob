# Goob database foundation

This directory contains a standalone PostgreSQL foundation for Goob. It does **not** change application code, data sources, identity handling, routes, startup behavior, or the existing `goob` cloud-backed demo. The new tables are in `goob_foundation`; migration/fixture manifests are in `goob_db_meta`. No ORM was added. Python uses the repository's existing pinned psycopg2 and dotenv dependencies.

All three foundation migrations were explicitly authorized and deployed to the configured Tiger Cloud `tsdb` service on 2026-10-10 (America/New_York). The 97 new tables are empty; existing `goob` data was backed up and verified unchanged. No demo seed, customer import, or application integration occurred. See [deployment evidence](docs/DEPLOYMENT.json).

## Offline schema check

```sh
python3 -m database.generate --check
```

The local PostgreSQL/Docker test launcher has been removed. Database mutation
verification remains available through `database.cli verify` only for a separately
configured, marked isolated development database. It must not run against the shared
Tiger Cloud application database. The fixture, reset, and migration guards remain.

## Connect and inspect

The read-only connection command can use the existing ignored `.env`:

```bash
.venv/bin/python -m database.cli --env-file .env check
.venv/bin/python -m database.cli --env-file .env migrate --dry-run
```

`check` only reads PostgreSQL version, TLS status, and installed extensions. It never initializes tables or prints a password/connection URL. Environment variables win over an explicitly supplied env file. There is no implicit dotenv loading in these tools. An explicitly named env file must exist; a typo fails instead of falling back to another configured target. Tool connections set UTC for deterministic timestamp snapshots even when the server default differs.

To use a **separately authorized isolated development database**, put placeholders like the following into a private, ignored `.env.database-dev` and replace them locally:

```dotenv
GOOB_DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/goob_dev_NAME?sslmode=require
GOOB_DB_ENV=development
GOOB_DB_EXPECTED_DATABASE=goob_dev_NAME
```

Development migration/seed/verify/reset commands require all three variables, a matching actual database name beginning `goob_dev_`, and the database comment `goob-isolated-development-v1`. An administrator must establish this marker **only after independently verifying the database is dedicated isolated development**:

```sql
-- Run only in the separately authorized isolated development database.
COMMENT ON DATABASE goob_dev_NAME IS 'goob-isolated-development-v1';
```

Do not rename or mark `tsdb`, the existing app database, or a production/shared database to bypass this guard. No command here provisions a remote database, modifies database roles, or marks a remote service automatically. A separately authorized schema deployment can use `migrate --apply --deploy-host EXACT_HOST --deploy-database EXACT_DATABASE` with `GOOB_DATABASE_URL` explicitly supplied. Both target identities and live TLS must match. This exception applies only to schema migrations; seed, reset and mutation tests retain the development-only guard. The marker is an operational guard, not a security boundary against a database administrator.

Exact commands once that separate target is configured:

```bash
# Connect (read-only)
.venv/bin/python -m database.cli --env-file .env.database-dev check

# Inspect pending versions/checksums (read-only)
.venv/bin/python -m database.cli --env-file .env.database-dev migrate --dry-run

# Apply additive migrations explicitly
.venv/bin/python -m database.cli --env-file .env.database-dev migrate --apply

# Fictional organization only; stable UUIDs and explicit timeline
.venv/bin/python -m database.cli --env-file .env.database-dev seed --as-of 2026-10-10

# Database tests; requires the known demo fixtures and isolated target
.venv/bin/python -m database.cli --env-file .env.database-dev verify

# Read-only SQL reports
.venv/bin/python -m database.cli --env-file .env.database-dev report

# Exact known fixtures only; refusal on edits, extra rows, or target mismatch
.venv/bin/python -m database.cli --env-file .env.database-dev reset --confirm-demo-reset
```

`verify` performs invalid writes inside rolled-back transactions, plus two concurrent reservation experiments whose committed test rows are cleaned up by explicit test identifiers. Do not run against a database being edited concurrently. If a process is killed during verification, the conservative fixture/reset checks will refuse unknown rows; investigate the `verify-*` reservation keys instead of loosening the guard.

## Migrations and rollback

1. `001_foundation.sql`: 97 module-owned tables, composite tenant foreign keys, constraints, indexes, and ownership/lifecycle comments.
2. `002_integrity.sql`: balance/reconciliation views, account locking, deferred capacity constraints, invoice issuance and append-only guards.
3. `003_record_guards.sql`: immutable record identity, frozen referenced plan contents, eligibility gates, execution/approval consistency, and finite decimal checks.

The runner obtains an advisory transaction lock and verifies SHA-256 checksums. Pending migrations and their version records commit together. Failure rolls back the batch. A second run is a no-op. Unknown applied versions and modified applied SQL are rejected. The baseline deliberately refuses to overlay an existing `goob_foundation` schema.

There are no destructive down migrations. Before future authorized migrations, take a database backup and inspect compatibility/permissions. Before commit, transaction rollback is sufficient. After commit or operational use, prefer a new forward migration; restoration is an operator-controlled backup workflow. `reset` removes demo **rows**, not schema or migration history. It never truncates tables.

`model.py` is the baseline schema specification. `generate.py` renders migration 001 and the physical dictionary/ERD; use `--check` for drift detection. Once the baseline is released/applied to a retained database, do not regenerate it with changes. Add the next migration and update the documentation for the new contract.

## Fixtures and calculated outcomes

The dedicated organization is **Goob Demo Services** (`f0d225c3-15b9-57ad-82ac-c684af8e0092`). All names, identity references, object references, source evidence, and events are fictional; email addresses use `example.com`. No actual authentication account or file upload is created.

206 records include three trades, an office employee and three technicians, differing qualifications, three customers/four properties, equipment, active/expired/ambiguous agreements, traceable inventory and benefit openings, reservations/releases, completed/scheduled/return jobs, a discrepant draft invoice, and an uncertain import. Integration configuration is disabled and stores only a placeholder secret reference. Empty future-facing tables are intentional: there are no fabricated deliveries, real imports, or completed external syncs.

Seed preflight compares full stored row snapshots and the requested fixture inputs/date. Unchanged rows are skipped. Changed, missing, or unregistered rows at fixture identifiers cause a conflict report with zero new writes. Reruns never silently overwrite edits. The reset locks tables, verifies every row of the demo organization against the exact manifest, and deletes only those tenant-scoped IDs in a transaction. Other organizations survive, including records with identical child IDs.

The six example reports calculate:

- Warehouse capacitors: 16 on hand. Truck A: 3 on hand, 1 reserved, 2 available. All locations together: 19 after 20 opening, 2 consumed, 1 returned. Transfers do not create stock.
- Active benefit account: 2 remaining, 1 reserved, 1 available. Expired agreement: ineligible and zero remaining. Ambiguous migrated account: remaining/available **NULL (unknown)**, not zero.
- Return visit: one required board and zero reserved, producing a shortage of one.
- Draft invoice: recorded $240, line sum $255, discrepancy −$15, three review flags. Separate semantic flags expose covered-service billing and material quantity disagreements.
- Four clearly fictional operational events grouped by UTC day/type.
- Explicit coverage matching, including an equipment scope and a trade scope. Multiple candidate agreements require review; this query is not an authorization policy.

These results validate database records and constraints, not application workflows or dispatch algorithms.

## Documentation

- [Table dictionary](docs/TABLES.md): types, nullability, PK/FKs, constraints, ownership and lifecycle.
- [Full physical ERD](docs/ERD.md) and [module dependencies](docs/ARCHITECTURE.md).
- [Integrity/concurrency contracts](docs/INTEGRITY.md).
- [Requirement completeness matrix](docs/COMPLETENESS.md).
- [Future application integration](docs/INTEGRATION.md).
- [Verification evidence](docs/VERIFICATION.md).

## Tiger Data compatibility and TLS

Verified against current official documentation on 2026-10-10. Tiger Cloud provides PostgreSQL connectivity; ordinary SQL tables, foreign keys, transactions, triggers and versioned SQL are suitable for this foundation. The tooling requires TLS `require`, `verify-ca`, or `verify-full` remotely and preserves stricter supplied settings. Plaintext is accepted only for explicitly configured loopback development. `require` encrypts traffic but does not itself establish the same hostname verification guarantee as `verify-full`. Tiger documents `verify-full&sslrootcert=system` for libpq 16+; a trusted CA file is an alternative. No application connection settings were changed. [Tiger TLS documentation](https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/security/strict-ssl)

No additional extensions are required or enabled. UUID generation uses PostgreSQL's built-in `gen_random_uuid()`. The live read-only check found TimescaleDB installed, but authoritative records and reporting events remain ordinary relational tables. Extensions vary by supported Tiger catalog; do not assume arbitrary superuser extensions can be installed. [Supported extensions](https://www.tigerdata.com/docs/deploy/tiger-cloud/tiger-cloud-aws/tiger-cloud-extensions)

No hypertable is justified for these initial volumes. If a later reporting-only hypertable is introduced, unique/primary keys must include every partition dimension; preserve ingestion idempotency independently if partition-key inclusion changes its semantics. No retention, compression, continuous aggregate, or background policy is configured. Authoritative ledgers must remain outside disposable reporting retention. [Hypertable uniqueness](https://www.tigerdata.com/docs/learn/hypertables/hypertable-indexes)

These schema migrations are distinct from a customer data migration or cloud cutover. Existing SQLite and `goob` records require a separately approved mapping/backfill/reconciliation process. [Tiger migration guidance](https://www.tigerdata.com/docs/migrate)
