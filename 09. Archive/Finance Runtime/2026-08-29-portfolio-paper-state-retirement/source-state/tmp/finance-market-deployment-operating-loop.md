# Finance Market Deployment Operating Loop

- Generated UTC: `2026-08-28T19:07:02Z`
- Final state: `review_opportunity`
- Operator action: `MAIN_SESSION_REVIEW`
- Next safe action: Review Tier A opportunity/drift rows; no approval is inferred.
- Market window: `late_session`
- Current deployable labels allowed: `True`
- Cross-surface reconciliation: `aligned`
- Determinism guard: `ok`

## Schedule
- `05:35` Macro - Energy and Geopolitical Inputs Refresh: Refresh macro/energy/geopolitical inputs before finance scoring.
- `05:58` Finance - Sector Allocation Decision Matrix: Refresh sector context before ticker-level deploy/wait review.
- `06:05` Finance - Weekday Morning Review Refresh and WF68 producer: Refresh morning review chain, alert quote proof, band/stop alerts.
- `06:08` Finance - WF78 Daily Freshness and Promotion Proof: Move derived Tier A/B/C routing and repair queues without capital authority.
- `06:20` Finance - WF78 Open-Ready Owner Review Proof: Prepare owner-review context for Tier A/B candidates.
- `06:35-06:42` Open-ready cards, WF85 radar, WF87 daylight gates: Open-settling proof only; suppress current deployment labels until the first settled probe.
- `06:42` Finance - Tier A Intraday Opportunity Probe: First fresh-price opportunity probe after the open has settled.
- `07:14` Finance - Tier A Confirmation Opportunity Probe: Confirm that early deployable/watch labels survive a second fresh quote pass.
- `08:00-08:50` WF68/WF87 intraday gates: Mid-morning alert and autonomy readiness proof.
- `12:07` WF87 gate and late-session Tier A probe: Final opportunity/risk/drift check during the last regular-session hour.
- `13:10-15:00` Post-close alerts, refresh, reconciliation, control digest: Close the loop, update quotes/cards, paper positions, shadow outcomes, and cron proof.

## Tier And Freshness
- Tier counts: `{'Tier A': 12, 'Tier B': 49, 'Tier C': 239}`
- Lane-qualified tier counts: `{'Tier A Equity': 10, 'Tier A Sleeve': 2, 'Tier B Equity': 49, 'Tier C Commodity': 1, 'Tier C Equity': 230, 'Tier C Rates/Income': 1, 'Tier C Sleeve': 7}`
- Tier states: `{'A-CHALLENGED': 9, 'A-WATCH': 3, 'B-CANDIDATE': 45, 'B-CHALLENGED': 4, 'C-CANDIDATE-REPAIR': 2, 'C-MONITOR': 236, 'C-REPAIR': 1}`
- WF85 timing states: `{'repair_first': 53, 'blocked_below_stop_or_invalidation': 8}`
- Quote freshness classes: `{'review_only_price_context': 61}`
- Market-hours readiness: `READY`

## Opportunity Probe
- Recommended action: `REVIEW`
- New review opportunities: `1`
- Clean paper-prep candidates: `0`
- Near deployment blocked: `0`
- No-chase: `4`
- Invalidation/risk: `0`
- Paper drift: `4`

## Scenario Context
- Status: `ok`
- Primary analogs: `['2023-2024 soft-landing / broadening attempt', '1980-1982 Volcker tightening / recession', '1994 bond/rate shock', '2022 inflation / rate shock']`
- Stress/caution analogs: `['1973-1974 oil shock / stagflation bear market', '1987 crash', '1990 Gulf War / recession shock', '1998 LTCM / emerging-market stress', '2007-2009 Global Financial Crisis']`
- Use: scenario context only; no probability, ranking, sizing, approval, or execution authority.

## Guardrail
- Review/prep only. Exact Randall approval and WF67 guard proof remain required before any paper action.
