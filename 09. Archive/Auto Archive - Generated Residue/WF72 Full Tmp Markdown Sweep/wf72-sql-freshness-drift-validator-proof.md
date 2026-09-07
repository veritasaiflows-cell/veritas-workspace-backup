# WF72 SQL Drift/Freshness Validator Proof

Generated: `2026-05-23T17:07:23Z`

Status: `ok`

Review-only. Read-only validator extension. No index mutation, no canon/portfolio/trade authority.

## Implementation

- File changed: `scripts/artifact_index.py`
- Change: extension — 4 new freshness checks added inside validate_index(), plus freshness_summary field in return dict

## New Checks

| Check | Pass | Detail |
|---|---|---|
| `freshness_live_files_all_indexed` | ok | not_indexed=0 |
| `freshness_no_orphaned_rows` | ok | orphaned=0 |
| `freshness_no_stale_content` | ok | stale=0 |
| `freshness_index_has_been_built` | ok | last_rebuilt=2026-05-23T01:53:24Z last_incremental=2026-05-23T01:04:47Z |

## Freshness Summary

- Live files: 46
- Indexed files: 46
- Not indexed: 0
- Orphaned: 0
- Stale content: 0
- Last full rebuild: `2026-05-23T01:53:24Z`
- Last incremental: `2026-05-23T01:04:47Z`

## What Each Check Detects

- `freshness_live_files_all_indexed`: Files returned by iter_artifact_paths() that have no row in artifact_file_state — live artifacts the index has never seen.
- `freshness_no_orphaned_rows`: Rows in artifact_file_state whose source files no longer exist on disk — orphaned index entries.
- `freshness_no_stale_content`: Files where the live sha256 differs from the stored sha256 — content changed after last index run but incremental rebuild missed them.
- `freshness_index_has_been_built`: Neither last_rebuilt_at_utc nor last_incremental_rebuilt_at_utc is set — index was never built.

## Residue

None. All 4 freshness checks pass. Dashboard decision-queue SQL migration remains deferred.

## Next

WF72 SQL cockpit is in steady-state. Monitor freshness_no_stale_content and freshness_live_files_all_indexed on each chain run via artifact_index.py validate.
