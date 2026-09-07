# WF72 SQL Cockpit Phase 4D Proof

- Status: `ok`
- Generated: `2026-05-23T00:16:53Z`
- DB: `tmp/veritas-artifact-index.sqlite`
- Authority: derived proof/index/staging only; not canon, not apply, not approval, not trade/account/paper authority.

## Implemented phases
- 1 views: action queue, ticker timeline, trust boundary, official-source fields, canon staging stoplines
- 2 hot indexes: upper ticker/time, escalation latest, validator severity, window latest, canon stopline, file-state
- 3 CLI cockpit commands: cockpit, ticker-cockpit, trust-cockpit, proof-field, stoplines
- 4 validation: read-only validate command plus expanded test suite/integrity/FK/authority/lineage/index-plan checks
- 5 incremental rebuild: artifact_file_state, changed/new/removed detection, BEGIN IMMEDIATE transaction, temp DB equivalence/delete tests

## Validation summary
- validate status: `ok`
- checks: `14`
- failed: `0`
- counts: `{'artifact_file_state': 46, 'artifact_runs': 46, 'authority_flags': 493, 'canon_proposal_evidence_links': 28, 'canon_proposal_staging': 18, 'canon_proposals': 18, 'capital_recommendations': 19, 'daily_review_objects': 72, 'market_events': 187, 'official_ir_capture_fields': 217, 'official_ir_capture_runs': 31, 'source_artifacts': 110, 'source_field_lineage': 217, 'today_decision_items': 7, 'validator_runs': 7}`

## Command proof
- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` -> `0` in `0.055s`
- `python scripts\artifact_index.py rebuild` -> `0` in `0.197s`
- `python scripts\artifact_index.py incremental` -> `0` in `0.107s`
- `python scripts\artifact_index.py validate --json` -> `0` in `0.109s`
- `python scripts\artifact_index.py cockpit --limit 5` -> `0` in `0.094s`
- `python scripts\artifact_index.py ticker-cockpit ETN --limit 5` -> `0` in `0.093s`
- `python scripts\artifact_index.py trust-cockpit --limit 5` -> `0` in `0.084s`
- `python scripts\artifact_index.py proof-field AMD adjusted_eps` -> `0` in `0.086s`
- `python scripts\artifact_index.py stoplines --limit 5` -> `0` in `0.082s`
- `python scripts\test_artifact_index.py` -> `0` in `1.4s`
