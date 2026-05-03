# E17 Universe Synchronization

## Objective
- Eliminate the mismatch between the current E17 thesis universe, trigger-sheet outputs, dashboard action cards, and workbook exports.
- Preserve the E17 names already deemed important for the current thesis.
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

## Outstanding
- Define formal universe semantics:
  - E17 thesis universe
  - execution-board universe
  - extended research-watch universe
- Decide the canonical meaning of the current E17 names that are tracked and banded but not shown on execution surfaces.
- Replace boolean gating with a normalized lane/entitlement model.
- Build a consistency gate for ticker-set parity across config, technical, trigger, dashboard, and workbook surfaces.
- Fix earnings-block semantics so distant earnings do not force false blocked states.
- Reconcile stale trigger-sheet note language with the current machine board.
- Decide how the broader Watchlist.md universe should relate to the narrower E17 machine universe.

## Blockers / Trust Gaps
- Current config semantics are ambiguous because multiple booleans can disagree.
- Current dashboard/workbook surfaces do not distinguish between intentionally non-execution names and accidentally missing names.
- Trigger-sheet note ownership is stale relative to machine outputs.
- Earnings blocking logic is over-broad and contaminates execution states.
- No chain-level universe consistency gate exists yet.

## Next Action
- Phase 0 decision pass: define the three universe layers explicitly and decide how each E17 name should map into execution, watch, macro, or speculative lanes before making script changes.

## Key Files
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

## Phase Approach

### Phase 0 — Universe semantics decision
Goal:
- define three layers cleanly

Deliverables:
- E17 thesis universe definition
- execution-board entitlement definition
- extended watch universe definition
- decision on how `CVX`, `PLTR`, `KTOS`, and `SLV` should surface

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

### Phase 4 — Note and surface reconciliation
Goal:
- restore coherence between canonical notes and machine surfaces

Deliverables:
- trigger-sheet note refresh policy
- watchlist semantics clarification
- explicit watch/macro/speculative surface treatment in dashboard/workbook outputs

### Phase 5 — Publication hardening
Goal:
- only publish surfaces that honor the universe contract

Deliverables:
- command center universe counts
- workbook lane/entitlement fields
- consistency-aware publication downgrade rules
