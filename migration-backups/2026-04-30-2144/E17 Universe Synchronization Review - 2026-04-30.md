# E17 Universe Synchronization Review - 2026-04-30

## Purpose

Review the mismatch between watchlist surfaces, trigger-sheet outputs, dashboard action cards, and workbook exports.

The goal is not to add more names casually.
The goal is to make the current **E17** thesis universe flow through the operating system coherently.

## What is true now

### Machine-tracked universe
The current machine-tracked universe in `tmp/portfolio-config.json` is **17 names**:
- `AMZN`
- `BRK.B`
- `CAT`
- `CVX`
- `ETN`
- `GOOG`
- `GS`
- `JPM`
- `KTOS`
- `LMT`
- `MSFT`
- `NVDA`
- `PLTR`
- `RTX`
- `SLV`
- `VRT`
- `XOM`

### Current split
- `tracked_universe` count: **17**
- `entry_bands` count: **17**
- `include_in_technical_refresh == true`: **13**
- `include_in_trigger_sheet == true`: **13**

That is the real split.

## Root issue

The system currently has one thesis universe but multiple execution filters.

In practice that means:
- all 17 names can exist in config and entry bands
- only 13 reach `technical-refresh.json`
- only 13 reach `trigger-sheet.json`
- dashboard action cards and workbook watchlist board therefore only reflect those 13
- validator and band-drift surfaces can still complain about names outside the 13

That creates operator confusion because the system is warning about some names while hiding them from the main operating surfaces.

This is an orchestration and semantics problem, not just a dashboard bug.

## Important correction from the audit review

The reviewed gap note was useful, but one claim was wrong:
- `PLTR`, `KTOS`, and `SLV` are **not** missing from config
- they are already in the tracked E17
- they are being dropped later by gating flags

That matters because the next step is not “add them to config.”
The next step is to decide how they should surface.

## Additional gap: watchlist versus machine universe

`02. Markets/Watchlist.md` currently lists names beyond the E17, including:
- `AMD`
- `LNG`
- `TLT`
- `SMCI`

That is not automatically wrong.
But it means the markdown watchlist is broader than the machine-tracked execution universe.

So the workspace currently has two overlapping concepts:
1. broader human tracking universe
2. narrower machine execution universe

Those need to be named explicitly instead of being left ambiguous.

## Current failure points

### 1. Universe semantics are ambiguous
The config uses multiple booleans:
- `include_in_technical_refresh`
- `include_in_trigger_sheet`
- presence in `entry_bands`

That is brittle.
A name can be “tracked” and “banded” but still disappear from execution surfaces.

### 2. Watchlist note and machine universe are not clearly separated
`Watchlist.md` is a navigation index, but it visually reads like an active universe board.
That makes missing names look like a pipeline bug even when some of them are simply outside the narrower machine universe.

### 3. Trigger sheet note is stale relative to machine outputs
`03. Portfolio/Deployment Trigger Sheet.md` still reflects older states and older blocker logic.
Meanwhile `tmp/trigger-sheet.json` is already surfacing different states such as:
- `GS` deployable now
- `CAT` almost deployable
- `VRT` almost deployable

That mismatch is operationally dangerous.

### 4. Earnings blocking semantics are too blunt
Names such as:
- `AMZN`
- `GOOG`
- `MSFT`
are still blocked by a boolean pre-earnings policy even when the next earnings date is far away.

That is already visible in validation warnings and is contaminating the action-card layer.

### 5. No consistency gate exists before dashboard publication
The chain does not currently fail or downgrade explicitly when ticker sets diverge across:
- config
- technical refresh
- deployment check
- trigger sheet
- workbook surfaces

### 6. Workbook and dashboard are still consuming partial local logic
The new run-summary plumbing now improves workflow-level trust state, but ticker-set consistency is still not enforced across workbook and dashboard surfaces.

## What should happen next

## Phase 0 — Define universe semantics
Decide and document three layers clearly:
- **E17 thesis universe** — the current machine-tracked core/tactical/speculative set that must be preserved
- **execution board universe** — the subset that belongs on trigger-sheet and action-card surfaces
- **extended research watchlist** — broader human-tracked names not yet entitled to execution-board treatment

This is the first decision because otherwise every later script change is guessing.

## Phase 1 — Replace boolean gating with one lane model
In `tmp/portfolio-config.json`, replace the current split-flag logic with one normalized field such as:
- `coverage_lane: execution | watch | macro | speculative`

Then derive downstream behavior from that lane instead of from drifting booleans.

Recommendation:
- keep all **E17** names in the unified machine universe
- allow some names to appear in non-action-card lanes instead of disappearing entirely

## Phase 2 — Add consistency gate to the chain
Build a dedicated script such as:
- `scripts/universe_consistency_check.py`

It should compare, at minimum:
- tracked E17 names
- entry-band names
- technical-refresh names
- trigger-sheet names
- workbook watchlist names

It should fail or downgrade visibly when expected lane membership is violated.

## Phase 3 — Fix earnings-block semantics
Replace boolean `block_pre_earnings` behavior with explicit timing-window logic.

Example direction:
- `earnings_block_days: 7` or `14`

That should clear false blocked states for names months away from earnings.

## Phase 4 — Reconcile canonical notes with machine outputs
Bring note ownership back under control:
- trigger-sheet note refreshed against the new machine board state
- technical note sync stays human-gated
- watchlist note explicitly identifies which names are machine-execution names versus broader research-watch names

## Phase 5 — Surface the full E17 intentionally
Do not silently hide non-execution E17 names.

Recommended dashboard/workbook direction:
- action cards remain execution-only
- add a separate **watch lane / macro lane / speculative lane** surface
- keep names like `CVX`, `PLTR`, `KTOS`, and `SLV` visible as intentional tracked names rather than invisible drift sources

## Phase 6 — Tighten publication rules
After consistency gate and lane model exist:
- dashboard generation should surface universe counts
- workbook export should carry lane and entitlement columns
- publication should downgrade when the universe contract is broken

## Recommendation

The right immediate project is **not** “fix the dashboard cards.”
That is too shallow.

The right project is:
- preserve the **E17** universe
- define explicit universe semantics
- unify lane entitlement across scripts
- then update dashboard and workbook surfaces to reflect those semantics honestly

## Proposed project outcome

At the end of this project, the workspace should support this truth:
- the E17 remain the thesis universe
- execution-only names are clearly entitled to action cards and trigger-sheet status
- broader tracked names are still visible on dashboard/workbook surfaces in the correct lane
- validator and dashboard no longer disagree about what names exist
