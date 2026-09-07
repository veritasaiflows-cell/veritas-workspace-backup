# WF72 SQL Adoption Phase 5C Today-card Proof

- Status: ok
- Generated: 2026-05-23T01:05:24Z
- Scope: Today-card source/proof routing now uses SQL cockpit source records first, with current-window artifact fallback.
- Authority: SQL remains derived proof/index/staging only; no canon/apply/portfolio/trade/account/paper/approval authority.

## What changed

- `today_card_generator.py` now loads source-role provenance from `tmp/veritas-artifact-index.sqlite` via `source_artifacts` for proof links.
- The compatibility `tmp/current-window-artifacts.json` path remains fallback.
- If SQL health is degraded, the Today-card trust banner degrades/warns; when SQL is healthy, output semantics are unchanged.
- `test_artifact_index.py` now verifies Today-card SQL source routing prefers SQL records and preserves the derived/review-only/non-apply boundary.

## Proof

- No-drift compare: `ok` excluding only `generated_at_utc`; decision items baseline/current `7/7`.
- Today-card validator: `ok`, summary `{'critical': 0, 'warning': 0, 'findings': 0}`.
- Artifact-index validation: `ok`, checks `{'checks': 15, 'failed': 0}`, safety counts `{'canon_stage_apply_allowed': 0, 'forbidden_true_authority_flags': 0, 'official_ir_fields_without_lineage': 0}`.
- SQL-routed source roles populated: `['capital_deployment_recommendations', 'dashboard_validation']`.

## Residue

- Today-card remains review-only/blocked when upstream current-window or run-summary trust is blocked.
- Dashboard decision queue and dashboard handoff proof state are the next low-risk SQL adoption candidates.
- Semantic bridge/reconciliation and canon-sensitive consumers remain deferred.
