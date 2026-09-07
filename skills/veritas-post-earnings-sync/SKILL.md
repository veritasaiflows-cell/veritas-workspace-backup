---
name: "veritas-post-earnings-sync"
description: "Synchronize earnings evidence, thesis, catalysts, freshness, and alert state."
---

# Veritas Post-Earnings Alert Sync

## Purpose

Turn a reported earnings event into a source-backed scorecard and synchronized alert/recommendation state. Machine output is evidence; interpretation must distinguish facts, judgment, and uncertainty.

## Inputs

Use current official company evidence, earnings/catalyst artifacts, guarded SQL, the quote snapshot, alert controller, and the relevant ticker research. Run the direct post-close alerts chain when current price context is needed.

## Closure States

- Reported, evidence pending
- Interpreted
- Synced
- Closed with follow-up

Never use Closed alone when a real dependency remains.

## Workflow

1. Confirm what happened versus expectations and guidance.
2. Record evidence dates, sources, conflicts, and missing fields.
3. Create or update the ticker/quarter scorecard under `05. Intelligence\Earnings`.
4. Reassess thesis, base/bull/bear, catalysts, risks, and confidence.
5. Reassess the active alert state using guarded bands and current quote proof.
6. Sync only the research, catalyst, alert, and recommendation owners whose truth materially changed.
7. Validate the direct alerts chain and pivot boundary.
8. Report the real closure state.

## Alert Vocabulary

Use Recommendation review, Band entry, Near band, No chase, Invalidation alert, Thesis change, Catalyst alert, Freshness decay, Monitor only, or Suppressed.

A good quarter, a durable thesis, and an attractive threshold state are separate judgments.

## Scorecard

Include:

- event metadata and sources
- results and guidance
- price reaction / as of
- thesis impact
- base / bull / bear
- risks and fastest breakers
- guarded band/invalidation context
- alert state
- recommendation and uncertainty
- follow-up owner
- closure state

## Boundary

Do not write or maintain holdings, positions, sleeves, allocations, weights, sizing, tranches, cash, rebalancing, simulated positions, order packages, account state, or execution routes. Any capital or execution choice belongs to Randall outside this OS.
