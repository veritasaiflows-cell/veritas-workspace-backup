# Alert Trigger Policy

## Purpose

Define when the system emits an alert or a non-executing recommendation.

## Required Conditions

Every material signal must evaluate:

1. **Thesis** — intact, challenged, changed, or invalidated, with evidence.
2. **Regime** — market, macro, sector, and policy context that materially changes risk.
3. **Technical level** — current price relative to the guarded reference band and invalidation threshold.
4. **Catalyst** — earnings, regulatory, company, or macro events that could alter the signal.
5. **Freshness** — quote, level, thesis, and source timestamps are current enough for the stated conclusion.
6. **Confidence** — high, medium, or low, with the limiting evidence named.

## Alert States

- **Recommendation review** — thesis and evidence support a material owner decision; no action is authorized.
- **Band entry** — price entered the current reference band while the thesis remains supportable.
- **Near band** — price is close enough to merit monitoring but has not entered the band.
- **No chase** — price is extended beyond the supported band.
- **Invalidation alert** — price or evidence breached a defined invalidation condition.
- **Thesis change** — material evidence changed the investment case.
- **Catalyst alert** — a time-sensitive event materially changes uncertainty or risk.
- **Freshness decay** — evidence is too old or incomplete for a material recommendation.
- **Monitor only** — evidence is useful, but no owner decision is presently warranted.
- **Suppressed** — duplicate, immaterial, conflicted, or insufficiently sourced signal.

## Freshness Rules

- Material claims require source-open evidence and explicit timestamps.
- Stale or missing evidence produces `Freshness decay`, never a false-ready recommendation.
- Live numeric reference levels and invalidation thresholds are guarded SQL `reference_levels`. The markdown Alert Bands register is thesis and interpretation only.
- Static reference levels are never re-derived merely because price moved.
- Level changes require a documented evidence basis, source timestamp, confidence, validator proof, and owner-aware SQL apply path. Do not write live numbers into markdown.
- Conflicting markdown snapshot and SQL evidence fails closed to SQL; do not treat the historical markdown table as the tie-breaker.

## Recommendation Contract

A material recommendation states conclusion, timeframe, evidence date, confidence, thesis, base/bull/bear cases, risks, band context, invalidation logic, uncertainty, and Randall's decision point.

It must distinguish evidence from judgment and recommendation from approval.

## Authority Boundary

This policy does not maintain or authorize sleeves, holdings, positions, allocations, weights, sizing, tranches, cash state, rebalancing, simulated account state, orders, account changes, money movement, or execution.
