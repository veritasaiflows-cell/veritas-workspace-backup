# Defense + Capital-Base Integration Summary — 2026-05-18

## Scope

Bounded workspace portfolio/canon maintenance only: sizing, sleeve, and sector-posture accounting in Portfolio Snapshot and `tmp/portfolio-config.json`.

No live trade, paper order, account action, brokerage action, money movement, cash-target change, risk-rule change, or execution entitlement was granted.

## Source packets

- `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase3-owner-review-historical-md/defense-sleeve-resolution-proposal-2026-05-18.md`
- `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase3-owner-review-historical-md/capital-base-sizing-proposal-2026-05-18.md`
- `tmp/defense-capital-base-integration-proposal-2026-05-18.json`
- `tmp/portfolio-pro-forma-risk-validation.json`

## Applied workspace model-accounting decisions

| Area | Applied state |
|---|---|
| LMT | `0% active / prior 10% suspended`; not counted as active Defense exposure while below-stop repair |
| KTOS | `2%` active speculative placeholder only; not a core Defense substitute |
| RTX | `0%` watch/repair; no replacement role |
| ITA | `0% active`; conditional future planning cap `5%` only after look-through acceptance and gates |
| Defense sector row | `2% active` via KTOS only; `7%` pro-forma if future ITA 5% is accepted; below 25% sector cap |
| Capital base overlay | $5k/$10k planning assumes 10% cash retained, fractional shares by default, and two-tranche sizing; GS is impractical for intended Tier 2 sizing without fractions or explicit re-tiering |

## Boundaries

- Draft/model weights are planning surfaces, not live allocations.
- Suspended LMT weight is not cash movement and not active allocation authority.
- ITA look-through acceptance remains required before any active weight or paper order.
- WF67 guardrails and exact owner order terms remain required before paper submit/cancel.
- Live trading/account/money movement remains blocked.

## Acceptance proof expected

- Portfolio pro-forma risk validator clean for the integration JSON.
- Portfolio config strict validator clean.
- Deployment/trigger surfaces regenerate cleanly.
- Canon drift gate clean after the Snapshot/config sync.
- Board-canon guardrail has no critical findings; warning-only risk alerts remain acceptable when they reflect true below-stop states.
