# WF72 Phase 4 SQL Truth Spine Prototype

- Generated: `2026-05-22T07:16:02Z`
- Status: **prototype_ready**
- DB: `tmp\veritas-artifact-index.sqlite`
- Posture: derived SQL index / staging spine, not canon owner

## Counts
- runs: `15`
- source_artifacts: `111`
- validator_runs: `7`
- authority_flags: `59`
- canon_proposals: `18`
- today_decision_items: `7`
- capital_recommendations: `19`

## Authority boundary
- `sql_is_canonical_source_of_truth`: `False`
- `sql_may_stage_canon_proposals`: `True`
- `sql_may_apply_canon_mutations`: `False`
- `canonical_note_mutation_allowed_by_sql`: `False`
- `portfolio_mutation_allowed_by_sql`: `False`
- `trade_or_account_action_allowed`: `False`
- `paper_order_allowed_by_sql`: `False`
- `owner_approval_inferred`: `False`

Forbidden true authority flags: `0`

## Query examples
- today: `python scripts\artifact_index.py today --limit 10`
- validators: `python scripts\artifact_index.py validators --limit 10`
- canon: `python scripts\artifact_index.py canon --limit 20`
- authority: `python scripts\artifact_index.py authority --limit 20`

## Next phase
- Add official IR capture/source field lineage tables after helper migration stabilizes.
- Add exact canon proposal staging schema with target text hashes as the single proposal audit surface.
- Keep markdown owner notes canonical until a deliberate owner-approved migration plan exists.
