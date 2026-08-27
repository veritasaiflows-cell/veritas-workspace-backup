# Learning Loop V2 Review Routing Automation Redesign Audit - 2026-06-22

Generated: 2026-06-22 20:54 America/Phoenix / 2026-06-23 03:54 UTC

## Conclusion

The learning-loop stack is useful, but it is not yet V2-grade. It is good at noticing recurring residue, converting most recommendations into routed rows, and preserving owner-gated boundaries. It is weaker at turning those rows into a single clean decision docket that says what is actionable now, what is waiting on evidence, what is monitor-only, and what is blocked by a hard stop.

The current live audit found one urgent regression that should be repaired before treating the control plane as clean: the one-shot `WF87 shadow threshold after-market check` reminder exists as an enabled cron job, but it has no freshness-spine contract. That makes cron freshness and cron control block even though the reminder itself is review-only. This is exactly the kind of governance gap V2 should prevent automatically.

Recommended V2 direction: keep the existing WF74/PM/cron/autonomy primitives, but add a stricter review/routing layer:

- A unified decision docket.
- A side-effect lifecycle rule for every created cron/reminder job.
- A parent/child maturity contract for WF87 and AUTONOMY-SPINE.
- Trace/eval-style regression cases for learning-loop routing.
- Skill/procedure updates through Skill Workshop after the design is approved.

This audit is review-only. It does not apply code, create skills, change cron schedules, mutate finance canon/portfolio state, or run paper/live/account actions.

## Scope

Audited surfaces:

- WF74 learning-loop artifacts.
- Improvement ledger and carry-forward rows.
- Startup/status pickup rows.
- PM control packet and implementation queue.
- Cron control, cron freshness, and cron signal scorecard.
- WF87 shadow/readiness and AUTONOMY-SPINE maturity rollups.
- Skill availability and procedure posture.
- External agent/workflow/eval guidance from current web sources.

Out of scope:

- Applying patches.
- Editing live skills or Skill Workshop proposals.
- Mutating cron schedules or creating/disabling cron jobs.
- Mutating SQL/finance canon, portfolio notes, cash/sizing/risk, brokerage/account state, or paper/live execution.
- Config/auth/runtime/channel changes.

## Web Calibration

External references support the V2 direction:

- OpenAI's agent-eval guidance says to start with traces for debugging workflow behavior and move to repeatable datasets/eval runs once the desired behavior is known. Relevance: WF74 needs trace-like run packets and stable eval cases for router/proposal regressions. Source: [OpenAI - Evaluate agent workflows](https://developers.openai.com/api/docs/guides/agent-evals).
- OpenAI's eval best practices emphasize eval-driven development, task-specific evals, logging, automation where possible, human calibration, and avoiding vibe-based evals. Relevance: WF74 should graduate from "observed residue" to scored routing cases. Source: [OpenAI - Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
- OpenAI Agents SDK tracing documents traces/spans for LLM calls, tool calls, handoffs, guardrails, and custom events. Relevance: local packets should preserve the same causal chain even when not using the SDK directly. Source: [OpenAI Agents SDK - Tracing](https://openai.github.io/openai-agents-python/tracing/).
- OpenAI Agents SDK guardrails distinguishes input, output, and tool guardrails. Relevance: OpenClaw needs tool/side-effect guardrails around cron creation, SQL repair, file writes, skills, and paper/live boundaries, not only final-response checks. Source: [OpenAI Agents SDK - Guardrails](https://openai.github.io/openai-agents-python/guardrails/).
- Anthropic's agent-pattern guidance recommends the simplest effective workflow first, then routing, parallelization, orchestrator-workers, and evaluator-optimizer only when complexity earns its cost. Relevance: V2 should not become a giant agent. It should be a predictable workflow with parallel review lanes where useful. Source: [Anthropic - Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
- LangGraph documentation emphasizes durable execution, persistence, and human-in-the-loop. Relevance: OpenClaw's lane register, ledgers, status packets, and owner gates are already aligned, but the side-effect lifecycle needs to be stricter. Sources: [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [LangChain human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop).
- OpenAI prompt guidance recommends specific instructions, structured outputs, tests/evals for prompt behavior, and context-window planning. Relevance: reusable prompts should produce structured decision objects, not free-text residue. Source: [OpenAI - Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering).

## Refreshed Proof

| Surface | Current proof |
|---|---|
| Lane register | One active lane: this audit, `AUDIT::LEARNING-LOOP-V2-REDESIGN-2026-06-22::audit`. |
| PM control | `status=ok`; PM readiness green 80.3; implementation queue active 0, ready 0, blocked 0, completed-by-ledger 15. |
| PM stale lanes | 2 stale lanes: Retail Truth Routing System, WF78 Tier A/B Evidence Repair & Auto-Routing. Both are real future work, not direct WF74 V2 blockers. |
| Cron freshness spine | `status=blocked`; enabled 46, disabled 38, total 84; unregistered enabled 1; missing expected artifact contract 1; blocked 4. |
| Cron control packet | `status=error`; `should_wake_main_session=true`; escalation signals 4 after latest refresh. |
| Cron signal scorecard | `status=ok`; enabled 45; blocked 0; requires_attention 1. It does not fully agree with cron freshness/control because it is not seeing the unregistered reminder the same way. |
| WF87 shadow scorecard | `status=ok`; scoreable decisions 20; pending regular-session followups 2. Prior threshold state remains 18/20 clean decisions, 6/5 clean sessions. |
| WF87 readiness | `phase_a_hardening_implemented_runtime_blocked`; blockers: shadow threshold, reconciliation maturity, position sizing, portfolio circuit breakers, approval freshness TTL, intraday monitor. |
| AUTONOMY-SPINE | `final_state=continue_accrual`; owner approval required; shadow decisions 18/20 not met; sessions 6/5 met; reconciliation false; WF87 runtime false; cron clean false. |
| Workflow advancement | `status=ok`, validation warning; 2 advanced, 3 blocked. |
| WF74 runner | `status=ok`, validation warning; steps ok 29, blocked 0; warnings are diagnostic/residue, not patch application authority. |
| WF74 opportunity queue | 5 opportunities; top is priority 92 cron regression after completed migration plan. |
| WF74 router | `status=warning`; recommendation-to-route 1.0; route-to-PM-job 1.0; high-priority overdue count 1; active cron repair plan required. |
| Improvement ledger | `status=ok`; open 10; high-priority open 1; overdue open 4; top item is cron regression. |
| Future-session packet | `status=warning`; warnings: stale `tmp/finance-evidence-warning-router.json`, high-priority improvement overdue. |
| Skills check | Clean: 99 total, 57 visible, 56 command-available, missing requirements 0. |

## Current Learning-Loop Map

The current loop is:

1. WF74 collection runner gathers coding, finance, OTEL, improvement, router, and proposal signals.
2. WF74 opportunity queue converts signals into improvement opportunities.
3. Reflection/proposal autopilot converts opportunities into proposals.
4. Auto-patch proposer converts proposals into patch plans, owner-gated reviews, or blocked actions.
5. Autonomy work router maps opportunities/followups to PM candidates and workflow followups.
6. Improvement ledger persists current open/closed carry-forward items.
7. Startup/status/future-session packets decide what should be visible on pickup.
8. PM/cron/workflow scorecards provide current operational proof.

What works:

- The chain is mostly measurable.
- Conversion rates are strong: recommendation-to-route 1.0 and route-to-PM-job 1.0.
- Auto-apply is correctly 0.
- Owner-gated and execution-gated boundaries are explicit.
- PM implementation queue is drained, so WF74 is not hiding a giant unworked implementation backlog.

What does not work yet:

- "Open" does not reliably mean "do now."
- "Monitor-only" is not always represented strongly enough in the improvement ledger.
- New side-effecting support jobs can be created without the freshness/contract layer being completed.
- Startup/status, cron control, cron signal, and WF74 router can disagree after a new scheduler side effect.
- Some generated patch plans are intentionally targetless and require main-session selection, but the status surfaces do not make that distinction crisp enough.

## Findings

### P1 - Reminder Cron Job Missing Freshness Contract

Evidence:

- `cron_freshness_spine.py --write --validate` is blocked.
- Enabled jobs are now 46, not the post-Phase-2A 45, because of the one-shot reminder job.
- `WF87 shadow threshold after-market check` is enabled and unregistered.
- Error: `enabled_job_missing_contract:WF87 shadow threshold after-market check`.
- Error: `enabled_job_missing_expected_artifacts:WF87 shadow threshold after-market check`.
- Cron control now reports `status=error`, `should_wake_main_session=true`.

Impact:

- The reminder itself is review-only, but the governance plane is red.
- WF74 correctly promotes this into a priority 92 high-priority overdue improvement.
- AUTONOMY-SPINE remains blocked partly by `cron_cadence_not_clean`.
- Startup/future-session packets now carry a high-priority overdue warning.

Root cause:

- The reminder creation path did not enforce "enabled cron/reminder jobs must have a matching freshness-spine contract or an explicit TTL/one-shot exemption contract."

Recommendation:

- Open a narrow cron-governance repair lane.
- Add the freshness-spine contract for `WF87 shadow threshold after-market check` or classify the one-shot reminder under a formal TTL reminder contract if that is the intended pattern.
- Do not change the reminder schedule unless the contract repair proves schedule data is wrong.

Acceptance proof:

- `python scripts\cron_freshness_spine.py --write --validate`
- `python scripts\cron_control_packet.py --write --validate`
- `python scripts\wf74_improvement_opportunity_queue.py --write --validate`
- `python scripts\wf74_autonomy_work_router.py --write --validate`
- `python scripts\workflow_advancement_scorecard.py --write --validate`
- `python scripts\control_closeout_bundle.py --validation-budget shared --write --validate`

Stop line:

- No live cron add/edit/disable/delete without exact approval.
- No finance, account, paper/live, config/auth/runtime, or external action.

### P1 - Side-Effect Lifecycle Rule Is Missing From Reminder/Automation Creation

Evidence:

- Phase 2A live cron patch required post-apply governance backfill for two new jobs.
- The new WF87 after-market reminder repeated the same class of problem: enabled scheduler object without freshness contract.

Impact:

- The system can perform a valid user-requested scheduling action and immediately make its own governance plane unclean.
- Learning loops then spend cycles reporting avoidable residue.

Recommendation:

- Add a side-effect lifecycle rule to the cron-automation procedure: every enabled cron/reminder creation must either create/verify a freshness contract before closeout or explicitly mark the job as one-shot/TTL-exempt with bounded proof.
- Add a validator guard that fails reminder creation closeout when a contract is missing.

Acceptance proof:

- A regression test where a new one-shot reminder without contract fails closeout.
- A regression test where the same reminder with TTL/freshness contract passes.
- Cron freshness/control green after reminder creation.

### P2 - WF74 Needs A Unified Decision Docket

Evidence:

- Improvement ledger has 10 open items and 1 high-priority overdue item.
- WF74 opportunity queue has 5 opportunities.
- WF74 router has 6 PM job candidates and 3 workflow followups.
- Startup/status surfaces hide some rows as monitor-only while the ledger still calls them open/overdue.

Impact:

- Randall has to ask follow-up questions to understand what is real action versus monitor-only proof.
- Open rows can look like neglected implementation work when they are actually owner-gated, maturity-gated, or measurement-only.

Recommendation:

- Add a single `wf74_decision_docket` artifact that classifies each row into one of these states:
  - `fix_now_local_governance`
  - `owner_decision_required`
  - `proof_refresh_only`
  - `market_session_accrual`
  - `skill_workshop_proposal`
  - `procedure_update`
  - `monitor_only`
  - `hard_stop`
- The docket should explain why the state was chosen and name the acceptance proof.

Acceptance proof:

- Docket count equals open opportunity/followup input count.
- Every docket row has one route, one owner, one next action, one stop line, and one validation command.
- Startup/status card can show "active action count" separately from "open monitor count."

### P2 - Cron Surfaces Disagree After Scheduler Side Effects

Evidence:

- `cron_freshness_spine` and `cron_control_packet` see 46 enabled jobs and the unregistered WF87 reminder.
- `cron_signal_scorecard` reports 45 enabled jobs and blocked 0.

Impact:

- Operators may see "cron ok" in one surface while another says cron is blocked.
- AUTONOMY-SPINE and WF74 can inherit different cron truth depending on which surface they read first.

Recommendation:

- Make cron signal scorecard consume the same live scheduler/freshness spine source as cron control for enabled-job count and unregistered enabled jobs.
- Add a parity check: if cron control enabled count differs from cron signal scorecard enabled count, validation should warn or block depending on severity.

Acceptance proof:

- `cron_signal_scorecard.py`, `cron_freshness_spine.py`, and `cron_control_packet.py` agree on enabled/disabled/blocked/unregistered counts after refresh.

### P2 - Workflow Maturity Followups Are Durable But Not Closed Cleanly

Evidence:

- Workflow advancement has 2 advanced and 3 blocked.
- The three followups are CRON, WF87, and AUTONOMY-SPINE.
- The routing job `Convert workflow advancement blockers into implementation follow-ups` is already completed by ledger, yet WF74 still surfaces residual maturity rows.

Impact:

- Completed routing work can keep reappearing as if implementation did not happen.
- The system needs clearer distinction between "routing done, evidence still accruing" and "implementation missing."

Recommendation:

- Implement the existing patch plan `wf74-auto-patch-b9f8be59c688` after the immediate cron regression is repaired.
- The patch should mark completed maturity-routing work as closed unless a new non-maturity implementation blocker appears.

Acceptance proof:

- `workflow_advancement_scorecard.py --write --validate`
- `wf74_improvement_opportunity_queue.py --write --validate`
- `wf74_autonomy_work_router.py --write --validate`
- Confirm residual followups remain visible as maturity/accrual, not active implementation residue.

### P2 - AUTONOMY-SPINE Parent/Child Maturity Contract Needs Tightening

Evidence:

- AUTONOMY-SPINE final state is `continue_accrual`.
- Shadow sessions are met: 6/5.
- Shadow decisions are not met: 18/20.
- Reconciliation maturity, WF87 runtime gates, and cron cadence are not clean.

Impact:

- The parent rollup correctly refuses maturity, but the same blockers are repeated through several surfaces.
- There is a risk future patches try to quiet the parent instead of clearing child proof.

Recommendation:

- Add an explicit parent/child maturity contract:
  - Parent rows can only close when named child proof is green.
  - Parent warnings may be compressed in status views but not suppressed in proof artifacts.
  - Child blockers need their own maturity state and next proof window.

Acceptance proof:

- `autonomy_spine_readiness_rollup.py --write --validate`
- `autonomy_spine_promotion_contract.py --write --validate`
- `wf87_v2_readiness_rollup.py --write --validate`
- `workflow_advancement_scorecard.py --write --validate`

### P2 - Patch Plans Are Useful But Not Implementation-Ready Enough

Evidence:

- `wf74-auto-patch-9982cbad32c6` is priority 92 and correctly owner-gated.
- It has no target files because main-session inspection is required first.

Impact:

- This is safe, but not efficient. The generated plan still needs a human/operator to infer whether the right target is `state/cron-contracts`, `cron_freshness_spine`, `cron_control_packet`, the reminder creation path, or a combination.

Recommendation:

- Add a target resolver phase before patch-plan publication:
  - identify likely owner files/scripts
  - mark confidence
  - list exact read-first surfaces
  - forbid mutation until main session verifies

Acceptance proof:

- Patch plan for current cron regression lists probable target `state/cron-contracts/<wf87-shadow-threshold-after-market-check>.json` or equivalent reminder-contract owner, plus the producer script that created the reminder if discoverable.

### P3 - Prompt And Procedure Outputs Need Structured Schemas

Evidence:

- Current prompts/procedures are strong in narrative, but WF74 outputs still require interpretation.
- External guidance favors structured outputs, trace/eval loops, and clear tool/guardrail boundaries.

Impact:

- Free-text patch plans and status summaries slow down routing.
- Review quality depends too much on operator memory.

Recommendation:

- Standardize reusable prompt outputs into typed objects:
  - `finding`
  - `route`
  - `authority_boundary`
  - `evidence`
  - `target_owner`
  - `action_state`
  - `acceptance_proof`
  - `stop_line`
  - `rollback_or_wait_reason`

Acceptance proof:

- Router/proposer tests validate required fields.
- Startup/status packet can render the same schema without custom interpretation.

### P3 - Token/Cost Metadata Depth Is Still Owner-Gated And Overdue

Evidence:

- `token_cost_metadata_depth` remains open, priority 75, overdue.
- The current action is local-only token/cost metadata capture with redaction validation and rollback, only if approved later.

Impact:

- Learning-loop efficiency cannot fully optimize model/cost choices without better local cost metadata.
- It should not be auto-applied because payload/content privacy and pricing assumptions need an explicit local policy.

Recommendation:

- Keep this as owner-gated.
- Add it to the V2 decision docket as `owner_decision_required`, not generic overdue implementation failure.

### P3 - Startup/Status Card Can Mislead When Cached Inputs Are Critical

Evidence:

- `status_card_packet.py --read-only --render --validate` returned validation critical due stale cached inputs.
- The rendered card still says cron escalation 0 from the stale card, while fresh cron control is now error after the reminder contract issue.

Impact:

- Shallow status is intentionally fast, but it can understate current high-priority control-plane regression after new scheduler side effects.

Recommendation:

- When fresh cron control is error or WF74 has high-priority overdue open, status-card render should display "cached stale, fresh control-plane warning exists" if the fresh artifact is newer and worse than cache.

Acceptance proof:

- Status card validation flags stale critical and points to the current fresh artifact that caused divergence.

## V2 Upgrade Blueprint

### 1. Unified Decision Docket

Create a new generated proof packet:

`tmp/wf74-v2-decision-docket.json`

Required row fields:

- `item_id`
- `source_surface`
- `title`
- `severity`
- `action_state`
- `route`
- `owner`
- `evidence`
- `target_owner_surface`
- `next_action`
- `acceptance_commands`
- `stop_lines`
- `approval_required`
- `why_not_auto_apply`
- `expected_close_condition`

Decision states:

- `fix_now_local_governance`
- `owner_decision_required`
- `proof_refresh_only`
- `market_session_accrual`
- `skill_workshop_proposal`
- `procedure_update`
- `monitor_only`
- `hard_stop`

### 2. Side-Effect Lifecycle Contract

Every workflow that creates an enabled cron/reminder/job must pass a lifecycle check:

1. Create or verify scheduler object.
2. Verify contract exists or generate a review-only contract proposal.
3. Verify expected artifact or formal one-shot/TTL proof.
4. Run cron freshness/control.
5. Write audit/ledger entry with rollback or expiry.

No enabled scheduler object should be considered closeout-clean without this.

### 3. Learning Loop Eval Harness

Build a small local eval dataset from recent real cases:

- Phase 2A cron patch governance backfill.
- SQL source-lineage metadata drift adjacent repair.
- WF87 threshold not met despite session count met.
- AUTONOMY-SPINE parent blocked by child proof.
- Current WF87 after-market reminder missing cron contract.
- Token/cost metadata owner-gated overdue row.
- Completed workflow-routing job with residual maturity followups.

Each eval case should score:

- correct severity
- correct route
- correct owner
- correct action state
- no authority widening
- correct stop line
- correct acceptance proof

### 4. Prompt Pack V2

Recommended reusable prompt contracts:

`audit_to_docket_prompt`

```text
Given refreshed proof artifacts, classify each issue into exactly one decision state.
Do not merge monitor-only, owner-gated, proof-refresh, and implementation-fix rows.
For every row return evidence, owner surface, next action, stop line, and acceptance proof.
If a row would mutate cron, SQL, skills, finance, runtime, account, or external surfaces, mark approval_required=true unless a standing gate explicitly covers it.
```

`implementation_plan_prompt`

```text
Produce a scoped implementation lane plan only after the decision docket says the row is actionable.
Name allowed writes, read-first surfaces, validators, rollback, and stop lines.
Do not infer approval from the existence of a patch plan.
```

`review_closeout_prompt`

```text
Verify the final state against the acceptance commands.
If release/control proof is blocked by deterministic local metadata/proof residue, route a separate cleanup lane.
If the blocker requires source-content, schema, finance, cron schedule, runtime/config, account, external, or ambiguous authority mutation, stop for Randall.
```

### 5. Skill Enhancements

Use Skill Workshop after Randall approves the design:

- `veritas-self-improvement`: add the V2 decision-docket taxonomy and eval-loop requirement.
- `cron-automation-manager`: require freshness/TTL contract before enabled scheduler-job closeout.
- `disciplined-implementation`: add scheduler side-effect contract check after reminder/cron creation, parallel to adjacent release-contract cleanup.
- `veritas-workspace-audit-orchestrator`: add audit-to-docket output and "fresh artifacts beat cached status" rule.
- `project-continuity-manager`: define when monitor-only followups stay in daily memory versus PM/workflow lanes.
- `workspace-qa-pass`: add route-parity tests for status/startup/WF74/cron truth disagreement.

Do not apply these directly from this audit. They should be Skill Workshop proposals first.

### 6. Workflow Efficiency Changes

- Replace "ask follow-up questions to explain status rows" with a generated decision docket.
- Separate active repair count from open monitor count in startup/status.
- Make cron control/freshness/signal counts parity-checked.
- Move maturity followups into evidence-accrual state unless a new implementation blocker appears.
- Let PM stale lanes remain PM work, not WF74 learning-loop failures, unless they block the learning loop.
- Keep owner-gated token/cost metadata as a decision item, not a false implementation miss.

## Parallel Redesign Plan

### Lane 0 - Immediate Cron Reminder Governance Repair

Purpose:

- Clear the current P1 cron regression caused by the unregistered WF87 after-market reminder.

Likely surfaces:

- `state/cron-contracts/`
- cron freshness/control artifacts
- the script/tool path that created the reminder, if discoverable

Deliverable:

- Freshness contract or one-shot/TTL reminder contract for `WF87 shadow threshold after-market check`.

Acceptance:

- Cron freshness/control green or warning-only with no unregistered enabled job.
- WF74 no longer marks the reminder as a priority 92 regression.

Stop line:

- No schedule mutation unless separately approved.

### Lane 1 - WF74 Decision Docket V2

Purpose:

- Generate one authoritative review/routing docket from WF74 opportunities, auto-patch plans, workflow followups, improvement ledger rows, PM queue state, and cron/autonomy proof.

Likely surfaces:

- `scripts/wf74_improvement_opportunity_queue.py`
- `scripts/wf74_autonomy_work_router.py`
- new script or module for `wf74_decision_docket`
- tests for classification.

Deliverable:

- `tmp/wf74-v2-decision-docket.json`.

Acceptance:

- Every open opportunity/followup has exactly one action state.
- Startup/status can render active action versus monitor-only rows.

### Lane 2 - Cron Surface Parity V2

Purpose:

- Make cron signal scorecard, freshness spine, and cron control agree on enabled count, blocked count, unregistered jobs, stale jobs, and escalation state.

Likely surfaces:

- `scripts/cron_signal_scorecard.py`
- `scripts/cron_freshness_spine.py`
- `scripts/cron_control_packet.py`
- contract validator tests.

Deliverable:

- Cross-surface cron parity validator or shared source adapter.

Acceptance:

- All cron front doors agree after a new reminder/job is created.

### Lane 3 - Workflow Maturity And AUTONOMY-SPINE Parent/Child Contract

Purpose:

- Keep maturity blockers visible without resurfacing completed routing jobs as active implementation failures.

Likely surfaces:

- `scripts/workflow_advancement_scorecard.py`
- `scripts/wf87_v2_readiness_rollup.py`
- `scripts/autonomy_spine_readiness_rollup.py`
- `scripts/wf74_improvement_opportunity_queue.py`

Deliverable:

- Explicit state machine: `blocked_child_proof`, `accruing_evidence`, `implementation_missing`, `owner_gated`, `closed_monitor`.

Acceptance:

- WF87 and AUTONOMY-SPINE remain blocked honestly, but completed workflow-routing work does not keep returning as implementation residue.

### Lane 4 - Learning Loop Eval Harness

Purpose:

- Prevent regressions in WF74 classification, patch-plan routing, owner-gate handling, and stop-line behavior.

Likely surfaces:

- new local eval/test fixtures from recent real cases
- WF74 router/proposer tests
- changed-file validator routing.

Deliverable:

- A deterministic local test suite for learning-loop routing decisions.

Acceptance:

- Tests catch targetless high-priority plans, missing cron contracts, parent/child maturity suppression, and owner-gated false auto-apply.

### Lane 5 - Skill Workshop Proposal Batch

Purpose:

- Make the V2 rules durable without directly editing live skills from the audit.

Likely skills:

- `veritas-self-improvement`
- `cron-automation-manager`
- `disciplined-implementation`
- `veritas-workspace-audit-orchestrator`
- `workspace-qa-pass`
- `project-continuity-manager`

Deliverable:

- Pending Skill Workshop proposals, not applied skills.

Acceptance:

- `openclaw skills check` clean after proposal creation.
- Governance index updated only after proposals are applied.

### Lane 6 - Startup/Status V2 Rendering

Purpose:

- Make shallow status safe when cached status is stale but fresh control packets show new blockers.

Likely surfaces:

- `scripts/status_card_packet.py`
- `scripts/startup_brief_packet.py`
- `scripts/future_session_enhancement_packet.py`

Deliverable:

- Active-action count, monitor-only count, owner-gated count, hard-stop count, and stale-cache divergence warning.

Acceptance:

- Status card no longer reports "cron escalation 0" when fresher cron control is error.

## Recommended Execution Order

1. Lane 0: repair the WF87 reminder freshness contract gap.
2. Lane 2: make cron surfaces agree.
3. Lane 1: build the decision docket.
4. Lane 3: normalize maturity followups and AUTONOMY-SPINE parent/child states.
5. Lane 4: add eval fixtures from these exact cases.
6. Lane 6: upgrade startup/status rendering.
7. Lane 5: propose durable skill/procedure updates through Skill Workshop.

Reason:

- The cron regression is live now and should be cleared before broader V2 architecture work.
- Cron parity is foundational because WF74 and AUTONOMY-SPINE both consume cron truth.
- The decision docket should be built after the core control-plane truth is stable.

## Authority Boundaries

Allowed under this audit:

- Read/refresh local proof artifacts.
- Write this audit file.
- Record a compact daily-memory checkpoint.

Not allowed under this audit:

- No cron schedule mutation.
- No cron create/disable/delete.
- No skill proposal/application unless separately approved.
- No SQL/finance canon mutation.
- No portfolio/canon note/cash/sizing/risk mutation.
- No paper/live/brokerage/account action.
- No config/auth/runtime/channel mutation.
- No external delivery or public action.
- No owner approval inference.

## Deferred Checks

Deferred until an implementation lane is approved:

- Exact contract file diff for `WF87 shadow threshold after-market check`.
- Code-path trace of the reminder creation tool.
- Cron parity patch.
- WF74 docket implementation.
- Skill Workshop proposal generation.
- Startup/status renderer patch.

Deferred until market evidence lands:

- WF87 threshold closure after Tuesday, 2026-06-23 market close.
- AUTONOMY-SPINE maturity reassessment after WF87/reconciliation/cron proof clears.

## Bottom Line

The V2 upgrade should not make OpenClaw more autonomous by letting it do more side-effecting work. It should make OpenClaw more autonomous by making review, routing, proof, stop lines, and owner gates sharper.

The immediate repair candidate is narrow: govern the already-created WF87 after-market reminder with a freshness/TTL contract. The broader redesign is a decision-docket and eval-backed routing upgrade so future learning-loop outputs become actionable without Randall needing to ask what every status row means.
