# Veritas OS Automation Spine

## Objective
- Build the bones that make the Veritas OS easier to automate safely when the trust layer is ready.
- Design automation around real operating windows, artifact contracts, approval boundaries, and note ownership instead of trying to force full autonomy too early.

## Current State
- Core refresh orchestration already exists in `scripts/run_finance_refresh_chain.py` with explicit windows: `morning`, `post-close`, `post-earnings`, and `sunday`.
- Cron is enabled but currently unused: 0 jobs configured.
- The workspace already has a real separation between:
  - scripts/artifacts
  - canonical notes
  - workbook output
  - PDF/presentation layer
- Entry-band upkeep is now semi-automated with a safer boundary: proposal generation + review surfaces + human-gated apply + thin note-sync helper.

## Last Meaningful Progress
- Built a thin project continuity layer so unfinished work can keep a compact pickup point.
- Built `band_note_sync.py`, which makes band automation more resumable without silently rewriting the canonical note layer.
- Verified the live chain already carries most of the freshness burden for technical and band-supporting artifacts.
- Reviewed the existing automation-relevant skill stack and confirmed the real gap was a phase-owner for automation hardening. Created `skills/automation-hardening-manager/SKILL.md` to own rollout phases, trust gates, authority boundaries, and safe mechanism choice across cron, heartbeat, TaskFlow, and manual workflows.
- Wrote the first real architecture document at `06. Playbooks/Automation Architecture Spec.md`, defining current allowed automation phases, authority model, workflow ownership, v1 schedule shape, safe mutation boundaries, and trust gates before wider autonomy.
- Turned the schedule shape into concrete v1 cron candidates in `America/Phoenix` for `morning` (05:45 weekdays), `post-close` (14:15 weekdays), and `sunday` (08:00 Sunday), with command center explicitly in current artifact radar and Excel/PDF packaging held in later radar until their owner layers are stable enough.
- Defined validation expectations by workflow window, explicit stop lines, fallback behavior, sequential plumbing order, and a five-phase rollout path from validation-first hardening through later presentation packaging.
- Added `06. Playbooks/Automation Run Summary Contract.md`, which defines the per-window machine-readable run-summary artifact, status vocabulary, stop-line semantics, required outputs, and failure-state propagation rules into command center, workbook trust surfaces, and future packaging eligibility.

## Outstanding
- Implement the run-summary writer for each workflow window.
- Normalize failure visibility across dashboard, command center, and workbook export surfaces.
- Decide which workflows are safe for cron now versus later.
- Specify the approval boundaries for note edits, config edits, and derived recommendation layers.
- Design the next-generation band methodology so automation improves decision quality rather than just increasing activity.

## Blockers / Trust Gaps
- The current OS is good at generating artifacts, but not yet good enough to let machine outputs silently rewrite canonical judgment notes.
- Some upstream layers still have honest trust downgrades or manual dependencies (for example policy expectations fallback/manual elements and timing-sensitive earnings verification).
- A stronger band engine still needs to be designed; current MA20 + ATR logic is a decent operator baseline, not final commercial-grade technical logic.

## Next Action
- Implement the run-summary writer and propagate its trust state into command center and workbook/export surfaces before creating real cron jobs.

## Key Files
- `06. Playbooks/Automation Architecture Spec.md` - first real automation architecture document and v1 policy baseline.
- `06. Playbooks/Automation Run Summary Contract.md` - workflow-level contract for machine-readable run closure and failure propagation.
- `scripts/run_finance_refresh_chain.py` - current operating-window orchestration spine.
- `scripts/README.md` - live supported script surface and workflow expectations.
- `skills/automation-hardening-manager/SKILL.md` - phase-owner for automation hardening and trust-gated rollout.
- `skills/cron-automation-manager/SKILL.md` - scheduling design guardrails.
- `skills/memory-continuity-manager/SKILL.md` - continuity routing guardrails.
- `06. Playbooks/Project Continuity/Excel Operating Workbook.md` - adjacent workstream where semi-automation is already being hardened.
- `03. Portfolio/Technical Entry and Invalidation Sheet.md` - canonical technical note layer.
- `scripts/band_refresh.py` - entry-band proposal engine.
- `scripts/apply_band_update.py` - human-gated band application boundary.
- `scripts/band_note_sync.py` - thin canonical note-sync checklist.
- `tmp/portfolio-config.json` - machine-readable execution/config spine.

## Automation / Refresh Path
- Current safe automation boundary:
  1. cron may run refresh and artifact-generation workflows
  2. cron may generate review surfaces and status pages
  3. human review still gates canonical note rewrites and high-consequence config changes
- Current operating windows already defined in code:
  - `morning` - pre-open readiness refresh
  - `post-close` - end-of-day refresh
  - `post-earnings` - event-driven follow-up packet generation
  - `sunday` - weekly rebuild

## Proposed Schedule Skeleton
- Weekdays, pre-open: run `morning` once early enough to support the first real working session.
- Weekdays, post-close: run `post-close` once after market close and initial data availability.
- Sunday: run `sunday` once before the weekly review workflow.
- Event-driven earnings: avoid blind per-ticker cron explosion; prefer one post-close chain and one next-morning chain unless a specific isolated earnings workflow proves necessary.
- Heartbeat stays lightweight and should not be overloaded with full rebuild work.

## Architecture Principles
- One owner per workflow window.
- Scripts generate evidence; notes retain canonical judgment.
- Automation should raise review quality, not fake certainty.
- Approval boundaries should tighten only after repeatable validation.
- More autonomy should come from better contracts and trust checks, not from removing human review first.

## Rollout Shape
- Phase A: validation-first hardening
- Phase B: scheduling-safe artifact plumbing
- Phase C: review-surface hardening
- Phase D: narrow gated mutation helpers
- Phase E: presentation packaging expansion
