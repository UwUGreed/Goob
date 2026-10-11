# Backend integration handoff

The backend changes are ready for the frontend owner to adopt. This document does
not claim that the existing React UI uses `/api/v1`: its Work review still calls
the legacy `/api/state`, `/api/propose`, and `/api/approve` endpoints. Dispatch and
voice implementations are unchanged. Gemini and ElevenLabs are TBD by team decision.

## Identity and company setup

1. Configure an OIDC provider that issues RS256 API access tokens. Supply
   `OIDC_ISSUER`, `OIDC_AUDIENCE`, and `OIDC_JWKS_URL` to the backend. Use the provider's
   supported browser login flow; do not put a client secret in the frontend.
2. Set `ALLOWED_ORIGINS` to the exact frontend origin(s), comma separated.
3. With the migration/operator database environment loaded, provision a company for
   a verified provider subject:

   ```sh
   python -m scripts.bootstrap_backend --name 'Goob demo company' --owner-subject 'VERIFIED_SUBJECT'
   ```

   Save the returned company and branch IDs. This command creates a new company on
   each run; do not repeat it to log in. No default user or fake login is installed.
4. The frontend sends `Authorization: Bearer <access token>` and
   `X-Tenant-ID: <company ID>` on business API requests. `GET /api/v1/me` returns
   the user's role and allowed branch IDs. Roles are owner, office, technician, viewer;
   the legacy demo-role names are not the new authorization contract.

## One job workspace request

`GET /api/v1/jobs/{job_id}/workspace?limit=50` returns:

| Field | Contents |
|---|---|
| `job`, `customer`, `property`, `equipment` | Linked persisted records, including job revision |
| `coverage` | Membership eligibility and remaining balance for the job service date |
| `readiness` | Material, coverage, prerequisite, approval, and unknown dispatch evidence |
| `parts`, `locations`, `stock` | Relevant catalog/location records and available quantities |
| `reservations`, `movements` | Job material reservation and movement evidence |
| `notes`, `proposals` | Recorded notes and proposals awaiting or completing human review |
| `invoices`, `events` | Preserved billing snapshots and job audit events |
| `truncated` | Per-list flags; never interpret a truncated list as complete history |

The endpoint is read-only and checks company membership, branch access, and required
modules. `limit` applies separately to each list (1–100). Time-stamped lists are newest
first; proposal/reservation lists use stable IDs, not inferred creation times. Read
the existing history/export endpoints when a complete history is needed. Multiple
reads are not a transactionally frozen snapshot; refresh after writes. Current
coverage may be exhausted after an approval; render its preserved invoice snapshot
for the historical approved amount.

## Review and mutation flow

1. List jobs with `GET /api/v1/records/jobs`; open the selected job's workspace.
2. Create a proposal with `POST /api/v1/jobs/{id}/proposals`. Until Gemini is enabled,
   send explicit reviewed `extraction` fields with the note and `expected_job_revision`.
   Omitting extraction requests Gemini and currently returns a configuration error.
3. Read `GET /api/v1/proposals/{id}` for its billing preview and original note.
4. An authorized person submits `POST /api/v1/proposals/{id}/review` with action
   `approve`, `reject`, or `revise`, a reason, and `expected_revision`.
5. Reload the workspace after success; show conflicts or permission failures clearly.

Every mutation needs a unique `Idempotency-Key`. Keep the same key and identical body
when retrying an uncertain network result. Generate a new key for a different action
or edited payload. A 409 means the record/key changed; reload and review before retrying.
A 401 requires login/token refresh; a 403 means access/module permission is missing.
Do not simulate success or update displayed balances when a request fails.

`python -m scripts.backend_demo --url http://127.0.0.1:8090 --branch BRANCH_ID`
creates a complete fictional manual workflow using the company/token in
`GOOB_TENANT_ID` and `GOOB_ACCESS_TOKEN`. Run it only in the team's designated demo
company. It creates new records each time. It does not copy legacy records or call
voice/Gemini by default.

All exact request fields are documented at `/api/v1/docs` and `/api/v1/openapi.json`.
The workspace supplements the existing CRUD, agreement, inventory, and import routes.

## Hosting and verification commands

Install dependencies in a persistent project `.venv`; no temporary `/tmp` environment
or local database server is required. The runtime requires Python 3.14.

```sh
python -m pip install -r requirements.txt -r deploy/backend/requirements-dev.txt
python -m scripts.backend_preflight --env-file .env --online
python -m scripts.verify_backend --env-file .env
```

Preflight exits nonzero when login/origin settings are missing, even if its cloud check
passes. It prints setting names and sanitized results, never credential values.
The regression runner uses the explicitly selected cloud URL, creates test-only
schemas, compares application table checksums before/after, and verifies that the
schema inventory is unchanged. Existing unowned test schemas are left untouched.
Run it while teammates are not writing demo data; legitimate concurrent changes also
cause the preservation check to fail. It never resets application records.

For production, follow [DEPLOYMENT.md](DEPLOYMENT.md), then run inside the API container:

```sh
python -m scripts.backend_preflight --production --online
```

This checks the configured CA/verify-full connection, expected migration revision,
all 17 tables' required columns/SELECT grants, and basic runtime-role restrictions.
It does not purchase a VM, configure DNS, create a login provider, or prove real login.
The readiness endpoint now rejects an incorrect revision or missing table/column.

After a real user login, run from the operator's machine with token/company in the
environment:

```sh
python -m scripts.check_backend --url https://API_HOST --job-id JOB_ID
```

This makes only GET requests: liveness, schema readiness, anonymous denial, company
identity, and optionally the persisted job workspace. Tokens are sent only to HTTPS
origins or HTTP loopback; redirects are not followed. A passing smoke test does not
prove a live Gemini/ElevenLabs call or a frontend screen is integrated.

## Work remaining with owners/accounts

- Frontend owner: wire screens and real login to v1, with one consistent demo company.
- Team: supply identity-provider settings and a verified owner subject; no provider
  has been selected/configured in this repository.
- Hosting owner: provide Vultr access, hostname/DNS, runtime DB role and trusted Tiger
  CA; build the container and verify the public HTTPS frontend/backend deployment.
- Gemini: TBD. ElevenLabs: TBD with the voice teammate.
- Pitch owner: finish actual customer validation and pitch delivery. Hardware concept,
  mockup, cost assumptions, startup model, and pilot plan already exist in `docs/pitch`.

No automatic mapping was made between `goob`, `goob_foundation`, and `public.*_v1`.
Use the new demo company consistently rather than assuming those records share IDs.
