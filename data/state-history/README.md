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

## Proof contract

Before relying on this durable path:

```bash
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
python scripts\state_history_capture.py sample --window post-close
python scripts\state_history_capture.py append --window post-close
python scripts\state_history_capture.py validate
```

Stop if validation fails, if a row lacks source provenance, or if authority fields imply model training, deployment authority, canonical mutation, trade execution, or owner approval.
