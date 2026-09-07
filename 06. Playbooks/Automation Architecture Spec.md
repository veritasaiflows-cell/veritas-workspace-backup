# Alerts and Recommendations Automation Architecture

## Purpose

Define the active finance automation architecture after the 2026-08-29 pivot. The system produces truthful alerts, evidence repair, freshness state, and non-executing recommendations. It does not maintain a portfolio or simulated account.

## Active chain

The deterministic finance chain is:

1. guarded SQL alert evidence
2. explicit quote snapshot and source proof
3. alert-level freshness controller
4. non-executing recommendation digest
5. validation and cron proof

Run it through `scripts/run_alerts_recommendations_chain.py` in `morning`, `midday`, `post-close`, or `weekly` mode. `03. Alerts and Recommendations/Alert Operations Board.md` owns the human route.

## Layers

### Canon

`03. Alerts and Recommendations/` owns preferences, trigger definitions, ticker-level bands and invalidation context, and read-only operations rules.

### Guarded evidence

`state/finance/finance-canon.sqlite` and approved source artifacts supply typed alert references, evidence lineage, thesis context, and freshness. Guard validation must fail when active provenance is missing or hash-mismatched.

### Derived proof

Current generated packets live under `tmp/`. They are rebuildable evidence and never outrank canon, source truth, or Randall's decision.

### Presentation

Dashboards, workbooks, PDFs, and digests are read-only views. They may summarize alert state, evidence date, freshness, confidence, thesis, risks, bands, invalidation, and recommendation rationale.

## Allowed automation

- bounded source collection and provenance checks
- quote and evidence freshness refresh
- alert-state classification and deduplication
- thesis, catalyst, risk, and contradiction surfacing
- non-executing recommendation ranking
- deterministic validation, proof, and failure recovery
- read-only PDF, workbook, dashboard, and digest generation

## Fail-closed boundary

Automation must not maintain sleeves, holdings, positions, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, brokerage/account state, money movement, or paper/live execution. It must not infer approval from a band, alert, recommendation, generated card, cron run, or prior decision.

## Window contract

| Window | Command | Required outcome |
|---|---|---|
| Morning | `python scripts\\run_alerts_recommendations_chain.py morning --timeout-seconds 120 --write --validate` | Current pre-market evidence and review digest |
| Midday | `python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate` | Current quote/freshness state and deduplicated alerts |
| Post-close | `python scripts\\run_alerts_recommendations_chain.py post-close --timeout-seconds 120 --write --validate` | Closing evidence, thesis/catalyst review, and digest |
| Weekly | `python scripts\\run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate` | Ranked weekly recommendations with explicit freshness and uncertainty |

## Trust gates

- **Truth:** current lineage resolves and hashes match.
- **Freshness:** dates and market-window context are explicit; stale inputs degrade or suppress output.
- **Efficiency:** deterministic local routes run before model work; duplicate producers stay retired.
- **Speed:** use bounded ticker scope, cached proof only when valid, and explicit timeouts.
- **No false green:** a successful packet write is not fleet health; validators report source, freshness, and scheduler failures separately.

## Cron ownership

Finance schedules are governed by active contracts, `cron_freshness_spine.py`, and `cron_control_packet.py`. A retired contract or job cannot be re-enabled without Randall's explicit schedule/config gate and a clean alerts-only payload review.

## Acceptance

The architecture is green only when the alerts pivot validator, guarded SQL access, direct chain, contracts, scheduler freshness, and cron control packet all pass without hiding truthful warnings.
