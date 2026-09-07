# Workflow 84 — Guarded Alert Evidence Plane

## Status

Active P0 evidence lane for the alerts-and-recommendations OS. Read-only and fail-closed.

## Objective

Provide the smallest trustworthy evidence plane needed to determine current alert state and support a non-executing recommendation.

## Inputs

- guarded SQL validation: `tmp/finance-sql-canon-access-validation.json`;
- active alert canon: `03. Alerts and Recommendations/`;
- explicit quote proof: `tmp/intraday-alerts/quote-snapshot-proof.json`;
- quote validation: `tmp/intraday-alerts/quote-snapshot-proof-validation.json`;
- alert-state/freshness controller: `tmp/alert-level-freshness-controller.json`.

## Output Contract

For each covered ticker, surface only the evidence needed for review:

- ticker and timeframe;
- evidence/source date and lineage;
- freshness and confidence;
- thesis and material risks;
- alert band and invalidation context;
- uncertainty or suppression reason.

Stale, missing, conflicted, or unverified evidence must lower confidence or block a material recommendation. A successful producer run proves only the checks that its validators cover.

## Current Route

1. `python scripts\finance_sql_canon_access.py --write --validate`
2. `python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
3. `python scripts\workflow_router.py WF84 --answer all --write-capsules --validate`

Primary proof: `tmp/finance-sql-canon-access-validation.json`.

## Acceptance

- guarded SQL passes integrity, authority, scope, lineage, and freshness checks;
- quote proof covers the explicit active alert universe and reports missing/stale observations truthfully;
- the alert controller validates and emits deterministic review states;
- no retired finance producer is required by this route;
- all output remains evidence and review context, never approval.

## Stop Lines

- No maintained holdings or simulated account state.
- No canon write from this evidence route.
- No capital, account, order, money-movement, or execution authority.
- No stale-context suppression to manufacture a green status.

Last updated: 2026-08-29 Phoenix / 2026-08-30 UTC.
