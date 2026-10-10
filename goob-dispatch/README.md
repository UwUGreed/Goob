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
