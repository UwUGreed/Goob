# Goob

Goob's React website uses the authenticated `/api/v1` operations API and the
portal dispatch API backed by Tiger Cloud PostgreSQL. The legacy website schema
and standalone 97-table foundation remain separate; see
[database ownership and integration](docs/backend/DATABASE-INTEGRATION.md).

The complete Dispatch application and public sign-in portal use the existing
SQLAlchemy v1 backend. See [portal startup and demo credentials](goob-dispatch/README.md).
Build with `npm --prefix goob-dispatch run build`, then run
`python -m operations.portal_server` and open `http://127.0.0.1:8090`.
The server loads the ignored root `.env` Tiger Cloud connection. This portal uses
an additive migration and a separate fictional demo workspace; legacy schemas
and records are retained. There is no local database fallback.

## Run the portal with the cloud database

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix goob-dispatch
npm run build --prefix goob-dispatch
.venv/bin/python -m operations.portal_server
```

Provide `DATABASE_URL` in the server environment or the private ignored `.env`.
Use the Tiger Cloud credentials, never a `VITE_` variable. The local portal is served at
http://127.0.0.1:8090. Normal startup does not initialize tables, seed customers,
import records, or start a database server. `/health/ready` checks the v1 schema.
Missing credentials or an unavailable cloud database produce an error. There is
no SQLite fallback. The old `GOOB_DEMO_DB` override is rejected.

The dispatch map remains a fictional local simulation. Customers, jobs, memberships,
inventory movements, work review, migration and opportunities use the same scoped
v1 records. Gemini extraction and spoken ElevenLabs job briefings remain TBD;
manual technician-note review and typed dispatch requests are available.

For frontend development, run the Python server and then
`npm run dev --prefix goob-dispatch`. Vite proxies `/api` to port 8090.
The backend has separate [setup instructions](docs/backend/README.md).

## Database ownership

- `goob`: retained legacy website history, not the portal's current data source.
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

## Vultr staging deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Ubuntu 24.04 app server, Nginx, systemd,
and GitHub Actions deployment using the existing Tiger Cloud database.
No local database server is installed and existing cloud records are preserved.
