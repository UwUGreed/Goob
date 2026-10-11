# Goob

Goob's React website uses the Python operations API backed by Tiger Cloud PostgreSQL.
The repository also contains the authenticated `/api/v1` backend and the standalone
97-table foundation. Their records remain separate; see
[database ownership and integration](docs/backend/DATABASE-INTEGRATION.md).

## Run the website with the cloud database

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix goob-dispatch
npm run build --prefix goob-dispatch
.venv/bin/python -m operations.database check
.venv/bin/python -m operations.server
```

Provide `DATABASE_URL` in the server environment or the private ignored `.env`.
Use the Tiger Cloud credentials, never a `VITE_` variable. The website is served at
http://127.0.0.1:8081. Normal startup only checks the existing schema: it does not
initialize tables, seed customers, import records, or start a database server.
Missing credentials or an unavailable cloud database produce an error. There is
no SQLite fallback. The old `GOOB_DEMO_DB` override is rejected.

The dispatch map remains a fictional local simulation. **Work review** reads the
cloud's separate Morgan Ellis workflow and preserves its existing approvals. Map
assignments and work-review jobs are not synchronized. Its identity selector and
AI proposal remain explicitly simulated; keep this server on loopback.

For frontend development, run the Python server and then
`npm run dev --prefix goob-dispatch`. Vite proxies `/api` to port 8081.
The new authenticated backend has separate [setup instructions](docs/backend/README.md).

## Database ownership

- `goob`: current website work review and its existing history.
- `goob_foundation`: teammate's normalized 97-table foundation.
- `public.*_v1`: new authenticated operations API.

SQL schemas and migrations are required by the cloud database and remain in the
repository. The local PostgreSQL Docker launcher, standalone local database test
launcher, SQLite adapter, and obsolete SQLite import command were removed.
Existing local data snapshots are retained only as backups, never used by the app.

Schema changes are explicit operator commands. `operations.database init` initializes
only the website schema and creates no demo records. Foundation migrations use
`database.cli`; v1 migrations use Alembic. Do not run seed/reset or mutation verification
against the shared application's records.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
npm test --prefix goob-dispatch
```

Database tests require explicitly supplied PostgreSQL test URLs. Without them they
skip rather than connect to `.env`. Tests create unique `goob_test_*` schemas and
remove only those schemas. V1 tests migrate into their isolated schema; they never
use public application tables. See the backend guide for pytest commands.

Browser tests require `GOOB_E2E_BASE_URL` pointing to a separately prepared isolated
test workspace with fresh fictional records. They no longer start a local database
or implicitly target the shared cloud-backed website. Then run:
`npm run test:e2e --prefix goob-dispatch`.

[Cloud cutover evidence](docs/backend/CLOUD-CUTOVER.md) ·
[Team integration handoff](docs/backend/TEAM-HANDOFF.md) ·
[Database foundation](database/README.md) ·
[Original dispatch journey](goob-dispatch/README.md)
