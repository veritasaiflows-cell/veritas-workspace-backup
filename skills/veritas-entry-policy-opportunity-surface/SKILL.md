---
name: "veritas-entry-policy-opportunity-surface"
description: "Surface alert opportunities from guarded bands without deployment semantics."
---

# Veritas Alert Opportunity Surface

## Purpose

Prevent a valid threshold, catalyst, thesis change, or freshness issue from being hidden by ranking. This skill is a thin visibility router over existing guarded evidence; it does not calculate a second technical truth layer.

## Sources

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

Read the guarded SQL `reference_levels` proof, explicit quote snapshot, alert-level freshness controller, and current digest. Live numeric levels come from SQL. The Alert Bands markdown register is thesis/interpretation only and is never re-derived here.

## Visibility Rule

A symbol may surface for review when current evidence shows:

- Band entry
- Near band
- No chase
- Invalidation alert
- Thesis change
- Catalyst alert
- Freshness decay
- a conflict that requires evidence repair

Attention tier or theme ranking may order the queue but must not suppress a material current alert.

## Thin Queue Contract

Each row contains:

- symbol
- alert state
- timeframe
- quote and evidence timestamp
- threshold/invalidation context and lineage
- freshness and confidence
- thesis/catalyst summary
- material risks and uncertainty
- recommendation-review reason
- source artifacts
- Randall's decision point, when needed

If sources conflict, emit a conflict warning and Suppressed or Freshness decay. Do not recompute moving averages, bands, or invalidation thresholds to hide the conflict.

## Recommendation Gate

Visibility is not endorsement. A non-executing recommendation requires current evidence, valid lineage, clear timeframe, thesis, risks, uncertainty, and an explainable state. No chase, invalidation, event risk, or stale evidence may keep a name visible while suppressing a positive recommendation.

## Boundary

No portfolio roles, capacity, sleeves, holdings, positions, allocation, weights, sizing, tranches, cash deployment, order alerts, request packages, paper state, account reads, or execution routes. Owner-provided objectives may be considered transiently and labeled as owner context.

## Acceptance

- current material alerts are visible regardless of secondary ranking
- stale/conflicting rows are truthfully degraded
- every numeric level has guarded lineage
- no duplicate technical calculation is introduced
- no output implies capital or execution approval
- alerts OS validator and direct chain remain green
