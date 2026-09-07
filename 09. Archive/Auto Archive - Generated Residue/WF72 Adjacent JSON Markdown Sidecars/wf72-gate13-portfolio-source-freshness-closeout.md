# WF72 Gate 13 portfolio source freshness redesign closeout

- Generated: `2026-05-24T19:58:30Z`
- Status: `closed_shadow_only_manual_dependency_contract_no_activation`
- Candidate: `portfolio:source_freshness_classification`
- Result: portfolio freshness is represented only as degraded/manual-dependency shadow metadata. It is not SQL-canon active, not portfolio truth, not apply readiness, and not execution authority.

## Implementation

- Added/reused shadow-only manual-dependency contract surfaces in preflight, consumer guard metadata, dashboard proof metadata, and artifact-index tests.
- Preserved Phase 7 exact 13-key SQL proof-metadata boundary.
- Explicitly forbids normalizing `manual_dependency` to `fresh` or `current`.
- Dashboard action/recommendation/deployment behavior is unchanged.

## Current state

| Metric | Value |
|---|---|
| portfolio key active in SQL cache | `false` |
| cache rows for portfolio key | `0` |
| portfolio classification | `manual_dependency` |
| normalization to fresh/current allowed | `false` |
| SQL-canon activation allowed by Gate 13 | `false` |

## Validation

- `python -m py_compile scripts\sql_canon_field_family_preflight.py scripts\sql_consumer_authority_guard.py scripts\dashboard_payload.py scripts\test_artifact_index.py` - passed
- `python scripts\sql_canon_field_family_preflight.py --write` - passed; already active 13, held 11, eligible 0
- `python scripts\test_artifact_index.py` - passed
- `python scripts\artifact_index.py validate` - passed, 28/0
- `python scripts\test_dashboard_acceptance.py` - passed, 28/28

## Stop lines

No SQL-canon expansion, no cache row for portfolio, no Markdown/canon/portfolio mutation, no owner approval inference, no cron-direct apply, no dashboard action-state change, no trade/account/paper/live/money/config authority.

## Next

Proceed to Gate 14: neutral deployment display field redesign.
