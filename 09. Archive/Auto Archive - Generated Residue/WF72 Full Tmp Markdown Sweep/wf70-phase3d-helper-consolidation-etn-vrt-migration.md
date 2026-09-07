# WF70 Phase 3D ETN/VRT Capture Helper Migration

- Status: `ok`
- Target: `scripts/etn_vrt_official_ir_capture.py`
- Helper updated: `scripts/official_ir_capture_common.py`
- Owner: Official Source Desk + Fundamental Research Desk

## What changed

`etn_vrt_official_ir_capture.py` now reuses the common WF70 helper for review-only authority defaults, official claim construction, capture-document construction, source metadata hashing/timestamps, period propagation, summary construction, UTF-8 artifact writing, and batch fetch/run output plumbing.

`official_ir_capture_common.run_capture_batch()` now accepts an optional `text_converter` so legacy migrated scripts can preserve exact source-text normalization during side-by-side proof.

Kept local: ETN/VRT-specific field extraction, legacy ETN/VRT HTML-to-text conversion, and excerpt formatting.

## Side-by-side proof

- Compared tickers: `ETN`, `VRT`
- Old artifacts:
  - `tmp/wf70-proof/etn-vrt-migration/etn-old.json`
  - `tmp/wf70-proof/etn-vrt-migration/vrt-old.json`
- New artifacts:
  - `tmp/wf70-proof/etn-vrt-migration/etn-new.json`
  - `tmp/wf70-proof/etn-vrt-migration/vrt-new.json`
- Compare report: `tmp/wf70-proof/etn-vrt-migration/etn-vrt-normalized-compare.json`
- Result: `ok`
- Ignored only volatile fields: `generated_at_utc`, `source.retrieved_at_utc`, `captures.*.capture_date_utc`

## Validation

- `python -m py_compile scripts\etn_vrt_official_ir_capture.py scripts\official_ir_capture_common.py` passed.
- `python scripts\etn_vrt_official_ir_capture.py` passed for `ETN`, `VRT`.
- `python scripts\official_ir_capture_validator.py --all --write` passed: 20 captures, 0 findings.
- `python scripts\validate_fundamental_ir_reconciliation.py --strict` passed: 31 packets, 0 findings.
- `python scripts\validate_official_earnings_bridge.py --strict` passed: 31 bridges, 0 findings.
- `python scripts\capital_deployment_recommendation_validator.py` passed: 7 packets, 0 critical, 0 warning.

## Authority boundary

Review-only evidence capture remains intact. No canonical note mutation, portfolio mutation, sizing/cash/risk-rule change, paper/live trade, account action, money movement, or owner-approval inference occurred.

## Remaining residue

Continue migrating `batch2_official_ir_capture.py` and `batch2b_official_ir_capture.py` before adding long-tail tickers. VRT Q1 adjusted EPS per-share remains partial by source/extractor limitation, not fabricated.
