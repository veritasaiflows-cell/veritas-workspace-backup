# WF43 State History v1 Report

## Implementation goal
Create the smallest append-only point-in-time state-history artifact for WF43 without enabling model training, model-driven deployment, canonical note mutation, historical rewrites, or hindsight backfill.

## Files changed / created
- `scripts/state_history_capture.py` - new JSONL append/validate/sample script.
- `scripts/test_state_history_capture.py` - validator/regression test for schema, authority fields, future-outcome separation, and append-only prefix preservation.
- `tmp/state-history-v1.jsonl` - live append-only v1 artifact generated from post-close artifacts.
- `tmp/state-history-v1-sample.json` - dry-run/sample row generated from the same post-close artifacts.
- `tmp/wf43-state-history-report.md` - this report.

## Artifact path
- Selected path: `tmp/state-history-v1.jsonl`.
- Rationale: repository already uses `tmp/` for finance machine artifacts and no durable `data/` directory exists. Choosing a long-term durable database/table path would be an owner policy decision, so v1 stays under `tmp/` as an append-only proof artifact.

## Schema summary
Each JSONL line is one independent `state_snapshot_v1` row:
- `schema_version`, `row_type`, `capture_run_id`, `captured_at_utc`, `window`
- `authority`: explicit false fields for model training, model-driven deployment, canonical note mutation, portfolio mutation, deployment-state mutation, trade execution, and owner approval granted
- `known_at_time`: point-in-time values from source artifacts, including run-summary state, deployment states, band statuses, review objects, capital recommendations, market-intelligence events, known gaps, and source generated timestamps
- `future_outcomes`: intentionally empty future-only fields: `owner_decision`, `owner_decision_at_utc`, `owner_decision_provenance`, `realized_outcomes`, `realized_outcomes_updated_at_utc`, `outcome_notes`
- `provenance`: producer script plus per-source artifact path, existence, generated timestamp, status, schema version, file mtime, and SHA-256 hash

## Source artifacts captured
- `tmp/daily-review-objects-post-close.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/deployment-check.json`
- `tmp/band-proposals.json`
- `tmp/run-summary-post-close.json`

## Live sample rows / counts
Latest live artifact summary:
- rows: 1
- window: `post-close`
- deployment states captured: 10
- band statuses captured: 18
- review objects captured: 16
- capital recommendations captured: 1
- market-intelligence events captured: 23
- provenance source artifacts: 6
- future outcomes: owner decision is `null`; realized outcomes are `[]`

## Proof run
Passed:
```text
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
# state_history_capture_tests_passed

python scripts\state_history_capture.py sample --window post-close --output tmp\state-history-v1.jsonl > tmp\state-history-v1-sample.json
python scripts\state_history_capture.py append --window post-close --output tmp\state-history-v1.jsonl
# state_history_appended rows=1 path=tmp/state-history-v1.jsonl
python scripts\state_history_capture.py validate --output tmp\state-history-v1.jsonl
# state_history_validation_passed rows=1 path=tmp/state-history-v1.jsonl
```

The test appends twice to `tmp/state-history-test.jsonl` and proves the second append preserves the exact original file prefix, so the writer appends instead of rewriting previous rows.

## Authority / no-model statement
This v1 state history is a historical review artifact only. It does not train models, authorize deployment, grant owner approval, mutate canonical notes, mutate portfolio state, mutate deployment state, or execute trades. Later WF27-style modeling remains blocked until retention is stable, audited, and explicitly reopened by the owner.

## Remaining gaps
- Durable storage location is unresolved by policy; v1 intentionally uses `tmp/` rather than inventing a permanent `data/` control plane.
- Future owner decision / realized outcome update flow is not implemented; fields are reserved and empty to prevent hindsight contamination.
- No consumer has been wired to treat `tmp/state-history-v1.jsonl` as available evidence yet; current recommendation packets may still report state-history as missing until a separate consumer update is approved.
- JSONL append-only behavior is process-level/test-enforced, not OS-level immutable storage.
