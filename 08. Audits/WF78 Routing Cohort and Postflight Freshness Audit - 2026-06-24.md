# WF78 Routing Cohort and Postflight Freshness Audit

Generated: 2026-06-23 23:03 MST / 2026-06-24 06:03 UTC  
Scope: WF78 routing Tier A cohort reconciliation, V2 conveyor postflight freshness, and decision-grade readiness as of the latest live run.  
Authority: review-only. No capital deployment, paper/live execution, portfolio/canon mutation, customer output, cron mutation, tmp deletion/archive, or owner approval inference.

## Executive Summary

The WF78 routing/freshness stack has active repair work in flight but is **not yet decision-grade**. The latest `daily_core_v2` run completed its routing/freshness/repair/ledger layers successfully but was marked **blocked** in postflight because `tmp/concurrent-lane-register.json` failed a stale-content freshness check. This is a control-plane proof artifact, not a finance output, but it prevents consumers from treating the run as fully green.

The deeper blocker remains the **Tier A cohort mismatch**: the auto-router admits 25 tickers, but `finance-canon.sqlite` only recognizes 19 as Tier A. The six router-only names are all ETF/fund/sector-style tickers (`PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`). Until this is resolved, the coverage gate permanently reports `decision_grade_allowed_count=0` and `tier_definition_aligned=false`.

There are active implementation lanes for both issues (`WF78::STALE-A-READY-PRODUCTION-ELIGIBILITY-REPAIR-2026-06-24` and `WF78::COHORT-MOVEMENT-EVENT-VERDICT-REPAIR-2026-06-24`), which indicates the system has correctly triaged the problem. This audit records the live state and recommends the exact bounded next steps.

## Live Proof (2026-06-24 05:59 UTC)

Commands executed:

- `python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --write --validate`
- `python scripts\tier_a_trade_grade_coverage_gate.py --write --validate`
- `python scripts\finance_sql_canon_access.py --write --validate`
- `python scripts\wf78_auto_tier_router.py --write --validate`

### WF78 daily_core_v2

| Layer | Status | Notes |
|---|---|---|
| preflight | ok | cron contracts, freshness spine, artifact index incremental ok |
| tier_routing | ok | all 15 steps ok |
| freshness | ok | all 10 steps ok, 200 resolved, 0 unresolved |
| repair_scan | ok | repair queue 42 |
| ledger_publish | ok | event ledger and daily movement ledger ok |
| postflight | **blocked** | `artifact_index_validate` failed `freshness_no_stale_content` |

Overall status: **blocked**.  
Failed step: `artifact_index_validate` in `postflight`.  
Reason: `freshness_no_stale_content` failed with `stale=1 files=[tmp/concurrent-lane-register.json]`.

### Coverage / depth gate

| Metric | Value |
|---|---|
| status | `coverage_floor_ok_tier_definition_mismatch` |
| coverage_floor_ok | true |
| depth_ready_all_tier_a | false |
| depth_ready_a_ready | true |
| decision_grade_allowed_count | **0** |
| tier_definition_aligned | false |
| router_finance_tier_definition_aligned | false |
| router_data_plane_tier_definition_aligned | true |
| router_tier_a_count | 25 |
| finance_tier_a_count | 19 |
| data_plane_tier_a_count | 25 |
| router_only_tickers | **PAVE, VAW, VXUS, WMB, XLF, XLI** |
| router_only_from_data_plane_count | 0 |
| finance_only_from_router_count | 0 |
| depth_blocker | `current_sector_performance_missing` (1 ticker) |

### Auto-router output

- Active tickers: 200
- Tier A: 25
  - A-CHALLENGED: 18
  - A-WATCH: 7
  - **A-READY: 0**
- Tier B: 39
- Tier C: 136
- Stale Tier A promotion packet rows: 3 (GOOG, NVDA, VRT)
- capital_deployment_approved_count: 0
- trade_or_execution_approved_count: 0

### Finance SQL canon access

- Sample output used NVDA.
- Validation status: ok.
- Authority flags: all false.

### Confidence gate (from V2 run)

- `allow_a_ready_tickers`: 19
- `force_a_challenged_tickers`: ITA, PAVE, VAW, VXUS, XLF, XLI (6)
- `conflicted_tickers`: 0

Note: WMB is in `allow_a_ready_tickers` but is still router-only relative to `finance-canon.sqlite`.

## Findings

### F1 — V2 Postflight Fails on Operational Lane Register Staleness

**Evidence:** `wf78_intelligence_routing_v2.py` reports `status=blocked` because `artifact_index_validate` finds `tmp/concurrent-lane-register.json` stale. The 5 preceding layers all pass.  
**Impact:** A consumer that gates on `wf78-intelligence-routing-v2.json status=ok` will reject the entire run even though routing, freshness, repair, and ledger data are current.  
**Severity:** P1 — operational noise that masks real green state.

### F2 — Router/SQL Canon Tier A Cohort Mismatch Blocks Decision Grade Forever

**Evidence:**
- Router Tier A count = 25.
- `finance-canon.sqlite` Tier A count = 19.
- `data_plane` Tier A count = 25 (aligned with router).
- Six router-only tickers: PAVE, VAW, VXUS, WMB, XLF, XLI.
- Coverage gate says `decision_grade_blocked_by_router_cohort_mismatch=true`.
- Confidence gate forces ITA, PAVE, VAW, VXUS, XLF, XLI to A-CHALLENGED.

**Impact:** The coverage gate cannot validate the full Tier A cohort, so `decision_grade_allowed_count` is structurally 0 regardless of freshness.  
**Severity:** P0 — this is the root reason the OS cannot currently produce a validated decision-grade recommendation.

### F3 — Stale A-READY Promotion Packet Is Partially Contained But Still Present

**Evidence:**
- `tmp/wf78-tier-a-final-promotion-packet.json` is from 2026-06-05 (19 days old).
- GOOG, NVDA, and VRT are correctly **not** A-READY in current router output.
- The router still reports `tier_a_stale_packet_row_count=3` and lists them as stale.
- Active lane `WF78::STALE-A-READY-PRODUCTION-ELIGIBILITY-REPAIR-2026-06-24` exists.

**Impact:** The TTL enforcement is working in the router, but the stale packet still feeds the input path and may leak into consumer surfaces as `approval_ready_if_fresh` language.  
**Severity:** P1 — safety boundary holds, but proof hygiene is degraded.

### F4 — WMB Has an Ambiguous Cohort Status

**Evidence:** WMB is in the router's Tier A cohort and in the confidence gate `allow_a_ready_tickers` list, but it is **not** in `finance-canon.sqlite`'s Tier A cohort. The coverage gate therefore counts it as router-only.  
**Impact:** WMB may be the ticker contributing the `current_sector_performance_missing` depth blocker, or it may simply be miscategorized relative to finance canon.  
**Severity:** P2 — needs inspection.

### F5 — Active Lanes Already Exist for F2 and F3

**Evidence:** Lane register shows:
- `WF78::STALE-A-READY-PRODUCTION-ELIGIBILITY-REPAIR-2026-06-24` (1 lane)
- `WF78::COHORT-MOVEMENT-EVENT-VERDICT-REPAIR-2026-06-24` (1 lane)

This is good triage. The task is to verify those lanes are actually fixing the root causes above and not treating symptoms.

## Recommendations

### R1 — Fix V2 Postflight Stale Lane Register (P1)

Options, in order of preference:

1. **Refresh the lane register before postflight.** Add a pre-postflight step in V2 that calls `concurrent_lane_manager.py --status --write --validate` so the freshness check sees current content.
2. **Exclude operational lane registers from `freshness_no_stale_content`.** Treat `concurrent-lane-register.json` as a control-plane log, not a generated proof artifact, and allow its staleness to be reported as a warning instead of a postflight failure.
3. **Separate operational proof freshness from finance routing proof freshness.** Give V2 two freshness outcomes: `routing_freshness` and `control_plane_freshness`, and let routing consumers use only `routing_freshness`.

Acceptance proof: `wf78_intelligence_routing_v2.py daily_core_v2` returns `status=ok` with no `postflight` failures while the active lanes are still in `running` or `complete` states.

### R2 — Reconcile Tier A Cohort Policy (P0)

Choose one policy and implement it:

- **Option A (recommended):** Add the six router-only ETF/fund names to `finance-canon.sqlite` with appropriate ETF/fund evidence families, then let the coverage gate validate them. This makes the router and finance canon cohorts identical and unblocks `tier_definition_aligned`.
- **Option B:** Introduce a dedicated `A-ETF` or `A-FUND` sub-state for ETF/fund/sector tickers and exclude them from the operating-company Tier A decision-grade cohort. This keeps the current 19-name finance-canon cohort as the decision-grade set while still allowing router-level Tier A attention for diversified funds.

Do not mix the two semantics inside the same `Tier A` count.  
Acceptance proof: `tier_a_trade_grade_coverage_gate.py` reports `router_finance_tier_definition_aligned=true` and `decision_grade_allowed_count > 0` after all depth blockers clear.

### R3 — Remove Stale Packet Rows from Action Queue (P1)

- After GOOG/NVDA/VRT are demoted due to stale packet, suppress them from `approval_ready_if_fresh` or similar language in `finance_intelligence_state.py` and action-queue consumers until a fresh promotion packet exists.
- Optionally delete or archive `tmp/wf78-tier-a-final-promotion-packet.json` after explicit owner approval and lineage review.

Acceptance proof: `finance_intelligence_state.py action-queue` shows no `approval_ready_if_fresh` rows for GOOG/NVDA/VRT, and `wf78_auto_tier_router.py` reports `tier_a_stale_packet_row_count=0` or `stale_input_ignored`.

### R4 — Inspect WMB Depth Blocker (P2)

- Run `python scripts\finance_intelligence_state.py ticker WMB --pretty` and check the coverage gate per-ticker verdict.
- Determine whether WMB needs sector performance data added or should be recategorized to `A-FUND`/`A-ETF`.

### R5 — Validate Active Lanes Against Root Causes (P1)

- Inspect `WF78::STALE-A-READY-PRODUCTION-ELIGIBILITY-REPAIR-2026-06-24` output to confirm it targets F1/F3, not just event-ledger wording.
- Inspect `WF78::COHORT-MOVEMENT-EVENT-VERDICT-REPAIR-2026-06-24` output to confirm it targets F2 cohort alignment, not just event labels.

## Acceptance Criteria for Decision-Grade Morning Alerts

Before morning alerts can be called decision-grade, all of these must pass:

- [ ] `wf78_intelligence_routing_v2.py daily_core_v2` returns `status=ok` with all 6 layers ok.
- [ ] `tier_a_trade_grade_coverage_gate.py` reports `decision_grade_allowed_count > 0`.
- [ ] `tier_a_trade_grade_coverage_gate.py` reports `router_finance_tier_definition_aligned=true`.
- [ ] `finance_intelligence_state.py action-queue` shows no `approval_ready_if_fresh` rows while `decision_grade_allowed_count=0`.
- [ ] `wf78_auto_tier_router.py` reports `tier_a_stale_packet_row_count=0` or explicitly `stale_input_ignored`.
- [ ] All authority flags remain false for capital, execution, paper/live, brokerage/account, and owner-approval inference.

## Current Decision-Grade Verdict

**No ticker is currently decision-grade for capital deployment.**  
The V2 conveyor is functionally green for routing/freshness/repair/ledger but blocked on a postflight operational artifact. The coverage gate is structurally blocked by the router/finance-canon cohort mismatch. These are fixable, bounded, non-capital control-plane and cohort-policy issues.

## Next Action

I will not start implementation because the active lanes may already cover R1–R3. When the other lane's response arrives, I will reconcile findings, inspect those lanes' outputs, and either confirm closure or open a narrowly scoped follow-up lane for any remaining root-cause gap.
