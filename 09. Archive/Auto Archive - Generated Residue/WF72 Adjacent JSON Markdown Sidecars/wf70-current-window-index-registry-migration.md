# WF70 Current-Window Index Registry Migration Proof

Generated: `2026-05-22T23:02:35Z`

Status: **ok**

current_window_artifact_index official IR/capture aliases are generated from official_capture_period_registry latest selector instead of duplicated static Q1 mappings

## What changed

- `scripts/official_capture_period_registry.py`
- `scripts/current_window_artifact_index.py`
- `scripts/test_current_window_artifact_index.py`
- `tmp/current-window-artifacts.json`
- `tmp/current-window-artifacts.md`

## No-drift proof

- Baseline/current normalized compare excluding `generated_at_utc`: `True`
- Compare artifact: `tmp/wf70-proof/current-window-index-registry-migration-normalized-compare.json`

## Validators

- capital_deployment_recommendation_validator: `ok; 7 packets, 0 critical, 0 warning`
- current_window_artifact_index_write: `passed; wrote tmp/current-window-artifacts.json and tmp/current-window-artifacts.md`
- fundamental_ir_reconciliation_validator: `{'critical': 0, 'expected_equity_tickers': 31, 'findings': 0, 'packets': 31, 'warning': 0}`
- official_earnings_bridge_validator: `{'bridges': 31, 'critical': 0, 'findings': 0, 'warning': 0}`
- official_ir_capture_validator: `{'captures_checked': 31, 'critical': 0, 'findings': 0, 'warning': 0}`
- py_compile: `passed before write pass for official_capture_period_registry/current_window_artifact_index/test_current_window_artifact_index/test_official_capture_period_registry`
- test_current_window_artifact_index: `passed`
- test_official_capture_period_registry: `passed`

## Authority

- Review-only. No canon/portfolio/deployment/trade/account/paper order/sizing/sleeve/cash/risk-rule mutation was performed or authorized. No owner approval was inferred.

## Residue

- scripts/chain_manifest.py still carries explicit q1-2026 expected output paths and should be migrated later, not in this pass.
- scripts/run_summary_refresh.py remains a candidate for the next low-risk registry/latest-selector consumer migration.
- fundamental_ir_reconciliation_packets.py and official_earnings_bridge.py should remain unchanged until more registry-consumer proof is clean.
