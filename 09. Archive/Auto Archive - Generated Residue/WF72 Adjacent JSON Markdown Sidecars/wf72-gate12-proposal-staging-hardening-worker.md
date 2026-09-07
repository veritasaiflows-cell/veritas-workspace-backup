# WF72 Gate 12 proposal staging hardening worker

- Status: `implemented_review_only_hardening_with_activation_apply_blockers_explicit`
- Generated: 2026-05-24T19:42:30Z
- Boundary: review-only derived SQL index; no canon/portfolio/apply/execution authority.

## What changed

- `scripts/artifact_index.py` - Added read-only canon-stage-readiness report/CLI, validation safety summary fields, and explicit activation/apply-ready zero check.
- `scripts/test_artifact_index.py` - Added CLI smoke and JSON assertions for canon-stage-readiness boundary and category separation.

## Staging readiness summary

| Metric | Count |
|---|---:|
| activation_or_apply_ready_rows | 0 |
| historical_applied_rows | 8 |
| incomplete_review_only_rows | 10 |
| pending_review_only_complete_rows | 0 |
| pending_review_only_rows | 10 |
| total_rows | 18 |

## Blockers

- historical applied rows exist in staging; treat as audit/history only, not pending readiness
- pending review-only rows are incomplete; source/evidence/validator gaps block apply readiness claims

## Proof

- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` - passed ()
- `python scripts\artifact_index.py canon-stage-readiness --limit 200` - passed (status=blocked_for_activation_or_apply_readiness total=18 historical_applied=8 pending_review_only=10 incomplete_review_only=10 activation_or_apply_ready=0)
- `python scripts\artifact_index.py incremental; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts\artifact_index.py validate` - passed (validate status=ok checks=28 failed=0, including canon_stage_activation_or_apply_ready_rows_zero)
- `python scripts\test_artifact_index.py` - blocked_by_preexisting_or_adjacent_cache_hash_drift (Failure in Phase 4A/low-risk consumer guard because live tmp/dashboard-data.json hash differs from SQL-canon cache rows for source_freshness_classification; not caused by proposal-staging hardening.)

## Residue

- Historical applied rows remain in canon_proposal_staging because DB rows are derived from artifacts and direct row rewrites/deletes were out of scope.
- Pending review-only rows remain incomplete until a separate source-lineage/evidence/validator cleanup pass hardens their source artifacts.
- Full artifact-index test suite is currently blocked by SQL-canon cache/source hash drift in dashboard-data metadata guard; proposal-staging validate path is green.

## Next workflow action

If Gate 12 continues, either repair/regenerate the active SQL-canon source-freshness cache hash drift under the appropriate exact SQL-canon gate, or separately improve source artifact classification for the 10 pending proposal rows; do not treat current staging as apply-ready.
