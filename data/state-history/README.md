# State History

Append-only durable history for WF43 point-in-time review state.

## Authority

- Historical review and provenance only.
- Not canonical portfolio truth.
- No model training by default.
- No model-driven deployment.
- No portfolio mutation, deployment-state mutation, trade execution, or owner-approval inference.

## Current file

- `state-history-v1.jsonl` — approved durable path for `scripts/state_history_capture.py` rows.

## Latest proof

- 2026-05-10 first controlled durable-path proof passed: compile, regression test, sample, append, validate, and direct row inspection.
- 2026-05-10 repeat durable proof also passed; rows increased from 1 to 2 and validation passed.
- Current validated durable rows: 2 post-close `state_snapshot_v1` rows.
- Latest capture run: `20260510T232051Z_postclose_ee2357cf8e68`.
- This proves durable presence/provenance and repeat append behavior only; lifecycle policy, owner-decision/outcome updates, modeling, probability scoring, and deployment authority remain blocked.

## Proof contract

Before widening reliance on this durable path:

```bash
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
python scripts\state_history_capture.py sample --window post-close
python scripts\state_history_capture.py append --window post-close
python scripts\state_history_capture.py validate
```

Stop if validation fails, if a row lacks source provenance, or if authority fields imply model training, deployment authority, canonical mutation, trade execution, or owner approval.
