# Regime Change Alert Protocol

## Purpose

Define when macro evidence should trigger a regime alert and how that alert changes recommendation context. This protocol does not maintain portfolio posture, cash, exposure, positions, or execution state.

## Regime states

### Baseline

Late-cycle, restrictive-policy, resilient-growth, selective risk-on. Recommendation implication: favor evidence quality, durable businesses, explicit invalidation, and no-chase discipline.

### Transition

One or more material thresholds deteriorate or improve while the full picture remains mixed. Recommendation implication: lower confidence, flag affected sectors and theses, require fresher evidence, and suppress aggressive timing language.

Example triggers include a material unemployment trend change, weak GDP, renewed curve inversion, sustained VIX elevation, credit-spread widening, explicit central-bank policy shift, a large oil shock, or a large dollar move.

### Broken

Multiple confirmed threshold breaches or one acute shock changes the operating environment. Recommendation implication: issue a high-priority regime alert, reassess every affected thesis and band, surface downside first, and suppress normal recommendation labels until evidence stabilizes.

Examples include recession evidence, sustained severe volatility, a credit event, emergency policy action, or a major geopolitical or supply shock.

## Update sequence

1. Record the trigger, timestamp, source, threshold, and confidence in the daily memory log.
2. Update `02. Markets/Macro Regime Dashboard.md` and the relevant source proof.
3. Reassess affected thesis, catalyst, band, invalidation, and alert states in `03. Alerts and Recommendations/`.
4. Refresh the bounded alerts chain and verify guarded SQL, quote proof, controller, and digest.
5. Update affected research notes and the current weekly alert/recommendation digest.
6. Record an audit summary when the change is material and durable.

## Alert implications

| Regime state | Recommendation posture | Freshness requirement | Alert treatment |
|---|---|---|---|
| Baseline | Normal review discipline | Current for the stated market session | Standard band/no-chase/invalidation states |
| Transition | Lower confidence and narrower claims | Refresh affected macro and ticker evidence | Elevate catalyst, thesis-change, and freshness alerts |
| Broken | Downside-first; suppress ordinary confidence | Current primary evidence required | High-priority regime and invalidation review |

## Trigger and declaration authority

Scripts may surface threshold evidence. Veritas may issue a transition alert from verified evidence. A durable broken-regime declaration requires either Randall's direction or two independent confirmed threshold breaches in the same review window.

Generated scores or dashboards are evidence only; they do not declare authority by themselves.

## Recovery

Return from a broken state requires resolution of primary breaches, a sustained stabilization window, deliberate re-declaration in the Macro Regime Dashboard, and reassessment of affected thesis/band records. Do not silently drift back to baseline language.

## Boundary

No regime state authorizes or maintains holdings, sleeves, allocations, weights, sizing, cash, rebalancing, simulated positions, capital action, orders, accounts, money movement, or execution.
