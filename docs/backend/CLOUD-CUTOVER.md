# Tiger Cloud cutover — 2026-10-10

The website now uses the supplied Tiger Cloud PostgreSQL connection. Its credentials
are stored only in the ignored root `.env`, with file permissions `0600`. They are
not included in source, frontend assets, or this report.

## Applied and verified

- Confirmed a live TLS 1.3 database connection using the provider's supplied
  `sslmode=require`. System certificate verification did not trust the provider's
  private CA. The v1 production requirement remains `sslmode=verify-full`; deployment
  needs the provider's trusted CA configuration.
- Applied Alembic revision `2558cea32be8`, adding the 17 `public.*_v1` tables and
  Alembic version metadata. The new tenant table remains empty; no app data was seeded.
- Compared row counts and canonical JSON checksums for all 111 existing tables in
  `goob`, `goob_foundation`, and `goob_db_meta` before and after the migration and
  regression tests. All existing records were unchanged.
- Saved a private, ignored pre-change row-data snapshot in
  `backups/cloud-before-v1-20261010.json`. This is not a full PostgreSQL backup of
  schema definitions, roles, or recovery configuration.
- Started the website at `http://127.0.0.1:8081` and inspected its Work review in the
  browser. It displayed the cloud's existing approved job, $180 draft, zero remaining
  maintenance visits, seven available capacitors, and existing approval audit entry.
  Browser verification performed no business mutations.

## Removed local database paths

- Removed the SQLite adapter, implicit file fallback, SQLite import command, and
  startup schema initialization/demo seeding. The old `GOOB_DEMO_DB` override fails
  explicitly instead of silently choosing a different database.
- Removed `deploy/backend/compose.test.yaml` and `database/test_local.py`, which
  launched local PostgreSQL instances. The previous local PostgreSQL process is stopped.
- Converted legacy workflow tests to explicit PostgreSQL test connections. Both
  backend suites create isolated schemas, with no application schema in their test
  search path, and drop only their own schemas afterward.
- Removed the browser test launcher's SQLite/server setup. Browser tests now require
  an explicit `GOOB_E2E_BASE_URL` for an isolated test workspace.
- Enforced TLS in database connection helpers and preserved stronger verification
  settings when supplied. Cloud schema definitions, SQL migrations, and PostgreSQL
  drivers remain necessary and are retained.

Frontend and voice implementations were not changed. The Playwright configuration
change only removes the obsolete database launcher. Old data backups are retained;
the app does not use them.

## Verification evidence

- 52 backend regression tests passed against isolated schemas on Tiger Cloud.
- The additional TLS guard and seven offline cloud-configuration checks passed.
- Re-ran the nine website workflow tests with explicit post-drop assertions; all
  passed and the schema inventory was identical before and after that run.
- Nine other test-named schemas were observed. Their origin was not established,
  so they were left untouched. No v1 test schemas remained after the suite.
- Ruff and Python compilation checks passed for the changed backend scope.
- Foundation generation check confirmed all 97 table definitions remain consistent.

These results verify cloud persistence and backend behavior. They do not establish
live Gemini/ElevenLabs integration, production identity login, or a Vultr deployment.

## Remaining integration boundaries

The existing website still uses `goob`. The teammate's foundation uses
`goob_foundation`, and the new authenticated API uses `public.*_v1`. Sharing the same
cloud database does not merge their records or change the frontend's API contract.
Frontend adoption and any reviewed data mapping remain separate work. The website's
demo identity/AI behavior remains unchanged and its server stays on loopback.
