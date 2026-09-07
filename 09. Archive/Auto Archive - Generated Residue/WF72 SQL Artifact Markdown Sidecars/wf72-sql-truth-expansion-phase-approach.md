# WF72 SQL truth expansion phase approach

- Generated: 2026-05-24T21:17:55Z
- Status: `complete`
- Current active boundary: `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`
- Entry/stop activation allowed now: `False`
- Broad SQL finance-canon authority allowed: **false**

## Phases

### Phase 1 - entry_stop_metadata_pilot
- Posture: `shadow_preflight_then_exact_gate_only`
- Allowed scope: `reference_price_low, reference_price_high, reference_invalidation_level, reference_level_source_timestamp, reference_level_source_sha256, reference_level_owner_source_path`
- Gate: exact key-level approval + fallback equality + rollback/export + no-drift proof

### Phase 2 - source_lineage_and_stale_drift_hardening
- Posture: `proof_metadata_only`
- Allowed scope: `source timestamps, source hashes, owner/source artifact lineage, stale/drift flags`
- Gate: must degrade confidence only; no recommendation/deployment/action-state behavior upgrade

### Phase 3 - proposal_only_portfolio_maintenance_staging
- Posture: `review_only_not_apply_ready_by_default`
- Allowed scope: `proposal ids, preview hashes, scope validation, evidence links`
- Gate: bounded WF64/WF56 gated apply path outside SQL-canon; SQL rows never imply apply approval

### Phase 4 - sizing_sleeve_cash_weight
- Posture: `held_unless_exact_later_gate`
- Allowed scope: `none now`
- Gate: separate model/sleeve/cash authority, validator proof, owner approval, and proposal-only staging first

### Phase 5 - risk_rule_metadata
- Posture: `proposal_only_owner_gated_later`
- Allowed scope: `none now`
- Gate: separate risk-rule owner approval and validator-backed proposal; no SQL-canon activation by default

### Phase 6 - execution_account_paper_live_and_credential_config_families
- Posture: `never_sql_canon`
- Allowed scope: `none now`
- Gate: blocked permanently for SQL-canon; at most redacted readiness/audit display under separate security/WF67 procedures

## Stop lines
- Do not activate without exact key-level approval, rollback/export, fallback equality, source-hash proof, and no-drift validators.
- Do not include sizing/sleeve/cash/weight, risk-rule, trade/account/paper/live execution, credential/config, portfolio freshness, or deployment_proof_status in this pilot.
- Do not infer owner approval, deployment entitlement, paper/live order authority, or canonical note mutation authority from these rows.
