---
name: "wf67-paper-trading-operator"
description: "Clarify cadence vs order approval"
---

# Proposed Update: Assisted Cadence And Maturity Semantics

Add this section to `wf67-paper-trading-operator` after the current standing approval or pre-submit checklist.

## Assisted Paper Cadence Is Not Order Approval

Randall's assisted-paper cadence approval authorizes Veritas to prepare for 1-2 small assisted paper maturity reps per week during fresh-gate windows. It does not approve any specific paper order.

Every exact paper submit/cancel/sell still requires:

- exact ticker, side, quantity/notional, order type, TIF, and limit/market terms
- fresh WF67 request artifact or order card
- fresh short-lived kill switch for the actual execution window
- rerun guard validation
- redacted audit path
- main-session notification posture
- Randall exact approval for that specific order/action

Cadence may justify preparing review packets and watching for fresh windows. Cadence must not trigger an order.

## Assisted Attempt Versus Maturity Rep

Classify paper outcomes conservatively:

- `attempt`: a submitted owner-approved paper order attempt.
- `terminal_attempt`: an attempted order with terminal broker state such as expired, canceled, rejected, or filled.
- `filled_order`: broker reports fill/partial fill according to the classifier.
- `maturity_rep`: a clean filled/reconciled proof category accepted by the workflow.
- `filled_round_trip`: a full buy/sell lifecycle with reconciliation proof.

Expired, unfilled, rejected, canceled, unresolved, or stale attempts are telemetry only. They do not count as maturity reps and do not satisfy reconciliation maturity.

## Blocked Automation

WF67/WF86/WF87 paper automation must not add:

- order resubmission automation
- cadence-triggered orders
- autonomous kill-switch creation or clearing
- autonomous phase promotion
- paper-to-live promotion
- owner approval inference from a clean card, score, alert, shadow decision, or cadence state

When in doubt, prepare the exact approval card and stop for Randall.
