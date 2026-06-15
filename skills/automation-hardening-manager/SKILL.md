---
name: "automation-hardening-manager"
description: "Add autonomous-trading hardening rules"
---

# Proposed Update: Autonomous Trading Hardening Rules

Add this section to `automation-hardening-manager` under the hardening rules for finance automation.

## Autonomous Trading Hardening Rules

When hardening WF86/WF87 or any finance workflow that could later influence paper/live execution, separate activity from maturity proof.

Required distinctions:

- Assisted paper attempt: an owner-approved order attempt that may expire, reject, cancel, partially fill, or fill.
- Terminal attempt: an attempted order with a broker-terminal status.
- Maturity rep: a clean filled/reconciled round trip or explicitly scoped proof category accepted by the workflow; expired, unfilled, rejected, canceled, or unresolved attempts do not count.
- Shadow decision: review-only would-buy/would-block evidence; it is not an order approval.
- Daylight runtime proof: market-hours proof that gates are clean while fresh quotes, bands, stops, guard, kill switch, and anomaly state are actually available.

Hardening requirements:

1. Do not promote autonomy from threshold counts alone. Require the threshold, source freshness, gate cleanliness, and reconciliation maturity to be true together.
2. Do not classify fail-closed nighttime or after-hours blockers as daytime runtime blockers unless a market-hours probe confirms the same failure.
3. Do not reclassify at-rest blocked gates as clean without daylight proof.
4. Do not count expired or unfilled paper attempts as maturity reps.
5. Add aging thresholds for pending outcome observations so shadow logging becomes quality calibration instead of raw count accumulation.
6. Keep blocker taxonomy explicit: maturity blockers, fail-closed-at-rest blockers, runtime blockers, and binding blockers.
7. A clean validator or cron run is evidence only; it does not imply owner approval, order authority, phase promotion, or live readiness.

Blocked automation expansions:

- order resubmission automation
- cadence-triggered order creation or execution
- autonomous phase promotion
- kill-switch creation, clearing, or lifecycle automation
- paper-to-live promotion
- at-rest-to-clean inference
- treating an alert, card, score, or shadow decision as owner approval

Acceptance proof for an autonomy-hardening change should include:

- focused tests for the new gate semantics
- live proof artifacts showing authority flags remain false
- cron freshness registration when a scheduled proof surface is added
- workflow route/continuity update
- daily memory update
- explicit statement of remaining blockers and non-authority boundaries
