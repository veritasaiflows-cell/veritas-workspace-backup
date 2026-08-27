---
name: "SQLite"
description: "Use SQLite correctly with proper concurrency, pragmas, and type handling."
metadata: {"clawdbot":{"emoji":"🪶","requires":{"bins":["sqlite3"]},"os":["linux","darwin","win32"]}}
---

# SQLite

## Concurrency (Biggest Gotcha)

- Only one writer at a time—concurrent writes queue or fail; not for high-write workloads
- Enable WAL mode: `PRAGMA journal_mode=WAL`—allows reads during writes, huge improvement
- Set busy timeout: `PRAGMA busy_timeout=5000`—waits 5s before SQLITE_BUSY instead of failing immediately
- WAL needs `-wal` and `-shm` files—don't forget to copy them with main database
- `BEGIN IMMEDIATE` to grab write lock early—prevents deadlocks in read-then-write patterns

## Foreign Keys (Off by Default!)

- `PRAGMA foreign_keys=ON` required per connection—not persisted in database
- Without it, foreign key constraints silently ignored—data integrity broken
- Check before relying: `PRAGMA foreign_keys` returns 0 or 1
- ON DELETE CASCADE only works if foreign_keys is ON

## Type System

- Type affinity, not strict types—INTEGER column accepts "hello" without error
- `STRICT` tables enforce types—but only SQLite 3.37+ (2021)
- No native DATE/TIME—use TEXT as ISO8601 or INTEGER as Unix timestamp
- BOOLEAN doesn't exist—use INTEGER 0/1; TRUE/FALSE are just aliases
- REAL is 8-byte float—same precision issues as any float

## Schema Changes

- `ALTER TABLE` very limited—can add column, rename table/column; that's mostly it
- Can't change column type, add constraints, or drop columns (until 3.35)
- Workaround: create new table, copy data, drop old, rename—wrap in transaction
- `ALTER TABLE ADD COLUMN` can't have PRIMARY KEY, UNIQUE, or NOT NULL without default

## Performance Pragmas

- `PRAGMA optimize` before closing long-running connections—updates query planner stats
- `PRAGMA cache_size=-64000` for 64MB cache—negative = KB; default very small
- `PRAGMA synchronous=NORMAL` with WAL—good balance of safety and speed
- `PRAGMA temp_store=MEMORY` for temp tables in RAM—faster sorts and temp results

## Vacuum & Maintenance

- Deleted data doesn't shrink file—`VACUUM` rewrites entire database, reclaims space
- `VACUUM` needs 2x disk space temporarily—ensure enough room
- `PRAGMA auto_vacuum=INCREMENTAL` with `PRAGMA incremental_vacuum`—partial reclaim without full rewrite
- After bulk deletes, always vacuum or file stays bloated

## Backup Safety

- Never copy database file while open—corrupts if write in progress
- Use `.backup` command in sqlite3—or `sqlite3_backup_*` API
- WAL mode: `-wal` and `-shm` must be copied atomically with main file
- `VACUUM INTO 'backup.db'` creates standalone copy (3.27+)

## Indexing

- Covering indexes work—add extra columns to avoid table lookup
- Partial indexes supported (3.8+): `CREATE INDEX ... WHERE condition`
- Expression indexes (3.9+): `CREATE INDEX ON t(lower(name))`
- `EXPLAIN QUERY PLAN` shows index usage—simpler than PostgreSQL EXPLAIN

## Transactions

- Autocommit by default—each statement is own transaction; slow for bulk inserts
- Batch inserts: `BEGIN; INSERT...; INSERT...; COMMIT`—10-100x faster
- `BEGIN EXCLUSIVE` for exclusive lock—blocks all other connections
- Nested transactions via `SAVEPOINT name` / `RELEASE name` / `ROLLBACK TO name`

## Common Mistakes

- Using SQLite for web app with concurrent users—one writer blocks all; use PostgreSQL
- Assuming ROWID is stable—`VACUUM` can change ROWIDs; use explicit INTEGER PRIMARY KEY
- Not setting busy_timeout—random SQLITE_BUSY errors under any concurrency
- In-memory database `':memory:'`—each connection gets different database; use `file::memory:?cache=shared` for shared

## Veritas Retrieval and Artifact Cockpit

Use this local pattern when the task is about generated artifacts, proof routing, provenance, staged canon proposals, workflow awareness, artifact freshness, or workspace-note retrieval inside Randall's workspace.

### Workspace retrieval index / FTS5

- Owner script: `scripts/workspace_index.py`.
- Primary DB: `tmp/workspace-index.sqlite`.
- Use it for Markdown/workflow lookup, owner maps, aliases, artifact inventory, and freshness hints before broad file scans.
- Common commands:
  - `python scripts\workspace_index.py`
  - `python scripts\workspace_index.py --search "WF72" --limit 10`
  - `python scripts\workspace_index.py --search "note-drift" --limit 10`
  - `python scripts\workspace_index.py --search "Phase 4A SQL canon" --limit 10`
- FTS5 query rule: exact aliases such as `WF72` / `Workflow 72` are returned first; raw FTS5 is tried for compatible/advanced queries; punctuation-heavy human text falls back to parser-safe quoted phrase and token-AND variants. Hyphenated terms such as `note-drift` must not fail as `no such column: drift`.
- Source-open rule: retrieval hits are routing hints. Open the target note/artifact before making workflow, finance, readiness, or action claims.
- Do not create a second retrieval index if `workspace_index.py` or `artifact_index.py` can be safely extended.

- Primary DB: `tmp/veritas-artifact-index.sqlite`.
- Owner script: `scripts/artifact_index.py`.
- Preferred read commands:
  - `python scripts\artifact_index.py cockpit --limit 20`
  - `python scripts\artifact_index.py ticker-cockpit <TICKER> --limit 30`
  - `python scripts\artifact_index.py trust-cockpit --limit 50`
  - `python scripts\artifact_index.py proof-field <TICKER> <field_name>`
  - `python scripts\artifact_index.py earnings-lifecycle <TICKER>`
  - `python scripts\artifact_index.py deployment-readiness <TICKER>`
  - `python scripts\artifact_index.py dashboard-findings --limit 30`
  - `python scripts\artifact_index.py source-freshness --limit 30`
  - `python scripts\artifact_index.py reconcile-sql-markdown --limit 200` to generate Phase 2A review-only SQL/Markdown reconciliation outputs (`tmp/sql-canon-field-registry.json`, `tmp/sql-markdown-reconciliation.json`, `tmp/sql-markdown-reconciliation.md`, `tmp/sql-reconciliation-validation.json`)
  - `python scripts\artifact_index.py phase3a-dry-run --limit 200` to generate Phase 3A dry-run architecture/promotion/validation artifacts; dry-run only, no SQL cache/canon writes
  - `python scripts\artifact_index.py phase3b-writepath-preflight --limit 200` to generate Phase 3B future-write preflight artifacts; review-only, actual write path remains blocked until exact explicit approval, rollback/export preflight, rebuild-safety proof, and parity tests
  - `python scripts\artifact_index.py phase3c-cache-write --limit 200` is the approved one-time Phase 3C SQL structured cache write path for the exact NVDA earnings lifecycle fields only; it writes to separate `tmp/veritas-canon-cache.sqlite` with rollback/export, ledger, validation, and rebuild-safety proof. Do not reuse for broader fields without a new exact approval gate.
  - `python scripts\artifact_index.py phase3d-consumer-parity --limit 200` to run read-only parity checks comparing the SQL cache to generated artifact, SQL proof, and Markdown extraction for the approved NVDA fields; no consumer migration or behavior change is allowed by this command.
  - `python scripts\artifact_index.py phase3e-dashboard-proof-pilot --limit 200` to generate the dashboard proof-metadata consumer pilot for exactly the two approved NVDA cache fields, using SQL cache as an optional read-only source with generated-artifact/Markdown fallback proof; it does not mutate dashboard payloads, trigger sheets, handoffs, post-earnings consumers, Markdown, canon, portfolio state, or trade/account/paper/live authority.
  - `python scripts\artifact_index.py phase3f-preflight` to run the approved Phase 3F implementation preflight: consumer-side forbidden-authority guard, machine-executable Phase 3C rollback proof, and read-only cross-database stale-check against `tmp/workspace-index.sqlite`. This is still preflight/planning proof only: no non-optional consumer migration, SQL write-scope expansion, cron schedule change, Markdown/canon/portfolio mutation, owner-approval inference, or trade/account/paper/live authority.
  - Legacy `python scripts\artifact_index.py phase4a-activate` exists for the original two-key activation path, but current WF72 low-risk SQL-canon authority has moved through the bounded WF72 activator below. Do not use the legacy command to infer the current active key set.
  - `python scripts\artifact_index.py stoplines --limit 50`
  - `python scripts\artifact_index.py validate`
- Refresh commands:
  - `python scripts\artifact_index.py incremental` for normal changed/new/removed artifact refresh.
  - `python scripts\artifact_index.py rebuild` when schema or broad artifact behavior changed.
- Current WF72 SQL-canon/cache state: `tmp/veritas-canon-cache.sqlite` has bounded SQL proof/cache authority for exactly 265 approved metadata rows, not broad canon/apply authority. WF72 A2 fallback-backed read guard is live/green through `tmp/wf72-a2-consumer-authority-fallback-manifest.json`, `tmp/wf72-a2-consumer-authority-fallback-values.json`, and `tmp/go-sql-consumer-authority-guard.json`; it keeps Python fallback retained and does not promote SQL-first/customer/canon behavior. The active set is: 13 low-risk proof/freshness/lifecycle metadata keys under `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority` plus 252 exact WF72 entry/stop reference metadata rows under `wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority` (42 tickers × `reference_price_low`, `reference_price_high`, `reference_invalidation_level`, `reference_level_source_timestamp`, `reference_level_source_sha256`, and `reference_level_owner_source_path`).
- SQL source-of-truth promotion preparation route: run `python scripts\sql_source_truth_promotion_readiness_gate.py --write --validate --run-gates`, then `python scripts\sql_source_truth_field_family_decision_packet.py --write --validate`, then `python scripts\sql_source_truth_apply_scaffold.py --write --validate --run-gates`, then `python scripts\sql_source_truth_exact_apply_packet.py --write --validate`, and source-open the proof artifacts before any SQL truth/promotion claim. Current bounded promotion scope is only 42-ticker entry/stop reference metadata read authority through the typed helper and `finance_intelligence_state.py entry-stop-refs`, with Markdown/source-open fallback required; it is not SQL write expansion, ticker import, archive moves/deletes, customer output, canon/portfolio mutation, owner approval, or execution/account authority.
- Retail truth routing route: run `python scripts\retail_truth_routing_contract.py --write --validate` before broad SQL automation claims. Phase 1 only names answer paths and stop lines; SQL remains bounded read/proof support, PM owns coordination only, and customer/export, SQL-first promotion, SQL writes/imports, canon/portfolio mutation, Python fallback retirement, and paper/live/account action remain blocked.
- WF78 scaleout route: `python scripts\wf78_phase_runner.py --phase all-safe --write --validate` refreshes the report-only SQL readiness, 101-200 source registry, 100->200 manifest, provider/SEC validation, and import-decision packet. It is not import authority; import still requires exact candidate-set provider/runtime proof, backup/rollback, production A/B no-regression, universe validation, post-import validators, and explicit owner approval.
- SQL-canon lookup rule: when the question is about SQL truth/canon/cache authority, do not rely on memory or only `tmp/veritas-artifact-index.sqlite`. Check `06. Playbooks/Active Workflows.md`, this skill, and/or live `tmp/veritas-canon-cache.sqlite` first; then open the relevant activation/closeout artifact before making authority claims.
- Current WF72 activator/guard/V2 surfaces:
  - `python scripts\sql_canon_v2_planner.py --write --validate` writes the SQL-canon V2 planning/state-contract artifact for the current 265-row boundary; it is report-only and does not activate rows or change consumers.
  - `python scripts\sql_canon_metadata_resolver.py --key <scope:field> --fallback <scope:field=value> --write --validate` is the V2 typed fallback-first metadata resolver scaffold. It is read-only and only makes SQL effective when the guard is clean, fallback exists, values match, and the row is not stale/unsafe.
  - `python scripts\sql_canon_low_risk_phase3_activate.py --write` is the bounded activator for the approved thirteen-key proof/freshness metadata set; despite the filename, that boundary is Phase 7/thirteen-key.
  - `python scripts\wf72_entry_stop_sql_activate.py --batch all --validate-only` validates the approved 252-row entry/stop reference metadata family; any write/expansion still requires the exact approved gate and rollback proof.
  - `scripts\sql_consumer_authority_guard.py` is the required fail-closed read guard before non-optional SQL-canon reads; A2 is clean only for the current 265-row read boundary. New V2 code may use the alias `build_sql_canon_consumer_authority_guard`.
  - `scripts\dashboard_payload.py` may consume only approved proof metadata when the guard is clean and fallback values are present/current.
  - `scripts\sql_canon_field_family_preflight.py --write` reports already-active vs held next families; it must not activate rows by itself.
- Held WF72 SQL-canon surfaces: `portfolio:source_freshness_classification` and all `*:deployment_proof_status` rows require separate gates because they can affect owner-truth/manual-dependency or action/deployment interpretation. Entry/stop is active only for neutral reference metadata, not recommendation/deployment/action authority. Sizing/sleeve/cash/weight/risk-rule families are proposal-only unless separately gated; trade/account/paper/live execution and credential/config families are never SQL-canon.
- Boundary: `tmp/veritas-artifact-index.sqlite` remains derived proof/index/staging only. It is not a canonical finance note, not an apply engine, not owner approval, not portfolio mutation authority, and not trade/account/paper execution authority. SQL-canon/cache activation is metadata/proof-only with fallback required; it does not authorize Markdown/canonical note mutation, portfolio mutation, owner approval inference, cron-direct apply, dashboard recommendation/deployment/action-state behavior change, paper/live trade/account authority, money movement, credentials, config, or channel/service changes.
- Claim rule: use SQL to find and triage artifacts quickly; inspect the target artifact or canonical owner note before making content, finance, readiness, or action claims.
- Current-window split: `current_window_artifact_index.py` owns the concise per-window artifact manifest; SQL cockpit owns cross-window proof retrieval, ticker timelines, validator/trust state, lifecycle/deployment/source-freshness rows, and helper handoff lookup. Do not duplicate broad cockpit logic into the current-window index.

### SMB / Node cockpit read-only service-state adapter

- Owner app: `apps/pm-control-cockpit`.
- Primary DBs: `tmp/generic-service-state.sqlite` and `tmp/wf75-service-state.sqlite`.
- Primary local routes: `/sql`, `/api/sql/control-plane`, `/api/sql/service-state`, and `/api/smb/service-runs`.
- Use this pattern when the Node cockpit needs real service-run, queue, artifact, event, metadata, scenario, training-progress, or workflow-history rows instead of JSON summaries alone.
- Query posture: fixed allowlisted `SELECT` statements only. Do not accept arbitrary SQL from chat, browser input, generated artifacts, or URL params.
- Access posture: read-only cockpit visibility. No SQL writes, customer-data import, customer retention, customer-system writeback, launch authority, canon authority, owner approval inference, portfolio mutation, paper/live trading authority, account authority, or credential/config authority.
- Integration posture: cron/scripts may generate JSON proof and derived SQLite rows; Node may read the derived rows to avoid reparsing many JSON files for dashboards, reminders, and operator queues.
- Daily coverage guard: `python scripts\sql_coverage_guard.py --write --write-md --validate` refreshes/validates the workspace/artifact/JSON-to-SQL/SMB/WF75/PM SQL surfaces and writes `tmp/sql-coverage-guard.json/.md`.
- Claim rule: SQL can show row state and route proof, but source-open the backing artifact or owner note before making material SMB, finance, readiness, customer, or action claims.

### JSON-to-SQL promotion index

- Owner script: `scripts/json_sql_promotion_index.py`.
- Primary DB: `tmp/json-sql-promotion-index.sqlite`.
- Registry proof: `tmp/json-sql-promotion-registry.json`.
- Summary proof: `tmp/json-sql-promotion-index.json`.
- Refresh command: `python scripts\json_sql_promotion_index.py --write --write-md --validate`.
- Current indexed families: macro event calendar, macro metrics, macro judgment draft, WF75 service-state/queue/PM handoff, WF60/WF61 research feeds, and decision-packet candidates.
- Boundary: JSON remains source/proof/rebuildable evidence. This DB is a derived lookup/control-plane layer only; it is not canon, approval, portfolio authority, capital action, customer authority, SQL import authority, or paper/live/account authority.
