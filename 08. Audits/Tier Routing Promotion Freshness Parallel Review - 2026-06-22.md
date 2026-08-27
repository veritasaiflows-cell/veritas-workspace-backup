# Tier Routing Promotion Freshness Parallel Review - 2026-06-22

Generated: 2026-06-23 UTC / 2026-06-22 America-Phoenix  
Scope: WF78 ticker tier movement, automatic routing quality, freshness/depth gates, Tier A fast-track risk, and parallel model audit synthesis.  
Authority: review-only. This audit does not approve trades, paper/live execution, portfolio mutation, cash/sizing/risk mutation, or customer output.

## Executive Finding

WF78 moved six tickers into Tier A today, but all six landed in `A-CHALLENGED`, not `A-READY`. That is the right safety outcome: the router can elevate a ticker quickly when thesis/opportunity evidence strengthens, but it should not treat the move as decision-grade readiness.

The blunt issue is that the current routing stack still lets old/stale promotion packets contribute to `A-READY` and production-answer routing. The strongest code finding is that `GOOG`, `NVDA`, and `VRT` still appear as `A-READY` from a Tier A final promotion packet generated on 2026-06-05 with quote timestamps from 2026-06-05. The latest coverage/depth gate says `decision_grade_allowed_count=0`, so `A-READY` should not be interpreted as decision-grade output today.

Current state is good enough for non-capital routing and review prioritization. It is not good enough to claim full decision-grade readiness, model-performance quality, customer output, autonomous paper readiness, or execution readiness.

## Proof Refreshed

Commands and artifacts reviewed:

- `python scripts\finance_sql_canon_access.py --write --validate`
- `python scripts\wf78_auto_tier_router.py --write --validate`
- `python scripts\wf78_tier_weighted_freshness_resolver.py --write --validate`
- `python scripts\tier_a_trade_grade_coverage_gate.py --write --validate`
- `python scripts\tier_a_depth_repair_phase_executor.py --write --validate`
- `python scripts\wf78_tier_routing_event_ledger.py --write --write-md --validate`
- `python scripts\wf78_daily_movement_ledger.py --write --write-md --validate`
- `state/workflows/wf78-tier-routing-events.jsonl`
- `tmp/wf78-auto-tier-routing.json`
- `tmp/wf78-tier-weighted-freshness-resolution.json`
- `tmp/tier-a-trade-grade-coverage-gate.json`
- `tmp/tier-a-depth-repair-phase-execution-packet.json`
- `tmp/wf78-tier-a-final-promotion-packet.json`
- `tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json`
- `tmp/wf78-tier-a-competitive-promotion-gate.json`

Current proof snapshot:

- Active tickers: 200.
- Auto-tier counts: Tier A 25, Tier B 39, Tier C 136.
- Auto-state counts: `A-READY` 3, `A-WATCH` 4, `A-CHALLENGED` 18, `B-CANDIDATE` 39, `C-CANDIDATE` 1, `C-CANDIDATE-REPAIR` 2, `C-MONITOR` 133.
- Weighted freshness: 195 resolved, 5 unresolved.
- Required depth counts: `decision_repair` 25, `promotion_repair` 39, `thin_monitor` 136.
- Tier A coverage/depth gate: coverage floor ok, all Tier A depth ready, A-READY depth ready, but `decision_grade_allowed_count=0`.
- Depth repair executor: `depth_repairs_complete_customer_and_decision_still_blocked`; customer output false; capital/execution false.
- Event ledger: 52 total events.
- Daily movement ledger: current rolling `moved_today_count=1`, but append-only local-day event history shows 12 local Phoenix events.

## Tickers Moved Today

The append-only event ledger uses `source_day=2026-06-23` because the events landed after 00:00 UTC. In Phoenix local time, these are Monday, 2026-06-22 events.

Tier promotions:

| Ticker | Movement | Current State | Reason |
|---|---:|---|---|
| PAVE | Tier C `C-MONITOR` -> Tier A | `A-CHALLENGED` | Production adjudication Tier A repair/watchlist candidate; inline confidence repair; confidence gate forced challenged |
| VAW | Tier C `C-MONITOR` -> Tier A | `A-CHALLENGED` | Same as above |
| VXUS | Tier C `C-MONITOR` -> Tier A | `A-CHALLENGED` | Same as above |
| WMB | Tier B `B-CANDIDATE` -> Tier A | `A-CHALLENGED` | Production adjudication Tier A repair/watchlist candidate; inline confidence repair |
| XLF | Tier C `C-MONITOR` -> Tier A | `A-CHALLENGED` | Production adjudication Tier A repair/watchlist candidate; inline confidence repair; confidence gate forced challenged |
| XLI | Tier C `C-MONITOR` -> Tier A | `A-CHALLENGED` | Same as above |

State changes without tier promotion:

| Ticker | Movement | Current State | Interpretation |
|---|---:|---|---|
| ABNB | Tier C `C-CANDIDATE-REPAIR` -> `C-MONITOR` | `C-MONITOR` | Returned to default breadth monitor |
| ASML | Tier C `C-MONITOR` -> `C-CANDIDATE-REPAIR`, then back to `C-MONITOR` | `C-MONITOR` | Current rolling state no longer repair candidate |
| CEG | Tier C `C-CANDIDATE` -> `C-CANDIDATE-REPAIR` | `C-CANDIDATE-REPAIR` | Attention/repair signal remains |
| DLR | Tier C `C-MONITOR` -> `C-CANDIDATE-REPAIR` | `C-CANDIDATE-REPAIR` | Attention/repair signal remains |
| TDG | Tier C `C-CANDIDATE-REPAIR` -> `C-MONITOR` | `C-MONITOR` | Returned to monitor |

Important ledger distinction:

- The append-only event ledger captures the full local-day history: 12 events, including 6 promotions.
- The daily movement ledger currently reports `moved_today_count=1` because it is reflecting the current rolling delta after the latest router state, not the whole local-day event history.
- This is not a trade problem, but it is a review-surface clarity problem. The UI/status layer should label these as `current_delta_moved_count` vs `local_day_event_count`.

## Current Review Quality By Tier

Tier A: highest attention, not fully decision-grade.

- Count: 25.
- States: 3 `A-READY`, 4 `A-WATCH`, 18 `A-CHALLENGED`.
- Freshness/depth: 10 fresh, 10 resolved to deployment-readiness review, 5 blocked unresolved Tier A/B debt.
- Decisions: 10 repair, 9 no-chase, 5 invalidation-review, 1 hold.
- Band posture: 14 above band, 5 below stop, 3 in band, 3 below band.
- Interpretation: Tier A is the strongest review lane, but most names are still challenged, no-chase, invalidation-review, or repair. The gate explicitly says decision-grade claims are still blocked.

Tier B: research bench, not promotion-ready by default.

- Count: 39.
- States: all `B-CANDIDATE`.
- Freshness/depth: 16 fresh, 13 deployment-readiness review, 10 owner-lineage proposal review.
- Decisions: 22 repair, 13 invalidation-review, 4 no-chase.
- Band posture: 17 above band, 13 below stop, 7 in band, 2 below band.
- Interpretation: Tier B is useful for research prioritization but is not a quiet promotion lane. It has meaningful stale/repair/invalidation burden.

Tier C: thin monitor plus attention candidates.

- Count: 136.
- States: 133 `C-MONITOR`, 2 `C-CANDIDATE-REPAIR`, 1 `C-CANDIDATE`.
- Freshness/depth: 132 resolved thin monitor, 4 blocked structural/candidate hold.
- Decisions: 132 hold, 3 repair, 1 state-change.
- Current attention names: `CEG`, `DASH`, `DLR`.
- Interpretation: Tier C is intentionally lighter review. A Tier C attention signal should create a repair or promotion-review lane, not an immediate Tier A/decision-grade claim.

## How Automatic Routing Works Today

The routing stack is producer-led:

1. `wf78_auto_tier_router.py` assigns `auto_tier` and `auto_state`.
2. Tier A promotion packets, competitive promotion gates, production adjudication, confidence gates, Tier B packets, and Tier C attention triggers feed the router.
3. `wf78_tier_weighted_freshness_resolver.py` assigns required depth by tier:
   - Tier A: `decision_repair`
   - Tier B: `promotion_repair`
   - Tier C: `thin_monitor`
4. `tier_a_trade_grade_coverage_gate.py` and `tier_a_depth_repair_phase_executor.py` validate Tier A coverage/depth posture.
5. `wf78_tier_routing_event_ledger.py` persists routing deltas.
6. `wf78_daily_movement_ledger.py` renders current movement/review posture.

Fast-track behavior exists:

- A ticker can move directly from Tier C or Tier B into Tier A when production adjudication and confidence convergence support it.
- The correct landing zone is `A-CHALLENGED` or `A-WATCH`, not `A-READY`.
- Today's fast-tracked names followed this pattern: six promotions, all `A-CHALLENGED`.

What it does not authorize:

- No capital deployment.
- No paper/live trading.
- No portfolio/cash/sizing/risk mutation.
- No customer output.
- No owner approval inference.

## Can A Ticker Bypass Up To Tier A?

Yes, but the word "bypass" should be replaced with "fast-track into challenged review."

Safe fast-track trigger:

- Thesis materially changes.
- Opportunity emerges.
- Price action creates a potentially strong entry.
- New evidence indicates a name is misplaced in Tier B/C.
- Momentum/fundamental/repair-burden score crosses the Tier A candidate threshold.

Safe fast-track target:

- `A-CHALLENGED` when evidence is promising but freshness/depth/coverage is incomplete.
- `A-WATCH` when thesis is interesting but entry/depth is not ready.
- `A-READY` only after current quote TTL, full-answer/source freshness, Tier A coverage/depth, confidence, and authority-boundary checks are clean.

Unsafe fast-track target:

- Directly to decision-grade.
- Directly to customer output.
- Directly to paper/live order readiness.
- Directly to capital deployment approval.

Recommended rule: fast-track should trigger the full pass, not skip it.

Full pass should include:

- Fresh quote and price/band/stop context.
- Tier-weighted freshness resolver.
- WF84 data-plane currentness check.
- WF85 full-answer/card freshness where applicable.
- Tier A coverage/depth gate.
- Competitive/thesis/invalidation review.
- Authority false flags.
- Event ledger entry with source hashes and gate verdicts.
- Owner-facing review packet only if the gates support review.

## Parallel Audit Synthesis

### DeepSeek Review

DeepSeek correctly identified:

- Six promotions into Tier A, all to `A-CHALLENGED`.
- The routing system permits fast elevation, but safety gates keep the result challenged.
- There is a producer/consumer clarity gap between current rolling movement and append-only local-day event history.
- ETF/sector-fund names need a more appropriate evidence model than single-company fundamentals.
- Stale/freshness burden is still material for Tier A review.

DeepSeek finding rejected:

- DeepSeek claimed the Tier A depth/coverage scripts were missing. That is false against the live workspace. The scripts exist as:
  - `scripts\tier_a_depth_repair_phase_executor.py`
  - `scripts\tier_a_trade_grade_coverage_gate.py`
- They are not named with a `wf78_` prefix. Both validate.

### Kimi Code Audit

Kimi's code findings were stronger and materially actionable:

- `A-READY` can still be driven by stale Tier A final promotion packets.
- `finance_sql_canon_access.py` treats `auto_tier='Tier A' AND auto_state='A-READY'` as the production answer definition, without requiring current freshness/coverage/depth/decision-grade proof.
- Competitive B-to-A promotion accepts field-presence heuristics and should require stronger WF85/full-answer parity, source hashes, and coverage/depth proof before emitting router-consumable Tier A eligibility.
- The coverage gate sees 19 SQL/data-plane Tier A rows while the live router has 25 Tier A rows. Missing from the SQL/data-plane gate cohort: `PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`.
- Weighted freshness needs explicit TTL windows per depth class. "Current" should not mean merely "field exists."
- Movement events should include freshness/depth/coverage verdicts and immutable source hashes.
- Startup/status should expose Tier A proof posture, unresolved weighted freshness, stale Tier A promotion packets, and router-vs-SQL cohort mismatch.

Main-session verification:

- The stale-packet issue is real. `tmp/wf78-tier-a-final-promotion-packet.json` was generated `2026-06-05T19:52:03Z`; its embedded quote timestamps are `2026-06-05T16:50:46Z`; it still lists `GOOG`, `NVDA`, and `VRT` as eligible for auto Tier A routing.
- The current gate says `decision_grade_allowed_count=0`.
- Therefore production-answer routing should be tightened before we treat `A-READY` as anything more than a review classification.

## Findings

### P1 - Stale Promotion Packet Can Preserve A-READY

Current `GOOG`, `NVDA`, and `VRT` `A-READY` posture is tied to a stale Tier A final promotion packet from 2026-06-05. That packet should not be able to preserve production-answer eligibility without fresh TTL proof.

Risk: stale routing evidence can look fresher than it is.

Recommended fix: hard quote/source TTL checks before any row can become or remain `A-READY`.

### P1 - Production Answer Definition Is Too Weak

`finance_sql_canon_access.py` currently uses Tier A plus `A-READY` as the production answer set. The live gate says decision-grade allowed count is zero.

Risk: consumers may treat a routing state as decision-grade readiness.

Recommended fix: production answer eligibility must require `A-READY`, current quote/full-answer freshness, coverage/depth green, `decision_grade_claim_allowed=true`, and authority flags false.

### P1 - Router Cohort And SQL/Data-Plane Cohort Are Misaligned

Live router Tier A count is 25. Coverage/data-plane gate sees 19. The six new Tier A names are not yet part of the SQL/data-plane Tier A cohort.

Risk: one surface says "Tier A," another validates a smaller set.

Recommended fix: coverage gate should compare the live auto-router Tier A cohort against SQL/data-plane Tier A and fail or warn on mismatch.

### P2 - Fast-Track Needs A Formal A-NOMINEE/A-CHALLENGED Contract

Fast-track is useful, but the system should make the intermediate state explicit.

Risk: a fast-track promotion may be misunderstood as a fully reviewed upgrade.

Recommended fix: create a formal `A-NOMINEE` or `A-CHALLENGED_FAST_TRACK` lane that always triggers the full freshness/depth pass and owner-review packet before `A-READY`.

### P2 - ETF/Sector Funds Need Different Evidence Families

`PAVE`, `VAW`, `VXUS`, `XLF`, and `XLI` are not single-company equities. The confidence gate correctly forces challenged posture, but the evidence model should reflect ETF/sector-fund reality.

Risk: sector/fund exposure can be evaluated with the wrong evidence families.

Recommended fix: add ETF/fund evidence requirements: sector/macro regime, holdings/constituent concentration, flow/relative-strength proxy, fee/liquidity profile, overlap with existing exposure, and band/stop posture.

### P2 - Movement Ledger Needs Two Counts

The daily movement ledger's `moved_today_count=1` is current-delta truth. The append-only event ledger's local-day event count is 12. Both are true, but the naming is confusing.

Risk: review can undercount actual day movement.

Recommended fix: expose `current_delta_moved_count` and `local_day_event_count` separately.

### P2 - Event Ledger Should Carry Gate Verdicts

Current event rows include source artifacts and hashes, but not the full gate verdict set.

Risk: historical review has to reconstruct why a move was allowed.

Recommended fix: include freshness verdict, depth verdict, coverage verdict, confidence verdict, source timestamps, and authority flags in every promotion event.

## Parallel Redesign Plan

### Lane 0 - Immediate Truth Labeling

Goal: prevent review users from misreading today's movements.

Work:

- Rename/render `moved_today_count` as current rolling delta.
- Add local Phoenix-day event count and promotion count from the append-only event ledger.
- Put six local-day Tier A promotions in the next review packet with `A-CHALLENGED` status.

Acceptance:

- Status/review packet clearly distinguishes current delta from local-day history.
- No finance canon, portfolio, cash, sizing, risk, or execution mutation.

### Lane 1 - A-READY Freshness TTL Gate

Goal: stale packets cannot preserve `A-READY`.

Work:

- Add quote/source TTL requirements to Tier A final promotion packet consumption.
- If packet age or quote age is stale, route to `A-WATCH` or `A-CHALLENGED`, not `A-READY`.
- Add tests for stale `quote_time_utc`.

Acceptance:

- Stale 2026-06-05 packet cannot produce current `A-READY`.
- Fresh packet can produce `A-READY` only when all required gates pass.

### Lane 2 - Production Eligibility View

Goal: SQL production-answer routing requires real proof, not state label alone.

Work:

- Replace or supplement `auto_tier='Tier A' AND auto_state='A-READY'` with a validated production-eligibility view.
- Join or consume proof from weighted freshness, Tier A coverage/depth, confidence, and decision-grade gate.
- Keep legacy production answer lookup explicitly labeled compatibility-only.

Acceptance:

- `production_answer_tickers()` excludes A-READY rows when `decision_grade_allowed_count=0`.
- Tests prove production answer count cannot exceed proof-allowed count.

### Lane 3 - Router/Coverage Cohort Reconciliation

Goal: live auto-router Tier A and SQL/data-plane Tier A cannot silently diverge.

Work:

- Add cohort comparison to `tier_a_trade_grade_coverage_gate.py`.
- Surface missing names: `PAVE`, `VAW`, `VXUS`, `WMB`, `XLF`, `XLI`.
- Decide whether mismatch is warning or blocker by consumer type.

Acceptance:

- Gate emits explicit mismatch verdict.
- Startup/status includes compact mismatch posture.

### Lane 4 - Fast-Track Contract

Goal: make opportunity-driven Tier A promotion safe and repeatable.

Work:

- Define fast-track source states and allowed target states.
- Allow C/B -> `A-CHALLENGED` on thesis/opportunity/entry evidence.
- Require full pass before A-READY: quote TTL, band/stop, WF84/WF85 freshness, confidence, coverage/depth, authority false flags.
- Add ETF/fund-specific evidence families.

Acceptance:

- Fast-track cannot set decision-grade/customer/capital/execution flags.
- ETF/fund names cannot be treated as single-equity fundamentals.

### Lane 5 - Event Ledger Enrichment

Goal: make every movement auditable without reconstructing state later.

Work:

- Add source proof hashes, gate verdicts, freshness timestamps, and authority flags to promotion events.
- Store prior snapshots separately from rolling `tmp` output.
- Add regression coverage for event rows.

Acceptance:

- A promotion event explains why the route changed and what was still blocked.

### Lane 6 - Status/Startup Surface Upgrade

Goal: shallow status cannot imply readiness from tier counts alone.

Work:

- Add Tier A proof posture to status/startup/future surfaces:
  - A-READY count
  - decision-grade allowed count
  - unresolved weighted freshness count
  - stale promotion packet state
  - router-vs-SQL cohort mismatch
  - authority false flags

Acceptance:

- "Status?" shows whether Tier A is review-ready, decision-grade-ready, or blocked.

### Lane 7 - Regression Tests And Eval Cases

Goal: make today's failures durable.

Tests/evals:

- Stale Tier A final packet cannot create A-READY.
- Competitive gate cannot emit auto Tier A eligibility from stale/missing decision cards.
- SQL production answer excludes A-READY rows when coverage/depth/freshness proof is blocked.
- Coverage gate warns/blocks on router-vs-SQL Tier A mismatch.
- Event ledger promotion row includes gate verdicts.
- Status card renders Tier A proof posture.

## Recommended Next Action

Do not change ticker tiers manually. Open a narrow implementation lane for Lane 1 and Lane 2 first:

1. Stop stale packet preservation of `A-READY`.
2. Make SQL production-answer eligibility require current proof.

Then do Lane 3 and Lane 6 so status surfaces show the truth. After that, formalize the fast-track contract and event-ledger enrichment.

This keeps the useful part of the system: rapid non-capital opportunity routing. It removes the dangerous part: letting a route label look like decision-grade readiness.

## Boundary

This review is non-capital and review-only. It does not approve or recommend any trade. It does not authorize paper/live orders, brokerage/account action, money movement, portfolio/canon-note mutation, cash/sizing/risk mutation, customer output, or owner approval inference.
