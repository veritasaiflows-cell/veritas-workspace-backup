# SQL Canon Phase 7 Source-Freshness Activation

- Status: `ok`
- Validation: `ok` (46/46)
- Boundary: `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`
- Scope: exactly thirteen low-risk metadata keys; seven newly approved source-freshness keys plus six preserved metadata keys.
- Stop line: no Markdown/canon/portfolio mutation, owner-approval inference, cron-direct apply, entry bands, technical state, sector/sleeve/sizing, trade/account/paper/live authority, or money movement.

## Activated rows

| Key | Operation | New value |
|---|---|---|
| `NVDA:earnings_lifecycle_status` | `noop` | `post_event_review_confirmed_next_date_pending` |
| `NVDA:post_earnings_review_confirmed` | `noop` | `1` |
| `NVDA:last_earnings_date` | `noop` | `2026-05-20` |
| `NVDA:post_earnings_review_date` | `noop` | `2026-05-20` |
| `deployment:source_freshness_classification` | `noop` | `fresh` |
| `earnings:source_freshness_classification` | `noop` | `fresh` |
| `breadth:source_freshness_classification` | `noop` | `fresh` |
| `credit:source_freshness_classification` | `noop` | `fresh` |
| `fundamental_ir:source_freshness_classification` | `noop` | `fresh` |
| `fundamentals:source_freshness_classification` | `noop` | `fresh` |
| `market:source_freshness_classification` | `noop` | `current` |
| `policy:source_freshness_classification` | `noop` | `current` |
| `technical:source_freshness_classification` | `noop` | `fresh` |

## Rollback

- Export: `tmp/sql-canon-low-risk-phase3-preactivation-export.json`
- SQL rollback script: `tmp/sql-canon-low-risk-phase3-rollback.sql`
- Export SHA256: `85113082e218b4dc715e747d2c855d16e4a637ff2c628f136e14f7e457f60f90`

## No-drift proof

- Status: `ok`
- Dashboard protected fingerprint equal: `True`
- Today/run-summary proof inherited from Phase 2: `ok`

## Validation checks

- ok | `activation_status_ok` | 
- ok | `exact_thirteen_keys_only` | ['NVDA:earnings_lifecycle_status', 'NVDA:last_earnings_date', 'NVDA:post_earnings_review_confirmed', 'NVDA:post_earnings_review_date', 'breadth:source_freshness_classification', 'credit:source_freshness_classification', 'deployment:source_freshness_classification', 'earnings:source_freshness_classification', 'fundamental_ir:source_freshness_classification', 'fundamentals:source_freshness_classification', 'market:source_freshness_classification', 'policy:source_freshness_classification', 'technical:source_freshness_classification']
- ok | `new_seven_keys_present` | ['NVDA:earnings_lifecycle_status', 'NVDA:last_earnings_date', 'NVDA:post_earnings_review_confirmed', 'NVDA:post_earnings_review_date', 'breadth:source_freshness_classification', 'credit:source_freshness_classification', 'deployment:source_freshness_classification', 'earnings:source_freshness_classification', 'fundamental_ir:source_freshness_classification', 'fundamentals:source_freshness_classification', 'market:source_freshness_classification', 'policy:source_freshness_classification', 'technical:source_freshness_classification']
- ok | `low_risk_boundary_all_rows` | 
- ok | `rows_clean_match_ok` | 
- ok | `rollback_export_exists` | tmp/sql-canon-low-risk-phase3-preactivation-export.json
- ok | `rollback_sql_exists` | tmp/sql-canon-low-risk-phase3-rollback.sql
- ok | `cache_integrity_ok` | 
- ok | `field_value_matches_current_source:NVDA:earnings_lifecycle_status` | sql=post_event_review_confirmed_next_date_pending current=post_event_review_confirmed_next_date_pending
- ok | `source_hash_matches:NVDA:earnings_lifecycle_status` | tmp/earnings-calendar.json
- ok | `field_value_matches_current_source:NVDA:last_earnings_date` | sql=2026-05-20 current=2026-05-20
- ok | `source_hash_matches:NVDA:last_earnings_date` | tmp/earnings-calendar.json
- ok | `field_value_matches_current_source:NVDA:post_earnings_review_confirmed` | sql=1 current=1
- ok | `source_hash_matches:NVDA:post_earnings_review_confirmed` | tmp/earnings-calendar.json
- ok | `field_value_matches_current_source:NVDA:post_earnings_review_date` | sql=2026-05-20 current=2026-05-20
- ok | `source_hash_matches:NVDA:post_earnings_review_date` | tmp/earnings-calendar.json
- ok | `field_value_matches_current_source:breadth:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:breadth:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:credit:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:credit:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:deployment:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:deployment:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:earnings:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:earnings:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:fundamental_ir:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:fundamental_ir:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:fundamentals:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:fundamentals:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:market:source_freshness_classification` | sql=current current=current
- ok | `source_hash_matches:market:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:policy:source_freshness_classification` | sql=current current=current
- ok | `source_hash_matches:policy:source_freshness_classification` | tmp/dashboard-data.json
- ok | `field_value_matches_current_source:technical:source_freshness_classification` | sql=fresh current=fresh
- ok | `source_hash_matches:technical:source_freshness_classification` | tmp/dashboard-data.json
- ok | `forbidden_false:canonical_note_mutation_allowed` | False
- ok | `forbidden_false:markdown_mutation_allowed` | False
- ok | `forbidden_false:markdown_or_canon_note_write_allowed` | False
- ok | `forbidden_false:portfolio_mutation_allowed` | False
- ok | `forbidden_false:owner_approval_inferred` | False
- ok | `forbidden_false:proposal_apply_allowed` | False
- ok | `forbidden_false:trade_or_account_action_allowed` | False
- ok | `forbidden_false:paper_trade_authority_allowed` | False
- ok | `forbidden_false:live_trade_authority_allowed` | False
- ok | `forbidden_false:money_movement_allowed` | False
- ok | `forbidden_false:dashboard_recommendation_deployment_action_state_behavior_change_allowed` | False
- ok | `forbidden_false:cron_direct_apply_allowed` | False
