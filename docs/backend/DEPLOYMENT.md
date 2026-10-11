# Vultr + Tiger Data deployment and recovery

Status: the supplied Tiger Cloud service is connected and the v1 schema is deployed;
see [cloud cutover evidence](CLOUD-CUTOVER.md). Vultr deployment, container build,
public HTTPS, OIDC login, and live Gemini inference still require environment
acceptance with the project's accounts.

## Provision and release

1. Use the team's authorized Vultr project and budget. Provision a small Linux VM with
   Docker/Compose and SSH restricted to the operator. Keep application port 8090 private;
   expose only HTTPS/HTTP for Caddy and restricted SSH. Size the VM from actual load.
2. Create Tiger Data database/service and obtain the provider's certificate chain and
   connection details. Use a schema-owner credential only for migrations. Provision a
   separate non-owner runtime login; apply `deploy/backend/grants.sql` with that role.
   Restrict database networking to authorized clients where supported. Do not share a
   development superuser connection string with the deployed application.
3. Agree the OIDC issuer/audience/JWKS and frontend origin with the existing owner. Keep
   voice/frontend services and their deployment files unchanged. Choose a separate API
   hostname with DNS pointing to the Vultr VM.
4. Copy `environment.example` to ignored `runtime.env`. Supply runtime DB, OIDC and
   Gemini settings. Store Tiger Data CA at ignored `tiger-ca.pem`. Create ignored
   `migration.env` containing `GOOB_ENV=production` and a separate schema-owner
   `DATABASE_URL` with `sslmode=verify-full` and the mounted CA path. Restrict secret file
   permissions and keep them out of screenshots, source, images, and logs.
   If using `GOOB_API_DATABASE_URL`, set it consistently in each service's environment:
   it takes precedence over `DATABASE_URL`, including for the migration process.
5. Build a release image, record its commit and digest, and run migrations once:

```sh
export API_DOMAIN=YOUR_BACKEND_HOSTNAME
export GOOB_IMAGE=goob-backend:YOUR_COMMIT
docker compose -f deploy/backend/compose.yaml build api
docker compose -f deploy/backend/compose.yaml --profile tools run --rm migrate
docker compose -f deploy/backend/compose.yaml up -d api proxy
```

6. Run the bootstrap operator command inside the backend image for the verified owner
   subject, or provision it beforehand with the same schema. Grant subsequent users
   through the authenticated admin endpoint after creating/inviting them in the chosen
   OIDC provider. Provider-specific login/invitation UI is outside this backend.
   Run `python -m scripts.backend_preflight --production --online` inside the API
   container before acceptance. It checks configuration, TLS, schema and basic runtime
   role restrictions without writing data or revealing credential values.
7. Inspect `/health/live` and `/health/ready`, then use a real access token to create/read
   records in an isolated demo tenant. Anonymous business requests must return 401;
   cross-tenant and revoked-user attempts must fail. Run the API demo, review a live
   Gemini proposal, and confirm persistence after restarting `api`.
8. Record image digest, commit, schema revision, deploy time, provider/model, and the
   acceptance results in a release manifest. Never put credentials in that manifest.

For a read-only authenticated smoke check, set `GOOB_ACCESS_TOKEN` and
`GOOB_TENANT_ID` in the operator environment and run
`python -m scripts.check_backend --url https://API_HOST --job-id JOB_ID`.
Gemini and ElevenLabs remain TBD; omit their live claims until separately verified.

No Terraform/API call in this repository automatically purchases or provisions a VM.
The Docker build copies only the new backend, migrations, and bootstrap command; it
does not bundle the frontend, voice code, or old demo HTTP server.

## Monitoring and resilience

- `/health/live` checks process response; `/health/ready` checks DB/schema availability.
- Container restart policy and bounded JSON logs are in Compose. Use provider monitoring
  for downtime, disk, memory, database connections, and Gemini quota failures.
- Application errors include request IDs. SQL and provider exceptions are sanitized;
  Uvicorn access logging is disabled to reduce exposure of URL identifiers.
- A failed provider call leaves no stock/benefit/invoice mutation. Manual structured
  proposals remain available. Two simultaneous confirmations have one business effect.
- Application workers do not auto-run schema migrations. Do not expose migration
  credentials to the normal API service or run incompatible app/schema versions.

## Backup and restore

Enable the Tiger Data plan's supported backup/recovery features and verify the actual
retention in that account. Do not assume a particular plan includes point-in-time restore.
Before cutover, create an operator-controlled logical backup using `pg_dump --format=custom`
with credentials passed through a protected service file/environment. Encrypt backups
and restrict access. API JSON exports aid portability but are not a complete DB backup.

Test restoration into a separate empty database with `pg_restore --no-owner`. Compare
row counts across all 17 application tables, then reconcile per-tenant benefit sums,
per-location stock/movement totals, reservation quantities, invoice snapshots, and audit
events. Start the same application release against the restored database and execute a
read plus a new idempotent command. Never test restoration over the live database.

Local implementation verification successfully dumped and restored the PostgreSQL test
database into a separate database and matched all 17 tables by row count and canonical
content checksum using `scripts/verify_restore.py`. Hosted recovery,
retention, encryption, and restore-time targets still require account-level verification.

## Rollback

Take a backup before schema changes. Redeploy a prior image only if its schema contract
is compatible. Otherwise pause writes and restore the verified snapshot into a separate
database, reconcile records written since the snapshot, and approve cutover. Do not
blindly run the initial Alembic downgrade against live data: it drops the v1 tables.
The initial migration is frozen; subsequent changes require new ordered revisions.

## Integration status

| Dependency | Code/configuration | Live evidence still needed |
|---|---|---|
| Tiger Data | Verified cloud connection, deployed v1 migration, TLS and persistence tests | Dedicated runtime DB grants and trusted production CA |
| Vultr | Container, Compose/Caddy, health checks, runbook | Image build and deployed HTTPS service |
| OIDC | RS256 issuer/audience/JWKS verification and memberships | Agreed provider and real user token |
| Gemini | Text schema, quote checks, quotas, provider failure handling | Key/model and measured sample evaluation |
| ElevenLabs | Existing team ownership | Their live spoken briefing demonstration |
| Messaging/payments/accounting sync | Draft/export foundations only | Provider selection, policies, sandbox implementation |
