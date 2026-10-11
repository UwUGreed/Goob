# Integration tooling verification — October 10, 2026

Implemented an authenticated job workspace response joining customer, property,
equipment, coverage, readiness, relevant inventory, proposals, invoices and audit
evidence. The current frontend remains unchanged; adoption instructions are in
[TEAM-HANDOFF.md](TEAM-HANDOFF.md).

Deployment tooling now includes a credential-safe preflight, a read-only authenticated
API smoke check, a repeatable cloud regression runner, stricter schema readiness, a
database connection timeout, and Docker build-context secret exclusions.

## Results

- `python -m scripts.verify_backend --env-file .env`: **78 passed** in 182.75 seconds.
  Includes persisted workspace responses before/after approval, read-only behavior,
  tenant/branch/module isolation, truncation, missing-table readiness failure,
  authenticated smoke checks, allowed/denied browser origins, existing stock/benefit
  transaction regressions, and offline configuration guards.
- All **129 application tables** matched their pre-run row counts and canonical
  content checksums. The test-schema inventory was unchanged after the run.
- One upstream Starlette/httpx test-client deprecation warning remains. No test failed.
- `npm test --prefix goob-dispatch`: **9 passed**.
- `npm run build --prefix goob-dispatch`: passed. Vite reports the existing large
  JavaScript chunk warning; no frontend implementation was changed.
- Ruff, Python compilation, Git whitespace checks, and the 97-table foundation
  generation check passed. Readiness's expected revision matches Alembic head.
- Live read-only preflight confirmed TLS connectivity and all **17 v1 tables**.
  It correctly exited nonzero for missing OIDC issuer, audience, JWKS URL and frontend
  origins. Missing settings were not replaced with fake production credentials.
- Changed files were checked against the private cloud URL/password; neither is in
  the changes. The ignored credential file remains mode `0600`.

The authenticated API checks used signed test identities and isolated schemas on
the real cloud database. They do not establish a real identity-provider login or
public website acceptance. Gemini/ElevenLabs calls remain mocked/TBD. No Docker or
Podman engine is installed here, so the container build and Vultr deployment remain
unverified. No new schema migration or application-data mutation was needed for this
release.

## Remaining work

1. Frontend owner: connect the UI to v1 and use consistent company/job IDs; integrate
   actual login and any persistent dispatch work they own.
2. Team: select/configure the identity provider and provision a verified owner/company.
3. Hosting owner: build/deploy on Vultr, configure frontend hosting, DNS/HTTPS, allowed
   origins, a restricted runtime DB role and trusted Tiger CA, then run hosted acceptance.
4. Gemini: TBD. ElevenLabs: TBD with the voice teammate.
5. Team: demonstrate the connected frontend workflow and refresh/persistence after
   deployment. Complete actual customer-validation evidence and final pitch delivery;
   hardware concept/mockup/budget and startup/pilot documents already exist.
