<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/04. Research/Coverage and Watchlist.md
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: research narrative index only; no execution state, owner approval, portfolio mutation, archive/delete/apply authority, or inferred approval.
-->

# Coverage and Watchlist

## Purpose

This page is the human research index for thesis work, owner research decisions, and durable narrative pointers. It no longer hand-maintains universe tables, queue membership, technical levels, evidence currentness, answer-scope membership, or routing status. Those structured facts are SQL-generated/read-only.

## Research Use

Use this page for:

- thesis narrative pointers
- owner research decisions and durable context
- audit/history references
- links to deeper company, ETF, sector, and macro notes

Do not use this page for:

- current ticker state
- action queue membership
- technical levels
- SQL-generated/read-only evidence currentness
- answer-scope eligibility
- execution permission

## Current Structured Views

Use these generated/read-only routes for machine-owned structured fields:

- SQL-generated/read-only structured canon guard: `python scripts\finance_sql_canon_access.py --write --validate`
- Current alert/recommendation refresh: `python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
- Current ticker alert state: `tmp/alert-level-freshness-controller.json`
- Current recommendation digest: `tmp/finance-alert-os-digest.json`

Generated/read-only proof files:

- `tmp/intraday-alerts/quote-snapshot-proof.json`
- `tmp/alert-level-freshness-controller.json`
- `tmp/finance-alert-os-digest.json`
- `state/finance/finance-canon.sqlite`

## Durable Research Pointers

Historical coverage sections and machine-tracked tables were preserved before thinning:

- `backups/sql-json-md-thinning/20260619T192613Z/04. Research/Coverage and Watchlist.md`

Use that backup for historical/audit review only. If a ticker thesis needs a durable human rewrite, create or update a focused research note rather than rebuilding a giant duplicated table here.

## Boundary

Research coverage is not deployment approval. A thesis can be attractive while the structured route still blocks action. Generated/read-only proof can support review; it cannot infer Randall approval or authorize paper/live execution.
