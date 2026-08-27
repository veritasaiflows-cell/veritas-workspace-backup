# OTEL Department Delegation and Implementation Job Routing Audit - 2026-06-22

## Conclusion

The delegation spine is close to usable, and the cron blocker cluster in Randall's prompt was already repaired while this audit was running. Current proof shows cron-control, freshness-spine, WF74 routing, PM queue, OTEL, SQL canon, and the WF74 Telegram wrapper are all operationally clean.

The next upgrade is not another cron schedule change. It is an ownership and automation hardening pass: make every WF74/OTEL opportunity carry a department owner, convert only policy-safe opportunities into PM implementation jobs, select collision-distinct jobs for parallel lanes, and require automatic closeout refresh after every proof repair.

## Scope

Audited:
- OTEL learning-loop and recommendation closeout surfaces.
- Cron control, cron freshness, cron contracts, and the four blocker jobs named by Randall.
- WF74 improvement queue and autonomy work router.
- PM implementation job queue, PM control, greenkeeper, dispatcher, worker, and execution loop.
- Concurrent lane register active collisions.

Out of scope:
- Live cron schedule mutation.
- Config/auth/runtime mutation.
- Finance canon or portfolio mutation.
- Customer/external delivery.
- Paper/live/account/brokerage action.
- Capital deployment or inferred owner approval.

## Current Proof

Latest live proof after the in-flight cron repair lane advanced:

- `tmp/cron-freshness-spine.json`: `status=ok`, `job_count=80`, `enabled_job_count=46`, `blocked_count=0`, `unregistered_enabled_count=0`, `missing_expected_artifact_contract_count=0`, `live_scheduler_last_run_exception_count=0`.
- `tmp/cron-control-packet.json`: `status=ok`, `blocked_count=0`, `stale_count=0`, `escalation_signal_count=0`, `should_wake_main_session=false`, OTEL collector `ok`, SQL canon `ok`, handoff-first proof `ok`.
- `tmp/wf74-learning-loop-telegram-cron-runner.json`: `status=ok`, `failed_step_count=0`, digest `ok`, `auto_apply_count=0`.
- `tmp/wf74-autonomy-work-router.json`: `status=ok`, `open_unrouted_recommendation_count=0`, `recommendation_to_route_conversion_rate=1.0`, `route_to_pm_job_conversion_rate=1.0`, cron signal classification `green_no_repair_required`.
- `tmp/pm-implementation-job-queue.json`: `status=ok`, `ready_job_count=0`, `blocked_job_count=0`, `active_job_count=0`, `completed_by_ledger_job_count=15`.
- `tmp/otel-ops-control.json`: `status=ok`, 24-hour event count about `1865`, collector loopback healthy.
- `tmp/otel-learning-loop.json`: `status=ok`, OTEL health `ok`, daily warning/error count `0`, token/cost coverage only `0.0263`.
- `tmp/otel-recommendation-closeout.json`: `status=warning`; unresolved items are owner-gated metadata-depth, archive hygiene dry run, and dead collector hygiene dry run.
- `tmp/cron-contract-validator.json`: `status=ok`, `contract_count=30`, `drift_count=0`, `missing_live_job_count=0`.

## Finding 1 - Blocker Cluster Was Real, Then Cleared

Severity: P1 resolved / watch.

Evidence:
- Randall's supplied snapshot showed four cron governance blockers.
- Current live proof shows the same blocker class is cleared: cron freshness `ok`, cron control `ok`, WF74 Telegram runner `ok`, and PM queue `0` ready/blocked/active jobs.
- The active lane register showed `CRON::cron-freshness-spine-registration-repair-2026-06-22` owned the exact cron repair surfaces during this audit, so the live state legitimately changed mid-audit.

Impact:
- The fleet was not broadly failing. The blocking issue was control-plane governance residue: registration, self-reference, and stale wrapper proof.
- Current state no longer justifies cron schedule mutation.

Recommendation:
- Treat the four named blocker repairs as completed pending closeout by the owning CRON lane.
- Preserve the new posture: weekly OS radar jobs may read `tmp/cron-control-packet.json` as diagnostic proof, but it must not be a self-blocking dependency for jobs that contribute to cron-control's own truth surface.

Acceptance proof:
- `python scripts\cron_freshness_spine.py --write --validate`
- `python scripts\cron_control_packet.py --write --validate`
- `python scripts\cron_contract_validator.py --write --validate`
- `python scripts\wf74_learning_loop_telegram_cron_runner.py --write --validate`
- Expected: freshness `ok`, control `ok`, contracts `ok`, WF74 runner `ok`, blocked `0`, escalation `0`.

## Finding 2 - OTEL-to-Job Routing Exists, But Ownership Is Too Implicit

Severity: P1.

Evidence:
- `tmp/wf74-autonomy-work-router.json` converts WF74 opportunities into PM job candidates with 100% route conversion.
- `tmp/pm-implementation-job-queue.json` emits implementation-class, owner-surface, collision-group, proof commands, validation budget, stop lines, and automation capabilities.
- PM job rows do not consistently carry explicit `department`, `department_owner`, `owner_workflow`, or `accountable_integrator` fields. The active cron repair job had `owner=null` and `department=null` before the final refresh.

Impact:
- The system can route work, but cannot reliably delegate work to departments without inference.
- Parallel work can be selected by collision group, but not governed by department capacity, ownership, or acceptance authority.

Recommendation:
- Add an explicit department-owner contract to PM jobs and WF74 router candidates.
- Department assignment should be deterministic from `implementation_class`, `owner_surface`, `collision_group`, and source workflow.

Required department map:
- `cron`: cron contracts, cron freshness, cron control, cron wrappers. No schedule mutation without exact approved diff.
- `runtime_ops`: OTEL, status card, startup/front-door, lane register, Go/read-only validator infrastructure.
- `pm`: PM queue, PM control, greenkeeper, dispatcher, worker, closeout ledger.
- `finance_wf78_wf84_wf85`: non-capital finance routing, SQL/JSON proof, decision cards. No capital/execution approval.
- `product_wf75_wf79`: anonymous SaaS/product/service-state surfaces. No real customer/external delivery.
- `qa`: independent validators, changed-file routing, proof sufficiency, warning classification.
- `skills_procedure`: Skill Workshop proposals and operating procedure updates only.
- `memory_continuity`: daily memory, future-session packet, project continuity.
- `main_session_veritas`: final integration, owner decision presentation, authority boundary enforcement.

Acceptance proof:
- PM queue jobs include `department`, `department_owner`, `owner_surface`, `accountable_integrator`, `allowed_execution_mode`, and `stop_lines`.
- `pm_implementation_job_queue.py --write --write-db --validate` fails if an active or ready job lacks those fields.

## Finding 3 - Parallel Completion Needs A Department Allocator, Not Just A Recommender

Severity: P1.

Evidence:
- `tmp/parallel-lane-recommendation.json` was blocked while active lanes existed and while the top PM candidate was not eligible.
- The lane register can enforce exact allowed writes and collision groups.
- PM queue already exposes collision groups and validation budgets.

Impact:
- The workspace can avoid write collisions, but it does not yet have a clean "run these N jobs in parallel by department" allocator.
- This is why parallel work still depends on main-session interpretation.

Recommendation:
- Add or harden a department allocator step between PM queue and helper spawning.
- The allocator should select at most one job per collision group and at most one write lane per exact file/path surface.
- It should emit a queue of `lane_contracts`, not spawn by itself unless explicitly run under a safe executor.

Parallel lane eligibility rules:
- `owner_gate_required=false`.
- Proof commands are review-only safe.
- No stop-line token: apply, import, archive/delete, live, brokerage, account, external, config/auth/runtime, cron schedule mutation.
- Validation budget is `micro`, `narrow`, or explicitly approved `shared`.
- Collision group is not active.
- Allowed writes are exact, not broad directory ownership unless the task is read-only or distinct-output.
- Department owner is populated.

Acceptance proof:
- `parallel_lane_recommender.py --write --validate` or a successor allocator returns `eligible_candidate_count > 0` only when lane register has no write collision for that job.
- `concurrent_lane_manager.py --status --write --validate` remains `ok` after leases.
- Each spawned/leased lane has proof artifacts and closeout requirements.

## Finding 4 - The Automation Loop Needs A Mandatory Post-Repair Quiescence Refresh

Severity: P2.

Evidence:
- During the audit, cron proof turned green before WF74 router/PM queue caught up.
- The stale intermediate state showed a ready PM job for `pm-wf74-cron-migration-regression-repair`; after router/queue refresh, PM ready jobs dropped to `0`.

Impact:
- Without mandatory post-repair refresh, a resolved issue can remain visible as active implementation work.
- This creates false work and can make automation run proof for already-cleared blockers.

Recommendation:
- After any cron/PM/WF74 proof repair, run a fixed quiescence sequence:
  1. `cron_freshness_spine.py --write --validate`
  2. `cron_control_packet.py --write --validate`
  3. `wf74_improvement_opportunity_queue.py --write --validate`
  4. `wf74_autonomy_work_router.py --write --validate`
  5. `pm_implementation_job_queue.py --write --write-db --validate`
  6. `pm_control_packet.py --write --write-db --validate`
  7. `status_card_packet.py --write --validate`

Acceptance proof:
- PM queue `ready_job_count=0` when cron-control is green and no active blocker remains.
- WF74 router `cron_signal_classification=green_no_repair_required` when cron-control `blocked_count=0` and `escalation_signal_count=0`.

## Finding 5 - OTEL Is Healthy Enough For Routing, Not Yet For Cost-Based Model Optimization

Severity: P2.

Evidence:
- OTEL collector health is `ok`; daily warning/error count is `0`.
- Token/cost coverage is only `0.0263`, with most rows under `unknown` or lacking token/cost fields.
- `tmp/otel-recommendation-closeout.json` marks token/cost metadata-depth as `partially_implemented_owner_config_decision_remaining`.

Impact:
- OTEL can safely detect operational opportunities and drift.
- OTEL cannot yet drive reliable model-economics routing, cost thresholds, or model selection automation.

Recommendation:
- Keep OTEL routing metadata-only and local-only.
- Do not capture raw prompts, responses, tool payloads, headers, secrets, system prompts, or customer/account data.
- If Randall approves the metadata-depth patch later, apply only a scoped local collector/runtime metadata diff with rollback and redaction validation.

Acceptance proof:
- Token/cost metadata coverage improves materially without any raw content capture.
- OTEL closeout still reports all content capture flags false.
- Cron/control authority flags remain false for runtime/config mutation unless an exact owner-approved patch is in progress.

## Finding 6 - Auto-Execution Semantics Are Still Conservative And Need Sharpening

Severity: P2.

Evidence:
- Dispatcher selected a PM cron-repair job as proof-refresh work before final refresh.
- Worker reported `executed=false`, and PM execution loop later selected `0` jobs after the issue resolved.
- This is safe, but the semantics are unclear: "selected" does not necessarily mean "executed."

Impact:
- The system is conservative, which is good.
- But delegation dashboards can overstate action if selected jobs are not actually executed or closed.

Recommendation:
- Split status terms:
  - `candidate_selected`
  - `lane_prepared`
  - `proof_executed`
  - `closeout_ledgered`
  - `frontdoors_refreshed`
  - `job_resolved_or_completed`
- A job should not be called auto-executable unless it can proceed through proof execution and closeout without main-session interpretation.

Acceptance proof:
- PM worker and verifier summaries distinguish selected-but-not-executed from executed-and-closeout-ledgered.
- PM queue active/ready counts match the closeout ledger after front-door refresh.

## Recommended OTEL-To-Implementation Architecture

Do not connect OTEL directly to implementation. Use a policy-filtered chain:

1. OTEL metadata and runtime facts
   - Source: `otel_ops_control`, tool metadata, model-run ledger, coding outcome ledger, validator timing, cron/PM scorecards.
   - Output: metadata-only signals with redaction and authority flags.

2. WF74 opportunity queue
   - Converts raw signals into opportunities.
   - Adds category, priority, source proof, proposal gate, recommended action, validation command, and owner-gate posture.
   - Owner-gated, measurement-only, or standing-guardrail items remain non-executable.

3. WF74 autonomy router
   - Converts only actionable categories into routes.
   - Keeps monitor-only and owner-gated opportunities visible but not executable.
   - Emits PM job candidates with proof commands and stop lines.

4. PM implementation job queue
   - Adds implementation class, collision group, validation budget, closeout mode, automation capabilities, and department owner.
   - Writes SQLite/index proof for cockpit and automation consumers.

5. Department allocator
   - Selects collision-distinct, owner-safe jobs across departments.
   - Produces lane contracts with exact allowed writes, read-first files, acceptance commands, proof artifacts, and stop lines.

6. Lane register and helper/main execution
   - Leases exact write surfaces.
   - Spawns helper lanes only for bounded, non-overlapping work.
   - Runs proof-refresh jobs inline only when commands are review-only safe.

7. Closeout and front-door refresh
   - Updates implementation completion ledger.
   - Reruns router/PM/control/status packets.
   - Marks resolved work complete or suppresses stale jobs.

## Automation Levels

- Level 0: Observe only. OTEL/cron/PM proof packets.
- Level 1: Route only. WF74 opportunity queue and router produce review-only PM candidates.
- Level 2: Auto proof refresh. Safe proof commands run and refresh front doors.
- Level 3: Helper lane preparation. Exact lane contracts and leases are created; helper may execute bounded non-overlapping work.
- Level 4: Closeout automation. Proof passes, ledger updates, and queues refresh automatically.
- Level 5: Owner-gated action. Cron schedule mutation, config/runtime mutation, archive/delete, customer/external action, finance canon/portfolio mutation, paper/live/account/brokerage action, and capital deployment remain blocked until exact approval.

Current implemented state is Level 3 capable for department lane contracts and Level 4 capable for proof/closeout semantics when a job is eligible and review-only safe. The current live queue has no ready jobs, so the system is quiet rather than blocked.

## Next Implementation Jobs

1. Department-owner contract for PM jobs.
   - Owner: PM + Runtime/Ops.
   - Status: implemented.
   - Files touched: `pm_implementation_job_queue.py`, `wf74_autonomy_work_router.py`, focused tests.
   - Acceptance: active/ready jobs cannot lack department/owner fields; PM queue mirrors department contract fields into JSON and SQLite.

2. Quiescence refresh after proof repair.
   - Owner: PM + Cron.
   - Status: implemented at worker/execution/verifier status level.
   - Files touched: `pm_job_worker_runner.py`, `pm_autonomy_verifier.py`, `pm_execution_loop.py`, focused tests.
   - Acceptance: worker state now separates proof, closeout ledger, front-door refresh, and job-resolved/completed states.

3. Department parallel allocator.
   - Owner: Runtime/Ops + PM.
   - Status: implemented.
   - Files touched: `parallel_lane_recommender.py`, focused tests.
   - Acceptance: emits department-aware lane contracts across unique departments and collision groups; does not spawn helpers itself.

4. Worker status semantics hardening.
   - Owner: PM.
   - Status: implemented.
   - Files touched: `pm_job_worker_runner.py`, `pm_autonomy_verifier.py`, `pm_execution_loop.py`, focused tests.
   - Acceptance: selected/prepared/executed/closed/refreshed/resolved are separate fields.

5. Owner-gated OTEL metadata-depth patch.
   - Owner: Runtime/Ops.
   - Status: not approved by this audit.
   - Acceptance: higher token/cost coverage with no raw content capture and rollback proof.

## Implementation Closeout

Completed implementation surfaces:
- `scripts/pm_implementation_job_queue.py`
- `scripts/wf74_autonomy_work_router.py`
- `scripts/parallel_lane_recommender.py`
- `scripts/pm_job_worker_runner.py`
- `scripts/pm_autonomy_verifier.py`
- `scripts/pm_execution_loop.py`

Current verified behavior:
- PM jobs now carry `department`, `department_owner`, `owner_workflow`, `accountable_integrator`, and `allowed_execution_mode`.
- WF74 router candidates and follow-ups carry the same department contract before they enter the PM queue.
- PM queue validation blocks active/ready jobs missing department contracts.
- PM queue summary exposes department counts, ready department counts, and allowed execution mode counts.
- Parallel lane recommender emits department-aware lane contracts and enforces unique departments and collision groups for proposed parallel work.
- PM worker/execution/verifier surfaces distinguish `candidate_selected`, `lane_prepared`, `proof_executed`, `closeout_ledgered`, `frontdoors_refreshed`, and `job_resolved_or_completed`.
- Current live PM queue is quiet: 15 jobs are completed-by-ledger, 0 ready, 0 active, 0 blocked.
- Current parallel allocator is quiet: all base candidates are complete and no new eligible lane is recommended.

## Stop Lines

This audit does not authorize:
- Cron schedule mutation.
- Collector/runtime config mutation.
- Config/auth/channel/service mutation.
- Archive/delete/move cleanup.
- Finance canon or portfolio mutation.
- SQL import/promotion.
- Customer/external delivery.
- Paper/live/account/brokerage action.
- Capital deployment.
- Owner approval inference.

## Audit Validation

Completed:
- Markdown diff check for this audit artifact passed.
- Lane register validation passed with no active write collision for this audit artifact.
- Focused acceptance tests passed:
  - `python scripts\test_pm_implementation_job_queue_capabilities.py`
  - `python scripts\test_wf74_autonomy_work_router.py`
  - `python scripts\test_parallel_lane_recommender.py`
  - `python scripts\test_pm_job_worker_runner.py`
  - `python scripts\test_pm_autonomy_verifier.py`
  - `python scripts\test_pm_execution_proof_reuse.py`
- Syntax proof passed:
  - `python -m py_compile scripts\pm_implementation_job_queue.py scripts\wf74_autonomy_work_router.py scripts\parallel_lane_recommender.py scripts\pm_job_worker_runner.py scripts\pm_autonomy_verifier.py scripts\pm_execution_loop.py`
- No-write live validations passed for PM queue, WF74 router, parallel lane recommender, and PM execution loop.
- Go binary freshness guard is now clean: `status=ok`, `stale_count=0`, `missing_count=0`.
- Go fast proof implementation profile completed with `failed_count=0`, `critical_count=0`, and `status=warning`.

Validation limits:
- Go fast proof warnings remain advisory residue, not failed validators: JSON proof contract warnings, SQL proof bundle warning, one finance authority-event validator-artifact warning, SQL source-artifact lineage/hash warnings, and active-lane-count warning.
- OTEL metadata-depth config/runtime expansion remains unimplemented and owner-gated pending an exact scoped diff, redaction proof, rollback packet, and post-change validation.

## Bottom Line

The path is viable:

OTEL can find opportunities; WF74 can classify them; PM can turn them into jobs; the lane register can prevent collisions; helper lanes can execute bounded work in parallel.

The missing pieces identified by this audit are now implemented for the reviewed PM/WF74/parallel-worker surfaces. The next real gap is not plumbing; it is authorized telemetry-depth expansion and continued queue replenishment from future OTEL/cron/workflow opportunities.
