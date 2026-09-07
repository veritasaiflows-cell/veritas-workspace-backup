# WF72 consumer authority guard implementation

Status: implemented; Phase 4A activation command remains blocked by existing workspace-index/source mtime preconditions outside this lane.

## Changed

- Added `scripts/sql_consumer_authority_guard.py` as a narrow read-only Phase 4A consumer guard.
- Wired `scripts/dashboard_payload.py` to call the guard before exposing SQL-canon rows in dashboard proof metadata.
- Added dashboard acceptance coverage for fail-closed guard degradation to generated-artifact/Markdown fallback.
- Added targeted artifact-index test assertions for guard allow/block behavior.

## Authority boundary

- Exact approved keys only:
  - `NVDA:post_earnings_review_confirmed`
  - `NVDA:earnings_lifecycle_status`
- Consumer family: dashboard proof metadata only.
- Fallback required before SQL read is allowed.
- No canonical note mutation, portfolio mutation, owner approval inference, trade/account authority, paper/live authority, or money movement.

## Validation

- `python -m py_compile scripts\sql_consumer_authority_guard.py scripts\dashboard_payload.py scripts\test_dashboard_acceptance.py scripts\test_artifact_index.py` — ok
- `python scripts\test_dashboard_acceptance.py` — ok, 28/28 passing
- `python scripts\artifact_index.py rebuild` — ok
- `python scripts\artifact_index.py validate` — ok, 27 checks / 0 failed
- Dashboard payload smoke — ok: guard status `ok`, SQL-canon status `ok`, NVDA proof metadata reads both approved fields from `sql_canon`, trade/account authority false
- `python scripts\artifact_index.py phase4a-activate` — blocked by existing Phase 3F/workspace-index stale preconditions; command wrote Phase 4A artifacts but activation validation stayed blocked. I did not edit or broaden `workspace_index.py`/FTS lane.

## Deferred debt

Refresh/reconcile workspace-index stale metadata for `tmp/earnings-calendar.json` before expecting `artifact_index.py phase4a-activate` to return `status=ok`.
