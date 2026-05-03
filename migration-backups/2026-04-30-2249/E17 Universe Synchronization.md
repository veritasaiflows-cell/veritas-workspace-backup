# E17 Universe Synchronization

## Objective
- Eliminate the mismatch between the current thesis universe, trigger-sheet outputs, dashboard action cards, and workbook exports.
- Preserve coherence first; do not assume the current E17 must remain permanently fixed if the Phase 0 decision proves a broader machine-tracked universe is the cleaner truth.
- Make universe membership and surface entitlement explicit instead of relying on drifting booleans.

## Current State
- `tmp/portfolio-config.json` currently defines a **17-name** tracked machine universe and a matching 17-name entry-band set.
- Only **13** names currently flow into `technical-refresh.json` and `trigger-sheet.json` because `include_in_technical_refresh` and `include_in_trigger_sheet` are narrower than the tracked E17.
- Dashboard action cards and `tmp/workbook-watchlist-board.csv` therefore reflect 13 names, not the full E17.
- Some E17 names outside the 13 still appear in validator and band-drift surfaces, which creates operator confusion.
- `02. Markets/Watchlist.md` is broader than the E17 machine universe and includes names such as AMD, LNG, TLT, and SMCI.
- `03. Portfolio/Deployment Trigger Sheet.md` is materially stale relative to the current machine outputs.

## Last Meaningful Progress
- Reviewed the gap note at `08. Audits/Ticket Mismatch in scripts, dashboard and notes.txt`.
- Confirmed the true machine universe counts live:
  - tracked universe: 17
  - entry bands: 17
  - technical-refresh coverage: 13
  - trigger-sheet coverage: 13
- Confirmed the E17 currently include `CVX`, `PLTR`, `KTOS`, and `SLV`; they are not missing from config, they are being filtered downstream.
- Wrote `08. Audits/E17 Universe Synchronization Review - 2026-04-30.md` to capture the real assessment, correction to the reviewed gap note, and phased remediation direction.
- Randall kicked off independent-contractor execution on 2026-04-30. Claude is the current IC for this project and is expected to work in explicit phases rather than one-shot sweeping rewrites.

## Outstanding
- Define formal universe semantics:
  - current thesis universe
  - execution-board universe
  - extended research-watch universe
- Decide whether the current machine-tracked universe should remain E17 or expand cleanly (for example if names like TLT, AMD, or LNG belong in a defined macro or watch lane).
- Decide the canonical meaning of the currently tracked and banded names that are not shown on execution surfaces.
- Replace boolean gating with a normalized lane/entitlement model.
- Build a consistency gate for ticker-set parity across config, technical, trigger, dashboard, and workbook surfaces.
- Fix earnings-block semantics so distant earnings do not force false blocked states.
- Run a separate macro/policy trust-repair track so the chain is not left in permanent degraded mode from the CME/manual fallback path.
- Reconcile stale trigger-sheet note language with the current machine board.
- Decide how the broader Watchlist.md universe should relate to the narrower current machine universe.

## Blockers / Trust Gaps
- Current config semantics are ambiguous because multiple booleans can disagree.
- Current dashboard/workbook surfaces do not distinguish between intentionally non-execution names and accidentally missing names.
- Trigger-sheet note ownership is stale relative to machine outputs.
- Earnings blocking logic is over-broad and contaminates execution states.
- No chain-level universe consistency gate exists yet.

## Next Action
- Operator review of `06. Playbooks/Project Continuity/E17 Universe Synchronization - Phase 0 Decision.md`. Decisions D1–D6 must be recorded inline before Phase 1 sub-pass 2 ships the downstream-script conversions and the universe expansion (AMD/LNG/TLT/SMCI add, CVX disposition).
- Phase 1 sub-pass 1 has landed (resolver + schema migration + contract tests, all backward-compatible). See `Phase 1 Progress` section below.

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

## Phase 1 Sub-Pass 2b — pending operator acknowledgment
- Convert `technical_refresh.py` and `entry_band_fetch.py` to consume `universe.is_entitled(..., "technical_refresh")`.
- Operator-visible effect: `tmp/technical-refresh.json` will grow from 13 to 17 records. Action cards remain limited to execution lane via downstream entitlement (no UI regression on action cards). Dashboard "Technical Posture" panel will surface the four watch/macro/speculative names as expected per Phase 0 Table 2.
- This expansion is an *intentional* implication of the lane model, not a smuggle of D2 or D3. D2 still gates whether AMD/LNG/TLT/SMCI enter the universe at all. D3 still gates CVX disposition.
- Recommended sequencing: operator confirms surface expansion is acceptable → land sub-pass 2b → run full chain dry-run → snapshot dashboard delta vs. last-good.

## Phase 1 Sub-Pass 3 — pending sub-pass 2b completion
- Remove the legacy fallback in `universe.resolve_lane()` once every script consumes `coverage_lane` directly.
- Delete `include_in_technical_refresh`, `include_in_trigger_sheet`, `include_in_post_earnings` from each `tracked_universe` entry. (`include_in_post_earnings` is already dead — no script reads it.)
- Apply operator decisions D2 (universe expansion) and D3 (CVX disposition) once recorded in the Phase 0 deliverable.

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
- Current IC: Claude.
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
