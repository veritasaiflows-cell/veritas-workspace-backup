# WF70 Phase 4 - Long-tail extractor hardening batch 3 closeout

Generated: 2026-05-22T17:59:55Z

## Result

LNG/LIN/ECL/VMC/WMB no longer have manual_required fields. All 11 long-tail tickers now have zero manual_required fields; statuses are official-captured/not-disclosed/not-applicable/partial only where official release evidence supports that status.

## Authority

Review-only. No canon/portfolio/deployment/trade/account/paper-order/sizing/cash-rule mutation. No owner approval inferred.

## Tickers

| Ticker | Manual remaining | Statuses |
|---|---:|---|
| LNG | 0 | acquisition_debt_notes=official_captured, adjusted_eps=not_disclosed_in_release, growth_bridge=official_captured, guidance=official_captured, management_explanation=official_captured, orders_backlog=partial, segment_margins=partial |
| LIN | 0 | acquisition_debt_notes=official_captured, adjusted_eps=official_captured, growth_bridge=official_captured, guidance=official_captured, management_explanation=official_captured, orders_backlog=partial, segment_margins=official_captured |
| ECL | 0 | acquisition_debt_notes=partial, adjusted_eps=official_captured, growth_bridge=official_captured, guidance=official_captured, management_explanation=official_captured, orders_backlog=partial, segment_margins=official_captured |
| VMC | 0 | acquisition_debt_notes=official_captured, adjusted_eps=official_captured, growth_bridge=official_captured, guidance=official_captured, management_explanation=official_captured, orders_backlog=partial, segment_margins=official_captured |
| WMB | 0 | acquisition_debt_notes=official_captured, adjusted_eps=official_captured, growth_bridge=official_captured, guidance=official_captured, management_explanation=official_captured, orders_backlog=official_captured, segment_margins=partial |

## Validation

- py_compile: passed for scripts/longtail_official_ir_capture.py
- targeted_capture_run: passed for LNG/LIN/ECL/VMC/WMB
- official_ir_capture_validator_all_write: passed: 31 captures / 0 findings / 0 warnings / 0 critical
- validate_fundamental_ir_reconciliation_strict: passed: 31 packets / 0 findings / 0 warnings / 0 critical
- validate_official_earnings_bridge_strict: passed: 31 bridges / 0 findings / 0 warnings / 0 critical
- capital_deployment_recommendation_validator: passed: 7 packets / 0 critical / 0 warning
- current_window_artifact_index: wrote current-window artifact index; status warning remains pre-existing/current-window posture, not an official-capture validation failure
