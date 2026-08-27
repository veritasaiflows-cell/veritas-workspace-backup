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
- SQL-generated/read-only ticker drilldown: `python scripts\finance_intelligence_state.py ticker <TICKER> --pretty`
- SQL-generated/read-only full-population parity: `python scripts\full_intelligence_answer_parity.py --all --write --validate`
- SQL-generated/read-only data-plane proof: `python scripts\canonical_finance_data_plane.py --write --write-db --validate`

Generated/read-only proof files:

- `tmp/full-answer-parity/full-answer-parity-rollup.json`
- `tmp/trade-grade-full-answer/`
- `tmp/ticker-intelligence-cards/`
- `tmp/canonical-finance-data-plane.sqlite`
- `state/finance/finance-canon.sqlite`

## Durable Research Pointers

Historical coverage sections and machine-tracked tables were preserved before thinning:

- `backups/sql-json-md-thinning/20260619T192613Z/04. Research/Coverage and Watchlist.md`

Use that backup for historical/audit review only. If a ticker thesis needs a durable human rewrite, create or update a focused research note rather than rebuilding a giant duplicated table here.

## Boundary

Research coverage is not deployment approval. A thesis can be attractive while the structured route still blocks action. Generated/read-only proof can support review; it cannot infer Randall approval or authorize paper/live execution.
