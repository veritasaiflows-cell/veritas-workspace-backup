# WF78 Progress Update — 2026-06-24 05:59 UTC

Scope: follow-up on the 2026-06-23/24 WF78 audit findings; verify whether L1 stale-packet TTL and router/SQL-canon cohort mismatch have changed since last run.  
Authority: review-only. No implementation, no capital/execution/customer/canon/portfolio action.

## Latest Run

Command chain executed:

1. `python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --write --validate`
2. `python scripts\tier_a_trade_grade_coverage_gate.py --write --validate`
3. `python scripts\finance_sql_canon_access.py --write --validate`
4. `python scripts\wf78_auto_tier_router.py --write --validate`

## Key Results

### WF78 daily_core_v2

- Status: **blocked** (was `ok` last run).
- 6 layers started; 5 layers ok, 1 layer blocked.
- Failed layer: `postflight`.
- Failed step: `artifact_index_validate`.
- Reason: `freshness_no_stale_content` failed — `tmp/concurrent-lane-register.json` has stale content.

This is a metadata/operational stale proof, not a finance authority problem. The routing/freshness/repair/ledger layers all completed ok.

### Coverage/depth gate

| Metric | Value |
|---|---|
| coverage_floor_ok | true |
| depth_ready_all_tier_a | false |
| decision_grade_allowed_count | **0** |
| tier_definition_aligned | false |
| router_finance_tier_definition_aligned | false |
| router_data_plane_tier_definition_aligned | true |
| router_tier_a_count | 25 |
| finance_tier_a_count | 19 |
| router_only_tickers | **PAVE, VAW, VXUS, WMB, XLF, XLI** |
| depth_blocker | current_sector_performance_missing (1 ticker) |

**Verdict: no change in decision-grade eligibility.** The cohort mismatch is unchanged.

### Auto-router

- Active tickers: 200
- Tier A: 25 (18 A-CHALLENGED, 7 A-WATCH, 0 A-READY)
- Tier B: 39
- Tier C: 136
- Stale packet rows: 3 (GOOG, NVDA, VRT)
- capital_deployment_approved_count: 0
- trade_or_execution_approved_count: 0

The stale packet is still being read and logged, but the TTL seems to be preventing A-READY from being assigned to those three tickers. The new issue is the V2 postflight stale-content check, which is now failing on the lane register file.

## What Changed Since Last Audit

| Item | Before (06-23 22:09 MST) | Now (06-23 22:58 MST) |
|---|---|---|
| V2 overall status | ok | **blocked** (postflight stale lane register) |
| Coverage gate decision_grade_allowed_count | 0 | **0** (unchanged) |
| Router Tier A cohort | 25 | 25 (unchanged) |
| Finance Tier A cohort | 19 | 19 (unchanged) |
| Router-only ETF/fund tickers | 6 | 6 (unchanged) |
| Stale packet rows (GOOG/NVDA/VRT) | 3 | 3 (still present, still not A-READY) |
| A-READY count | 0 | 0 |

## Findings from This Pass

### G1 — V2 Postflight Is Now Blocked by Stale Lane Register Content

- `artifact_index_validate` reports `freshness_no_stale_content` failed with `tmp/concurrent-lane-register.json` as the stale file.
- This is a control-plane proof artifact, not a finance/routing output.
- Impact: downstream consumers that check `wf78-intelligence-routing-v2.json` for `status=ok` will see `blocked` and should not trust the run as fully green, even though routing/freshness/ledger layers succeeded.

### G2 — Cohort Mismatch Remains Unresolved

- The six router-only tickers (`PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`) are still not in `finance-canon.sqlite`'s Tier A cohort.
- The confidence gate marks `ITA`, `PAVE`, `VAW`, `VXUS`, `XLF`, `XLI` as `force_a_challenged`.
- `WMB` is in the `allow_a_ready` list but still not in the finance-canon Tier A cohort.

### G3 — Decision-Grade Count Is Still Zero

- `decision_grade_allowed_count=0` because `depth_ready_all_tier_a=false` and `tier_definition_aligned=false`.
- No ticker is decision-grade for capital deployment.

## Recommendations

### R1 — Decide Policy on Router-Only ETF/Fund Tickers (P1)

The cohort mismatch will keep `decision_grade_allowed_count=0` and `tier_definition_aligned=false` forever unless we either:

- Add the six names to `finance-canon.sqlite` with ETF/fund evidence families; or
- Exclude them from the decision-grade operating-company Tier A cohort (e.g., `A-ETF` / `A-FUND` sub-state).

### R2 — Harden V2 Postflight Stale-Content Handling (P2)

`tmp/concurrent-lane-register.json` is not a routing/finance output; it should not be able to block the entire `daily_core_v2` postflight. Either:

- Add an exclusion/retention rule for lane-register files in the freshness check; or
- Refresh the lane register before postflight runs; or
- Separate operational proof freshness from finance routing freshness.

### R3 — Keep Stale-Packet TTL Behavior (P3)

Current behavior is correct: GOOG/NVDA/VRT are not A-READY. But the packet is still read and still appears in the action queue. After the cohort policy is fixed, consider regenerating a fresh promotion packet or removing stale rows so the system does not keep surfacing them as `approval_ready_if_fresh`.

### R4 — Make Finance SQL Canon Access Fail Closed (P0)

`finance_sql_canon_access.py` should not emit `production_answer_path_member=1` for any ticker while `decision_grade_allowed_count=0` and `tier_definition_aligned=false`.

## Stop Lines

- No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.
- Do not delete or move `tmp/concurrent-lane-register.json` without checking whether it is an active lane-lease register.

## Next Action

I will not implement fixes until the other lane's response arrives. Once we reconcile findings, I can open a bounded implementation lane for R1 + R2 + R4 if you approve.
