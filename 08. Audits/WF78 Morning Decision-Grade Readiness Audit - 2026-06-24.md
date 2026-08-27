# WF78 Morning Decision-Grade Readiness Audit

Generated: 2026-06-23 22:09 MST / 2026-06-24 05:09 UTC  
Scope: WF78 routing, freshness, promotion/demotion evidence, and whether morning alerts can safely carry decision-grade recommendations.  
Authority: review-only. This audit does not approve capital deployment, paper/live execution, portfolio/canon mutation, customer output, or owner approval inference.

## Executive Summary

The WF78 daily_core_v2 conveyor ran successfully overnight with **57/57 steps ok, 0 failed layers, 0 authority drift**. The safety architecture is intact: every gate keeps `capital_deployment_approved=false`, `trade_or_execution_approved=false`, and `owner_approval_inferred=false`.

However, **no ticker currently qualifies as a decision-grade capital recommendation**, and the system still has the same three readiness-overclaim gaps I identified in the 2026-06-23 audit:

1. **A-READY is only routing readiness, not deployability.** The tier semantics guard explicitly says `decision_grade_allowed_count=0` and warns not to translate A-READY into decision-grade language. Yet downstream consumers (status card, finance SQL canon access, action queue) still surface `approval-ready paper starter if fresh in band` for Tier A names in band.
2. **Router/SQL canon cohort mismatch persists.** Router has 25 Tier A tickers; `finance-canon.sqlite` only has 19 in the Tier A cohort. The six ETF/fund names (`PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`) are routed Tier A by the auto-router but are not validated by the same coverage/depth gate.
3. **Stale promotion packet was only partially neutralized.** GOOG, NVDA, and VRT were demoted from `A-READY` to `A-WATCH` by the latest run, but the same packet still feeds the router and the action queue still lists these three as `approval_ready_if_fresh`.

**Bottom line for morning alerts:** they can carry research/routing signals and review prompts, but they must not carry decision-grade capital recommendations until the fixes below are implemented and validated.

## Live State as of 2026-06-24 05:12 UTC

### Tier counts

| Tier | Count | States |
|---|---:|---|
| Tier A | 25 | 18 A-CHALLENGED, 7 A-WATCH, 0 validated A-READY |
| Tier B | 39 | all B-CANDIDATE |
| Tier C | 136 | 1 C-CANDIDATE, 3 C-CANDIDATE-REPAIR, 132 C-MONITOR |

### Coverage/depth gate verdict

- `coverage_floor_ok`: true
- `depth_ready_all_tier_a`: false
- `depth_ready_a_ready`: true
- `decision_grade_allowed_count`: **0**
- `finance_tier_a_count`: 19
- `router_tier_a_count`: 25
- `router_only_tickers`: **PAVE, VAW, VXUS, WMB, XLF, XLI**
- `depth_blocker`: `current_sector_performance_missing` (1)

### Confidence gate verdict

- `allow_a_ready_tickers`: 19 names
- `force_a_challenged_tickers`: **ITA, PAVE, VAW, VXUS, XLF, XLI** (6 names forced to challenged because data confidence = not_applicable)
- `conflicted_tickers`: 0

### Cron/escalation state

- `trade_grade_os_freshness_cron_runner.py`: ok, 27/27 steps
- `wf78_intelligence_routing_v2.py daily_core_v2`: ok, 57/57 steps, 6 layers
- `cron_control_packet.json`: status=ok, 3 escalations
- `main_session_escalation_consumer.py` (dry_run): warning, 3 unresolved blocked signals, 0 safe auto-actions

The blocked cron signals are old and unrelated to WF78 routing safety (WF74 learning loop, OTEL digest, WF78 opportunity refresh controller). They need handler mapping, but they do not change the finance authority boundary.

## What Was Promoted/Demoted Today

### Promotions

- **No new Tier A promotions completed today.**
- **Tier C attention candidates:** ABBV, ALL, BALL, DLR. All four were blocked from Tier B promotion by the `wf78_tier_c_to_b_auto_promotion_pipeline.py` with status `blocked_pending_repair`.
- **Tier C→B phase2 eligible:** 15 names (ACN, ADI, ADP, ADSK, AKAM, ALB, ALLE, AMAT, AMCR, AME, ANET, AOS, APH, APP, CDNS). These are research-bench eligible only; no Tier B admission executed.
- **Competitive gate Tier A candidate:** BKNG — still report-only, not promoted.

### Demotions

- **GOOG, NVDA, VRT** were demoted from `A-READY` to `A-WATCH` at 2026-06-24 01:20 UTC.
- Reason: `auto_admitted_from_tier_a_final_packet_but_stale_rerouted_to_watch`.
- This is the correct safety outcome for stale packet rows.

### Event ledger

- `state/workflows/wf78-tier-routing-events.jsonl`: 62 total events
- New events in latest run: 0
- Last event: 2026-06-24 01:20:11 UTC (the GOOG/NVDA/VRT demotions)

## Morning-Alert Decision-Grade Assessment

| Requirement | Status | Evidence |
|---|---|---|
| All authority flags false | ✅ Pass | Every artifact checked shows capital/execution/owner-approval false |
| Coverage floor ok | ✅ Pass | 43 tickers pass coverage floor |
| Tier A depth ready | ⚠️ Fail | `depth_ready_all_tier_a=false`, one `current_sector_performance_missing` blocker |
| Decision-grade allowed count > 0 | ❌ Fail | `decision_grade_allowed_count=0` |
| Router/finance canon cohort aligned | ❌ Fail | 25 vs 19; 6 router-only ETF/fund names |
| A-READY label ≠ deployable | ⚠️ Partial | Tier semantics guard blocks decision-grade language, but action queue still uses `approval_ready_if_fresh` |
| Freshness resolver has no unresolved rows | ✅ Pass | 200 resolved, 0 unresolved |
| Daily movement ledger published | ✅ Pass | 200 records, 42 repairs |
| Repair debt scoreboard published | ✅ Pass | 4 phases |
| Full-answer parity ok | ✅ Pass | All 200 tickers built with 0 validation errors/warnings |

**Verdict:** The conveyor is green, but the output is **research-grade and routing-grade**, not **decision-grade**. Morning alerts should lead with `review_only` / `monitor` / `no_chase` language, not `buy` or `deploy`.

## Findings

### F1 — A-READY Language Still Leaks Into Consumer Surfaces

**Files:** `scripts/finance_sql_canon_access.py`, `scripts/finance_intelligence_state.py`, status card generator  
**Issue:** The SQL canon access layer maps `auto_state='A-READY'` to `production_answer_path_member=1` and `recommendation_posture='approval-ready paper starter if fresh in band'`. The tier semantics guard explicitly says this is routing readiness only and `decision_grade_allowed_count=0`.

**Risk:** A user reading the status card or action queue can interpret `approval-ready` as a go signal without opening source artifacts.

**Fix:** Make `finance_sql_canon_access.py` require current proof from `tier_a_trade_grade_coverage_gate.py` (or the V2 tier semantics guard) before setting `production_answer_path_member=1`. If `decision_grade_allowed_count=0`, then `production_answer_path_member` must be 0 for all tickers and `recommendation_posture_key` must map to `monitor` or `review_required`.

### F2 — Router/SQL Canon Tier A Cohort Mismatch

**Files:** `scripts/wf78_auto_tier_router.py`, `scripts/tier_a_trade_grade_coverage_gate.py`, `state/finance/finance-canon.sqlite`  
**Issue:** Router admits 25 Tier A names. Finance canon only has 19. The six extra names are ETFs/funds with `not_applicable` data confidence, yet the router routes them Tier A.

**Risk:** The coverage gate cannot validate the full Tier A cohort, so it permanently reports `decision_grade_allowed_count=0` and `tier_definition_aligned=false`.

**Fix:** Choose one of:
- (a) Add the six ETF/fund names to `finance-canon.sqlite` with appropriate ETF/fund evidence families so they can be validated by the coverage gate; or
- (b) Route them to a dedicated `A-ETF` or `A-FUND` sub-state that does not count toward the operating-company Tier A decision-grade cohort.

### F3 — Stale Promotion Packet Still Feeds the Router

**Files:** `scripts/wf78_auto_tier_router.py`, `tmp/wf78-tier-a-final-promotion-packet.json`  
**Issue:** The 18-day-old promotion packet still exists and is read by the router. GOOG/NVDA/VRT were demoted to `A-WATCH`, but the packet still appears in the routing input path and the action queue still surfaces these three as `approval_ready_if_fresh`.

**Risk:** A later code change or cron timing gap could re-promote them to A-READY based on the same stale packet.

**Fix:** After demotion, the router should (1) mark stale packet rows as `stale_input_ignored` in its report, (2) not allow any stale-packet row to map to `A-READY`, and (3) surface a warning when the packet age exceeds the configured TTL.

### F4 — Daily Core V2 Passes but V1 Cron Is Still Blocked

**Files:** `scripts/trade_grade_os_freshness_cron_runner.py`, `scripts/wf78_intelligence_routing_v2.py`  
**Issue:** The V2 conveyor is green. The legacy V1 cron runner (`trade_grade_os_freshness_cron_runner.py`) still reports `wf85_review_ready=0` and `approval_drafts=0`. The status card may still read from legacy surfaces.

**Risk:** Mixed V1/V2 signals create confusion about which surface is authoritative.

**Fix:** Update the status card and morning-alert generators to read from `wf78_intelligence_routing_v2.json` and `wf78-tier-semantics-guard.json`, not legacy V1 counts.

### F5 — `wf78_tier_routing_event_ledger.py` Reports Blocked with 0 Candidates

**File:** `scripts/wf78_tier_routing_event_ledger.py`  
**Issue:** When called with `--delta 1`, the ledger reports `status=blocked` and `candidate_event_count=0` even though the V2 run just published events. The `--write`/`--write-md` path in V2 reports `status=ok`.

**Risk:** Inconsistent status depending on invocation path.

**Fix:** Align the `--delta` path with the V2 publisher path so the same state produces the same status. Add unit test for both invocation modes.

## Recommended Fix Priority

### P0 — Make Decision-Grade Language Impossible When Coverage Gate Says 0

1. `scripts/finance_sql_canon_access.py`: join `tier_a_trade_grade_coverage_gate.json` and only set `production_answer_path_member=1` when `decision_grade_allowed_count > 0` for that ticker's cohort. Otherwise set to 0 and posture to `monitor_only_no_owner_action`.
2. `scripts/finance_intelligence_state.py`: if `decision_grade_allowed_count=0`, downgrade `recommendation_posture_key` from `approval_ready_if_fresh` to `monitor_or_source_open_review` for all Tier A names.
3. Update status card to surface `decision_grade_allowed_count` and `validated_production_answer_count` prominently.

### P1 — Reconcile Router/SQL Canon Tier A Cohort

1. Decide policy for the six ETF/fund names.
2. If they stay Tier A, add them to `finance-canon.sqlite` with ETF/fund evidence families and route them through `tier_a_trade_grade_coverage_gate.py`.
3. If they do not belong in the same decision-grade cohort, introduce `A-ETF`/`A-FUND` sub-state and exclude from `decision_grade_allowed_count`.

### P2 — Harden Stale Promotion Packet Handling

1. `scripts/wf78_auto_tier_router.py`: explicitly ignore rows from a packet older than `tier_a_packet_max_age_hours`.
2. Add `stale_input_ignored` count to router output.
3. Ensure demoted stale-packet tickers are removed from `approval_ready_if_fresh` action queue until a fresh promotion packet is generated.

### P3 — Standardize Morning-Alert Surface on V2

1. Move status card, action queue, and pending-approval generators to use `wf78_intelligence_routing_v2.json` and `wf78-tier-semantics-guard.json`.
2. Deprecate V1 `trade_grade_os_freshness_cron_runner.py` counts in user-facing surfaces.

### P4 — Fix Ledger Invocation Inconsistency

1. Make `wf78_tier_routing_event_ledger.py --delta N` and V2 publisher path produce consistent status when no new events exist.
2. Add regression test.

## Acceptance Criteria for "Decision-Grade Morning Alerts"

Before any morning alert can be called decision-grade, all of these must pass:

- [ ] `wf78_intelligence_routing_v2.py daily_core_v2` completes with 0 failed layers and 0 authority drift.
- [ ] `tier_a_trade_grade_coverage_gate.py` reports `decision_grade_allowed_count > 0`.
- [ ] `tier_a_trade_grade_coverage_gate.py` reports `tier_definition_aligned=true` and `router_finance_tier_definition_aligned=true`.
- [ ] `finance_intelligence_state.py action-queue` shows only `monitor_only_no_owner_action` or `review_required` when `decision_grade_allowed_count=0`.
- [ ] No `approval_ready_if_fresh` rows exist for tickers whose full-answer decision state is `blocked_missing_source_open`.
- [ ] `wf78_tier_semantics_guard.json` is the source of truth for whether A-READY language may be used.
- [ ] Authority flags remain false for capital, execution, paper/live, brokerage/account, and owner-approval inference.

## Next Action

The other lane is already working on this. I will **pause implementation** until you provide their response. Then I will reconcile findings, decide whether any additional audit or implementation lane is needed, and update `06. Playbooks/Active Workflows.md` and today's daily note with the result.
