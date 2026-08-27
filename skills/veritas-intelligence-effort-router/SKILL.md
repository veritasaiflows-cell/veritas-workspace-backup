---
name: "veritas-intelligence-effort-router"
description: "Absorb practical opportunity next-action routing."
---

# Veritas Intelligence Effort Router

## Purpose

Route finance intelligence effort by current WF78 scarce-attention tier before spending model time, helper lanes, source-open research effort, owner attention, or practical recommendation-review effort.

This skill decides how much effort to spend, which truth surfaces to trust, and what the next non-capital recommendation-review action should be. It does not approve capital deployment, paper/live orders, brokerage/account action, portfolio/canon mutation, external/customer delivery, or owner approval.

Use this skill when Randall asks for opportunity review, ticker recommendations, candidate ranking, deployment readiness, blocker explanation, approval-card preparation, or whether something should move toward capital-deployment review. Use `veritas-response-contract` for the final Randall-facing answer shape and authority wording.

## Primary Route

For finance/ticker effort routing:

1. Run or read the SQL/JSON guard first:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
```

2. Use current WF78 lane-qualified truth for tier/routing:
   - `tmp\wf78-auto-tier-routing.json`
   - `tmp\wf78-clean-tier-roster.json`

3. Treat `lane_tier` and `review_lane` as the forward route. Flat `auto_tier` remains compatibility for older consumers.

4. Use WF84 data plane for review context after the router is fresh:

```powershell
python scripts\canonical_finance_data_plane.py --write --write-db --validate
```

5. Use WF85 cards/timing for approval-card readiness only after current routing/data proof is clean:
   - `tmp\trade-grade-decision-cards.json`
   - `tmp\trade-grade-approval-card-gate.json`
   - `tmp\wf85-deployment-timing-gate.json`

6. Use WF86/WF87 artifacts when the question is specifically about assisted decisions, shadow decisions, promotion outcomes, command-center state, or follow-on workflow queues.

7. For material Tier A, A-READY, SQL-canon production answer, trade-grade coverage, or Retail-Grade Truth Routing claims, route through the Tier A gates after the SQL-canon front door:

```powershell
python scripts\tier_a_trade_grade_coverage_gate.py --write --validate
python scripts\tier_a_depth_repair_phase_executor.py --write --validate
```

Then inspect:

- `tmp\tier-a-trade-grade-coverage-gate.json`
- `tmp\tier-a-depth-repair-phase-execution-packet.json`
- ticker-specific WF85 full answer/card/parity when naming a ticker

## Scarce-Attention Policy

- Tier A: highest attention, but not automatic deployment. Requires current quote, current band/stop, source freshness, source-open status, earnings/sector/macro gates, WF85 timing gate, and production/authority proof before owner review. If paper is involved, require WF67 guard plus fresh short-lived kill switch and exact Randall approval.
- Tier B: research bench and promotion/repair queue. Spend effort on source-open repair, owner lineage, quote/band context, fundamentals, analyst/earnings/technical coverage, and promotion evidence. Tier B does not create owner approval or execution authority.
- Tier C: thin monitor. Spend only cheap monitor effort unless an attention trigger, catalyst, repair signal, or promotion candidate exists. Do not spend Tier A depth on broad Tier C.

## Practical Next-Action Route

Use this route after the primary truth surfaces are current enough for the requested consequence level.

- **Tier A / A-READY:** run quote/band/stop reconciliation, WF85 timing gate, source freshness/source-open checks, concentration/crowding review, and paper-card readiness only when paper preparation is in scope. If clean, prepare an owner approval card with sizing/notional proposal and explicit blockers. Do not imply approval.
- **Tier B:** route to research-bench repair: source-open, owner lineage, missing band/quote context, fundamentals, analyst coverage, earnings, technical coverage, and promotion evidence. Do not produce deployment cards from Tier B unless the ticker is promoted and revalidated.
- **Tier C:** thin monitor only. Surface trigger candidates, catalyst flags, or promotion-worthy names; otherwise keep cheap watch status.

Translate machine state into practical decision labels:

- `watch-only`: useful to monitor, not worth deeper work now
- `repair-needed`: interesting but blocked by missing/stale evidence or conflicting gates
- `review-ready`: enough evidence for Randall review, not capital approval
- `assisted-ready`: decision-assist artifacts are ready for review, not approval
- `approval-card-ready`: exact owner approval card can be presented, still not approval or execution

## Approval-Card Readiness Gate

An approval-ready review card requires:

- current market-window quote proof when the market is open or the action depends on execution freshness
- current written band/stop or explicit missing-band blocker
- clean WF85 timing gate for the intended action state
- source freshness and source-open proof appropriate to the decision
- concentration/crowding and portfolio-fit context when relevant
- explicit authority boundary
- WF67 paper guard proof if paper is involved
- fresh kill switch only when execution preparation is actually in scope
- exact Randall approval before any paper action

A card can be ready for review without approving capital deployment or execution.

## Tier A Coverage / Depth Effort Rule

If the Tier A coverage floor is green but depth readiness is blocked, answer with:

- coverage floor status
- depth blockers
- unique ticker or blocker-instance denominator
- current customer/capital/execution boundary
- next repair phase

Do not run a broad source-open research pass unless Randall asks to repair specific tickers or approves a bounded helper-lane batch.

Never call Tier A trade-grade, deployable, customer-safe, approval-ready, or execution-ready solely because SQL-canon access, WF85 assembly, parity, A-READY routing, or 17/17 sections are clean.

## Historical Surface Rule

Do not use stale lineage artifacts, old Tier B evidence repair packets, old legacy-42 surfaces, or readiness-review labels as quote source or current tier authority. Use the current WF78 router, current WF84 data plane, and current WF85 generated proof.

If current surfaces conflict, downgrade confidence, name the conflict plainly, and route the repair instead of forcing a recommendation.

## Recommendation And Blocker Handoff

Use `veritas-response-contract` for final answer shape, but this skill should supply the practical recommendation state and plain-English blocker root cause.

Preferred blocker translation:

```text
<Ticker> was <positive condition>, but could not move to <target state> because <review debt/gate/source issue>. Cron/main should <automatic repair>. Randall is needed only for <capital/execution/policy decision>.
```

For serious finance recommendations, make sure the final answer has enough context for `veritas-response-contract` to state thesis/timeframe, current price versus written band when available, source freshness/confidence, base/bull/bear cases when decision-grade, entry/no-chase logic, invalidation/stop context, concentration/crowding, action state, and owner approval required for capital or execution.

## Automation Allowed

Automate non-capital ticker research, routing, tier state, repair packets, freshness classification, review packets, rankings, blocker explanations, sizing/staggering proposals for review, paper-order request drafts, and review-card preparation when validators pass.

Use bounded helper lanes for broad research, repair batches, source-open sweeps, or QA only after exact outputs, stop lines, validation proof, and writable surfaces are defined.

## Current Known Truth Split

If SQL canon `tier_routing_state` conflicts with the WF78 router, prefer the current WF78 router for live scarce-attention routing and open the narrow SQL refresh path:

```powershell
python scripts\sql_canon_tier_routing_refresh.py --write --validate
```

Apply only through the gated DB apply lane with backup/rollback and validation. Do not mutate SQL/canon state from this skill alone.

## Stop Lines

Never infer capital deployment approval, paper/live order approval, brokerage/account action, money movement, live endpoint use, customer delivery, portfolio/canon/cash/sizing/risk mutation, or owner approval.

Generated artifacts are proof/review surfaces unless an exact gated apply path says otherwise.

No recommendation label creates capital deployment approval, order submit/cancel/sell authority, live endpoint authority, account action, money movement, external delivery, portfolio/canon/cash/sizing/risk mutation, or owner approval.

Stop or downgrade confidence when sources are stale/conflicting, gates disagree, the answer would influence capital without fresh proof, a recommendation lacks downside/invalidation, approval-card preconditions are missing, or a proposed action needs Randall approval.
