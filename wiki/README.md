# Veritas Wiki

Status: synthesis only
Owner workflow: WF88
Generated page type: landing
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/wf88-wiki-synthesis-packet.json`
This folder is the durable synthesis layer for Veritas OS 2.0.

It exists to help new sessions retrieve the right proof, understand the current learning loop, and route recommendations into action. It is not canon or approval authority.

Start with `wiki/index.md`. Cold sessions should use `wiki/syntheses/Cold Session Operating Routes.md`, then drill into the exact owner artifacts named on each page.
Material implementation sessions must consume the versioned efficiency route from `scripts/project_implementation_router.py`; the wiki only retrieves and explains that owner contract.

## Current action posture

- `refresh-wf88-wiki-synthesis`: `active` - Run the wiki synthesis packet after WF88/WF74/PM/OTEL producers refresh or after material implementation closeout.
- `grade-recommendation-outcomes`: `followup_required` - Grade mature outcomes represented in the current recommendation preview before making decision-quality claims; historical grades do not satisfy current-preview evidence.
- `mature-rsi-eval-harness`: `proof_worker_ready` - Keep RSI guarded; supervised proof refresh may run, while cron proof execution still requires explicit graduation proof.
- `route-open-improvement-followups`: `monitor` - Route open follow-up debt through WF74 docket, PM jobs, owner packets, or monitor-only rows; do not leave it as chat residue.
- `enforce-no-orphan-improvement-actions`: `clean` - Refresh the actionable improvement queue and no-orphan validator so every open improvement has a durable destination and next action.
- `maintain-wf74-wf88-loop-trace`: `warning` - Use the stitched loop trace to verify each current opportunity has a durable destination, PM/lane link when applicable, and WF88 consumer refresh.
- `maintain-long-work-job-status`: `clean` - Use the long-work status packet to resume provider-backed or full-source local jobs in bounded slices before rerunning expensive foreground commands.
- `optimize-token-heavy-cron-api-calls`: `monitor` - Use the token efficiency scorecard to pick changed-only prefilter or prompt-compression candidates before modifying any cron command.
- `close-implementation-token-attribution-gap`: `repair_required` - Use concurrent_lane_manager closeout token fields plus the implementation token attribution bridge when provider usage is exposed.
- `maintain-wf88-retrieval-regression-corpus`: `clean` - Keep the retrieval corpus current as source ownership changes; preserve SQL/thin-Markdown authority, derive eligible freshness from timestamps/age, and keep label-only scenarios outside live-source proof.
- `collect-frontier-capability-eval-results`: `evidence_collection_required` - Collect source-identical, metadata-only matched results through the blinded scorer surface; do not rank from the empty scaffold.
- `compile-wf88-decision-objects`: `warning_review_only` - Use the deterministic compiler as the decision-object first hop, then let wiki synthesis render those objects without feeding wiki/OS2 back into the compiler.
- `close-rsi-outcome-linkage-debt`: `evidence_linkage_required` - Add exact RSI correlation IDs and recurrence, stayed-closed, SLA, token/cost, and later-grade observations at owner sources.
- `run-isolated-advanced-capability-pilots`: `fixture_ready_execution_gated` - Keep the six capability contracts fixture-only until a separately scoped isolated runner has cost limits, matched baselines, privacy-safe attribution, and stop-line proof.
- `preserve-zero-auto-apply`: `clean` - Treat any nonzero auto_apply_count as a hard blocker before startup/status surfaces can call the loop healthy.

## Claim evidence

- `action-state:refresh-wf88-wiki-synthesis`: `{"state":"active"}`; authority `review_only`; source refs `wf88_os2_control#/status`.
- `action-state:grade-recommendation-outcomes`: `{"state":"followup_required"}`; authority `review_only`; source refs `wf88_os2_control#/summary/recommendation_current_preview_later_outcome_graded_rows`.
- `action-state:mature-rsi-eval-harness`: `{"state":"proof_worker_ready"}`; authority `review_only`; source refs `wf74_learning_loop_eval_harness#/rsi_maturity/status`.
- `action-state:route-open-improvement-followups`: `{"state":"monitor"}`; authority `review_only`; source refs `improvement_ledger#/summary/followup_required_open_count`.
- `action-state:enforce-no-orphan-improvement-actions`: `{"state":"clean"}`; authority `review_only`; source refs `no_orphan_validator#/validation/status`.
- `action-state:maintain-wf74-wf88-loop-trace`: `{"state":"warning"}`; authority `review_only`; source refs `wf74_wf88_loop_trace#/summary/high_priority_unrouted_count`, `wf74_wf88_loop_trace#/summary/duplicate_pm_job_id_count`, `wf74_wf88_loop_trace#/summary/downstream_stale_after_router_count`, `wf74_wf88_loop_trace#/summary/lane_link_missing_count`.
- `action-state:maintain-long-work-job-status`: `{"state":"clean"}`; authority `review_only`; source refs `long_work_job_status#/validation/status`, `long_work_job_status#/summary/blocked_job_count`, `long_work_job_status#/summary/resumable_job_count`, `long_work_job_status#/summary/stale_active_job_count`, `long_work_job_status#/summary/active_job_count`.
- `action-state:optimize-token-heavy-cron-api-calls`: `{"state":"monitor"}`; authority `review_only`; source refs `token_efficiency_scorecard#/summary/api_call_reduction_candidate_count`.
- `action-state:close-implementation-token-attribution-gap`: `{"state":"repair_required"}`; authority `review_only`; source refs `implementation_token_attribution_bridge#/summary/implementation_token_gap_count`.
- `action-state:maintain-wf88-retrieval-regression-corpus`: `{"state":"clean"}`; authority `review_only`; source refs `retrieval_quality_scorecard#/status`, `retrieval_quality_scorecard#/validation/status`.
- `action-state:collect-frontier-capability-eval-results`: `{"state":"evidence_collection_required"}`; authority `review_only`; source refs `frontier_capability_eval_spine#/status`, `frontier_capability_eval_spine#/validation/status`, `frontier_capability_eval_spine#/result_collection/row_count`, `frontier_capability_eval_spine#/comparison_readiness/cross_model_ranking_allowed`.
- `action-state:compile-wf88-decision-objects`: `{"state":"warning_review_only"}`; authority `review_only`; source refs `wf88_decision_compiler#/status`, `wf88_decision_compiler#/validation/status`, `wf88_decision_compiler#/summary/decision_object_count`, `wf88_decision_compiler#/leak_guard/pass`.
- `action-state:close-rsi-outcome-linkage-debt`: `{"state":"evidence_linkage_required"}`; authority `review_only`; source refs `rsi_outcome_scorecard#/status`, `rsi_outcome_scorecard#/validation/status`, `rsi_outcome_scorecard#/maturity_gate/mature`, `rsi_outcome_scorecard#/summary/live_complete_stable_count`, `rsi_outcome_scorecard#/summary/missing_link_debt_item_count`.
- `action-state:run-isolated-advanced-capability-pilots`: `{"state":"fixture_ready_execution_gated"}`; authority `review_only`; source refs `advanced_capability_pilot_packet#/status`, `advanced_capability_pilot_packet#/summary/executed_pilot_count`, `advanced_capability_pilot_packet#/summary/promotion_ready_count`.
- `action-state:preserve-zero-auto-apply`: `{"state":"clean"}`; authority `review_only`; source refs `wf74_auto_patch_proposer#/summary/auto_apply_count`.
