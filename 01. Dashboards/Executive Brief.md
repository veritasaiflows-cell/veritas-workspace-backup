# Executive Brief

## Bottom Line

Veritas is an alerts-and-recommendations OS. Its finance job is to keep evidence, market context, alert levels, thesis state, freshness, and recommendation review clear and current. It does not maintain account or execution state.

## Fast Read Order

1. Veritas Command Center: `http://127.0.0.1:8765`
2. `03. Alerts and Recommendations/Alert Operations Board.md`
3. `03. Alerts and Recommendations/Alert Trigger Policy.md`
4. `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
5. `04. Research/Coverage Universe.md`
6. `02. Markets/Macro Regime Dashboard.md`
7. `07. Risk/Risk Rules.md`

## Current Trust Routes

- Alerts/recommendations chain: `python scripts/run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
- Guarded SQL: `python scripts/finance_sql_canon_access.py --write --validate`
- Pivot boundary: `python scripts/alerts_os_pivot_validator.py --write --validate`
- Workflow lookup: `python scripts/workflow_router.py WF## --answer summary`

## Output Standard

Every material recommendation should expose the ticker, timeframe, evidence date, freshness, confidence, thesis, base/bull/bear view, risks, alert-band and invalidation context, uncertainty, and Randall's decision point.

## Authority Boundary

Dashboards and generated proof are review-only. They do not grant capital, order, account, money-movement, external-delivery, or live/simulated execution authority and do not become maintained account state.
