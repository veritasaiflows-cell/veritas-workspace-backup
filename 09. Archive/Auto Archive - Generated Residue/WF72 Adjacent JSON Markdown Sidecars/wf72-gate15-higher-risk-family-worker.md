# WF72 Gate 15 higher-risk family worker

- Generated: 2026-05-24T20:19:52Z
- Status: `complete_review_only_no_activation`
- Boundary: `review_only_gate15_no_sql_canon_expansion_no_canon_portfolio_mutation_no_execution_or_config_authority`
- Activation/cache/canon/portfolio/execution/config authority: **false**

## Classification matrix

### entry/stop metadata
- Classification: `future_exact_gated_metadata_candidate`
- SQL-canon activation now: **false**
- Route: Keep out of active SQL-canon now; route changes to proposal/gated-apply, not cache activation.
- Phase 10 classification: `future_exact_gated_metadata_candidate`

### sizing/sleeve/cash/weight metadata
- Classification: `proposal_only_sql_staging`
- SQL-canon activation now: **false**
- Route: Use SQL as review/proposal staging only; keep canonical allocation truth in owner notes/config and gated apply artifacts.
- Phase 10 classification: `proposal_only_sql_staging`

### risk-rule metadata
- Classification: `proposal_only_sql_staging`
- SQL-canon activation now: **false**
- Route: Keep risk rules in owner guardrail surfaces; SQL may stage proposed deltas and proof links only.
- Phase 10 classification: `proposal_only_sql_staging`

### trade/account/paper/live execution metadata
- Classification: `never_sql_canon`
- SQL-canon activation now: **false**
- Route: Never route execution/account/paper/live authority through SQL-canon. Keep as guarded workflow telemetry only.
- Phase 10 classification: `never_sql_canon`

### credential/config metadata
- Classification: `never_sql_canon`
- SQL-canon activation now: **false**
- Route: Never place credential/config truth in SQL-canon; at most index redacted validation status.
- Phase 10 classification: `never_sql_canon`

## Enforcement/tests added

- scripts/sql_consumer_authority_guard.py now exposes HIGHER_RISK_SQL_CANON_FAMILY_GATES and classify_higher_risk_sql_canon_family() for Gate 15 exact routing.
- Consumer guard output now includes higher_risk_family_gates and a higher_risk_family_gates_no_activation check.
- Forbidden field-family terms were tightened for entry_band/band/stop_loss/risk_rule plus existing sizing/sleeve/cash/weight/execution/account/credential/config terms.
- scripts/sql_canon_field_family_preflight.py protocol now records the five Gate 15 higher-risk family routes without eligible fields or activation authority.
- scripts/test_artifact_index.py adds Gate 15 classification/guard assertions for representative entry, stop, weight, cash, risk-rule, paper/live execution, and credential/config fields.

## Validation run

- `python -m py_compile scripts\sql_canon_field_family_preflight.py scripts\sql_consumer_authority_guard.py scripts\artifact_index.py scripts\test_artifact_index.py` - passed
- `python scripts\sql_canon_field_family_preflight.py --write` - passed (status=ok; active=13; held=11; eligible=0; blocked=0)
- `python scripts\test_artifact_index.py` - passed (artifact_index_tests_passed)
- `python scripts\artifact_index.py validate` - passed (status=ok checks=28 failed=0)
- `python scripts\test_dashboard_acceptance.py` - passed (29/29 passed)

## Changed files

- `scripts/sql_consumer_authority_guard.py`
- `scripts/sql_canon_field_family_preflight.py`
- `scripts/test_artifact_index.py`
- `tmp/sql-canon-field-family-migration-protocol.json`
- `tmp/sql-canon-field-family-migration-protocol.md`
- `tmp/sql-canon-low-risk-field-family-preflight.json`
- `tmp/sql-canon-low-risk-field-family-preflight.md`
- `tmp/sql-canon-low-risk-shadow-activation-plan.json`
- `tmp/sql-canon-low-risk-shadow-activation-plan.md`
- `tmp/wf72-gate15-higher-risk-family-worker.json`
- `tmp/wf72-gate15-higher-risk-family-worker.md`

## Residue

- No Gate 15 activation occurred; entry/stop remains only a future exact-gated neutral display metadata candidate.
- Sizing/sleeve/cash/weight and risk-rule metadata remain proposal-only staging unless separately exact-approved through portfolio/canon maintenance gates.
- Trade/account/paper/live execution and credential/config metadata are permanently never-SQL-canon.
- No final workflow state was moved; main session must integrate Gate 15 and decide Gate 16 timing.
