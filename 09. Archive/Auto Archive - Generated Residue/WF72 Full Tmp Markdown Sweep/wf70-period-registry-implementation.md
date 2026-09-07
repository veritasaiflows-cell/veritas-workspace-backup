# WF70 Step 1 - Official Capture Period Registry & Latest-Selector

- Generated: 2026-05-22T20:45:00Z
- Status: ok
- Review-only. No portfolio/canon/trade/account authority widened. No owner approval inferred.

## Scope

| Surface | Change |
|---|---|
| `scripts/official_capture_period_registry.py` | NEW. Single source of truth for ticker -> period -> file paths + latest-validator-clean selector. 31 tickers, self-check ok. |
| `scripts/official_ir_capture_common.py` | Added `period_slug` / `period_label` params to `run_capture_batch()` and `write_md()`; defaults preserve Q1 behavior. |
| `scripts/chain_manifest.py` | Post-processes `WINDOW_MANIFESTS` to overwrite expected_outputs for all capture scripts and the official IR capture validator from registry. |
| `scripts/current_window_artifact_index.py` | 60 literal alias entries replaced with registry-driven population for the 20 historical alias tickers. |
| `scripts/run_summary_refresh.py` | 4 windows x 40 literal entries replaced with registry-driven extension for the 20 alias tickers. |
| `scripts/fundamental_ir_reconciliation_packets.py` | `load_validated_official_captures()` now groups by ticker and picks max(period_end); no longer depends on filename sort. |
| `scripts/official_earnings_bridge.py` | Same latest-by-period_end selection as reconciliation. |

## Side-by-side no-drift proof

| Consumer | Result |
|---|---|
| `current_window_artifact_index.py` | Alias paths and artifact set identical. Only diff: two unrelated artifact-internal timestamps from independent upstream regeneration. |
| `run_summary_refresh.py` | 40 capture keys identical, 0 path mismatches. Other diffs are time-of-run variance (chain_status, NVDA warning, freshness fields). |
| `fundamental_ir_reconciliation_packets.py` | NO DRIFT after timestamp normalization. |
| `official_earnings_bridge.py` | NO DRIFT after timestamp normalization (only `source_generated_at_utc` changed). |

Baseline snapshots: `tmp/wf70-proof/period-registry-baseline/`.

## Validators

| Validator | Status | Findings |
|---|---|---|
| `official_ir_capture_validator.py --all --write` | ok | 31 captures / 0 critical / 0 warning |
| `validate_fundamental_ir_reconciliation.py --strict` | ok | 0 warning / 0 findings |
| `validate_official_earnings_bridge.py --strict` | ok | 0 warning / 0 findings |
| `capital_deployment_recommendation_validator.py` | ok | 7 packets / 0 critical / 0 warning |

## Rollforward invariant

- Q1 capture artifacts are immutable (`{ticker}-q1-2026.json` and friends).
- A future-quarter capture for a ticker is an additive registry edit: add a `TickerPeriod` row with `q2-{year}` slug and updated `period_end`.
- `chain_manifest` expected outputs, `current_window_artifact_index` aliases, `run_summary_refresh` required outputs, reconciliation latest-selection, and bridge latest-selection all reflect the change without further code edits.
- The `latest_validated_capture()` selector picks the highest `period_end` among validator-clean artifacts with `review_only=true` and `resolved_for_apply=false`.

## Long-tail alias decision

Long-tail tickers (BKNG, KTOS, LNG, SMCI, LIN, ECL, VMC, NFLX, TMUS, CME, WMB) intentionally remain non-aliased in `current_window_artifact_index.py` and `run_summary_refresh.py` to preserve the historical surface scope. They are fully covered by `chain_manifest` expected outputs and by reconciliation/bridge latest-selection.

## Authority

Review-only. No portfolio/canon/trade/account/paper-order/sizing/sleeve/cash/risk-rule mutation or owner-approval inference occurred.
