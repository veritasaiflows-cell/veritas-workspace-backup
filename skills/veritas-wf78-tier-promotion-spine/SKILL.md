---
name: "veritas-wf78-tier-promotion-spine"
description: "WF78 current tier authority and tier ladder."
---

# WF78 Tier Promotion Spine

## Purpose

Operate WF78 as the non-capital attention and promotion spine for the finance OS. Keep tier answers model-safe by separating current tier membership from repair/readiness, audit-only labels, legacy/shadow migration, and paper-readiness guardrails.

WF78 may automate derived non-capital research, routing, tier state, repair packets, and review-only card preparation. It never grants capital deployment, trading, paper/live execution, brokerage/account action, money movement, portfolio/canon mutation, or owner approval.

## Production Scope Posture

WF78 production scope must be SQL-first and dynamic, not a preserved legacy list.

- Dynamic production-review scope: current SQL/router Tier A and Tier B names. This is attention/routing scope only.
- Strict production-grade answer scope: proof-joined SQL Tier A/A-READY rows only when router, coverage, confidence, freshness, and authority gates all clear.
- Legacy 42: historical compatibility only. It must not be used as active production, readiness, or repair authority.
- Empty strict production-grade scope is valid and means wait/fail-closed, not fallback to the old 42.

Do not hardcode roster counts in skill doctrine. Current Tier A/B/C membership must come from live router artifacts.

## Current Truth Rule

Use these as current non-capital routing proof:

- `tmp\wf78-auto-tier-routing.json`
- `tmp\wf78-clean-tier-roster.json`
- `tmp\canonical-finance-data-plane.json` after WF84 refresh

Answer current tier membership only from `tmp\wf78-auto-tier-routing.json` and `tmp\wf78-clean-tier-roster.json`.

Use `true_tier_a`, `true_tier_b`, and `true_tier_c` from the clean roster for direct user-facing lists when available.

Treat `lane_tier` and `review_lane` as the forward route. Flat `auto_tier` remains compatibility for older consumers.

Treat labels such as `A-READY`, `A-CHALLENGED`, `A-REPAIR`, `A-WATCH`, `B-CANDIDATE`, `B-VALIDATED`, `B-STALE`, `C-CANDIDATE`, `C-CANDIDATE-HOLD`, `C-CANDIDATE-REPAIR`, and `C-MONITOR` as tier states/substates inside their parent tier, not separate tiers.

## Truth-Layer Map

Before answering or generating WF78 tier-cleanup work, read `tmp\wf78-truth-layer-map.json` when present.

The map classifies:

- Current authority: `tmp\wf78-auto-tier-routing.json`, `tmp\wf78-clean-tier-roster.json`
- Repair/readiness: `tmp\wf78-tier-promotion-review-gate.json`, `tmp\deployment-readiness-surface.json`, `tmp\wf78-deployment-readiness-review.json`
- Audit-only labels: `tmp\wf78-tier-label-sync-preview.json`, `tmp\wf78-tier-label-decision-register.json`
- Legacy/shadow migration: `tmp\wf78-legacy-42-tier-migration-planner.json`, `tmp\wf78-legacy-42-tier-state-shadow.sqlite`
- Execution guardrails: `tmp\alpaca-paper-readiness\*`

## Forbidden Merges

Do not merge these layers into current Tier A/B/C membership:

- promotion review queue status
- deployment readiness/actionability status
- label-sync preview labels
- legacy/shadow migration counts or parity language
- paper readiness or Alpaca execution guardrail artifacts
- customer-output readiness labels
- approval-card readiness labels

If surfaces disagree, answer from the current authority layer and route the stale/conflicting surface to repair.

## Tier Ladder

- Tier C: thin monitor by default. Spend only cheap monitor effort unless a named attention trigger, promotion candidate, catalyst, or repair signal exists.
- Tier B: research bench. Requires source-open/owner-lineage repair, quote/band context, fundamentals, analyst/earnings/technical coverage, and promotion evidence before scarce Tier A attention.
- Tier A: scarce decision-review bench. Requires current quote, current band/stop, evidence freshness, source-open status, timing gate, and authority proof before owner-facing approval-card review.

Tier A does not mean deployable. A-READY is routing readiness unless the depth and decision gates clear.

## Tier A / A-READY Depth Gate

Before any Tier A readiness, A-READY, production answer, trade-grade coverage, or Retail-Grade Truth Routing claim, run or inspect:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\tier_a_trade_grade_coverage_gate.py --write --validate
python scripts\tier_a_depth_repair_phase_executor.py --write --validate
python scripts\finance_production_grade_policy_gate.py --write --validate
```

Interpretation:

- `coverage_floor_ok=true`: structural packet floor exists.
- `depth_ready_a_ready=false`: A-READY names remain review-only repair candidates.
- `decision_grade_allowed_count=0`: no decision-grade claims are allowed.
- `customer_output_allowed=false`: no retail/customer output.
- `dynamic_production_review_candidate_count>0`: Tier A/B names can be routed for review and repair, but this is not strict production-grade answer eligibility.
- `production_grade_candidate_count=0`: strict production answer scope remains empty/fail-closed.

Use `tmp\tier-a-depth-repair-phase-execution-packet.json` to route work:

- Phase A: cohort alignment
- Phase B: source-open thesis synthesis
- Phase C: quote/band freshness
- Phase D: competitive moat structuring
- Phase E: sector/proxy context
- Phase F: response contract, skills, and retail truth-routing integration

## Required Command Chain

Run as needed in this order for current WF78/WF84/WF85 routing work:

```powershell
python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate
python scripts\wf78_auto_tier_router.py --write --validate
python scripts\wf78_clean_tier_roster.py --write --validate
python scripts\wf78_truth_layer_map.py --write --validate
python scripts\wf78_tier_semantics_guard.py --write --validate
python scripts\wf78_daily_freshness_loop.py --phase tier_routing --write --validate
python scripts\canonical_finance_data_plane.py --write --write-db --validate
python scripts\trade_grade_os_freshness_cron_runner.py --write --write-md --validate
python scripts\trade_grade_decision_cards.py --write --validate
python scripts\wf85_deployment_timing_gate.py --write --validate
python scripts\cron_freshness_spine.py --write --validate
```

`wf78_tier_semantics_guard.py` must fail if any non-authority layer can decide current membership, if the truth-layer map is missing/blocked, if tier states are confused with membership, or if capital/trade flags widen.

## Stale / Historical Surfaces

Old Tier B evidence lineage, legacy 42 migration packets, deprecated recommendation/adjudication surfaces, stale owner packets, and old source-capture packets are history/compatibility only unless a current workflow explicitly reactivates them.

Prefer fresh quote/band repair context, current router outputs, current SQL-canon guard, WF84 data plane, and WF85 decision-card/timing gates.

## Boundary

This procedure is review-only/non-capital. It grants no universe/canon/portfolio/cash/sizing mutation, no production answer-path promotion by itself, no customer output, no paper/live submit/cancel/sell, no brokerage/account action, no capital deployment, and no owner approval inference.

Paper order preparation routes through WF67 and still requires exact Randall approval.
