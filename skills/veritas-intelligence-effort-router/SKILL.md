---
name: "veritas-intelligence-effort-router"
description: "Route finance work through guarded alert freshness and non-executing recommendation review."
---

# Veritas Intelligence Effort Router

## Purpose

Choose the smallest trustworthy route for finance alerts and non-executing recommendations. This skill allocates research effort; it grants no canon mutation, capital, order, account, brokerage, money-movement, or execution authority.

## Active Truth Route

Use these sources in order:

1. Active canon in `03. Alerts and Recommendations/`.
2. Guarded SQL validation:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
```

3. Current explicit quote proof and alert evaluation:

```powershell
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

4. `tmp/alert-level-freshness-controller.json` for ticker-level alert state.
5. `tmp/finance-alert-os-digest.json` for ranked review context.
6. Current WF84 evidence and WF85 non-executing recommendation cards only when their sources, freshness, and authority flags are clean.

Indexes, caches, dashboards, old workflow packets, and archived files are routing or history only. They never outrank active canon.

## Effort Bands

- Band 0 — explain a concept from current canon without refresh.
- Band 1 — read the current controller/digest and answer.
- Band 2 — refresh the four-stage alerts chain because required proof is missing or stale.
- Band 3 — perform bounded source-open research for a material recommendation, then reconcile it to active canon.
- Band 4 — use implementation and independent QA governance when code, contracts, cron, SQL lineage, or skills change.

Do not run a broad legacy finance stack merely because more artifacts exist.

## Alert States

Use only these operating states:

- `recommendation_review`
- `band_entry`
- `near_band`
- `no_chase`
- `invalidation_alert`
- `thesis_change`
- `catalyst_alert`
- `freshness_decay`
- `monitor_only`
- `suppressed`

A state is an observation or review route, never an action instruction.

## Recommendation Contract

For a material ticker recommendation, supply:

- ticker and timeframe
- current evidence date and market-session context
- freshness and confidence
- thesis and material catalyst
- base, bull, and bear cases when evidence supports them
- risks and uncertainty
- current price versus the written alert band
- invalidation context
- no-chase or freshness blocker when present
- fit with Randall's stated objectives and limits
- Randall's decision point

Owner-provided objectives or limits may inform the current answer transiently. Never store them as system-maintained holdings, sleeves, allocations, weights, sizing, tranches, cash posture, simulated positions, or account state.

## Freshness Rules

- Current-last-completed-session data is valid closed-market evidence when the market calendar confirms it.
- Market-hours claims require current quote proof appropriate to the decision consequence.
- Stale, missing, conflicted, or hash-mismatched inputs emit `freshness_decay`; they must not be hidden to make the chain green.
- Static bands are read from guarded canon. Do not silently re-derive or auto-apply them.
- A structurally green chain proves only that its checks passed, not that the recommendation is correct.

## Automation Allowed

Automate bounded research, source lineage checks, quote proof, freshness classification, deduplication, alert routing, rankings, review packets, and blocker explanations.

Use helpers only with exact outputs, read/write scope, stop lines, and validation. Main verifies their proof before user-facing judgment.

## Retired Routes

Do not invoke or recreate:

- former portfolio board/snapshot/config maintenance
- sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, or rebalancing state
- deployment/trade-grade gates or capital-priority queues
- simulated account, request-card, order, reconciliation, or execution routes
- WF56/WF58/WF63/WF64/WF67/WF86/WF87 operational paths

Historical artifacts may be inspected read-only for audit.

## Stop Lines

Stop or downgrade confidence when provenance is unresolved, freshness is inadequate, material downside or invalidation is missing, active canon conflicts, or a request crosses into capital, order, account, brokerage, money movement, execution, external delivery, or authority expansion.

No alert, rank, confidence label, card, validator, cron run, or clean proof implies Randall's approval.
