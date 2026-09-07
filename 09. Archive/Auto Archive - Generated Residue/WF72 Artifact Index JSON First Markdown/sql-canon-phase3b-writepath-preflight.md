# SQL canon Phase 3B write-path preflight

- Generated: 2026-05-25T19:43:32Z
- Boundary: `phase3b_writepath_preflight_review_only_no_sql_canon_cache_writes`
- Validation: ok
- Posture: review-only preflight; no durable canon/cache DB or table creation; no SQL cache rows written.
- Actual write path: BLOCKED pending explicit main/Randall approval gate.
- Future DB path: `tmp/veritas-canon-cache.sqlite` separate from `tmp/veritas-artifact-index.sqlite`.

## Approved-for-review candidates from Phase 3A

| Scope | Field | Value | Source artifact | Note proof |
|---|---|---|---|---|
| NVDA | post_earnings_review_confirmed | 1 | tmp/earnings-calendar.json | 03. Portfolio/Execution Board.md#### NVDA |
| NVDA | earnings_lifecycle_status | watchlist_already_closed | tmp/earnings-calendar.json | 03. Portfolio/Execution Board.md#### NVDA |

## Required gate before any future write

- Owner: Randall/main Veritas session
- Scope: Approve exactly the Phase 3A candidate rows for a one-time SQL structured cache write preflight-to-write promotion.
- Forbidden inference: no note/portfolio/trade/account/paper/live authority.

## Rollback/export preflight

- schema_version
- db_path
- table_names
- pre_write_integrity_check
- pre_write_foreign_key_check
- full prior rows for affected scope/field keys
- row_count
- sha256 for exported rows
- approval artifact path
- restore procedure

## Rebuild safety test plan

- Record existence/hash/mtime for tmp/veritas-canon-cache.sqlite and WAL/SHM sidecars before artifact_index.py rebuild.
- Run artifact_index.py rebuild against tmp/veritas-artifact-index.sqlite only.
- Verify durable cache DB and sidecars are unchanged or still absent if absent before test.
- Run artifact_index.py validate and Phase 3B preflight again; ensure candidate readiness unchanged.

## Consumer parity test plan

- Keep all consumers on Markdown/generated artifact sources until parity passes.
- For each future consumer, compare SQL cache reads vs current Markdown/artifact read for the same scope/field.
- Required sample scopes: ETN, NVDA, JPM, LMT when available; NVDA must cover both Phase 3A candidate fields.
- No deployment/readiness/recommendation behavior may change during parity testing.
- Fallback to Markdown remains mandatory until main accepts parity proof.
