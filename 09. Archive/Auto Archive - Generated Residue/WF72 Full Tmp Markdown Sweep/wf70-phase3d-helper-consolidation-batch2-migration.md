# WF70 Phase 3D Batch-2 Helper Migration

- Status: `ok`
- Targets:
  - `scripts/batch2_official_ir_capture.py`
  - `scripts/batch2b_official_ir_capture.py`
- Owner: Official Source Desk + Fundamental Research Desk
- Helper reused: `scripts/official_ir_capture_common.py`

## What changed

Both batch-2 capture scripts now reuse the common WF70 helper for review-only authority defaults, official claim construction, capture-document construction, source metadata hashing/timestamps, period propagation, summary construction, UTF-8 artifact writing, and batch fetch/text/run output plumbing.

Kept local: ticker-specific field extraction, source sections, and excerpt/first-excerpt behavior.

## Side-by-side proof

- Compared tickers: `AMD`, `CAT`, `CVX`, `PLTR`, `GE`, `LLY`, `META`, `PH`
- Compare report: `tmp/wf70-proof/batch2-migration/batch2-normalized-compare.json`
- Result: `ok`
- Ignored only volatile fields: `generated_at_utc`, `source.retrieved_at_utc`, `captures.*.capture_date_utc`

## Validation

- `python -m py_compile scripts\batch2_official_ir_capture.py scripts\batch2b_official_ir_capture.py scripts\official_ir_capture_common.py` passed.
- `python scripts\batch2_official_ir_capture.py` passed for `AMD`, `CAT`, `CVX`, `PLTR`.
- `python scripts\batch2b_official_ir_capture.py` passed for `GE`, `LLY`, `META`, `PH`.
- `python scripts\official_ir_capture_validator.py --all --write` passed: 20 captures, 0 findings.
- `python scripts\validate_fundamental_ir_reconciliation.py --strict` passed: 31 packets, 0 findings.
- `python scripts\validate_official_earnings_bridge.py --strict` passed: 31 bridges, 0 findings.
- `python scripts\capital_deployment_recommendation_validator.py` passed: 7 packets, 0 critical, 0 warning.

## Authority boundary

Review-only evidence capture remains intact. No canonical note mutation, portfolio mutation, sizing/cash/risk-rule change, paper/live trade, account action, money movement, or owner-approval inference occurred.

## Remaining residue

The existing 20 official captures are now helper-consolidated across GOOG, tech, priority, ETN/VRT, and batch-2 scripts. Next pass can begin long-tail expansion with source/extractor proof for `BKNG`, `KTOS`, `LNG`, `SMCI`, `LIN`, `ECL`, `VMC`, `NFLX`, `TMUS`, `CME`, and `WMB`.
