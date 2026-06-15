# WF77 Price Row Classification Hardening - 2026-05-30

## Bottom Line

WF75/WF77 remains `completed_with_warning`, but the warning is now precise.

The four unavailable price rows are no longer treated as unexplained missing data:

- `KTOS` - `coverage_lane=speculative` is not entitled to `technical_refresh`
- `SLV` - `coverage_lane=macro` is not entitled to `technical_refresh`
- `SMCI` - `coverage_lane=speculative` is not entitled to `technical_refresh`
- `TLT` - `coverage_lane=macro` is not entitled to `technical_refresh`

This preserves the current portfolio technical-refresh contract instead of widening macro/speculative lanes into downstream portfolio/deployment surfaces.

## Implementation

- Updated `scripts/wf77_price_freshness_bridge.py`:
  - added `row_count`
  - added `valid_price_row_count`
  - added `invalid_price_row_count`
  - changed `price_rows` to the valid-row compatibility count
  - added `price_rows_definition`
  - added `excluded_price_rows`
  - added `price_unavailable_rows`
  - added `price_unavailable_details`
  - added per-row `technical_refresh_entitlement`
- Updated `scripts/wf75_service_state.py` so excluded rows remain warning-level blockers/handoffs.
- Added `scripts/test_wf77_price_freshness_bridge.py`.
- Expanded `scripts/test_wf75_service_state.py` to assert WF77 row-count fields and excluded-row capture.
- Updated operator, workflow-review, PM, continuity, active-workflow, daily-memory, and overnight-plan surfaces to avoid stale "unexplained missing" wording.

## Current Proof

- `tmp/wf77-price-freshness-bridge.json`
  - `row_count`: 42
  - `valid_price_row_count`: 38
  - `missing_price_rows`: none
  - `excluded_price_rows`: `KTOS`, `SLV`, `SMCI`, `TLT`
- `tmp/wf75-service-state-current.json`
  - validation status: `ok`
  - warning: `excluded_price_rows`
- `tmp/wf75-operator-queue.json`
  - validation status: `ok`
  - heartbeat may queue review, not execute phases

## Boundary

No portfolio/canon mutation, SQL/ticker import, customer data, external delivery, paper/live/account action, or owner approval inference was enabled.

## Remaining Work

Next implementation step is renderer/export hardening:

1. Promote fixture/HTML generation into a reusable anonymous-request renderer.
2. Add a real regression harness covering clean, seeded-bad customer data, seeded-bad authority flag, missing evidence, and broken renderer/export cases.
3. Add two or three anonymous scenario templates.
4. Move service-state from JSON proof to SQLite/PostgreSQL-compatible v1 only after the contract stabilizes.
