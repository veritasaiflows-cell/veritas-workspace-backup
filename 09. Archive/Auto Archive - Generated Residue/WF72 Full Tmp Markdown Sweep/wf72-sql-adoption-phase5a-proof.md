# WF72 SQL Adoption Phase 5A Proof

- Status: ok
- Generated: 2026-05-23T00:45:57Z
- Scope: run-summary/status SQL health adoption, scheduled chain tail incremental refresh, and stable row-fingerprint drift proof.
- Authority: derived SQL index only; no canon, portfolio, trade/account, paper/live order, or owner-approval authority.

## What changed

- `run_summary_refresh.py` now surfaces SQLite artifact-index health, validation summary, safety counts, and drift fingerprint coverage.
- `chain_manifest.py` now runs `artifact_index.py incremental` after `current_window_artifact_index.py` so scheduled windows refresh the primary generated-artifact lookup after compatibility artifacts are written.
- `artifact_index.py` now emits stable per-table row fingerprints for full-vs-incremental drift proof.
- Acceptance tests cover the new run-summary SQL health field, manifest tail, CLI fingerprints, and fingerprint equivalence.

## Proof

- Artifact index validation: `ok`, checks `{'checks': 15, 'failed': 0}`.
- Safety counts: `{'canon_stage_apply_allowed': 0, 'forbidden_true_authority_flags': 0, 'official_ir_fields_without_lineage': 0}`.
- Drift fingerprint tables: `15`.
- Run-summary no-drift compare: `ok` across morning, post-close, post-earnings, and sunday; exclusions were only `artifact_index`, `generated_at_utc`, and `run_id`.
- Post-close dry-run showed `artifact_index.py incremental` as the final chain step after `current_window_artifact_index.py`.

## Residue

- Semantic consumers (`fundamental_ir_reconciliation_packets.py`, `official_earnings_bridge.py`) remain deferred.
- SQL remains a derived proof/index/staging surface, not canon or apply authority.
