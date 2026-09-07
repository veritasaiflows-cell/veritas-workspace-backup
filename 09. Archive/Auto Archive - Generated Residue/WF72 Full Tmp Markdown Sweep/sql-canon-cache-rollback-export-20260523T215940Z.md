# SQL canon cache rollback export

- Generated: 2026-05-23T21:59:40Z
- DB path: `tmp/veritas-canon-cache.sqlite`
- Path absent before write: False
- Prior affected row count: 2
- Rows SHA256: `304e70b8ceecdfa078c693500a26ba99efbce99bebc0e6750658d867dae9c660`
- Integrity check: `ok`
- Approval artifact: `tmp/sql-canon-phase3c-approval-context.json`

## Affected keys

- NVDA:post_earnings_review_confirmed
- NVDA:earnings_lifecycle_status

## Restore procedure

If rollback is needed, restore canon_cache_fields values for affected_keys from prior_rows and append compensating canon_cache_change_ledger rows; if path_absent=true, delete only the Phase 3C-created cache DB and sidecars after main approval.
