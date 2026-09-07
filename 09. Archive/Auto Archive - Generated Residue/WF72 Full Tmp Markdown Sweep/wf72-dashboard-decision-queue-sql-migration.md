# WF72 Dashboard Decision-Queue SQL Migration Proof

Generated: `2026-05-23T17:25:12Z`

Review-only proof. No source fetches, canon/portfolio mutations, trades, orders, or authority widening.

## Migration

- **File changed:** `scripts/dashboard_payload.py`
- **Change:** Added _load_daily_intel_from_db() helper that routes _build_decision_queue() reads through SQLite cockpit (artifact_runs + daily_review_objects + capital_recommendations + market_events) instead of direct JSON file loads. Falls back to _latest_window_artifact() JSON load when DB is absent or returns no rows for the window.
- **DB:** `tmp/veritas-artifact-index.sqlite`
- **Tables queried:** `artifact_runs`, `daily_review_objects`, `capital_recommendations`, `market_events`
- **Output shape unchanged:** True

## Acceptance Test Results (No-Drift Proof)

| | Before | After |
|---|---|---|
| Passed | 25/26 | 25/26 |
| Pass count unchanged | — | True |
| Meaningful drift cases | — | 0 |
| Pre-existing failures | workflow8_command_center_alignment | workflow8_command_center_alignment |

## Decision Queue Cases

| Case | Before | After |
|---|---|---|
| `decision_queue_visibility` | PASS | PASS |
| `payload_shape_contract` | PASS | PASS |

Decision queue no drift: **True**

## Status

**OK** — migration complete, acceptance tests prove no output drift.
