# Retrieval Quality Scorecard

Generated UTC: `2026-05-25T00:05:03Z`
Status: **ok**
Authority boundary: `review_only_retrieval_scorecard_not_canon_not_memory_service_not_vector_or_kg_not_owner_approval_not_apply_authority`

## Executive verdict

**defer KG/vector/temporal-memory expansion**. KG/vector expansion justified now: **false**.
- Existing SQL cockpit + workspace-index + direct inspection cover the required known-answer routes.
- Remaining weak spot is fixture depth/contrast for stale-vs-current history, not a proven need for a new KG/vector memory plane.
- Generated artifacts and SQL rows remain review/proof routing surfaces only; canon stays in owner notes.
- Next best step: Add more stale-vs-current and archive/current-window negative fixtures before any memory infrastructure prototype.

## Summary

- Fixtures: **6**
- Pass / partial / fail: **6 / 0 / 0**
- Average score: **0.983**

## Fixture results

| Fixture | Class | Status | Score | Recommendation |
|---|---|---:|---:|---|
| `rq_owner_note_execution_board` | owner_note_lookup | pass | 1.0 | Use workspace-index as the route, then open the owner note before finance claims. |
| `rq_proof_artifact_capital_validation` | proof_artifact_lookup | pass | 1.0 | SQL cockpit is suitable for proof-artifact routing; direct artifact open remains required for content claims. |
| `rq_stale_current_market_state` | stale_vs_current_artifact_disambiguation | pass | 1.0 | Do not build KG/vector yet; first add more stale/current historical fixtures if this gap matters. |
| `rq_finance_stopline_rtx` | finance_stop_line_lookup | pass | 0.9 | Use direct owner note for stop/authority facts; SQL staging rows are context only. |
| `rq_generated_artifact_not_canon_dashboard_validation` | generated_artifact_is_not_canon_labeling | pass | 1.0 | Generated-artifact labeling is adequate; keep enforcing the direct owner-note inspection rule. |
| `rq_surface_split_etn_deployable` | sql_cockpit_vs_workspace_index_vs_direct_file_inspection | pass | 1.0 | Current stack is good enough for routing; final claims must cite direct owner/proof inspection. |

## Gaps

- No fixture-blocking gaps found. Stale-vs-current fixture depth still should be expanded before infrastructure work.

## Boundary

This is a validate-only/report-only retrieval scorecard. It does not create a memory service, vector DB, KG, canon replacement, approval surface, portfolio mutation path, or execution authority.
