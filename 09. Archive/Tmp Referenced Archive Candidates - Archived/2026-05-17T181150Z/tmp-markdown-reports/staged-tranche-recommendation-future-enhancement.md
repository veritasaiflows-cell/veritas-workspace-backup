# Future Enhancement - Staged Tranche Recommendation Engine

Status: captured / deferred; do not build without explicit resume approval.
Captured: 2026-05-12

## Idea

Add a review-only staged deployment recommendation object for owner-promoted names such as MSFT.

Example output:
- starter tranche while inside current band but below 200-day
- add tranche after support reclaim or upper-band hold
- add tranche after 20-day / short-term trend improvement
- final tranche only after clean 200-day reclaim/hold

Use planned allocation as the denominator, not total portfolio.

## Authority boundary

Allowed:
- recommend staged percentages and trigger conditions
- flag concentration, chase risk, stop breach, stale sources, earnings proximity, and missing owner approval
- output review-only JSON/Markdown packets

Blocked:
- no trades or account actions
- no inferred owner approval
- no live allocation mutation
- no sizing, cash, sleeve, risk-rule, or execution-entitlement mutation
- no auto-promotion of unapproved names

## Resume condition

Revisit only after WF58 capital recommendation Markdown/validator/current-window wiring is complete and several normal morning/post-close/Sunday cycles prove the auto-band/reference-band/dashboard paths are stable.
