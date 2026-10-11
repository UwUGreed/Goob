# Customizable workspaces

Overview and Dispatch have named views and a workspace editor. Save explicitly to persist settings to the signed-in account. Cancel restores the state from before editing. Personal views take precedence over the published team default, then the built-in Balanced starter. Choosing Use team default clears the selection while preserving personal views.

Balanced, Dispatch focus and Owner focus starters can be edited and saved as personal copies. Widgets have fixed identities. Desktop uses 12 columns, tablet six and mobile one; each breakpoint retains its layout. Edit handles enable drag/resize on desktop and tablet. Keyboard buttons move panels and change their dimensions; mobile uses move buttons. Job identity remains visible regardless of optional list columns.

Only presentation settings are stored: versioned layout JSON, visibility, columns, display filters, density and map mode. Selected records, dates, search and active travel remain operational/transient state. Import device settings copies the former device preference into a draft; cloud saving is still explicit.

## API

Authenticated `/api/v1/workspace-views` uses the existing session's user and tenant. No tenant or user IDs are accepted in configuration bodies.

- `GET ?page=overview|dispatch`: personal views, team default and selected personal view ID.
- `POST`: create and select a personal view (`page`, `name`, `configuration`).
- `PATCH /{id}`: rename/change an owned personal view (`revision`, `name`, `configuration`).
- `DELETE /{id}`: delete an owned personal view (`revision`); clear its selections.
- `POST /selection`: choose a personal view or follow team default (`page`, `view_id` nullable).
- `POST /team-default`: publish (`page`, `name`, `configuration`, `revision`); requires owner access to all tenant branches. Revision zero means no existing default.

Writes require the existing `Idempotency-Key` contract. Revisions return 409 when stale. Reload saved views retains the draft, fetches current revision, and permits explicit retry; failed saves retain the draft. Saved views never grant operational access.

## Deployment and verification

Migration `20261013_workspace_views` adds `workspace_views_v1` and `workspace_selections_v1`. Existing push-to-main deployment backs up Tiger Cloud and runs Alembic before switching releases. For installations with a separate runtime database role, apply `deploy/backend/grants.sql` as the migration owner to grant access to these tables. Existing data and personal views are retained; downgrade deliberately requires a reviewed forward migration.

The rollout found an existing cloud revision `20261014_view_preferences` missing from source control. Its compatibility migration records the inspected historical table definition; merge revision `20261015_merge_workspace_views` joins both histories. Upgrading that cloud database creates the new workspace tables and preserves its historical preference table without restamping, resetting or editing existing records.

Frontend: `npm test --prefix goob-dispatch`, `npm run build --prefix goob-dispatch`.
Browser: from `goob-dispatch`, `npx playwright test --config playwright.workspace.config.ts`. This suite launches an isolated Vite instance with mocked HTTP data; it tests editing, retries, saved selections across browser sessions, owner defaults, mobile layout, and dispatch travel preservation. It never changes shared CRM records.
Backend: `.venv/bin/python -m pytest tests -q`, with an explicit `TEST_DATABASE_URL` for the cloud API integration suite. The fixture creates a uniquely named disposable PostgreSQL schema, migrates and tests it, then drops only that schema. The workspace tests cover persistence, permissions, cross-user/tenant isolation, validation, idempotency and revision conflicts.
