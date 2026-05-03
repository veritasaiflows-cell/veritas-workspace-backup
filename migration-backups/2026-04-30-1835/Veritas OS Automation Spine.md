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

## Outstanding
- Define the automation architecture standards for the OS.
- Decide which workflows are safe for cron now versus later.
- Specify the approval boundaries for note edits, config edits, and derived recommendation layers.
- Design the next-generation band methodology so automation improves decision quality rather than just increasing activity.
- Create a rollout plan from manual -> semi-automated -> more autonomous, with explicit trust gates.

## Blockers / Trust Gaps
- The current OS is good at generating artifacts, but not yet good enough to let machine outputs silently rewrite canonical judgment notes.
- Some upstream layers still have honest trust downgrades or manual dependencies (for example policy expectations fallback/manual elements and timing-sensitive earnings verification).
- A stronger band engine still needs to be designed; current MA20 + ATR logic is a decent operator baseline, not final commercial-grade technical logic.

## Next Action
- Write the automation architecture spec: what runs on schedule, what stays human-gated, what artifacts are authoritative, and what trust conditions must be met before more autonomy is allowed.

## Key Files
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
- Phase 1: stable scheduled artifact generation
- Phase 2: stable review surfaces and sync checklists
- Phase 3: gated patch/apply helpers for narrow note sections
- Phase 4: broader autonomous maintenance only where trust is demonstrably high
