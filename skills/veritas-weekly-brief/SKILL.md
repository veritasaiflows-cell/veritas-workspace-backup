---
name: "veritas-weekly-brief"
description: "Build the weekly alerts-and-recommendations intelligence brief."
---

# Veritas Weekly Alerts Brief

## Purpose

Turn the current guarded evidence set into a concise weekly market-intelligence and recommendations map. Scripts stage evidence; the brief integrates judgment without creating account or execution state.

## Refresh

```powershell
python scripts\run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate
```

Inspect:

- guarded SQL validation
- explicit quote snapshot and validation
- alert-level freshness controller
- weekly chain proof
- weekly digest
- current macro signal/judgment artifacts
- catalyst and earnings evidence
- `03. Alerts and Recommendations` canon

If any source is partial or stale, show that near the conclusion.

## Weekly Questions

Answer:

- What changed from the prior week?
- Which alerts are new, escalated, resolved, stale, or suppressed?
- Which names merit Recommendation review and why?
- Which names are No chase or Invalidation alert?
- What macro or catalyst risks matter next week?
- What evidence must be refreshed?
- What decision, if any, belongs to Randall?

## Output

1. weekly verdict and trust state
2. major macro/market changes
3. ranked non-executing recommendations
4. alert-state table
5. catalysts and event risk
6. thesis changes and invalidations
7. freshness/conflict queue
8. next safe automation and Randall decision points

Each recommendation includes timeframe, evidence date, freshness, confidence, thesis, base/bull/bear, risks, band/invalidation context, and uncertainty.

## Sync Rule

Update only active alerts/recommendations or intelligence notes whose owned truth materially changed. Old positioning, portfolio snapshot, execution board, and deployment artifacts are retired historical surfaces and must not be repopulated.

## Boundary

No holdings, positions, sleeves, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, account reads, or execution routes. A recommendation never implies approval.

## Verification

```powershell
python scripts\alerts_os_pivot_validator.py --write --validate
python scripts\run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate
```

Report truthful freshness degradation instead of laundering it into a green narrative.
