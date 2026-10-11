# Goob Operations API v1

A separate Python backend for the Goob operations workflow. The React frontend,
voice dispatch, original SQLite demo, and their existing APIs are unchanged.
The entrypoint is `operations.api_v1.app:create_app`; it serves no product UI.

## Implemented scope

- PostgreSQL/Tiger Data-compatible schema, versioned Alembic migration, tenant/branch
  composite foreign keys, immutable ledger/snapshot design, and safe command retries.
- OIDC RS256 token verification; server-side company memberships and branch grants;
  owner administration and revocation. The identity provider supplies login, signup,
  password reset, and invitations. This service does not add frontend login screens.
- Customer/contact/property/equipment/job/catalog/location create, read, update,
  search, and archive commands. One serviced equipment record per operational job.
- Effective-dated agreement versions, renewals, upgrades, cancellations, signed
  adjustments, coverage on the service date, and explicitly scheduled obligations.
- Inventory receiving, transfers within a branch, reservations/release, issue,
  installed/returned/damaged disposition, adjustments, and replenishment suggestions.
  Catalog quantities are bounded integer `each` units in this version.
- Text-only Gemini extraction, exact source-quote validation, unknown handling,
  proposal revision/rejection, human approval, and hourly provider-attempt budgets.
- Atomic equipment history, work confirmation, material disposition, benefit usage,
  draft billing, and audit events. Approved invoice snapshots remain intact on reversal.
- JSON/CSV import staging, review, transactional commit, duplicate-batch detection,
  source mapping, opening-stock/benefit reconciliation, and JSON export.
- Readiness evidence for materials, prerequisite work, coverage and customer approval.
  Technician qualification/availability deliberately stays **unknown** until the
  dispatch owner supplies it. This API never schedules or assigns technicians.
- Reviewed cross-trade opportunities and exactly-once conversion into operational jobs.
- Tenant-scoped daily material/event analytics and draft overcharge correction totals.
- Stored message drafts and approved-draft accounting exports. No messages, charges,
  or external accounting posts are sent by these features.

## External dependencies and deliberate limits

Code and local PostgreSQL tests do not establish a live cloud deployment. Configure
Tiger Data, Gemini, an OIDC provider, and Vultr before running provider/cloud acceptance.
No live provider credentials were available during implementation. Docker was not
installed in the authoring environment, so the container build is not yet verified.

ElevenLabs, voice, dispatch scheduling/state, and frontend adoption remain with their
existing owners. SMS/email delivery, payment processing, and accounting-provider sync
remain deferred until providers and policies are selected. Message drafts and exports
are not represented as completed external integrations.

Tax is not calculated: invoices are approved **drafts** in USD, not tax-compliant final
invoices. Subscription pricing is unset. Allowance grants are additive; unused benefits
carry forward until an explicit audited adjustment. No automatic refunds or proration.
Transfers between branches, fractional inventory units, uploads/attachments, arbitrary
CRM import formats, offline writes, and Timescale-specific hypertables are outside this
bounded implementation. Standard PostgreSQL time-series queries work on Tiger Data;
this code does not claim a benchmarked Timescale optimization.

Mutation commands serialize per tenant with a PostgreSQL transaction advisory lock.
This intentionally favors correctness for the pilot over high mutation throughput.
Financial evidence can be made append-only for the runtime database role using
`deploy/backend/grants.sql`; migrations use a separate schema-owner credential.

## Local setup

Run commands from the repository root with Python 3.14:

```sh
python3 -m venv .venv-backend
.venv-backend/bin/pip install -r deploy/backend/requirements-dev.txt
```

Use a dedicated PostgreSQL database (or the loopback-only test container):

```sh
docker compose -f deploy/backend/compose.test.yaml up -d --wait
export DATABASE_URL='postgresql+psycopg://goob_test:local_test_only@127.0.0.1:55439/goob_test'
.venv-backend/bin/alembic -c alembic-backend.ini upgrade head
```

The test password above is only for the disposable local test container. For Tiger
Data use its connection details, a dedicated runtime role, and certificate verification.
The service rejects SQLite URLs and rejects production URLs without `sslmode=verify-full`.

Configure `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, and `ALLOWED_ORIGINS` to
match the existing frontend team's identity decision. Supported signing algorithm is
RS256. The configured issuer/JWKS must use HTTPS and are never accepted from a token.
Use API access tokens with `sub`, `iss`, `aud`, `iat`, and `exp` claims.

Create a tenant for an already verified identity-provider subject:

```sh
.venv-backend/bin/python -m scripts.bootstrap_backend \
  --name 'Goob fictional pilot' --owner-subject 'SUBJECT_FROM_YOUR_OIDC_PROVIDER'
.venv-backend/bin/uvicorn operations.api_v1.app:create_app --factory \
  --host 127.0.0.1 --port 8090 --no-access-log
```

Bootstrap prints tenant/branch IDs, not credentials. It is a local operator command;
there is no anonymous tenant-creation or demo-role bypass in the new HTTP service.
Do not point the original React client at v1 without coordinating its contract adoption.

## API contract

OpenAPI: `/api/v1/openapi.json`; interactive API docs: `/api/v1/docs`.
In the API docs, click **Authorize** and enter the access token without the `Bearer`
prefix. Enter the company ID in each request's `x-tenant-id` field.
Every business endpoint requires `Authorization: Bearer <access token>` and
`X-Tenant-ID: <authorized tenant>`. Every mutation also requires an `Idempotency-Key`.
Reusing a key for a different actor, operation, or payload returns 409. Reusing it for
the same request returns the stored response after current authorization is checked.

| Route family | Purpose |
|---|---|
| `/records/{customers,contacts,properties,equipment,jobs,skus,locations}` | Create/list; detail GET/PATCH with `expected_revision`; archive through PATCH |
| `/agreements`, `/agreements/{id}/commands` | Create/read, preview/renew/upgrade/cancel/adjust |
| `/jobs/{id}/coverage`, `/obligations` | Coverage and scheduled service/renewal evidence |
| `/inventory/commands`, `/inventory/balances`, `/inventory/barcodes/{value}` | Ledger actions, available/replenishment quantities, SKU lookup |
| `/jobs/{id}/proposals`, `/proposals/{id}`, `/proposals/{id}/review` | Manual/Gemini proposals and employee review |
| `/jobs/{id}/history`, `/equipment/{id}/history`, `/jobs/{id}/reverse` | Evidence and explicit correction |
| `/jobs/{id}/readiness` | Read-only prerequisite evaluation; no dispatch mutation |
| `/imports`, `/imports/csv`, `/imports/{id}/rows/{index}`, `/imports/{id}/commit` | Stage, review, resolve, commit |
| `/records/opportunities`, `/opportunities/{id}/{convert,dismiss}` | Cross-trade follow-up review |
| `/admin/members/{OIDC-subject}`, `/admin/modules` | Owner-controlled access and module configuration |
| `/analytics`, `/export` | Scoped reports and portable evidence |
| `/message-drafts`, `/invoices/{id}/accounting-export` | Draft communications and reviewed invoice export; no external side effects |

List endpoints use `limit` (1–100), `offset`, and optional `q`. Record links/branches
are immutable after creation; correct identities by creating the right record rather
than rewriting historical links. Archive is limited to unused records: dependent CRM
records, equipment with agreements, jobs with work notes, and inventory with a ledger
must remain available for reconciliation. Module configuration preserves records and validates
dependencies. Export is an owner/office portability operation, including preserved
records from disabled modules within authorized branches.

API errors are sanitized and include a request ID. No arbitrary tenant/role header
grants access. Runtime API does not accept the old `X-Demo-Role` identity simulation.
Default dates for balances, adjustments, agreement changes, and obligations use UTC,
independent of the server's timezone. Coverage uses the explicitly supplied job service
date; obligations also accept an explicit `as_of` date. Tenant-local default dates
require a future timezone setting.

## Gemini and demonstration

Set `GEMINI_API_KEY` and a currently supported `GEMINI_MODEL` with structured-output
support. The adapter calls Google's `generateContent` API with a JSON schema. No model
name, fake inference, or fallback response is silently substituted. Up to two provider
attempts are allowed per extraction, with a default company limit of 30 extraction
attempts/hour. Failed calls count toward the budget. Returned metadata includes model,
schema/prompt versions, latency, usage, and the coverage at proposal preparation.

```sh
# Supply access token and tenant ID through the environment, not command arguments.
export GOOB_TENANT_ID='YOUR_TENANT_ID'
.venv-backend/bin/python -m scripts.backend_demo \
  --url http://127.0.0.1:8090 --branch YOUR_BRANCH_ID
```

The default demo is explicitly **manual** and produces the $240 to $180 correction.
Add `--gemini` to request actual provider extraction. Live AI proposals are left pending
review, never automatically approved by the script. Every run creates new fictional
records; use a separate demo tenant. Running the default does not prove Gemini usage.

The example dataset and evaluator in `docs/backend/gemini-evaluation.json` and
`scripts/evaluate_gemini.py` are synthetic. Run them with credentials before reporting
any extraction accuracy. Their expected outcomes are test labels, not measured results.

## Migration and export

Import rows carry a stable `source_id`, typed `kind`, `name`, and `data`. Parent/customer/
property/equipment source references must point to earlier rows. CSV has the same
fields; the `data` cell contains quoted JSON. Import commits require reviewer permission.
Missing/invalid links fail transactionally. Ambiguous matches and conflicting balances
require a resolution reason. Identical batch content is deduplicated. Exact-name
duplicates are review signals, not automatic identity merges.

```sh
.venv-backend/bin/python -m scripts.reconcile_demo_export legacy-export.json \
  --branch YOUR_BRANCH_ID --output /tmp/goob-import-review
```

This prepares a source archive, staged import, and reconciliation report without any
database writes. The old export lacks sufficient evidence to recreate historical
movements and job/dispatch relationships. Those differences are explicitly reported;
original invoices/audits stay in the archived source. New stock/benefit records are
reviewed opening balances, not fabricated historical transactions. Commit the staged
batch only after resolving its review flags, then stop writing the old source.

## Verification

```sh
export TEST_DATABASE_URL="$DATABASE_URL"
.venv-backend/bin/pytest -c tests/backend_v1/pytest.ini tests/backend_v1 tests/test_operations.py
.venv-backend/bin/ruff check --config deploy/backend/ruff.toml \
  operations/api_v1 operations/domain operations/persistence operations/integrations \
  scripts tests/backend_v1
```

Tests require a migrated dedicated PostgreSQL database, create fictional tenant IDs,
and exercise signed tokens, transactions, concurrency, rollback, imports, stock,
benefits, provider errors, and the API demo. Tests include a temporary database trigger
to prove rollback, so run them as the test database owner, not the runtime app role.
Mocked provider tests are labeled; they do not establish live provider connectivity.

Production setup and recovery: [deployment runbook](DEPLOYMENT.md).
