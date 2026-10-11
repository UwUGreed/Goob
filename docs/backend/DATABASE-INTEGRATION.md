# Teammate database and operations API integration

The integration branch combines upstream `1fa4a13` (including the Tiger Cloud work
in `0f00db3`) with our backend through `2f66d51`. No existing database migration SQL
was modified. No hosted database migrations, imports, seeds, or deployments were run
as part of this merge. The frontend, voice/dispatch, and existing API contract are
preserved exactly as supplied by upstream.

## One database, explicit ownership

| Owner | PostgreSQL location | Used by | Migration tool |
|---|---|---|---|
| Existing website operations | `goob` | `operations.server`, existing `/api` | `operations.database` |
| Teammate's 97-table foundation | `goob_foundation`, metadata in `goob_db_meta` | Standalone database tooling and SQL reports | `database.cli` |
| New authenticated backend | 17 `public.*_v1` tables, `public.alembic_version` | `operations.api_v1.app`, `/api/v1` | `alembic -c alembic-backend.ini` |

These are separate data models, not mirrored copies. Creating a customer through v1
does not create a legacy or foundation customer. The website still reads the legacy
contract. Moving v1 onto the foundation requires explicit UUID identity mappings,
adapters for its normalized tables and constraints, and a reconciled cutover. This
merge does not silently double-write records or import historical data.

V1 explicitly sets its connection search path to `public, pg_catalog` and timezone
to UTC so a shared role's default cannot send migrations or queries into `goob` or
`goob_foundation`. Explicit service dates are preserved; the foundation's property-
local business dates are not converted by this integration.

## Install and configure

`pip install -r requirements.txt` now installs both the teammate's psycopg2/dotenv
dependencies and the new API's dependencies. The backend-only container retains its
smaller dependency list. Both drivers are intentional: the existing adapter uses
psycopg2 while SQLAlchemy v1 uses psycopg 3.

The native `postgresql://` URL used by the website is accepted by v1, along with
`postgres://` and `postgresql+psycopg://`. Keep the shared `DATABASE_URL` in native
`postgresql://` form so the existing website can use it too. Optional
`GOOB_API_DATABASE_URL` selects a separate v1 runtime-role credential and takes
precedence over `DATABASE_URL`. V1 production requires `sslmode=verify-full` and a
trusted CA. There is no fallback to SQLite or weaker production TLS.

V1 never automatically loads the repository's `.env` or runs migrations on startup.
Load an intended environment explicitly, for example after configuring a migrated
development database and OIDC issuer/audience/JWKS:

```sh
.venv/bin/uvicorn operations.api_v1.app:create_app --factory \
  --env-file .env --host 127.0.0.1 --port 8090 --no-access-log
```

For migrations, export the intended v1 migration credential into the shell, then
run Alembic. If both database variables are set, the API-specific one wins. Use
separate migration/runtime credentials for deployment. The standalone foundation
tools continue using `GOOB_DATABASE_URL` and their isolated-development/deployment
guards; v1 does not consume that variable.

Starting the existing website remains `.venv/bin/python -m operations.server`.
The old `GOOB_DEMO_DB` override is removed. Database tests use explicit URLs and
unique temporary schemas; browser tests require an explicit isolated workspace URL.
No cloud credentials are included in Git or copied between environments by this merge.

## Historical merge verification on a shared isolated PostgreSQL 18 database

These are the merge-time results. See [cloud cutover](CLOUD-CUTOVER.md) for the
subsequent removal of local database paths and live cloud verification.

The local test database was newly created and marked as isolated development. It
contained all three foundation migrations, the 206 known fictional foundation rows,
the v1 migration, and the legacy `goob` demo. Tests used explicit local URLs; no
cloud environment file was loaded.

- 61 Python tests passed: 35 existing v1 tests, 8 new connection/configuration cases,
  9 original SQLite workflow tests, and the same 9 workflows through the teammate's
  PostgreSQL adapter in isolated test schemas.
- All 43 foundation checks passed, including tenant constraints, immutable records,
  inventory/benefit concurrency, and unchanged fixture reconciliation.
- All 9 frontend simulation unit tests passed.
- All 4 browser scenarios passed across the initial run and a targeted rerun. The
  full dispatch journey exceeded its original 60-second limit at the final reload;
  it passed alone with a 120-second limit. No browser test or frontend source was
  changed. These website browser tests use their own isolated SQLite fixture.
- The 97-table generated foundation artifacts match their source specification.
- Alembic reported no missing v1 migrations. Existing migration files are unchanged.

The URL tests cover driver normalization, credential precedence, production TLS
validation, sanitized invalid-URL errors, and forced v1 schema/timezone selection
even when connection options initially select the foundation schema.

These checks establish local compatibility. Live v1 Tiger Cloud deployment, live AI,
frontend adoption of v1, and data-model consolidation remain separate work.
