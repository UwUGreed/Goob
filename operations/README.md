# Goob operations demo

From the repository root: `python3 -m operations.server`, then open http://127.0.0.1:8081.

Prepare the demo proposal, review the $240 original draft versus the $180 corrected draft, then confirm work and approve. The covered visit drops from one to zero, one spare returns to stock, and the immutable approved draft and audit record persist across reloads. Try the technician/dispatcher roles to see server-side approval rejection. Export downloads the demo records as JSON.

Test: `python3 -m unittest discover -s tests -v`.

SQLite data lives at `operations/demo.sqlite3`; use `GOOB_DEMO_DB=/path/to/new.sqlite3` for a fresh scenario. Back up the database before future migrations. The server binds to loopback only and is for local demonstration, with a role simulation instead of authentication. Do not expose it publicly. No API keys or external services are used.

Implemented: persistent transactional approval, exact coverage checks, benefit consumption, issued/installed/returned material accounting, integer-cent invoice corrections, stale-proposal checks, retry protection, module dependency checks, approval history and export.

Simulated: fixed AI proposal, demo identity, seeded original invoice/material issue. Preview-only: return-visit blocker and uncertain migration row. Roadmap: real identity/branch scopes, comprehensive inventory/reservations, agreement lifecycle, communication drafts, migrations, integration adapters and dispatch synchronization.

`goob-dispatch/` remains untouched and runs independently using its own README. See `docs/OPERATIONS-ARCHITECTURE.md` for module ownership, assumptions and phased delivery.
