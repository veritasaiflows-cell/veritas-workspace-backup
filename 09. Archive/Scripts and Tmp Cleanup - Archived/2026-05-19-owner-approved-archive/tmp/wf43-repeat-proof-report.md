# WF43 Repeat Durable State-History Proof Report

- generated_at_utc: 2026-05-10T23:21:39Z
- status: passed
- authority: historical-review-only; no model training, model-driven deployment, canonical mutation, portfolio/deployment mutation, trade execution, or owner approval inference.

## Commands run

1. `python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py` — passed.
2. `python scripts\test_state_history_capture.py` — `state_history_capture_tests_passed`.
3. `python scripts\state_history_capture.py sample --window post-close > tmp\state-history-v1-repeat-sample.json` — passed; sample parsed successfully with detected UTF-16 BOM from PowerShell redirection.
4. `python scripts\state_history_capture.py append --window post-close` — `state_history_appended rows=2 path=data/state-history/state-history-v1.jsonl`.
5. `python scripts\state_history_capture.py validate` — `state_history_validation_passed rows=2 path=data/state-history/state-history-v1.jsonl`.

## Durable history inspection

- row_count_before: 1
- row_count_after: 2
- latest_run_id: `20260510T232051Z_postclose_ee2357cf8e68`
- latest_captured_at_utc: 2026-05-10T23:20:51Z

## Captured counts

- deployment_states: 10
- band_statuses: 19
- review_objects: 12
- capital_deployment_recommendations: 6
- market_intelligence_events: 14
- source_artifacts: 6
- known_gaps: 4

## Remaining blockers

- Retention lifecycle / archive / backup policy is still undefined.
- Future owner approval/rejection and realized-outcome update flow remains blocked.
- Stale-note handling contract remains pending; it must flag review needs, not silently edit canonical notes.
- WF27 modeling, probability scoring, outcome analytics, and any model-driven deployment authority remain blocked until repeated rows exist and Randall explicitly reopens that lane.
- Minor evidence-handling note: the assigned PowerShell `>` redirection wrote `tmp/state-history-v1-repeat-sample.json` as UTF-16 with BOM. It was parsed successfully via detected encoding, but UTF-8 consumers should not assume that redirected sample artifact is UTF-8.
