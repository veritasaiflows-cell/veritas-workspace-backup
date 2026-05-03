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
- do not treat a workflow as advanced unless `execution mode` and `QC complete` are visible here or in the linked active queue entry

## Active Projects

| Project | Lane | Owner | Status | Current phase | Execution mode | QC complete | Last completed pass | Next pass | Waiting on operator? | Continuity note | Chain log |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OpenClaw Trust-Hardening Queue | Control plane / workspace governance | Veritas | Active | Workflow 9 is closed; Workflow 9A remains the active reorganization gate before the older Workflow 10-12 backlog. Phase 2 caller-risk tracing is now complete: `generated documents/` is confirmed as live code-path debt, `scripts/.claude/...` appears to be untracked stale residue, the technical-pass overlap is a skill-boundary issue rather than an automation-chain dependency, and `.gitignore` now carries the missing `__pycache__/` rule while the upstream daily-note writer remains unpatched runtime debt. | Main-session queue restructure / continuity update | Yes | Workflow 9A Phase 2 - caller-risk analysis completed; `.gitignore` hardened with `__pycache__/`; Phase 3 operator packet drafted | Run the Workflow 9A Phase 3 decision packet: get operator decisions on the fast-track delete/move bucket, the `generated documents/` outcome, and the technical-skill boundary; then execute only approved cleanup before handing residue to Workflow 9B / Workflow 10 | Yes - delete/move/archive actions and the `generated documents/` end-state now need Randall's explicit decisions | `06. Playbooks/Project Continuity/Workflow 9A - Workspace Structure and Drift Cleanup.md` | - |
| E17 Universe Synchronization | Core OS integrity | Veritas | Closed with follow-up | Core ownership drift closed; residual warning stack handed forward into Workflow 5 packaging guardrails | Main-session closure / QA | Yes | Phase 4 Sub-Pass 2 - direct date pass plus GOOG/MSFT revalidation | None inside E17; residual timing-sensitive/date-trust caveats now live in the Workflow 5 degraded-contract guardrails and later trust repair work | No - the broader warning-gate judgment is now complete enough for honest handoff | `06. Playbooks/Project Continuity/E17 Universe Synchronization.md` | `06. Playbooks/Project Continuity/E17 Universe Synchronization - Chain Log.md` |
| Capital Deployment Readiness | Deployment readiness | Claude | Held / review-ready | Phase 3 handoff wait | Other - Claude/Gemini handoff path | No | Phase 2 - Morning decision surface design | Claude post-Phase-3 review after Gemini implementation pass | Yes - Gemini Phase 3 output and operator re-engagement | `06. Playbooks/Project Continuity/Capital Deployment Readiness.md` | `06. Playbooks/Project Continuity/Capital Deployment Readiness - Chain Log.md` |
| Research Automation Freshness Monitor | Research / automation | Veritas | Defined / queued | Project definition and source-boundary design | Other - not opened yet | No | - | Define the first review-only automation pass for news, geopolitics, and company-response monitoring after the current note-sync chain is stable | Yes - should not outrun Workflow 4B / 4C truth-sync work | `06. Playbooks/Project Continuity/Research Automation - News, Geopolitics, and Thesis Drift Monitoring.md` | - |

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
- Healthcare Sleeve Thesis Tightening
- Controlled Note Reconciliation
- Morning Deployment Surface

These should not all be opened at once.
