# WF72 Phase 4 Six-Key Stabilization Proof

- Status: `blocked`
- Generated: `2026-05-24T17:46:13Z`
- Scope: exact-six SQL-canon/cache stabilization and temp-copy rollback drill only.
- Boundary: no Markdown/canon/portfolio/security authority mutation, no owner-approval inference, no cron-direct apply, no trade/account/paper/live authority, no money movement, no config/auth/channel/service mutation.

## Verdict
- Blocked: exact-six row count and rollback drill passed, but consumer/value stabilization is not clean.

## Checks
- ok `live_cache_integrity_ok`
- ok `live_cache_exact_six_keys`
- ok `live_cache_boundary_exact`
- ok `live_cache_consumer_scope_dashboard_metadata_only`
- ok `live_cache_fallback_required_true`
- ok `live_rows_match_ok_fresh`
- ok `live_cache_source_hashes_match`
- ok `fallback_values_extracted_for_exact_six`
- FAIL `live_cache_values_match_current_fallbacks`
- ok `consumer_guard_passes_with_complete_fallback_map`
- ok `dashboard_build_protected_fingerprint_stable_across_two_reads`
- FAIL `dashboard_sql_canon_guard_ok_no_drift_acceptance`
- ok `protected_dashboard_today_run_summary_files_unchanged_by_phase4_drill`
- ok `temp_copy_rollback_sql_applies_cleanly`
- ok `temp_copy_rollback_matches_preactivation_export_rows`
- ok `py_compile_passed`
- ok `artifact_index_validate_passed`

## Blockers / residue
- `live_cache_values_match_current_fallbacks`: [{'key': 'NVDA:earnings_lifecycle_status', 'sql_value': 'watchlist_already_closed', 'fallback_value': 'post_event_review_confirmed_next_date_pending', 'matches': False}, {'key': 'NVDA:post_earnings_review_confirmed', 'sql_value': '1', 'fallback_value': '1', 'matches': True}, {'key': 'NVDA:last_earnings_date', 'sql_value': '2026-05-20', 'fallback_value': '2026-05-20', 'matches': True}, {'key': 'NVDA:post_earnings_review_date', 'sql_value': '2026-05-20', 'fallback_value': '2026-05-20', 'matches': True}, {'key': 'deployment:source_freshness_classification', 'sql_value': 'fresh', 'fallback_value': 'fresh', 'matches': True}, {'key': 'earnings:source_freshness_classification', 'sql_value': 'fresh', 'fallback_value': 'fresh', 'matches': True}]
- `dashboard_sql_canon_guard_ok_no_drift_acceptance`: {'sql_canon_status': 'degraded_fallback_required', 'sql_canon_issues': ['fallback_values_present: NVDA:last_earnings_date, NVDA:post_earnings_review_date, deployment:source_freshness_classification, earnings:source_freshness_classification'], 'sql_canon_sqlIsCanon': False, 'sql_canon_guard_failed_checks': [{'name': 'fallback_values_present', 'ok': False, 'detail': 'NVDA:last_earnings_date, NVDA:post_earnings_review_date, deployment:source_freshness_classification, earnings:source_freshness_classification'}], 'nvda_sqlCanonProofMetadata': {'consumerFamily': 'dashboard proof metadata', 'status': 'degraded_fallback_required', 'sqlIsCanon': False, 'authorityBoundary': 'phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority', 'fallbackRequired': True, 'metadataOnly': True, 'dashboardBehaviorChangeAllowed': False, 'canonicalNoteMutationAllowed': False, 'portfolioMutationAllowed': False, 'ownerApprovalInferred': False, 'tradeOrAccountActionAllowed': False, 'fields': {'earnin

## Artifacts
- JSON: `tmp/wf72-phase4-six-key-stabilization.json`
- Temp rollback DB copy: `tmp/wf72-phase4-six-key-stabilization-cache-copy.sqlite`
