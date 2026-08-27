<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/03. Portfolio/Portfolio Snapshot.md
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: portfolio policy and owner-decision context only; no execution, account action, archive/delete/apply authority, or inferred approval.
-->

# Portfolio Snapshot

## Purpose

This page owns human portfolio posture, owner policy, and durable allocation decisions. It no longer hand-maintains ticker-level current state, routing, technical levels, evidence currentness, answer-scope membership, or queue status. Those structured facts are SQL-generated/read-only.

## Durable Owner Decisions

- Long-term-first posture with selective tactical and speculative sleeves inside written risk limits.
- Capital-base planning can use the owner-approved flat planning base from the historical/audit record.
- Cash discipline remains policy-level context and does not authorize brokerage, account, or money movement.
- Draft model allocations are planning context only until a separate validator-backed owner approval exists.
- Direct concentration and correlated-sleeve discipline stay binding; quality does not override risk limits.
- ETFs are valid review instruments when they solve diversification, sizing, or sleeve-construction problems better than a single name.

## Current Structured Views

Use these generated/read-only routes instead of hand-maintained tables:

- SQL-generated/read-only structured canon guard: `python scripts\finance_sql_canon_access.py --write --validate`
- SQL-generated/read-only ticker drilldown: `python scripts\finance_intelligence_state.py ticker <TICKER> --pretty`
- SQL-generated/read-only trade-grade readiness: `python scripts\trade_grade_os_freshness_cron_runner.py --write --validate`
- SQL-generated/read-only parity proof: `python scripts\full_intelligence_answer_parity.py --all --write --validate`
- SQL-generated/read-only lifecycle planning: `python scripts\db_lifecycle_manifest.py --write --validate`

Generated/read-only proof files:

- `tmp/trade-grade-os-freshness-cron-runner.json`
- `tmp/full-answer-parity/full-answer-parity-rollup.json`
- `tmp/db-lifecycle-manifest.json`
- `tmp/canonical-finance-data-plane-retirement-readiness.json`

## Portfolio Boundary

This page does not grant:

- capital deployment approval
- paper or live order approval
- brokerage or account action
- cash, sizing, sleeve, or risk-rule mutation
- SQL write expansion beyond approved field-family promotion
- archive/delete/apply authority

## Historical Trail

The pre-thinning snapshot was preserved before this rewrite:

- `backups/sql-json-md-thinning/20260619T192613Z/03. Portfolio/Portfolio Snapshot.md`

Use archived material for historical/audit context only. Current structured facts must come from SQL-generated/read-only proof.
