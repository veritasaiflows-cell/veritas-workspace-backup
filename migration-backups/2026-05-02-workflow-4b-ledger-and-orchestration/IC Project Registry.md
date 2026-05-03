# IC Project Registry

## Purpose

Single operator view of active independent-contractor projects.

Use this file to track:
- which IC owns what
- which phase is active
- what the next pass is
- which projects are blocked on operator judgment
- where the continuity note and chain log live

This is the control layer above individual project notes.

## Operating Rules

- one row per active or recently paused project
- update when ownership, phase, or next pass changes materially
- continuity note remains project truth
- chain log remains pass-by-pass ledger
- this registry is the operator control board

## Active Projects

| Project | Lane | Owner | Status | Current phase | Last completed pass | Next pass | Waiting on operator? | Continuity note | Chain log |
|---|---|---|---|---|---|---|---|---|---|
| OpenClaw Trust-Hardening Queue | Control plane / automation | Veritas | Active | Workflow 4B preflight / proof planning | Workflow 4 — sequential chain protocol completed with QA/audit | Launch Workflow 4B controlled cron-proof pass, then Workflow 4C — Finance Chain Truth Sync Hardening before trust-grade reassessment | No — next workflow is clear; preflight is the active step | `06. Playbooks/Project Continuity/Workflow 4B - Live Cron Shakedown + Run Ledger Hardening.md` | — |
| E17 Universe Synchronization | Core OS integrity | Veritas | Active | Cross-project review / note reconciliation | Phase 3 Sub-Pass 3 — workflow/action integrity repair | Targeted note/date reconciliation for stale workflow_state and post-earnings states | Yes — judgment on note-layer reconciliation and post-earnings posture | `06. Playbooks/Project Continuity/E17 Universe Synchronization.md` | `06. Playbooks/Project Continuity/E17 Universe Synchronization - Chain Log.md` |
| Capital Deployment Readiness | Deployment readiness | Claude | Held / review-ready | Phase 3 handoff wait | Phase 2 — Morning decision surface design | Claude post-Phase-3 review after Gemini implementation pass | Yes — Gemini Phase 3 output and operator re-engagement | `06. Playbooks/Project Continuity/Capital Deployment Readiness.md` | `06. Playbooks/Project Continuity/Capital Deployment Readiness - Chain Log.md` |

## Intake Criteria For New Projects

Before opening another IC project, confirm:
- it improves freshness, deployability, trust, or coverage materially
- it has a distinct lane
- it has a continuity note home
- it has a named owner
- it is not overlapping an active semantic rewrite

If any answer is no, do not open the project yet.

## Current Capacity Guidance

Current recommended parallel load:
- 2 active IC-owned projects at once
- plus 1 active OpenClaw subagent pilot lane for bounded implementation or inspection work
- plus 0-1 cheap helper lane (Gemini Flash or equivalent) only for bounded follow-up checks

Codex Spark rule:
- `openai-codex/gpt-5.3-codex-spark` is removed from Veritas-routed workflow use
- Randall may still use it manually for QA/reports and bring the output back for review

Do not scale beyond this until:
- registry discipline is stable
- chain logs are consistently updated
- project handoffs are staying short instead of growing
- cross-project synthesis burden remains manageable

OpenClaw pilot control note:
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`

## Likely Next Project Candidates

Only after current lanes stabilize:
- OpenClaw Parallel Pilot Queue execution
- Macro / Policy Trust Repair
- Coverage Admission Model
- Controlled Note Reconciliation
- Morning Deployment Surface

These should not all be opened at once.
