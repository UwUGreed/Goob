# Goob Dispatch

The existing React + TypeScript + Tailwind dispatch app now supports Google Maps 2D, native photorealistic 3D, server-side driving directions, and ElevenLabs Scribe realtime transcription. Goob's interface, readiness checks, dispatch workflow, and architectural Three.js district remain available.

## Run and verify

From the repository root, configure the existing Tiger Cloud PostgreSQL URL in the ignored root `.env` (`DATABASE_URL`, or the existing `GOOB_API_DATABASE_URL` runtime-role override). No SQLite, D1, or in-memory database is used by the application.

```sh
python -m alembic -c alembic-backend.ini upgrade head
python -m scripts.provision_portal_demo
npm --prefix goob-dispatch install
npm --prefix goob-dispatch run build
python -m operations.portal_server
```

Open `http://127.0.0.1:8090`. `/` is public; Launch demo opens `/sign-in`. The server reads Tiger Cloud through the existing SQLAlchemy/domain layer, applies workspace permissions, and persists sessions, customers, jobs, reservations, inventory movements and dispatch status. Database failures produce errors rather than fixture fallback.

The additive `20261011_portal_dispatch` migration adds portal users/sessions, request counters, technicians and visit metadata to the existing public v1 schema. It does not reset or replace `goob`, `goob_foundation`, or existing v1 records. The idempotent development provisioning command creates a separate fictional demo workspace and `goob`; it writes credentials to the ignored root `.demo-credentials.json`. The current demo uses username `goob` and password `goob`; fresh provisioning generates a password. Existing accounts/passwords remain unchanged. Keep this file private; presenters can read it locally. Do not use a password hash to sign in.

For Vite development, run the Python server above alongside `npm run dev` in this folder. Vite proxies `/api` to port 8090. Development accepts `localhost` and `127.0.0.1` origins on ports 5173 and 8090; custom frontend origins require `GOOB_PUBLIC_ORIGIN` on the Python process. Optional `GOOB_BACKEND_URL` changes the proxy target. The build's Worker is a static frontend/API proxy, with no database binding; hosted use requires an HTTPS `GOOB_BACKEND_URL` and matching `GOOB_PUBLIC_ORIGIN`. Production requires `GOOB_ENV=production`, PostgreSQL `sslmode=verify-full` with the provider CA, and HTTPS secure cookies. Existing OIDC bearer authentication remains supported.

```sh
npm test
npm run build
```

Cloud persistence browser verification: set `GOOB_E2E_BASE_URL=http://127.0.0.1:8090` and `GOOB_CLOUD_E2E=1`, then `npm run test:e2e`. This explicitly uses the designated demo account and adds clearly named verification records; providers are disabled in the test. Backend tests require an explicit `TEST_DATABASE_URL`; they create/drop only a unique test schema, never reset application tables. Original fixture browser tests describe the previous standalone preview and are retained separately.

## Environment configuration

| Variable | Purpose |
| --- | --- |
| `GOOGLE_MAPS_BROWSER_KEY` | Browser-visible Maps JavaScript key. Restrict production keys to approved website referrers and Maps JavaScript API. |
| `GOOGLE_MAP_ID` | Optional Map ID with published cloud styles for vector 2D and 3D Hybrid. Without it, 2D uses supported raster styling and 3D uses Google's default Hybrid style. |
| `GOOGLE_MAPS_SERVER_KEY` | Backend Routes API credential. Use a separate Routes-only key for production. |
| `ELEVENLABS_API_KEY` | Permanent server-only key authorized to create `realtime_scribe` tokens. |
| `DATABASE_URL` / `GOOB_API_DATABASE_URL` | Server-only Tiger Cloud PostgreSQL connection, root `.env`. |
| `GOOB_PUBLIC_ORIGIN` | Exact public origin for cookie-authenticated mutation checks. |
| `GOOB_BACKEND_URL` | HTTPS backend target for the hosted Worker, or Vite proxy target. |

Real credentials belong in ignored `.env.local` and hosted runtime secrets. `.env.example` contains placeholders only. The browser receives the Google browser key and temporary Scribe tokens; it never receives the permanent ElevenLabs key or a dedicated server routing key.

Google's [free Maps Demo Key](https://developers.google.com/maps/demo-key) supports Maps JavaScript and Compute Routes without billing information. Daily limits pause usage. This private prototype uses the supplied demo key for both Google variables, so that Google demo credential is browser-visible. Separate restricted keys are needed before production use.

For standard Google Cloud projects, link billing and enable **Maps JavaScript API** and **Routes API**. Create separate keys. Allow the exact deployed browser origin and needed local origins, such as `http://127.0.0.1:5173/*`. The loader uses an origin referrer policy, so referrer restrictions must match at origin level. Restrict the server key to Routes API and approved static outbound IPs when available; Workers have dynamic egress unless separately configured. Set API quotas and budget alerts; budget alerts are not spending caps. This app does not provision paid Google projects or billing accounts. See [Google setup](https://developers.google.com/maps/documentation/routes/get-api-key), [key security](https://developers.google.com/maps/api-security-best-practices), and [pricing](https://developers.google.com/maps/billing-and-pricing/overview).

The default 2D view uses Google's supported raster styling to hide business, medical, and transit labels while retaining streets, parks, and civic landmarks. Compact trade pins use `OverlayView`, with collision handling for hover/selection details. A configured `GOOGLE_MAP_ID` enables vector 2D and passes the same ID to native 3D. Reducing 3D business labels requires publishing a cloud style hiding commercial POI labels for **3D Hybrid** and associating it with that ID; inline JavaScript styles cannot alter the 3D basemap. See [Google's 3D styling guide](https://developers.google.com/maps/documentation/javascript/3d/customize-maps). 3D uses the real `maps3d` **Map3DElement** with native interactive trade pins, rather than tilted 2D or glTF vehicles. The app uses the current **weekly** channel and core supported APIs; alpha HTML markers and beta-only quality controls are excluded. Photorealistic imagery is not recolored. Google attribution remains visible. Hardware acceleration, browser support, connectivity, and coverage affect availability; initialization failures fall back to Google 2D with progress preserved. See [3D reference](https://developers.google.com/maps/documentation/javascript/reference/3d-map), [browser support](https://developers.google.com/maps/documentation/javascript/browsersupport), and [coverage](https://developers.google.com/maps/documentation/javascript/3d/coverage).

## Try the dispatch journey

1. Select **124 Oak Lane**. Review Maya's plumbing match, availability, and the part reserved on Truck P-02. Expand **Why this technician?** for the alternatives.
2. Wait for the driving preview, then click **Confirm assignment**. The backend rechecks skills, availability, job status, and parts. Approval does not start travel.
3. Click **Start travel simulation**. Switch 2D/3D, follow Maya, pause/resume, and select 1×, 5×, or 10×.
4. At arrival, click **Start work**, then **Complete job**.
5. Choose **Return to depot**, or review and confirm the unlocked follow-up at **46 Willow Way**.

Routes errors block real-map travel and offer **Fictional map**. This fallback uses its own street graph and says **Simulation — fictional locations**. Google route content is never rendered on the fictional map. Finish or reset an active Google journey before changing providers; switching Google 2D/3D remains available.

Google's estimated driving duration is separate from the accelerated simulation countdown. Vehicles follow decoded route segments by cumulative distance, with movement-derived heading. Routes are requested when the origin/destination changes, not each frame. Return travel requests a new route. Google route responses remain in active browser memory, with `no-store` responses, and are not persisted in PostgreSQL, local storage, logs, or fixtures. See [routing policies](https://developers.google.com/maps/documentation/routes/policies) and [service terms](https://cloud.google.com/maps-platform/terms/maps-service-terms).

## Real geography, fictional operations

Columbia public road intersections were verified against the [City street GIS](https://gis.columbiasc.gov/cola/rest/services/BaseMap/Street/MapServer/0). These are demo stops, not customer premises.

| Demo alias | Public intersection | Latitude, longitude |
| --- | --- | --- |
| Goob Depot | Lincoln / Gervais | 33.999743, -81.038546 |
| 124 Oak Lane | Park / Lady | 34.001573, -81.037475 |
| 82 Maple Avenue | Main / Lady | 34.002610, -81.034134 |
| 210 Cedar Street | Sumter / Gervais | 34.001766, -81.031937 |
| Chris's start / follow-up | Park / Gervais | 34.000252, -81.036894 |

Customers, technician locations, assignments, and inventory are fictional. Google views visibly say **Columbia, SC · Simulated technicians** One simulation state drives both views. Reload starts a fresh demo session; only view preferences persist locally. The backend stores the fictional approval/status ledger, not Google geometry or audio. No command changes stock quantities or membership balances. Reduced-motion mode disables camera transitions and uses discrete vehicle updates.

## Voice and typed commands

Open **Voice or type commands**, then click **Start microphone**. The authenticated, same-origin server endpoint issues a single-use Scribe token, limited to five requests per user per minute and twenty per IP. Listening begins when Scribe confirms the session. **Stop**, **Cancel**, dialog close, and unmount release microphone tracks. Recording stops automatically after one minute. Errors preserve the typed alternative.

Review/edit the transcript and click **Run command**. A deterministic parser resolves existing records and asks for clarification on ambiguous names. Supported examples:

- Who is available for electrical?
- Show available plumbers.
- Open the Oak Lane job.
- Check parts for this visit.
- Find the best technician for this job.
- Preview Maya's route.
- Switch to 3D.
- Follow Maya.

Availability questions return actual demo status and speak the answer using the browser's built-in voice. Scribe remains the ElevenLabs transcription provider; no ElevenLabs text-to-speech endpoint is called. Use Stop to review your question, then Run command to hear the reply. Jordan starts on a job, so the initial electrical reply says no electrician is available. Replay and Stop reply control the speech; starting the microphone or closing the dialog cancels it.

Recommendations propose a technician and reasons. Assignments still require **Confirm assignment** and backend approval. The labeled **Try demo command** runs a preset text command. Goob does not save audio or transcripts. ElevenLabs receives audio only while recording. See the official [React Scribe SDK](https://elevenlabs.io/docs/eleven-api/resources/libraries/scribe-stt/react-scribe), [token endpoint](https://elevenlabs.io/docs/api-reference/tokens/create), and [privacy policy](https://elevenlabs.io/privacy-policy). Public production use needs the owner's terms, privacy notice, and retention policy.

## Screen polish

One slim status bar identifies the map and simulation. Trade filters sit above the map; zoom, fit/reset, and follow controls share one edge. Selected routes have a contrasting outline, and unselected routes are muted. The simulation bar separates accelerated travel progress from Google driving time in the visit panel. Assignment confirmation appears above the map. Below 1120 px, details open in a keyboard-accessible drawer.

A single requestAnimationFrame clock drives distance-based vehicle interpolation, heading easing, and camera following. Maps consume motion directly while React progress text updates at 5 Hz; changing views does not reset progress or recreate the map. Dragging or zooming pauses camera following. Reduced motion retains discrete movement and immediate camera positioning.

## Code and checks

- `src/data.ts`, `routing.ts`, `simulation.ts`: mock records, fictional roads, guarded shared simulation.
- `src/integrations/`: geography, route decoding/interpolation, API client, dispatch coordinator, validated command parser.
- `GoogleDispatchMap.tsx`, `VoiceCommands.tsx`: Google adapters and official Scribe SDK, with cleanup and error handling.
- `mapScene.ts`, `mapLayout.ts`, `DistrictMap.tsx`: retained architectural miniature and screen-space label placement.
- `server/`: optional static frontend/backend proxy Worker.
- `../operations/api_v1/portal*.py`, `../operations/domain/desk.py`: authenticated cloud adapters and persistent sessions.
- `../operations/migrations/`: additive PostgreSQL migrations.

Unit checks cover commands, interpolation, simulation, identity/origin checks, token limits, routing fields, duplicate/concurrent assignments, and rejected inventory/route injection. Browser checks cover the complete journey, mobile layout, preferences, marker bounds, follow/manual interruption, adapter synchronization, API errors, denied permission, and microphone cleanup. Test adapters prevent provider calls even when local credentials are configured. Playwright uses installed Microsoft Edge on Windows, software WebGL, and one worker; adapt the executable path for another machine.

Live local checks with the supplied credentials returned a real Google driving route, rendered native Columbia 2D and photorealistic 3D with trade pins, preserved paused progress across modes, and transcribed synthetic speech through ElevenLabs. Stop released microphone tracks. Deployed origin restrictions and browser hardware must also permit map use.

Presentation refinements: Ask Goob accepts typed requests directly on the board, with microphone transcription and spoken availability replies in its dialog. Requests show their interpretation before separate assignment approval. Arrived journeys offer a local travel replay; replay never approves another visit, changes its arrived status, or increments visits completed. The job panel keeps its primary action outside its scrollable content. Manual map exploration pauses following and automatic route framing until a new selection or explicit recenter.


## Operations pages

Overview is available at /overview; / and /today redirect there. Customers, Jobs and Inventory have list and detail routes (/customers/:id, /jobs/:id, /inventory/:id). Dispatch accepts ?job=:id and retains selection through navigation and refresh. Unknown routes show a not-found view.

All pages share the dispatch simulation records. Local preview is visibly a demo and saves customer, job, inventory and assignment records on this device. Hosted authenticated sessions use the existing dispatch API and database store. Authentication enforcement remains on the server. There is no separate login route in this app.

Truck parts are reserved for approved active jobs, consumed once on completion, and cannot be reduced below reservations. Warehouse stock does not count as truck-ready stock. Use separate location records and stock adjustments to record stock movement. Custom service addresses require choosing a clearly labelled existing demo route destination; arbitrary addresses are not geocoded. Fixture contact details are intentionally left unknown.

Checks: npm run build (TypeScript, Vite, Worker), npm test, and npx playwright test e2e/dispatch.spec.ts e2e/operations.spec.ts. No lint script is configured.

## Backend work review

Work review remains available from the workspace menu and connects to the existing operations backend, with separate fictional job identities. Run the operations server on port 8081 for this view. Vite proxies its API endpoints while the Dispatch adapter serves its own endpoints. Browser tests require GOOB_E2E_BASE_URL for an explicitly selected isolated workspace and optionally PLAYWRIGHT_CHROMIUM_EXECUTABLE.
