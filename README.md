# Goob

A combined contractor workspace: the React dispatch frontend now includes **Work review**, connected to the Python operations API with Tiger Cloud PostgreSQL support.

## Run the combined demo

From this folder:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix goob-dispatch
npm run build --prefix goob-dispatch
.venv/bin/python -m operations.server
```

Open http://127.0.0.1:8081. Use the dispatch map as before, then select **Work review** in the navigation to inspect customer equipment, coverage, material disposition, billing corrections and approval history.

The map uses its original fictional visit records and local travel simulation. Work review uses the separate Morgan Ellis HVAC scenario persisted in the configured database. Closing or approving a work review does not alter map assignments or complete a dispatch visit. Address similarity is not a job link. Both workflows are accessible within the same frontend; shared job identities and dispatch-to-approval synchronization remain planned.

## Development

Start `.venv/bin/python -m operations.server` in one terminal, then `npm run dev --prefix goob-dispatch` in another. Vite proxies `/api` to the local operations server on port 8081.

## Verify

```sh
python3 -m unittest discover -s tests -v
npm test --prefix goob-dispatch
npm run test:e2e --prefix goob-dispatch
```

The browser tests build the frontend and start an isolated demo API/database on port 8082. If Chromium is missing, install it with `npx --prefix goob-dispatch playwright install chromium`. A custom browser executable can be supplied through `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

Implemented: interactive dispatch, persisted work proposals, coverage checks, benefit consumption, issued/installed/returned material accounting, integer-cent billing corrections, atomic approval, retry/staleness protection, module dependency checks, audit history and JSON export.

Simulated: AI proposal and identity. Preview only: return-visit readiness and uncertain migration. No real messages, payments or integration services run.

Operations details: `operations/README.md`. Architecture and roadmap: `docs/OPERATIONS-ARCHITECTURE.md`. Original dispatch journey: `goob-dispatch/README.md`.

## Tiger Cloud database

This checkout is configured through a private, ignored `.env` file. The supplied
service is Tiger Cloud PostgreSQL, not Tigris object storage. Credentials remain
on the Python server and must never go into frontend code or `VITE_` variables.
For a new checkout, copy `.env.example` to `.env` and supply `DATABASE_URL`.

```sh
.venv/bin/python -m operations.database init
.venv/bin/python -m operations.database check
.venv/bin/python -m operations.server
```

The backend uses the `goob` schema, versioned schema initialization, TLS, and
transactional writes. Existing SQLite data was copied into this checkout's
cloud service, including approval history. The original SQLite file is retained;
consistent pre-import backups are in ignored `backups/`.
To import another SQLite snapshot into **empty** application tables:

```sh
.venv/bin/python -m operations.database import-sqlite --source operations/demo.sqlite3
```

Import refuses any nonempty target and commits all rows together. Initialization
is idempotent and never resets existing records. With no `DATABASE_URL`, the app
uses SQLite. An explicit `GOOB_DEMO_DB` takes precedence, keeping browser tests
isolated from cloud data. Connection failures do not silently fall back to SQLite.

Run offline tests with `.venv/bin/python -m unittest discover -s tests -v`.
The same workflow suite can also run against PostgreSQL by setting
`GOOB_TEST_POSTGRES_URL`; it creates and drops unique `goob_test_*` schemas and
never uses the application's tables. Do not commit either connection URL.

The current server still uses simulated identity and loopback binding. Cloud
persistence does not add production authentication. Dispatch map state remains
in-memory; the connected persistence covers Work review. Write transactions
currently serialize across application tables to preserve the existing SQLite
approval guarantees; finer-grained locking is a future scaling improvement.
