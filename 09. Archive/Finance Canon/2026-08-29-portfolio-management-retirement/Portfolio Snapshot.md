<!-- THIN HUMAN SURFACE
Backup before thinning: backups/sql-json-md-thinning/20260619T192613Z/03. Portfolio/Portfolio Snapshot.md
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: portfolio policy and owner-decision context only; no execution, account action, archive/delete/apply authority, or inferred approval.
-->

# Portfolio Snapshot

## Purpose

This page owns human alert/recommendation posture and owner policy context for the alerts-and-recommendations OS. It does not manage positions, sizing, sleeves, or allocations, and it no longer hand-maintains ticker-level current state, routing, technical levels, evidence currentness, answer-scope membership, or queue status. The single structured source of truth is `state/finance/finance-canon.sqlite` (SQL-generated/read-only).

## Durable Owner Policy (Alerts-OS)

- Long-term-first posture; tactical and speculative ideas are surfaced as alerts inside written risk limits, not managed as portfolio sleeves.
- Capital-base numbers are reference-only planning context (the risk envelope lives in `Model Portfolio.md`); this OS does not size, allocate, or deploy capital.
- Cash discipline remains policy-level context and does not authorize brokerage, account, or money movement.
- Concentration and correlation are alert-prioritization inputs; quality does not override written risk limits.
- ETFs are valid alert/review instruments when they express a thesis better than a single name.

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

## Last updated

- 2026-08-29 — aligned to the alerts-and-recommendations OS pivot: removed sleeve/allocation/portfolio-construction ownership language; reframed durable decisions as alert posture; affirmed `state/finance/finance-canon.sqlite` as the single structured source of truth.
