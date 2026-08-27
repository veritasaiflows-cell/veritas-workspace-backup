# Veritas PM Control Cockpit

Local TypeScript/Node cockpit over PM program-state proof packets.

## Run

```powershell
cd apps\pm-control-cockpit
npm run validate
npm run start
```

Then open:

```text
http://127.0.0.1:8765
```

Set a different port with:

```powershell
$env:PORT='8770'; npm run start
```

## Source Registry

The cockpit does not hardcode PM artifact paths in the UI. It reads:

```text
state/pm-cockpit-source-registry.json
```

That registry maps the current generated proof packets:

- `tmp/pm-program-state.json`
- `tmp/pm-lane-scoreboard.json`
- `tmp/pm-next-actions.json`
- `tmp/pm-blocker-register.json`
- `tmp/pm-main-session-handoff.json`
- `tmp/pm-dispatch-ledger.json`
- `tmp/heartbeat-continuation-candidates.json`
- `tmp/wf75-closeout-refresh.json`
- WF75/autonomy/boundary support packets
- SMB/generic pivot packets:
  - `tmp/generic-service-run-contract.json`
  - `tmp/wf75-smb-workflow-scenario-library.json`
  - `tmp/wf75-smb-customer-preview.json`
- `tmp/wf75-smb-customer-preview-validation.json`
- `tmp/wf75-smb-pilot-decision-packet.json`
- workflow route packets:
  - `tmp/workflow-routing-index.json`
  - `tmp/workflow-routing-index-validation.json`
  - `tmp/workflow-routing-index.sqlite`

If PM state moves from `tmp/` to `state/` later, update the registry first.

## Local API

Core routes:

```text
/api/state
/api/sources
/health
```

SMB/generic routes:

```text
/api/generic/pivot
/api/smb/scenarios
/api/smb/service-runs
/api/smb/customer-preview
```

Academy and SQL-control routes:

```text
/api/academy/current
/api/sql/control-plane
/api/sql/service-state
/api/workflows/routes
```

Talk Lite routes:

```text
/api/talk-lite/status
/api/talk-lite/transcribe
/api/talk-lite/ask
/api/talk-lite/tts
```

The browser routes `/generic`, `/smb`, `/smb/scenarios`, `/smb/service-runs`, `/smb/customer-preview`, `/academy`, `/sql`, `/workflows`, and `/talk-lite` all serve the local cockpit shell. The app remains a local internal review surface.

## Talk Lite

The Talk Lite tab is a local push-to-talk path:

```text
browser microphone or audio upload
-> tmp/talk-lite audio file
-> scripts/local_audio_transcriber.py
-> openclaw agent session agent:main:talk-lite
-> openclaw infer tts convert using the configured Microsoft TTS provider
-> browser audio playback
```

It does not use OpenAI Realtime voice. The GPT/Veritas step is a normal text agent turn through Gateway, and Microsoft TTS is used only for the spoken response. Voice turns stay review-only: no paper/live/account action, no portfolio/canon mutation, no config/auth/runtime change, and no owner approval inference.

## Academy And SQL Posture

The cockpit now has:

- an `Academy` tab over `training/wf75-academy/wf75-academy-current.json` and `training/wf75-academy/wf75-academy-manifest.json`
- a `SQL` tab over the derived service-state caches `tmp/generic-service-state.sqlite` and `tmp/wf75-service-state.sqlite`
- a `Workflows` tab over `tmp/workflow-routing-index.json`, `tmp/workflow-routing-index-validation.json`, and the derived route-control DB `tmp/workflow-routing-index.sqlite`

The SQL and Workflows tabs are deliberately control-plane bridges, not canon surfaces. JSON contracts still drive core UI state, and SQLite is queried through a read-only, allowlisted Node adapter.

Current read-only SQL views:

- generic service runs, operator queue, QA events, renderer outputs, artifact refs, and authority events from `tmp/generic-service-state.sqlite`
- WF75 service requests, queue items, artifact refs, events, and metadata from `tmp/wf75-service-state.sqlite`
- workflow routes, freshness counts, stale/aging routes, helper-safe lanes, owner-gated lanes, next actions, and authority flags from `tmp/workflow-routing-index.sqlite`

This makes crons/reminders more efficient because scheduled jobs can write structured proof rows once, then the local cockpit and reminder/handoff logic can query row state directly instead of reparsing many JSON files on every view.

## Boundary

This is an internal control surface only. It reads generated proof packets and exposes status, readiness, blockers, next actions, handoff state, closeout proof, source freshness, and authority flags.

It does not grant public launch, customer data, external delivery, SQL import, canon/portfolio mutation, cleanup move/delete/archive, paper/live/account action, config/auth/runtime mutation, or owner approval.
