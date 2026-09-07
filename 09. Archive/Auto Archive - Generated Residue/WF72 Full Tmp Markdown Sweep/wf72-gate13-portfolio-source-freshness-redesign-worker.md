# WF72 Gate 13 - Portfolio Source Freshness Redesign Worker

## Objective
Review-only/shadow redesign for `portfolio:source_freshness_classification`: preserve portfolio freshness as degraded/manual-dependency metadata, not `fresh`/`current`, and do not SQL-canon activate it.

## Status
Implemented and validated as `implemented_review_only_shadow_contract_validated`.

## Changed files
- `scripts/sql_canon_field_family_preflight.py`
- `scripts/sql_consumer_authority_guard.py`
- `scripts/dashboard_payload.py`
- `scripts/test_artifact_index.py`
- `tmp/sql-canon-low-risk-field-family-preflight.json`
- `tmp/sql-canon-low-risk-field-family-preflight.md`
- `tmp/sql-canon-field-family-migration-protocol.json`
- `tmp/sql-canon-field-family-migration-protocol.md`
- `tmp/sql-canon-low-risk-shadow-activation-plan.json`
- `tmp/sql-canon-low-risk-shadow-activation-plan.md`

## Exact counts / values
- Active approved SQL-canon keys: `13`
- Portfolio key in approved set: `False`
- Preflight summary: `{'already_phase4a_active': 13, 'blocked': 0, 'eligible_review_only_shadow_preflight': 0, 'hold_separate_gate_shadow_only': 11, 'total': 24}`
- Portfolio field value: `manual_dependency`
- Portfolio trust level: `review_required`
- Portfolio cache rows: `0`
- Portfolio usable for review / presentation / canon mutation: `True` / `False` / `False`
- Shadow issues: `[]`

## Proof commands / results
- `python -m py_compile scripts\sql_canon_field_family_preflight.py scripts\sql_consumer_authority_guard.py scripts\dashboard_payload.py scripts\test_artifact_index.py` -> pass (exit 0)
- `python scripts\sql_canon_field_family_preflight.py --write` -> pass (exit 0); status=ok; already_phase4a_active=13; hold_separate_gate_shadow_only=11; total=24; shadow_eligible_keys=[]
- `python inline guard/dashboard metadata smoke` -> pass (exit 0); guard_status=ok; approved_key_count=13; portfolio fallback_value=manual_dependency; cache_row_present=false; dashboard metadata helper returns shadow-only manual-dependency metadata
- `python inline test_artifact_index.check_portfolio_source_freshness_shadow_contract` -> pass (exit 0); portfolio_shadow_test_passed
- `python scripts\artifact_index.py incremental; python scripts\artifact_index.py validate` -> pass (exit 0); status=ok checks=28 failed=0

## Stop lines
- No SQL-canon activation for portfolio:source_freshness_classification.
- No cache row activation or approved-key expansion beyond the existing 13 keys.
- No canon/portfolio note mutation, no dashboard recommendation/deployment/action-state behavior change.
- No owner approval inference, cron/direct apply, trade/account/paper/live/money/config/auth/channel/service/delete/move.

## Residue
- Dashboard payload helper now exposes portfolio shadow metadata internally, but the persisted tmp/dashboard-data.json did not show a new top-level sql_canon portfolioSourceFreshnessShadowMetadata field after direct script invocation in this environment; guard/preflight artifacts carry the enforceable review-only contract.
- Full scripts/test_artifact_index.py was not run because it includes broader phase activation paths outside this Gate 13 targeted scope; the new targeted contract check was run directly and passed.

## Recommendation
Keep portfolio:source_freshness_classification held as shadow-only degraded/manual-dependency trust metadata. If Gate 14+ wants UI surfacing, wire it as display-only trust metadata from the preflight/guard contract without adding it to active SQL-canon approved keys.
