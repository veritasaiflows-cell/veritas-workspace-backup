# WF70 Phase 4 - Long-tail official source expansion proof

Generated: 2026-05-22T16:34:12Z

Script: `scripts/longtail_official_ir_capture.py`
Common helper: `scripts/official_ir_capture_common.py`

## Authority

- Review-only: true
- Canon/portfolio/deployment/trade/account/paper-order/sizing/cash-rule mutation: false
- Owner approval inferred: false

## Result

Added source-resolved official capture files for 11 long-tail tickers. This v1 pass proves official SEC exhibit source/provenance and intentionally leaves the seven detailed fields `manual_required` until ticker-specific extractors are hardened.

| Ticker | Capture | Accession | Manual fields | Source |
|---|---|---:|---:|---|
| BKNG | `tmp/official-ir-captures/bkng-q1-2026.json` | `None` | 7 | None |
| KTOS | `tmp/official-ir-captures/ktos-q1-2026.json` | `None` | 7 | None |
| LNG | `tmp/official-ir-captures/lng-q1-2026.json` | `None` | 7 | None |
| SMCI | `tmp/official-ir-captures/smci-q1-2026.json` | `None` | 7 | None |
| LIN | `tmp/official-ir-captures/lin-q1-2026.json` | `None` | 7 | None |
| ECL | `tmp/official-ir-captures/ecl-q1-2026.json` | `None` | 7 | None |
| VMC | `tmp/official-ir-captures/vmc-q1-2026.json` | `None` | 7 | None |
| NFLX | `tmp/official-ir-captures/nflx-q1-2026.json` | `None` | 7 | None |
| TMUS | `tmp/official-ir-captures/tmus-q1-2026.json` | `None` | 7 | None |
| CME | `tmp/official-ir-captures/cme-q1-2026.json` | `None` | 7 | None |
| WMB | `tmp/official-ir-captures/wmb-q1-2026.json` | `None` | 7 | None |

## Validation

- py_compile: passed for scripts/longtail_official_ir_capture.py and scripts/official_ir_capture_common.py
- official_ir_capture_validator_all_write: passed: 31 captures / 0 findings / 0 warnings / 0 critical
- validate_fundamental_ir_reconciliation_strict: passed: 31 packets / 0 findings / 0 warnings / 0 critical
- validate_official_earnings_bridge_strict: passed: 31 bridges / 0 findings / 0 warnings / 0 critical
- capital_deployment_recommendation_validator: passed: 7 packets / 0 critical / 0 warning
- chain_manifest_py_compile_and_inspection: passed: longtail step present in morning/post-close/post-earnings/sunday/full; validator outputs=31 and depends_on includes longtail in each window
- current_window_artifact_index: wrote current artifacts; status warning due existing upstream artifact posture, not a long-tail capture validator failure
