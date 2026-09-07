# WF70 Phase 3D Priority Capture Helper Migration

- Status: `ok`
- Target: `scripts/priority_official_ir_capture.py`
- Owner: Official Source Desk + Fundamental Research Desk
- Helper reused: `scripts/official_ir_capture_common.py`

## What changed

`priority_official_ir_capture.py` now reuses the common WF70 helper for review-only authority defaults, official claim construction, capture-document construction, source metadata hashing/timestamps, period propagation, summary construction, UTF-8 artifact writing, and batch fetch/text/run output plumbing.

Kept local: priority-ticker field extraction and the prior excerpt fallback formatting, to avoid output drift.

## Side-by-side proof

- Compared ticker: `JPM`
- Old artifact: `tmp/wf70-proof/priority-migration/jpm-old.json`
- New artifact: `tmp/wf70-proof/priority-migration/jpm-new.json`
- Compare report: `tmp/wf70-proof/priority-migration/jpm-normalized-compare.json`
- Result: `ok`
- Ignored only volatile fields: `generated_at_utc`, `source.retrieved_at_utc`, `captures.*.capture_date_utc`

## Validation

- `python -m py_compile scripts\priority_official_ir_capture.py scripts\official_ir_capture_common.py` passed.
- `python scripts\priority_official_ir_capture.py` passed for `BRK.B`, `GS`, `JPM`, `LMT`, `RTX`, `XOM`.
- `python scripts\official_ir_capture_validator.py --all --write` passed: 20 captures, 0 findings.
- `python scripts\validate_fundamental_ir_reconciliation.py --strict` passed: 31 packets, 0 findings.
- `python scripts\validate_official_earnings_bridge.py --strict` passed: 31 bridges, 0 findings.
- `python scripts\capital_deployment_recommendation_validator.py` passed: 7 packets, 0 critical, 0 warning.

## Authority boundary

Review-only evidence capture remains intact. No canonical note mutation, portfolio mutation, sizing/cash/risk-rule change, paper/live trade, account action, money movement, or owner-approval inference occurred.

## Remaining residue

Continue migrating `etn_vrt_official_ir_capture.py` and the batch-2 scripts onto the common helper before adding long-tail tickers.
