# Operational Readiness Sprint - 2026-04-23

## Sprint objective

Close the latency and sequencing gaps between live catalysts, note updates, and next-session execution surfaces so the finance workspace can move from event to interpretation to readiness without ad hoc chat rescue work.

## Why this sprint exists

The hardening sprint fixed governance drift. The remaining gaps are operational:
- `05. Intelligence/Event Calendar.md` still pointed to a post-LMT refresh as due, which is a freshness lag after a live catalyst.
- `01. Dashboards/Daily Executive Summary/2026-04-23.md` gave the right directional read, but tomorrow-readiness still depended too much on manual reconstruction.
- `scripts/run_finance_refresh_chain.py` produces core artifacts, but it does not yet encode a full close-to-next-session operating loop or explicit validation step.

## Phase map

| Phase | Name | Purpose | Exit condition |
|---|---|---|---|
| 0 | Sprint control note | Define scope, sequence, and acceptance gates | This note reflects the full phase map and tracked readiness items |
| 1 | Post-earnings closure audit | Map the current prepare, report, interpret, sync flow and identify closure gaps | Closure states and missing handoffs are explicit |
| 2 | Event-calendar freshness repair | Define how live catalysts clear or roll forward in the calendar | Elapsed critical events no longer linger as upcoming |
| 3 | Daily execution readiness surface | Decide the durable next-session readiness surface and required fields | Tomorrow-readiness can be read from one governed surface |
| 4 | Chain timing and workflow split | Redesign the refresh chain around real operating windows | Morning, post-close, and post-earnings timing model is explicit |
| 5 | Cron sequencing | Align scheduled jobs with decision windows | Automation timing matches actual use |
| 6 | Readiness validation | Add or place validator checks inside the operating loop | Stale, partial, or unsynced states are surfaced automatically |
| 7 | Integrated dry run | Run the updated sequence against a realistic catalyst path | End-to-end flow works without manual patching |
| 8 | Final acceptance | Confirm all sprint outcomes and record residual risks | Acceptance pass is written and unresolved items are explicitly listed |

## Tracked readiness items

### 1. Post-earnings closure workflow
- **Status:** resolved
- **Scope:** Define what counts as done after a tracked earnings event, from prep through interpretation and note sync.
- **Affected files/surfaces:** `scripts/post_earnings_prep.py`, `scripts/post_earnings_note_targets.py`, `scripts/prompts/post_earnings_vault_update_v1.md`, `05. Intelligence/Event Calendar.md`, related note targets, daily execution surfaces.
- **Closure-state model adopted:**
  - **Prepared** — pre-event packet exists and blocker posture is visible
  - **Reported, evidence pending** — event happened but result interpretation is still incomplete
  - **Interpreted** — the note layer contains what happened / what it means / what we do now
  - **Synced** — required note targets were selectively updated and the calendar no longer treats the event as upcoming
  - **Closed with follow-up** — interpretation and sync are done, but a real next dependency remains explicit
- **Current workflow audit:**
  - The machine side is real through prep and selective targeting, but the closure handoff is not explicit enough once a report lands.
  - `post_earnings_prep.py` still depends on `earnings-calendar.json` date freshness, so a just-reported name can remain staged as pre-event if the calendar is stale or unresolved.
  - `post_earnings_note_targets.py` narrows candidate files well, but it does not encode whether the selective note pass actually happened.
  - Daily executive summaries can carry the interpretation before canonical files are fully synced, which creates a half-updated state.
  - `05. Intelligence/Event Calendar.md` had freshness guidance, but it did not yet carry an explicit closure-state rule for reported events.
- **Required handoffs now made explicit:**
  - prep packet creation
  - selective target map creation
  - agent interpretation pass
  - selective note sync
  - explicit closure or closed-with-follow-up marking
- **Likely failure points:**
  - stale or mismatched earnings-date inputs keep a reported event looking upcoming
  - empty interpretation slots after the event
  - candidate note targets exist but the note pass never happens
  - daily card reflects the report while canonical notes remain stale
  - remaining follow-up dependency is real but not written down
- **Acceptance criteria:**
  - Each tracked earnings event can be labeled prepared, reported with evidence pending, interpreted, synced, or closed with follow-up.
  - Major portfolio or top-watchlist earnings no longer sit in a half-updated state.
  - The note layer makes the post-earnings closure state visible.

### 2. Event-calendar freshness after live catalysts
- **Status:** resolved
- **Scope:** Make elapsed critical catalysts clear or convert promptly after they occur, especially portfolio-company earnings.
- **Affected files/surfaces:** `05. Intelligence/Event Calendar.md`, `tmp/earnings-calendar.json`, post-earnings workflow outputs.
- **Changes made in Phase 2:**
  - Cleared the stale LMT upcoming framing and replaced it with an explicit post-event closure state.
  - Rewrote the refresh trigger language so it points to the next material closure-state or timing change instead of a catalyst that already elapsed.
  - Linked event-calendar maintenance directly to the Phase 1 post-earnings closure workflow so reported names must advance through visible states instead of lingering as pseudo-upcoming items.
  - Preserved the explicit treatment of unconfirmed future date changes such as ETN, NVDA, and BRK.B instead of flattening them into false certainty.
- **Acceptance criteria:**
  - Critical events do not remain listed as upcoming after they have already happened.
  - "Next refresh due" language stays current after material catalysts.
  - Calendar maintenance is explicitly linked to the post-earnings closure process.

### 3. Daily execution readiness surface
- **Status:** resolved
- **Scope:** Establish the durable surface for next-session deployability, blocked names, trigger lines, no-chase lines, and degradation state.
- **Affected files/surfaces:** `01. Dashboards/Daily Executive Summary/2026-04-23.md`, `06. Playbooks/Operating Model.md`, dashboard-facing summaries.
- **Decision adopted in Phase 3:** tighten the existing `Daily Executive Summary` into the governed next-session execution-readiness surface rather than creating a new note layer.
- **Why this surface won:** it was already the closest derived daily surface, it naturally sits below the weekly map and trigger sheet, and upgrading it avoids adding another readiness note that would compete with the same inputs.
- **Fields now made explicit in the daily surface:**
  - deployable now
  - closest actionable / conditional names
  - blocked names
  - no-chase / do-not-touch names
  - trigger and invalidation lines
  - freshness state of the machine artifacts feeding the board
  - trust and degradation warnings that limit confidence
  - one-line readiness verdict for the next session
- **Duplication deliberately avoided:** no new standalone readiness dashboard, no extra portfolio-state note, and no attempt to duplicate the full trigger-sheet or portfolio-snapshot detail inside the daily card.
- **Acceptance criteria:**
  - Tomorrow's actionable posture can be read quickly from one durable surface.
  - Actionable, blocked, conditional, no-chase, and degraded states are explicit.
  - Next-session readiness no longer requires reconstruction across multiple notes and chat turns.

### 4. Chain timing / workflow split
- **Status:** resolved
- **Scope:** Split or restructure refresh flows so artifact generation matches actual operating windows instead of one generic pass.
- **Affected files/surfaces:** `scripts/run_finance_refresh_chain.py`, `scripts/README.md`, `06. Playbooks/Operating Model.md`, `05. Intelligence/Event Calendar.md`, validator placement.
- **Timing model adopted:**
  - **Morning readiness** = `python scripts/run_finance_refresh_chain.py morning`
    - order: market state -> technical -> deployment -> trigger sheet -> dashboard -> validator
    - use when the goal is session readiness, not rebuilding every catalyst workflow
  - **Post-close refresh** = `python scripts/run_finance_refresh_chain.py post-close`
    - order: earnings calendar -> market state -> technical -> deployment -> trigger sheet -> post-earnings prep -> post-earnings note targets -> dashboard -> validator
    - use as the default close-to-next-session rebuild
  - **Post-earnings refresh** = `python scripts/run_finance_refresh_chain.py post-earnings`
    - order: earnings calendar -> post-earnings prep -> post-earnings note targets -> dashboard -> validator
    - use as the event-driven closure path after a material report lands when the close-level board already exists
  - **Compatibility rule:** `full` remains as an alias for `post-close` so the older convenience call still works.
- **Why this resolves the phase:**
  - the workflow now explicitly distinguishes the three real operating windows
  - the earnings-date layer now refreshes before trigger logic in the close and post-earnings paths
  - post-earnings prep and selective targeting are now built into the close workflow instead of being left to memory
  - the convenience runner is no longer a single generic pass with implicit timing assumptions
- **Acceptance criteria:**
  - The workflow explicitly distinguishes morning readiness, post-close refresh, and post-earnings refresh when needed.
  - Script order matches real decision use.
  - Required post-earnings and calendar steps are not left to memory or ad hoc chat prompting.

### 5. Cron sequencing
- **Status:** resolved
- **Scope:** Align scheduled automation with close, post-earnings, and next-morning decision windows.
- **Affected files/surfaces:** cron/task scheduler definitions, refresh entrypoints, downstream notes and generated artifacts.
- **Current audit finding:** the timing map is substantially improved, but cron prompt text still restates long multi-script chains that now duplicate the orchestration logic already encoded in `scripts/run_finance_refresh_chain.py`. That increases maintenance cost and raises the chance that prompt text drifts from the actual supported runner.
- **Upgrade direction now adopted:** move recurring cron workflows toward runner-first orchestration where possible, keeping only note-specific interpretation instructions in prompt text.
- **Acceptance criteria:**
  - Recurring jobs land when the outputs are actually decision-useful.
  - The system relies less on manual prompts after major events.
  - Sequence dependencies are explicit so downstream steps do not run on stale upstream state.
  - Cron prompts do not duplicate full refresh-chain logic when the runner already owns it.

### 6. Readiness validation
- **Status:** resolved
- **Scope:** Make freshness, completeness, and contradiction checks part of the operating loop rather than a separate afterthought.
- **Affected files/surfaces:** `scripts/validate_dashboard_state.py`, `scripts/run_finance_refresh_chain.py`, `scripts/README.md`, `06. Playbooks/Operating Model.md`, dashboard validation outputs, readiness-facing notes and generated surfaces.
- **Validation placement decision:** keep `generate_dashboard.py` responsible for emitting the inline validation payload used by the dashboard, but make `python scripts/validate_dashboard_state.py --write` the final independent closure gate at the end of each operating-window chain.
- **Why this resolves the phase:**
  - validation now runs after the material refresh work, not as an optional extra step off to the side
  - the final trust gate is explicit in morning, post-close, and post-earnings flows
  - readiness surfaces are less likely to be treated as clean execution truth when dependencies are stale, partial, manual, or unconfirmed
- **Acceptance criteria:**
  - Validation runs at the right point in the workflow after material updates.
  - Partial, stale, manual, or unsynced states are surfaced clearly.
  - Readiness surfaces do not imply clean execution truth when dependencies are degraded.

### 7. Final acceptance
- **Status:** resolved
- **Scope:** Confirm the sprint solved the operational gaps without re-opening unrelated hardening work.
- **Affected files/surfaces:** this sprint note, final acceptance write-up, any residual-risk note produced at sprint close.
- **Acceptance criteria:**
  - A major earnings event can move cleanly from report to interpretation to synced readiness.
  - The event calendar stays current after live catalysts.
  - The next-session execution surface is durable and decision-useful.
  - Timing, cron sequencing, and validation operate as one coherent loop.
  - Any remaining manual dependencies are explicit rather than hidden.

## Phase status snapshot

| Phase | Status |
|---|---|
| 0. Sprint control note | resolved |
| 1. Post-earnings closure audit | resolved |
| 2. Event-calendar freshness repair | resolved |
| 3. Daily execution readiness surface | resolved |
| 4. Chain timing and workflow split | resolved |
| 5. Cron sequencing | resolved |
| 6. Readiness validation | resolved |
| 7. Integrated dry run | resolved |
| 8. Final acceptance | resolved |

## Integrated dry run

- **Status:** resolved
- **What was exercised:** the runner-first timing model, downstream note-boundary cleanup, and the validation gate were rechecked after the note and cron cleanup pass.
- **Observed outcome:** the workflow now lands in the expected state without needing prompt-level reconstruction of multi-step script chains.
- **Validation result:** `python scripts/validate_dashboard_state.py --write` completed with **0 critical** and **2 warning** conditions, both already-known external/manual dependencies rather than new internal sequencing failures.
- **Interpretation:** the operating loop is now coherent enough for regular use, but still correctly degraded by unresolved macro-manual fields and timing-sensitive earnings dates.

## Final acceptance

The operational sprint is complete.

### Acceptance outcome
- Morning, post-close, and post-earnings runner paths are now the default operating model.
- Recurring cron jobs now point to the supported runner entrypoints instead of duplicating full script chains in prompt text.
- The dashboard and note surfaces now better respect role boundaries, reducing contradiction risk across the weekly map, daily readiness layer, portfolio posture, and deployment logic.
- Post-earnings and timing-sensitive states are reflected more honestly in the live note layer, especially for LMT and the still-unconfirmed earnings-date set.
- Validation remains part of the operating loop and continues to surface degraded trust when external/manual dependencies remain unresolved.
- Follow-on architecture tightening completed on 2026-04-24:
  - `tmp/portfolio-config.json` now governs tracked-universe policy, coverage tiers, workflow semantics, and entry-band metadata for the machine layer.
  - `scripts/technical_refresh.py` now reads tracked names and band semantics from config instead of hardcoded local maps.
  - `scripts/trigger_sheet_refresh.py` now reads trigger semantics, workflow state, and entry-band metadata from config instead of local static truth.
  - Daily technical coverage expanded cleanly to include `RTX`, `CAT`, and `GS`, while `CVX`, `PLTR`, `KTOS`, and `SLV` remain explicitly tiered outside the daily deployment board.
  - Validator and dashboard acceptance still passed after the refactor, with no new critical issues introduced.

### Residual risks that remain open
- `macro_manual_dependency` still persists until Fed target maintenance and FedWatch sourcing are improved.
- `timing_sensitive_earnings_dates` still persists for names like LMT, NVDA, and BRK.B until directly confirmed or reconciled cleanly in the note layer.
- The tracked technical surface now has daily weekday ownership, but it still depends on disciplined note updates rather than automatic note rewriting.
- The system is now operationally tighter, but it is not allowed to pretend those external uncertainties are solved.

## Out of scope for phase 0

- No reopening of workspace hardening unless a new operational change exposes a real trust failure.
- No new dashboards used as a substitute for fixing timing and workflow gaps.
