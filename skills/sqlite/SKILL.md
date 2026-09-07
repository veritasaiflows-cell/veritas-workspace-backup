---
name: "SQLite"
description: "Use SQLite safely and route finance reads through guarded alerts-OS canon."
metadata: {"clawdbot":{"emoji":"🪶","requires":{"bins":["sqlite3"]},"os":["linux","darwin","win32"]}}
---

# SQLite

## Concurrency And Integrity

- SQLite has one writer at a time. Set `PRAGMA busy_timeout=5000`.
- Enable `PRAGMA foreign_keys=ON` on every connection.
- Use WAL only when concurrent readers justify it; preserve the main DB, nonempty WAL, and SHM consistently.
- Use `BEGIN IMMEDIATE` for read-then-write transactions.
- Run `PRAGMA integrity_check` and `PRAGMA foreign_key_check` before and after material migrations.
- Prefer explicit primary keys; do not depend on unstable implicit row IDs.
- Use ISO-8601 text or Unix integers for time and document the choice.
- Use parameterized statements and allowlisted read queries. Never execute chat-supplied SQL.

## Backup And Migration

Use the SQLite backup API or `VACUUM INTO` for a consistent standalone backup. Do not copy an open database as if it were an ordinary file.

For a material migration:

1. stop the exact writer
2. capture backup and source hash
3. record schema and row-count proof
4. open one transaction with foreign keys enabled
5. make the smallest scoped mutation
6. abort on integrity, foreign-key, projection, authority, or provenance failure
7. rebuild derived mirrors only from clean generators
8. preserve audit rows and rollback proof

## Workspace Retrieval

Use existing derived indexes before creating another one:

- `scripts\workspace_index.py` / `tmp\workspace-index.sqlite` for FTS discovery
- `scripts\artifact_index.py` / `tmp\veritas-artifact-index.sqlite` for generated-artifact routing
- `scripts\sql_coverage_guard.py --write --write-md --validate` for coverage proof

These are routing and evidence surfaces, not canon or approval. Open the target source before a material claim.

## Active Finance Route

Finance reads start here:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

The durable current-state database is `state\finance\finance-canon.sqlite`, accessed only through its guard. Active output is limited to alert levels, source lineage, evidence freshness, thesis/routing state, and non-executing recommendations.

The following old families are retired historical artifacts and must not be used or rebuilt as active finance sources:

- canon-cache compatibility DB
- portfolio intelligence/current-state DB
- canonical portfolio data plane
- portfolio/paper stack snapshot
- paper-position/account snapshot DB

A retired artifact may be opened read-only only for explicit audit, archive validation, or rollback investigation.

## Finance Authority Boundary

Current finance tables and derived outputs must not maintain sleeves, holdings, positions, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, brokerage/account state, or execution permissions. Static alert levels retain exact lineage and are not re-derived by consumers.

Owner-provided objectives or limits may inform a response transiently but are not written as maintained portfolio state.

## Derived Service State

SMB, PM, workflow, and evaluation databases remain derived control or lookup layers under their named owners. Use fixed allowlisted `SELECT` statements for cockpit reads. JSON/source artifacts remain proof where the owner contract says so.

## Performance

- Batch related writes in one transaction.
- Add indexes only from measured query plans.
- Use `EXPLAIN QUERY PLAN` before broad indexing.
- `VACUUM` rewrites the whole DB and needs free space; do not run it as casual cleanup.
- Run `PRAGMA optimize` after material index or query changes.

## Claim Rule

A clean SQLite validator proves only database mechanics and declared invariants. It does not prove market freshness, recommendation quality, owner approval, or any capital/execution authority.
