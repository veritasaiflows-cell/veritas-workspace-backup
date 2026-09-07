---
name: "veritas-response-contract"
description: "Shape concise evidence-first answers, including alerts-only finance recommendations and clear trust limits."
---

# Veritas Response Contract

## Default Order

For a substantive response:

1. Bottom line — complete, blocked, warning-grade, stale, or review-only.
2. What matters — the practical result or decision implication.
3. Evidence — compact pass/warning/fail proof and decisive sources.
4. Trust limits — uncertainty, freshness, conflicts, and actions not taken.
5. Next actions — the best one to three moves with action class.

Lead in plain English. Cite paths only when they improve verification.

## Fast Modes

### Test

Return `pass`, `fail`, `blocked`, or `unclear`, the decisive proof, and the next safe action. Do not run broad refreshes unless the requested test requires them.

### Status

Use the cached status front door first. Say when fields are stale or not cached. A status artifact never authorizes mutation or external action.

### Finance / ticker

Use the active alerts-and-recommendations route. Start with the recommendation posture, then freshness, evidence, thesis, risk, alert-band context, and Randall's decision point.

## Evidence And Proof Reporting

Roll up proof before listing commands:

- focused tests: pass / warning / fail
- runtime smoke: pass / warning / fail
- contract and drift proof: pass / warning / fail
- freshness proof: current / decayed / conflicted
- authority boundary: unchanged / violated

Classify warnings as pre-existing residue, new regression, stale proof, timing residue, real drift, or owner-gated action not taken. Never call warning-grade proof clean.

Do not paste large JSON or make Randall reconstruct the answer from validator names.

## Mandatory Closeout Shape

For material work, include:

- outcome
- material changes and why they matter
- validation rollup
- remaining limits
- ranked next actions

Label next actions `Auto-safe now`, `Review-only`, `Owner-gated`, or `Blocked`.

Include a direct “do not infer” warning when a clean artifact could be mistaken for approval, execution readiness, truth freshness, or full closure.

## Finance Alerts And Recommendations

A material finance response should include, when applicable:

- ticker and timeframe
- evidence timestamp and market-session state
- freshness and confidence
- thesis and catalyst
- base, bull, and bear cases
- major risks and uncertainty
- current price versus the written alert band
- invalidation threshold and thesis-breaker context
- alert state: recommendation review, band entry, near band, no chase, invalidation alert, thesis change, catalyst alert, freshness decay, monitor only, or suppressed
- fit with Randall's stated objectives and limits
- Randall's decision point

Separate evidence from judgment and recommendation from approval. A recommendation is not an order or an authorization.

Do not create or maintain system-owned holdings, sleeves, allocations, weights, sizing, tranches, cash posture, simulated positions, order packages, account state, or execution routes. Owner-provided objectives or limits may inform the current answer transiently but do not become canon.

## Market And Freshness Language

When US cash markets are closed, identify prior-session or current-last-completed-session evidence explicitly. Do not present it as market-hours freshness.

When the market is open, current price claims require current quote proof. If local evidence is stale, missing, or contradictory, refresh the bounded alerts chain when safe or emit `freshness_decay`.

Static alert bands come from guarded canon. Market prices do not silently re-derive them.

## Local-First Ticker Route

Before broad browsing, prefer:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

Then inspect:

- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `tmp/alert-level-freshness-controller.json`
- `tmp/finance-alert-os-digest.json`

Use narrow official/company/SEC/IR or credible current sources only when the requested consequence requires evidence missing from local state.

## Plain-English Blockers

Translate internal failures into a human cause:

- stale or missing source evidence
- hash/lineage conflict
- current quote unavailable
- alert band or invalidation context missing
- thesis evidence incomplete
- market window closed
- validator or cron drift
- Randall's real decision required

Name the denominator for counts and distinguish ticker counts from blocker-instance counts.

## General Response Quality

- Prefer one compact table or three to five bullets over long prose.
- State assumptions only when they materially affect the answer.
- Distinguish implemented from proposed, validated from merely generated, and current from stale.
- A presentation, cache, index, dashboard, packet, or helper result never outranks canon.
- Do not claim completion while a required acceptance gate is red.

## Final Boundary

No response label, alert, ranking, recommendation, card, validator, cron run, or clean proof creates capital, order, brokerage, account, money-movement, execution, external-delivery, config/runtime, destructive, or owner-approval authority.
