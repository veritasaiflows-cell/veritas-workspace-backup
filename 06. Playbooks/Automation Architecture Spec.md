# Automation Architecture Spec

## Purpose

Define the first real architecture for scheduled and semi-automated Veritas OS operation.

This spec is not trying to maximize automation.
It is trying to make automation trustworthy, legible, and easy to expand later.

## Core principle

Automation should progress in this order:
1. generate fresh artifacts
2. generate useful review surfaces
3. provide gated apply helpers
4. expand autonomous maintenance only where trust is repeatedly proven

Do not skip steps.

## Current operating phases

### Phase 1 — Stable scheduled artifact generation
Allowed now.

### Phase 2 — Stable review surfaces and sync checklists
Allowed now.

### Phase 3 — Gated patch/apply helpers for narrow note sections
Allowed selectively when the mutation boundary is narrow and validation is clear.

### Phase 4 — Broader autonomous maintenance
Not yet allowed as a default posture.

## Authority model

### Canonical note layer
Human-readable notes remain canonical for judgment, interpretation, and final operating guidance.

Examples:
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Earnings/`
- `05. Intelligence/Weekly Positioning Review.md`

### Machine-readable config and artifact layer
Scripts may produce and maintain structured artifacts and machine-readable config used for workflow acceleration.

Examples:
- `tmp/portfolio-config.json`
- `tmp/technical-refresh.json`
- `tmp/trigger-sheet.json`
- `tmp/positioning-ranking.json`
- `tmp/band-proposals.json`

### Presentation layer
Workbook, dashboard, and PDF outputs are operator surfaces and presentation surfaces, not canonical judgment.

Examples:
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- `tmp/veritas-command-center.html`
- PDF products built from the note layer

## Workflow ownership by window

### Morning window
Owner:
- `scripts/run_finance_refresh_chain.py morning`

Job:
- pre-open readiness refresh
- rebuild macro, technical, regime, band-supporting, dashboard, and workbook export artifacts

Safe outputs:
- generated artifacts
- review surfaces
- status/checklist surfaces

Not safe yet:
- silent canonical note rewrites

### Post-close window
Owner:
- `scripts/run_finance_refresh_chain.py post-close`

Job:
- end-of-day refresh
- earnings timing refresh
- post-earnings prep staging
- dashboard/workbook refresh

Safe outputs:
- generated artifacts
- selective post-earnings prep packets
- review surfaces

Not safe yet:
- autonomous interpretation notes
- silent trigger-sheet doctrine changes in note layer

### Post-earnings window
Owner:
- `scripts/run_finance_refresh_chain.py post-earnings`

Job:
- event-driven packet refresh and selective sync preparation

Safe outputs:
- prep artifacts
- candidate note-target surfaces

Not safe yet:
- autonomous scorecard conclusions
- autonomous downstream note mutation without approval

### Sunday window
Owner:
- `scripts/run_finance_refresh_chain.py sunday`

Job:
- weekly rebuild
- macro/positioning/intelligence prep
- workbook/dashboard refresh

Safe outputs:
- refreshed artifacts
- weekly prep surfaces

Not safe yet:
- autonomous final weekly judgment note without review

## Schedule recommendation v1

Time zone for all live and planned schedules:
- `America/Phoenix`

### Concrete v1 cron candidates

#### 1. Weekday pre-open readiness
- Live schedule: Monday-Friday at **06:05 America/Phoenix**
- Owner: `scripts/run_finance_refresh_chain.py morning`
- Purpose: finish before the first serious market-prep session while leaving time for rerun/debug if a source fails
- Primary outputs in radar:
  - `tmp/veritas-command-center.html`
  - `tmp/dashboard-validation.json`
  - `tmp/technical-refresh.json`
  - `tmp/trigger-sheet.json`
  - `tmp/positioning-ranking.json`
  - workbook CSV export surfaces
  - `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`

#### 2. Weekday post-close rebuild
- Live schedule: Monday-Friday at **13:20 America/Phoenix**
- Owner: `scripts/run_finance_refresh_chain.py post-close`
- Purpose: allow market close to settle, then refresh earnings timing, dashboard, command center, workbook exports, and post-close intelligence surfaces
- Primary outputs in radar:
  - `tmp/veritas-command-center.html`
  - `tmp/post-earnings-prep.json`
  - `tmp/post-earnings-note-targets.json`
  - workbook CSV export surfaces
  - `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`
  - `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`

#### 3. Weekly Sunday rebuild
- Live schedule: Sunday at **08:00 America/Phoenix**
- Owner: `scripts/run_finance_refresh_chain.py sunday`
- Purpose: complete the weekly intelligence rebuild before the main review block, without pushing into late Sunday crunch
- Primary outputs in radar:
  - `tmp/veritas-command-center.html`
  - `tmp/weekly-macro-snapshot.json`
  - `tmp/weekly-intelligence-brief.json`
  - workbook CSV export surfaces
  - refreshed weekly dashboard and intelligence staging notes

#### 4. Daily day-job orchestrator
- Live schedule: Daily at **19:45 America/Phoenix**
- Owner: Veritas control-plane review in the main workspace session
- Purpose: harden queue/registry/continuity synchronization, confirm whether the current workflow is truly complete, choose the next approved queue item, run preflight QA/review first when the next project is major, route work by effort level, and spawn at most one secure detached subagent worker when the protocol says the task is automation-ready
- Governing references:
  - `06. Playbooks/Continuity Stewardship Protocol.md`
  - `06. Playbooks/Cron Job Protocol.md`
- Primary outputs in radar:
  - `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
  - `06. Playbooks/IC Project Registry.md`
  - `06. Playbooks/Continuity Stewardship Protocol.md`
  - relevant `06. Playbooks/Project Continuity/*.md`
  - `memory/YYYY-MM-DD.md`

#### 5. Weekly continuity hygiene pass
- Live schedule: Sunday at **18:45 America/Phoenix**
- Owner: Veritas control-plane hygiene review in the main workspace session
- Purpose: run a deeper continuity cleanup pass after the weekly rebuild cadence settles; archive clearly finished control-plane notes when safe; trim stale queue/registry/continuity noise; and check whether the stewardship protocol itself needs tightening
- Primary outputs in radar:
  - `06. Playbooks/Project Continuity/*.md`
  - `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
  - `06. Playbooks/IC Project Registry.md`
- `09. Archive/Project Continuity/`

### Earnings follow-up
Default posture:
- do not create many per-ticker cron jobs yet
- rely on `post-close` and next `morning` first
- add isolated event jobs only when a specific workflow repeatedly proves it deserves one

## Artifact radar: now vs later

### In radar now
- command center / dashboard surface
  - `tmp/veritas-command-center.html`
- workbook export layer
  - `tmp/workbook-*.csv`
- review and sync surfaces
  - dashboard validation
  - band status and note-sync outputs
- intelligence staging notes
  - pre-market, post-market, daily executive, weekly intelligence surfaces

### In radar later, not first-wave scheduled outputs yet
- Excel packaging artifact
  - `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- PDF deliverables
  - e.g. `equity_pdf_report.py` outputs and future weekly/portfolio PDF products

### Policy for future Excel/PDF scheduling
- do not schedule workbook or PDF packaging as first-wave cron owners
- first stabilize the artifact and review layers they depend on
- once stable, prefer packaging after the owning review window, not before it
- likely future candidates:
  - Excel packaging after post-close or Sunday rebuild
  - PDF packaging only after the note layer and validation state are clean enough for presentation

## Safe automation boundary now

Allowed now:
- scheduled artifact generation
- scheduled chart/report generation
- scheduled workbook export generation
- scheduled dashboard generation
- scheduled review/checklist generation
- thin gated apply helpers

Still human-gated:
- canonical note rewrites
- interpretation-heavy note updates
- recommendation-bearing narrative changes
- high-consequence config changes where the rollback path is weak

## Trust gates before wider autonomy

Before expanding autonomy, verify all of the following:
- artifact freshness is explicit
- upstream source conflicts are visible
- one workflow window owns each output
- validation exists and is run after mutation-capable helpers
- canonical note ownership is explicit
- rollback or correction path is simple
- automation does not erase uncertainty language

If any gate is weak, do not widen autonomy.

## Validation expectations by workflow window

Validation is not optional.
Each workflow window needs explicit pass conditions, downgrade behavior, and a stop line.

### Morning window validation

Required checks:
- chain completes without hard failure
- `test_dashboard_acceptance.py` passes
- `validate_dashboard_state.py --write` runs and writes the latest validation artifact
- command center renders successfully
- workbook CSV exports complete
- pre-market snapshot writes successfully if the chain includes it

Minimum pass standard:
- no critical validation failures
- trust state may still be downgraded to warning or `usable_with_caution`, but that downgrade must stay visible
- stale/manual warnings remain allowed only when surfaced explicitly

Stop line:
- do not treat the morning outputs as clean decision support if validation is missing, command center rendering failed, or dashboard acceptance failed

Fallback behavior:
- keep the prior canonical notes untouched
- allow artifact outputs to exist with degraded status
- surface the downgrade instead of suppressing the run

### Post-close window validation

Required checks:
- chain completes without hard failure
- earnings staging artifacts write successfully
- `test_dashboard_acceptance.py` passes
- `validate_dashboard_state.py --write` runs after dashboard generation
- command center renders successfully
- workbook CSV exports complete
- post-market snapshot and daily executive summary write successfully when scheduled in the chain

Minimum pass standard:
- no critical validation failures
- post-earnings prep artifacts may be partial only if partial state is explicit
- next-day catalyst visibility must not be silently omitted

Stop line:
- do not promote the post-close bundle as ready if earnings staging failed, dashboard validation is absent, or generated intelligence notes did not write

Fallback behavior:
- preserve prior canonical notes
- keep candidate note-target surfaces as evidence only
- explicitly retain warning state around earnings timing or policy/manual dependencies

### Post-earnings window validation

Required checks:
- chain completes without hard failure
- `post_earnings_prep.py` writes current prep artifact
- `post_earnings_note_targets.py` writes current candidate targets
- dashboard generation and `validate_dashboard_state.py --write` complete if invoked in the chain
- any downstream sync helper output is clearly labeled as prep or candidate state, not final interpretation

Minimum pass standard:
- candidate targets are generated from current artifacts
- no autonomous interpretation is inserted into canonical scorecards
- ownership of downstream note targets remains explicit

Stop line:
- do not allow autonomous scorecard conclusion writes or downstream note mutation without a separate approval layer

Fallback behavior:
- keep the run as prep-only
- surface missing evidence or unresolved target ambiguity as a blocker, not a silent omission

### Sunday window validation

Required checks:
- chain completes without hard failure
- full weekly artifact rebuild completes
- `test_dashboard_acceptance.py` passes
- `validate_dashboard_state.py --write` runs after dashboard generation
- weekly macro snapshot and weekly intelligence brief staging outputs write successfully
- workbook CSV exports complete

Minimum pass standard:
- no critical validation failures
- weekly outputs may contain judgment placeholders, but those placeholders must remain visible
- weekly prep artifacts must reflect the latest macro/technical/earnings state rather than stale prior-week carryover

Stop line:
- do not treat the weekly prep package as ready for presentation if validation is absent, weekly artifact writes failed, or stale prior-week framing remains in place

Fallback behavior:
- keep generated weekly surfaces as staging only
- do not auto-package into presentation deliverables when trust is degraded

## Sequential plumbing order for automation

Build the plumbing in this order.
Do not start with cron creation.
Start by making each scheduled window trustworthy enough to deserve a cron owner.

### Step 1 — Lock validation contracts per window
- name the required scripts and outputs for `morning`, `post-close`, `post-earnings`, and `sunday`
- define pass, warning, and stop-line states for each window
- define what counts as degraded-but-usable versus blocked

### Step 2 — Add machine-readable run summaries per window
- emit a compact per-window result artifact
- include run time, status, warning count, critical count, stop-line state, fallback state, and key output presence
- keep this separate from canonical notes
- use `06. Playbooks/Automation Run Summary Contract.md` as the contract source of truth

### Step 3 — Normalize failure visibility
- ensure failed or partial runs produce visible status artifacts
- make command center and workbook/export surfaces consume the same trust state instead of inventing separate confidence language
- propagate stop lines, fallback honesty, and missing-required-output states downstream instead of letting rendered HTML or CSV files fake success

### Step 4 — Define cron payload ownership
- map one cron owner to each approved window
- define exact command or entrypoint per window
- define whether each scheduled run belongs in current session, isolated session, or main-session system event follow-up

### Step 5 — Add lightweight run logging and review surfaces
- keep a compact run history or daily operator log for scheduled windows
- make it easy to see which window failed, what artifact was missing, and whether rerun is safe

### Step 6 — Schedule artifact windows only
- create cron jobs for `morning`, `post-close`, and `sunday`
- do not schedule canonical note mutation jobs in v1
- keep `post-earnings` event-driven until repeated need justifies a stable trigger

### Step 7 — Add gated apply helpers selectively
- only after scheduled artifact windows are stable
- start with narrow mutation surfaces where rollback is clear
- keep approval explicit

### Step 8 — Add packaging workflows later
- Excel packaging after workbook export stability is proven
- PDF packaging only after note-layer and validation cleanliness are consistently strong

## Phase approach

### Phase A — Validation-first hardening
Goal:
- make each workflow window measurable and stoppable

Deliverables:
- per-window validation rules
- stop lines
- degraded-state rules
- run-summary contract

### Phase B — Scheduling-safe artifact plumbing
Goal:
- make `morning`, `post-close`, and `sunday` safe to schedule without pretending they can rewrite truth

Deliverables:
- cron owner map
- run logging surface
- visible failure propagation into dashboard/command center/workbook exports

### Phase C — Review-surface hardening
Goal:
- improve operator visibility and decision support from scheduled runs

Deliverables:
- stronger command center status integration
- stable workbook export trust columns
- review checklists for post-earnings and band-sync paths

### Phase D — Narrow gated mutation helpers
Goal:
- allow small, auditable, approval-backed apply flows where the boundary is tight

Deliverables:
- safe apply candidates
- rollback rules
- post-apply validation requirements

### Phase E — Presentation packaging expansion
Goal:
- add Excel and PDF packaging only when upstream trust is boringly reliable

Deliverables:
- workbook packaging cadence
- PDF packaging cadence
- packaging preconditions tied to validation cleanliness

## Band automation policy

### Current status
Current band workflow is in the correct semi-automated phase:
- `technical_refresh.py`
- `band_refresh.py`
- `entry_band_fetch.py --all-tracked --html`
- `generate_entry_band_status.py`
- `apply_band_update.py`
- `band_note_sync.py`

### Current allowed automation
- proposal generation
- review-surface generation
- thin sync-checklist generation
- human-gated application to machine config

### Not yet allowed by default
- silent canonical note rewrites
- auto-approval of proposed bands
- automatic recommendation-state promotion from mechanical bands alone

## Mechanism routing

### Use cron when
- timing matters
- the job is recurring
- the output is artifact generation or review preparation

### Use heartbeat when
- the task is lightweight maintenance only
- no exact schedule is required

### Use TaskFlow when
- the work spans detached tasks but still needs one owner context
- waiting state and resumable state matter

### Keep manual when
- the workflow is interpretation-heavy
- trust is weak
- the mutation surface is too broad

## Immediate next build targets

1. Implement the machine-readable run-summary writer using `06. Playbooks/Automation Run Summary Contract.md`
2. Normalize failure visibility across dashboard, command center, and workbook export surfaces
3. Design the v2 band methodology spec
4. Decide where a gated note patch/apply helper is safe enough to introduce next
5. Turn the concrete schedule candidates into actual cron jobs only after the validation rules, run-summary contract, and failure-propagation rules are agreed

## Non-goals for this phase

- full autonomous portfolio management
- silent narrative rewriting of the note layer
- replacing judgment with formula theater
- scheduling every possible event just because it can be scheduled
