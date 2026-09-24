# Structured Thesis Records (T-1)

Owner decision: Randall, 2026-09-23 17:05 MST ("Proceed with recommendations"). Design source: `06. Playbooks/Project Continuity/Alerts OS Audit and Monetization Readiness - 2026-09-23.md` §5.1 and `Recommendation Readiness Before Ledger - 2026-09-23.md`.

One JSON file per evaluated ticker: `state/finance/thesis/<TICKER>.json`, schema `veritas.thesis_record.v1` (`thesis-record.schema.json`). Durable path, never `tmp/`.

## Rules

- Veritas drafts from sourced evidence; **Randall accepts**. A record with `status: draft` grants nothing. Only `status: accepted` with `owner_accepted_at` set makes a name eligible for recommendation review.
- A name with no accepted thesis is **monitor-only**: it can still raise invalidation and data-quality alerts, but never appears as a recommendation candidate.
- Thesis ages like quotes: past `review_due` it drops back to monitor-only until re-accepted.
- Every change bumps `thesis_version` and keeps the prior version under `history/`. Nothing is overwritten without a copy; the alert ledger records `thesis_version` on every event.
- No position, sizing, allocation, holding, order, or account field. A thesis states why a name is worth watching and what would prove it wrong, not what to do with money.

## Tier A first batch

CME, ITA, LIN, META, PH: drafts due 2026-09-24 for owner acceptance.
