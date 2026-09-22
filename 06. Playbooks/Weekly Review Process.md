# Weekly Alerts and Recommendations Review

## Purpose

Keep market understanding, alert state, evidence freshness, and recommendation quality current.

## Steps

1. Run `python scripts/run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate`.
2. Review `02. Markets/Macro Regime Dashboard.md` and preserve all source warnings.
3. Review `04. Research/Coverage Universe.md` for evidence gaps and suppressed names.
4. Reconcile results with `03. Alerts and Recommendations/Alert Trigger Policy.md`, guarded SQL `reference_levels` / the current alert controller, and `Alert Bands and Invalidation Register.md` for thesis only.
5. Rank material recommendation reviews in `05. Intelligence/Thesis Ranking and Leadership Board.md`.
6. Update `MEMORY.md` only when a durable preference, rule, or decision changed.

## Questions

- What materially changed in macro, leadership, catalysts, or thesis evidence?
- Which names entered a band, moved near a band, became no-chase, or crossed an invalidation threshold?
- Which evidence is stale, conflicting, or too weak for a material recommendation?
- What should be monitored, suppressed, or presented to Randall for a decision?

## Boundary

The weekly review produces alerts and non-executing recommendations only. It does not maintain account, capital, order, execution, or simulated-account state.
