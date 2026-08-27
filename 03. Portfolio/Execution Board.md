<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/03. Portfolio/Execution Board.md
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: human routing page only; no owner approval, portfolio mutation, order authority, archive/delete/apply authority, or execution.
-->

# Execution Board - Human Policy and SQL Routes

Generated/read-only route note: monthly lightweight governance review plus event-driven updates only. This page is not the source for daily or market-window ticker freshness; current structured state lives in SQL/JSON proof routes.

## Purpose

This page preserves the canonical human path for execution discipline. It no longer hand-maintains ticker levels, routing states, price context, evidence currentness, or queue status. Those structured facts are SQL-generated/read-only outputs from the finance canon and proof packets.

Use this page for:
- execution discipline and owner boundary
- where to find current structured views
- historical audit trail and rollback reference
- monthly governance checks for route, cadence, and authority drift

Do not use this page as:
- a live ticker table
- an approval record
- an order ticket
- a portfolio/cash/sizing mutation surface
- an archive/delete authorization

## Current Route

Run these generated/read-only routes for current structured state:

- SQL-generated/read-only structured canon guard: `python scripts\finance_sql_canon_access.py --write --validate`
- SQL-generated/read-only ticker drilldown: `python scripts\finance_intelligence_state.py ticker <TICKER> --pretty`
- SQL-generated/read-only trade-grade readiness: `python scripts\trade_grade_os_freshness_cron_runner.py --write --validate`
- SQL-generated/read-only parity proof: `python scripts\full_intelligence_answer_parity.py --all --write --validate`
- SQL-generated/read-only data-plane proof: `python scripts\canonical_finance_data_plane_phase6_10.py --write --validate`

Primary generated/read-only proof files:

- `tmp/trade-grade-os-freshness-cron-runner.json`
- `tmp/full-answer-parity/full-answer-parity-rollup.json`
- `tmp/canonical-finance-data-plane-phase6-10.json`
- `tmp/trade-grade-decision-cards.json`
- `tmp/wf85-deployment-timing-gate.json`

## Owner Boundary

The structured canon can route and evaluate review work. It does not approve capital deployment, paper execution, live execution, account changes, cash changes, model allocation changes, or portfolio mutations.

Paper execution remains simulation-only and requires the WF67 guard path plus Randall's exact order approval. Live trading, money movement, account settings, live endpoints, and inferred approval remain blocked.

## Human Policy Notes

- Do not chase a setup just because quality is high.
- A constructive thesis is not an entry.
- A generated card is not approval.
- A clean readiness runner is not execution authority.
- A thin Markdown page is not permission to delete historical/audit provenance.

## Historical Trail

The pre-thinning board was preserved before this rewrite:

- `backups/sql-json-md-thinning/20260619T192613Z/03. Portfolio/Execution Board.md`

Older archived board material remains historical/audit context only. It is not the current structured owner.
