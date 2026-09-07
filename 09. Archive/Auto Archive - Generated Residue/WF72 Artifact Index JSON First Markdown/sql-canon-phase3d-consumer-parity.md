# SQL canon Phase 3D consumer parity

- Generated: 2026-05-25T19:43:29Z
- Status: blocked
- Validation: failed
- Boundary: `phase3d_consumer_parity_read_only_no_consumer_migration`
- Scope: read-only parity plan/test artifacts for exactly NVDA:post_earnings_review_confirmed and NVDA:earnings_lifecycle_status.
- Stop line: no consumer migration, no dashboard/trigger/handoff behavior change, no Markdown/canon/portfolio mutation, no trade/account/paper/live authority.

## Parity rows

| Key | Cache value | Generated artifact value | Generated/SQL value | Markdown value | Generated parity | Markdown parity | Overall |
|---|---|---|---|---|---|---|---|
| NVDA:post_earnings_review_confirmed | 1 | 1 | 1 | 1 | conflict_review_required | conflict_review_required | conflict_review_required |
| NVDA:earnings_lifecycle_status | post_event_review_confirmed_next_date_pending | watchlist_already_closed | watchlist_already_closed | watchlist_already_closed | conflict_review_required | conflict_review_required | conflict_review_required |

## Consumer plan

- 1. dashboard proof metadata: parity_compare_only; fallback_required=True; migration_allowed_now=False
- 2. trigger sheet freshness/lifecycle reads: parity_compare_only; fallback_required=True; migration_allowed_now=False
- 3. post-earnings prep/note-target context: parity_compare_only; fallback_required=True; migration_allowed_now=False
- 4. run summary / handoff packets: parity_compare_only; fallback_required=True; migration_allowed_now=False

## Validation checks

- ok | phase3d_boundary | 
- ok | cache_db_readonly_available | {"db_path": "tmp/veritas-canon-cache.sqlite", "exists": true, "integrity_check": "ok", "read_mode": "sqlite_ro", "table_names": ["canon_cache_change_ledger", "canon_cache_fields", "canon_cache_meta"]}
- ok | exact_two_approved_keys | NVDA:post_earnings_review_confirmed, NVDA:earnings_lifecycle_status
- FAIL | all_rows_consistent | [{"artifact_run_id_cache": null, "artifact_run_id_current": 10, "behavior_change_allowed": false, "cache_authority_boundary": "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority", "cache_value": "1", "consumer_migration_allowed": false, "current_generated_artifact_value": "1", "current_generated_sql_value": "1", "current_markdown_value": "1", "current_reconciliation_status": "match", "field": "post_earnings_review_confirmed", "generated_artifact_parity_status": "conflict_review_required", "key": "NVDA:post_earnings_review_confirmed", "markdown_owner_path_current": "03. Portfolio/Execution Board.md", "markdown_parity_status": "conflict_review_required", "note_excerpt_sha256_cache": "df12f0a746901114b5be7e08cb45357fb92e513dd842e1aeac0daa8558a148d8", "note_excerpt_sha256_current": "416cfa9ba8f49c039a24e62eb02ac4c6472c9d624b396b91845787f5c4bcdb86", "overall_parity_status": "conflict_review_required", "owner_mirror_note_path_cache": "tmp/earnings-calendar.json", "scope": "NVDA", "source_artifact_hash_cache": "60fdebf9748fce8269c724945c4940cd9132c3a8d2cbb9bd4d5cf393e14a646b", "source_artifact_hash_current": "14bf4a381d8bf1d645c7e272642a1e39e1c4fdf2409e763ccff3f64366749c35", "source_artifact_path_cache": "tmp/earnings-calendar.json", "source_artifact_path_current": "tmp/earnings-calendar.json"}, {"artifact_run_id_cache": null, "artifact_run_id_current": 10, "behavior_change_allowed": false, "cache_authority_boundary": "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority", "cache_value": "post_event_review_confirmed_next_date_pending", "consumer_migration_allowed": false, "current_generated_artifact_value": "watchlist_already_closed", "current_generated_sql_value": "watchlist_already_closed", "current_markdown_value": "watchlist_already_closed", "current_reconciliation_status": "match", "field": "earnings_lifecycle_status", "generated_artifact_parity_status": "conflict_review_required", "key": "NVDA:earnings_lifecycle_status", "markdown_owner_path_current": "03. Portfolio/Execution Board.md", "markdown_parity_status": "conflict_review_required", "note_excerpt_sha256_cache": "19d0488225774718fc55d3d98d8d55fde9f056ea69dca4dde081545d17b99083", "note_excerpt_sha256_current": "416cfa9ba8f49c039a24e62eb02ac4c6472c9d624b396b91845787f5c4bcdb86", "overall_parity_status": "conflict_review_required", "owner_mirror_note_path_cache": "tmp/earnings-calendar.json", "scope": "NVDA", "source_artifact_hash_cache": "60fdebf9748fce8269c724945c4940cd9132c3a8d2cbb9bd4d5cf393e14a646b", "source_artifact_hash_current": "14bf4a381d8bf1d645c7e272642a1e39e1c4fdf2409e763ccff3f64366749c35", "source_artifact_path_cache": "tmp/earnings-calendar.json", "source_artifact_path_current": "tmp/earnings-calendar.json"}]
- FAIL | generated_artifact_parity_consistent | 
- FAIL | markdown_parity_consistent | 
- FAIL | cache_rows_approved_boundary | 
- ok | current_reconciliation_still_match | 
- ok | no_consumer_migration_or_behavior_change | 
- ok | forbidden_false:canonical_note_mutation_allowed | 
- ok | forbidden_false:markdown_mutation_allowed | 
- ok | forbidden_false:portfolio_mutation_allowed | 
- ok | forbidden_false:owner_approval_inferred | 
- ok | forbidden_false:trade_or_account_action_allowed | 
- ok | forbidden_false:paper_trade_authority_allowed | 
- ok | forbidden_false:live_trade_authority_allowed | 
- ok | forbidden_false:money_movement_allowed | 
