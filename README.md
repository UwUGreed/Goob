# Goob

A combined contractor workspace: the React dispatch frontend now includes **Work review**, connected to the Python/SQLite operations API.

## Run the combined demo

From this folder:

```sh
npm ci --prefix goob-dispatch
npm run build --prefix goob-dispatch
python3 -m operations.server
```

Open http://127.0.0.1:8081. Use the dispatch map as before, then select **Work review** in the navigation to inspect customer equipment, coverage, material disposition, billing corrections and approval history.

The map uses its original fictional visit records and local travel simulation. Work review uses the separate Morgan Ellis HVAC scenario persisted in SQLite. Closing or approving a work review does not alter map assignments or complete a dispatch visit. Address similarity is not a job link. Both workflows are accessible within the same frontend; shared job identities and dispatch-to-approval synchronization remain planned.

## Development

Start `python3 -m operations.server` in one terminal, then `npm run dev --prefix goob-dispatch` in another. Vite proxies `/api` to the local operations server on port 8081.

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
