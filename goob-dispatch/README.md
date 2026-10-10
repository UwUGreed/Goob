# Goob Dispatch

An interactive React + TypeScript + Tailwind demo for MEP dispatchers. The ivory, aubergine, and coral interface is inspired by the supplied dashboard references.

## Run

```sh
npm install
npm run dev
```

```sh
npm test
npm run build
```

On Windows with restricted PowerShell script execution, use `npm.cmd`.

## Try the journey

1. Select **124 Oak Lane**, review Maya's matching plumbing skills, truck inventory, and the route preview. Expand **Why this technician?** for alternatives.
2. Click **Assign visit**, then **Start travel simulation**.
3. Switch between **2D** and **3D**, try **Follow technician**, pause/resume, and use 5× or 10× speed.
4. At arrival, click **Start work**, then **Complete job**.
5. Choose **Return to depot**, or review and approve the plumbing follow-up at **46 Willow Way**.

Chris can be dispatched to Maple Avenue independently. Jordan starts working at Cedar Street. The sidebar provides functional demo schedule, customer, job, and inventory views.

## Structure

- `src/data.ts`: fictional technicians, customer visits, truck stock, default preferences
- `src/routing.ts`: connected street graph, routes, distance-based interpolation
- `src/simulation.ts`: guarded assignment reducer and time progression
- `src/mapScene.ts`: self-contained Three.js district, shared vehicles, orthographic and angled views
- `src/components/`: map, selection details, playback, dialogs
- `src/App.tsx`: dashboard composition and validated local view preferences

This demo uses no API keys, map-provider requests, real customer data, GPS, voice recognition, or live AI. The microphone button runs a labeled preset demo command. Simulation state resets on reload; view preferences are saved in local storage. Reduced-motion mode disables decorative transitions and shows travel in discrete position updates.

## Integrated operations review

The navigation now includes **Work review**, a React view connected to the operations API. It displays equipment coverage, proposals, returned materials, billing corrections, benefit ledger and employee approval history. The Morgan Ellis operations example has separate fictional job identities from the map visits; approvals do not change dispatch simulation state.

For development, start `python3 -m operations.server` from the repository root, then run `npm run dev` here. The Vite server proxies `/api` to port 8081. For a single-address demo, build here and run the API; it serves this frontend at http://127.0.0.1:8081. If the API is unavailable, Work review shows an error with a retry button while dispatch continues working.

`npm test` runs simulation unit tests. `npm run test:e2e` builds and starts an isolated combined app on port 8082, then runs dispatch and operations browser tests.
