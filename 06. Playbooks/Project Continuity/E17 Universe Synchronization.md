# E17 Universe Synchronization

## Objective
- Eliminate the mismatch between the current thesis universe, trigger-sheet outputs, dashboard action cards, and workbook exports.
- Preserve coherence first; do not assume the current E17 must remain permanently fixed if the Phase 0 decision proves a broader machine-tracked universe is the cleaner truth.
- Make universe membership and surface entitlement explicit instead of relying on drifting booleans.

## Current State
- `tmp/portfolio-config.json` now defines a **21-name** tracked machine universe under explicit `coverage_lane` semantics.
- Lane split after Phase 2 completion:
  - execution: 13
  - watch: 4 (`AMD`, `LNG`, `CVX`, `PLTR`)
  - macro: 2 (`TLT`, `SLV`)
  - speculative: 2 (`SMCI`, `KTOS`)
- `scripts/universe.py` is now the single entitlement authority and no longer falls back to legacy `include_in_*` booleans.
- `scripts/universe_consistency_check.py` is live, wired into the chain, and surfaces drift through `tmp/universe-consistency.json` into validation and dashboard/workbook trust surfaces.
- Dashboard and workbook surfaces now display universe consistency state and lane counts explicitly instead of implying health silently.
- The broad note-layer drift is narrower than it was: `Watchlist.md` now truthfully acts as the machine-tracked index, and `Coverage Universe.md` now explicitly declares itself a thesis-ownership note rather than a deployment-entitlement note.
- The explicit `GOOG` / `MSFT` post-earnings residue is now closed and the `BRK.B` timing mismatch is materially narrowed by Berkshire homepage-level confirmation for May 2. The remaining timing-sensitive residue is now concentrated mainly in `NVDA` direct-date confirmation, while in-band `WATCH` residue for `GS`, `CVX`, and `PLTR` plus non-daily deployment-flow warnings for `AMD`, `CVX`, `LNG`, and `PLTR` still remain visible outside the core E17 ownership fix.

## Last Meaningful Progress
- Reviewed the gap note at `08. Audits/Ticket Mismatch in scripts, dashboard and notes.txt`.
- Confirmed the true machine universe counts live:
  - tracked universe: 17
  - entry bands: 17
  - technical-refresh coverage: 13
  - trigger-sheet coverage: 13
- Confirmed the E17 currently include `CVX`, `PLTR`, `KTOS`, and `SLV`; they are not missing from config, they are being filtered downstream.
- Wrote `08. Audits/E17 Universe Synchronization Review - 2026-04-30.md` to capture the real assessment, correction to the reviewed gap note, and phased remediation direction.
- Randall kicked off independent-contractor execution on 2026-04-30. The implementation-heavy contractor phases are complete enough that the project is now back in Veritas-controlled reconciliation and interpretation work.
- Narrowed the note/control-surface residue on 2026-05-02 by clarifying the machine-tracked versus thesis-ownership boundary, explicitly marking `GOOG`/`MSFT` technical copy as pre-print residue, and removing the need to treat watch-lane names as if they belonged to the execution board.
- Closed the explicit `GOOG` / `MSFT` post-earnings blocker on 2026-05-02 (later) by writing canonical scorecards, selectively syncing the owner notes, and directly confirming both Apr 29 report dates via SEC 8-K filings. `BRK.B` timing also improved from an unconfirmed likely change to homepage-level confirmed May 2 timing.

## Outstanding
- Direct-confirm the remaining timing-sensitive earnings dates that still matter to trust, led by `NVDA`.
- Keep trigger-sheet and watchlist language aligned with the repaired machine state as the next catalyst cluster lands.
- Run a separate macro/policy trust-repair track so the chain is not left in permanent degraded mode from the CME/manual fallback path.
- Decide later whether `CAT`, `CVX`, and `SMCI` need full thesis blocks here or should remain outside this note until the coverage-tier framework workstream.

## Blockers / Trust Gaps
- `NVDA` still lacks a clean direct earnings-date confirmation path; May 20 remains a likely but not primary-confirmed date.
- Non-daily deployment-flow warnings remain live for `AMD`, `CVX`, `LNG`, and `PLTR`.
- In-band `WATCH` residue remains live for `GS`, `CVX`, and `PLTR`.
- Macro/policy degraded trust remains an independent rot vector even after lane and consistency cleanup.

## Next Action
- Treat the core E17 synchronization work as closure-ready; the remaining blocker stack now belongs mainly to the broader trust-grade gate rather than universe-ownership drift.
- Keep `03. Portfolio/Deployment Trigger Sheet.md` and `02. Markets/Watchlist.md` synchronized through the next catalyst cluster while the residual warning stack is reduced.
- Use the chain log at `06. Playbooks/Project Continuity/E17 Universe Synchronization - Chain Log.md` as the pass-by-pass execution ledger.

## Phase 1 Progress (sub-pass 1 — 2026-04-30)
- `scripts/universe.py` — single resolver. Lanes: execution / watch / macro / speculative. Reads `coverage_lane` field; falls back to legacy booleans only when the field is absent. Defines a closed entitlement matrix (`technical_refresh`, `trigger_sheet`, `action_card`, `band_drift`, `earnings_calendar`, `deployment_ranking`).
- `scripts/test_universe.py` — 8 contract test suites, all passing. Critical contract: only execution-lane names can ever be action-card eligible (`test_action_cards_only_execution`).
- `tmp/portfolio-config.json` — `coverage_lane` field added to all 17 existing `tracked_universe` entries per the Phase 0 proposal. Legacy `include_in_*` booleans retained intentionally for backward compatibility until each downstream script is converted in sub-pass 2. Schema version stamped (`schema_version.coverage_lane = "phase1.0"`).
- `migration-backups/portfolio-config.pre-phase1.json` — pre-migration backup.
- Live lane resolution: execution=13 (unchanged), watch=2 (CVX, PLTR), macro=1 (SLV), speculative=1 (KTOS). Universe expansion (AMD/LNG/TLT/SMCI add) and CVX disposition deferred to sub-pass 2 pending operator D2/D3 decisions.

## Phase 1 Sub-Pass 2a — landed (2026-04-30)
- `scripts/trigger_sheet_refresh.py` converted to consume `universe.is_entitled(..., "trigger_sheet")`. Behavior is bit-preserving: 13 records out, identical bucket distribution, identical warnings vs. pre-conversion.
- Live verification: `python scripts/trigger_sheet_refresh.py` produced the same 13-record output. `python scripts/test_universe.py` continues to pass 8/8 suites.
- Audit of remaining gating sites (no other script alters universe selection on its own — the rest inherit from upstream JSON):
  - `scripts/technical_refresh.py:65,81` — `include_in_technical_refresh` gate. **Conversion deferred to sub-pass 2b** because flipping it to `is_entitled(..., "technical_refresh")` expands the fetched universe from 13 to 17 (adds CVX, PLTR, KTOS, SLV) by lane design, which is an operator-visible surface change.
  - `scripts/entry_band_fetch.py:316` — same `include_in_technical_refresh` gate, same surface implication. Convert alongside technical_refresh.
  - `scripts/deployment_check.py`, `scripts/dashboard_payload.py`, `scripts/workbook_export.py` — no entitlement decisions; iterate upstream JSON. Do not need rewiring as long as the upstream is the entitlement gate.

## Phase 1 Sub-Pass 2b — landed (2026-04-30)
- `scripts/technical_refresh.py` and `scripts/entry_band_fetch.py` now consume `universe.is_entitled(..., "technical_refresh")` rather than reinterpreting legacy booleans.
- Operator-visible effect landed as intended: `tmp/technical-refresh.json` grew from 13 to 17 records, adding lane-appropriate non-execution names without leaking them into action cards or trigger-sheet execution buckets.
- `entry_band_fetch.py --all-tracked` now scales across the tracked machine universe while still respecting downstream execution boundaries.
- Validation reported the lane model still protecting action-card surfaces correctly.

## Phase 1 Sub-Pass 3 — landed (2026-04-30)
- Operator decisions applied:
  - D2 approved expansion: `AMD -> watch`, `LNG -> watch`, `TLT -> macro`, `SMCI -> speculative`
  - D3 approved retention: `CVX -> watch`
- `tmp/portfolio-config.json` expanded from 17 to 21 names and legacy `include_in_technical_refresh`, `include_in_trigger_sheet`, and `include_in_post_earnings` fields were removed.
- `scripts/universe.py` now enforces `coverage_lane` strictly with no fallback logic.
- `scripts/test_universe.py` was updated and passed after the stricter lane-only model was applied.
- Phase 1 is complete: lane-model unification is now the live source of truth.

## Key Files
- `06. Playbooks/Project Continuity/E17 Universe Synchronization - Phase 0 Decision.md` *(Phase 0 deliverable — proposal pending decision)*
- `08. Audits/Ticket Mismatch in scripts, dashboard and notes.txt`
- `08. Audits/E17 Universe Synchronization Review - 2026-04-30.md`
- `tmp/portfolio-config.json`
- `scripts/technical_refresh.py`
- `scripts/deployment_check.py`
- `scripts/trigger_sheet_refresh.py`
- `scripts/dashboard_payload.py`
- `scripts/workbook_export.py`
- `scripts/run_finance_refresh_chain.py`
- `02. Markets/Watchlist.md`
- `03. Portfolio/Deployment Trigger Sheet.md`

## Automation / Refresh Path
- This project should remain architecture-first at the start.
- Do not patch isolated dashboard symptoms before the universe semantics are decided.
- After the lane model exists, downstream scripts and surfaces should derive from it automatically.
- Consistency validation should become part of the chain before broader scheduling or surface-polish work.

## Independent Contractor Notes
- Current owner posture: Veritas main lane for reconciliation and interpretation; contractor-style implementation phases already advanced the machine stack.
- Expected posture: phased execution, not one-pass cosmetic cleanup.
- Highest-priority standards for IC work:
  - one declared owner per artifact or surface
  - no fake green states
  - no ad hoc ticker hardcoding in dashboard/workbook layers
  - no silent canonical note rewrites
  - no new boolean sprawl when a normalized lane/entitlement model can replace it
  - macro/policy degraded-trust path must be treated as a parallel systems issue, not hidden under universe cleanup
- Preferred Phase 0 deliverable shape:
  1. ticker-lane table
  2. lane-definition / surface-entitlement table
  3. source-owner-reader-cadence table
- Preferred implementation discipline after Phase 0 is approved:
  - trust the approved model
  - implement mechanically against the model
  - do not relitigate semantics inside each script edit unless new evidence forces it

## Phase Approach

### Phase 0 — Universe semantics decision
Goal:
- define three layers cleanly

Deliverables:
- current thesis-universe definition
- decision on whether the coherent machine universe remains E17 or expands
- execution-board entitlement definition
- extended watch universe definition
- decision on how `CVX`, `PLTR`, `KTOS`, and `SLV` should surface
- decision on whether names like `TLT`, `AMD`, and `LNG` belong in the machine universe at a non-execution lane

### Phase 1 — Lane-model unification
Goal:
- replace drifting booleans with one normalized lane/entitlement model

Deliverables:
- updated config semantics
- downstream script entitlement rules
- preserved E17 membership

### Phase 2 — Consistency gate
Goal:
- fail loudly when ticker sets drift

Deliverables:
- ticker-set consistency checker
- chain insertion point before dashboard publication
- visible downgrade behavior when contract breaks

### Phase 3 — Earnings-block repair
Goal:
- stop false blocked states from contaminating execution surfaces

Deliverables:
- explicit earnings-block window logic
- validator alignment
- corrected trigger/dashboard states for long-dated earnings names

### Phase 4 — Note reconciliation
Goal:
- restore coherence between canonical notes and the machine board without taking unsafe write shortcuts

Deliverables:
- trigger-sheet note refresh policy
- watchlist semantics clarification
- technical-note sync remains gated and dry-run-first

### Phase 5 — Surface reconciliation
Goal:
- restore coherence between dashboard/workbook surfaces and the defined universe lanes

Deliverables:
- explicit watch/macro/speculative surface treatment in dashboard/workbook outputs
- execution-only action-card entitlement
- visible non-execution tracked names where appropriate

### Phase 5.5 — Macro/policy trust repair
Goal:
- stop the workflow from living in permanent degraded trust because policy sourcing is stuck in fallback/manual mode

Deliverables:
- trustworthy source-path decision or formal manual TTL policy
- honest but non-pathological downgrade behavior
- updated presentation-eligibility logic once the policy trust contract is cleaner

### Phase 6 — Publication hardening
Goal:
- only publish surfaces that honor the universe contract

Deliverables:
- command center universe counts
- workbook lane/entitlement fields
- consistency-aware publication downgrade rules
