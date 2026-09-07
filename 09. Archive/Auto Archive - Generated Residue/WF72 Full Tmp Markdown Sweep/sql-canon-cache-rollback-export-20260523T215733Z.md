# SQL canon cache rollback export

- Generated: 2026-05-23T21:57:33Z
- DB path: `tmp/veritas-canon-cache.sqlite`
- Path absent before write: True
- Prior affected row count: 0
- Rows SHA256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Integrity check: `db_absent`
- Approval artifact: `tmp/sql-canon-phase3c-approval-context.json`

## Affected keys

- NVDA:post_earnings_review_confirmed
- NVDA:earnings_lifecycle_status

## Restore procedure

If rollback is needed, restore canon_cache_fields values for affected_keys from prior_rows and append compensating canon_cache_change_ledger rows; if path_absent=true, delete only the Phase 3C-created cache DB and sidecars after main approval.
