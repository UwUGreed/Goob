# Goob website operations API

Build the existing frontend with `npm ci --prefix goob-dispatch` and
`npm run build --prefix goob-dispatch`. Configure the private server `.env` with
Tiger Cloud's native PostgreSQL `DATABASE_URL`, then run
`python3 -m operations.database check` and `python3 -m operations.server`.
Open http://127.0.0.1:8081 and select **Work review**.

All work-review records come from the cloud `goob` schema. Normal connections and
server startup do not migrate or seed. There is no local SQLite database fallback,
SQLite import command, or supported `GOOB_DEMO_DB` override. The explicit
`operations.database init` command creates missing schema only, without demo rows.

This is still a loopback demonstration server with simulated roles and a fixed AI
proposal. Cloud persistence is not production authentication. Dispatch map state
and voice behavior are unchanged. The new authenticated backend is documented in
[the v1 guide](../docs/backend/README.md); its tables and identities remain separate.

Work review supports atomic approval, equipment coverage, benefits, returned stock,
integer-cent draft billing, retry protection, audit history, and JSON export. It does
not collect payment or calculate production tax. Readiness and migration cards in
this existing UI remain previews.

The nine workflow tests now run only against an explicitly supplied
`GOOB_TEST_POSTGRES_URL`, creating and removing their own uniquely named schemas.
They skip when no URL is supplied and never read the application's `.env` themselves.
