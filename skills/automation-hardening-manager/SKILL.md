---
name: "automation-hardening-manager"
description: "Harden OTEL routing, autonomy levels, and card authority audits."
---

# Automation Hardening Manager

Use this skill when deciding what should run on schedule, what must remain human-gated, how to phase automation rollout, how to define trust gates and ownership boundaries, or how to turn a partially manual workflow into a safer automated operating path.

## Purpose

Move the OS toward better automation by improving architecture, contracts, review surfaces, and trust gates first. This skill does not exist to maximize automation volume. It exists to reduce unsafe ambiguity.

## Ownership

This skill owns automation architecture judgment:

- workflow-window design
- authority boundaries
- artifact contracts
- review surfaces
- trust gates
- rollout phases
- validation expectations

It does not replace `cron-automation-manager` for specific cron design, `memory-continuity-manager` for memory routing, `project-continuity-manager` for project pickup, `openclaw-operator` for runtime hygiene, or specialized finance/paper skills for gated authority.

## Core Review Questions

For any workflow under consideration, answer these in order:

1. What is the real job?
2. What is the canonical truth layer?
3. What artifacts are generated versus authoritative?
4. What can run safely without human review?
5. What still requires approval?
6. What failures would be silent or dangerous?
7. What validation proves the automation is helping rather than drifting?

If those answers are vague, the workflow is not ready for more autonomy.

## Hardening Workflow

1. Define the workflow boundary.
2. Name the owner layer for each output.
3. Separate artifact generation, review surface generation, apply/update actions, and canonical mutation.
4. Decide the current safe phase: manual, scheduled artifact generation, scheduled review surface, gated apply helper, or higher-autonomy maintenance.
5. Define trust gates before expanding autonomy.
6. Define the smallest useful schedule.
7. Validate outputs and downgrade confidence honestly when upstream inputs are stale, partial, or manual.
8. Record meaningful rollout state in the relevant continuity surface.

## Safe Automation Preference Order

Prefer this progression:

1. stable script output
2. stable scheduled artifacts
3. stable review/checklist surfaces
4. gated patch/apply helpers
5. selective autonomous maintenance only where trust is repeatedly proven

Do not jump from manual work directly to silent canonical rewrites.

## Automation Levels

Use these levels when proposing, reviewing, or hardening automation. Higher levels are not implied by lower-level success.

- Level 0: observe only.
- Level 1: route only.
- Level 2: review-only proof refresh.
- Level 3: helper-lane contract preparation with exact allowed writes.
- Level 4: proof execution, closeout ledger, and front-door refresh when eligible.
- Level 5: owner-gated action only after exact approval.

Level 5 does not mean autonomous execution. It means a separately approved owner-gated path exists and all scoped preconditions must still pass.

## Scaling And Repeatability Default

When a workflow is scaling in ticker count, PM lanes, SQL rows, cron windows, customer/service scenarios, or recurring proof passes, assume the next useful improvement is to make the work easier to repeat safely.

Before widening scope, check whether the current manual command sequence should become:

- a phase runner
- a manifest-driven command set
- a validator or acceptance harness
- a review-only packet generator
- a PM/heartbeat handoff artifact
- a skill or runbook procedure

Default posture:

- report-only first
- explicit stop lines in summary artifacts
- `--apply` or external/runtime/customer/finance actions only with exact approval scope
- boot/core Markdown files stay thin routers, not procedure dumps
- generated proof defaults to JSON/SQLite
- Markdown sidecars are opt-in only when a real human-review route exists

## PM / OTEL Delegation Hardening

Do not wire OTEL directly into implementation. OTEL and drift signals are evidence and metadata layers until a separate owner queue and validator contract authorize action.

Safe delegation chain:

`OTEL metadata -> WF74 opportunity queue -> WF74 router -> PM implementation jobs -> department allocator -> lane register -> helper/main execution -> closeout ledger -> refreshed front doors`

Required routing contract:

1. OTEL and runtime proof packets produce metadata-only signals.
2. WF74 opportunity rows classify signals by `category`, `priority`, `proof_source`, `owner_gate`, `recommended_action`, and `validation_command`.
3. WF74 may convert actionable, non-owner-gated opportunities into PM job candidates.
4. PM implementation jobs must add implementation class, validation budget, closeout mode, automation capabilities, department owner, collision group, target files, proof commands, and stop lines.
5. Parallel lane recommendation may emit department-aware lane contracts, but it must not spawn helpers by itself.
6. Lane-register leases exact write surfaces before any helper or main-session implementation work begins.
7. PM execution, worker, and verifier surfaces must separate candidate selection, lane preparation, proof execution, closeout ledger, front-door refresh, and resolved/completed state.

Department contract fields for active or ready implementation jobs:

- `department`
- `department_owner`
- `owner_workflow`
- `accountable_integrator`
- `allowed_execution_mode`
- `validation_budget`
- `closeout_mode`
- `automation_capabilities`
- `collision_group`
- proof commands
- acceptance criteria
- target files or write surfaces
- stop lines
- authority boundary

Validation should fail for active or ready jobs missing the core owner, execution-mode, proof, or boundary fields.

Hardening requirements:

1. Scheduled workers must be proof-only first. They may run guarded review/proof commands and mark already-resolved jobs clean, but must not infer approval or widen authority.
2. Every repair pass needs a post-repair quiescence refresh so resolved cron/PM/WF74 jobs do not remain visible as stale ready work.
3. Worker state must be explicit: candidate selected, lane prepared, proof executed, closeout ledgered, front doors refreshed, resolved, completed, or blocked.
4. Parallel allocation should start at one job per department and one job per collision group per pass unless later proof supports wider fanout.
5. `quiet_success` or no safe PM job selected is a valid clean result, not a failure.
6. Main session remains the accountable integrator for final truth, user-facing synthesis, and any boundary escalation.

Blocked expansions unless explicitly approved and separately proven:

- unattended patching from OTEL signals alone
- helper/session spawning directly from cron without a scoped lane contract
- cron schedule/config/auth/runtime mutation
- finance canon, portfolio, cash, sizing, risk, paper, live, account, customer, or external action
- treating a PM job, score, telemetry signal, or queue state as owner approval

Acceptance proof should include PM queue counts, selected job state, quiescence artifact, cron drift validation, lane-register terminal proof, refreshed front-door state, focused tests for PM queue capabilities and WF74 router contracts when touched, and clear warning/blocker classification.

## Autonomy Spine Promotion Rules

Use this rule when Randall asks to make finance automation more autonomous, promote P1/P2 workflows, harden WF86/WF87 readiness, or expand scheduled finance proof.

Autonomy promotion means attention, cadence, measurement, and proof priority only. It never grants capital, execution, account, canon, portfolio, cron-apply, predictive-claim, paper/live, brokerage, or owner-approval authority.

The autonomy spine is:

```text
WF55 outcome measurement -> WF76 scheduled cadence -> WF74 safe self-improvement -> WF71 helper factory
```

This spine exists to mature WF86/WF87 empirical gates. It does not bypass them.

Required pattern:

1. Promote WF55 before widening finance features.
   - Build neutral outcome ledgers from WF86/WF87 shadow and review artifacts.
   - Allowed event classes include `decision_observed`, `band_touched`, `band_rejected`, `stop_breached`, `missed_window`, `still_pending`, and `invalid_due_to_stale_data`.
   - Block probability, win-rate, expected-return, predictive-score, and model-performance claims until separate gates clear.
2. Harden WF76 cadence after measurement exists.
   - Cron may refresh read-only outcome, readiness, scorecard, and freshness artifacts.
   - Cron must not run `--apply`, mutate canon/portfolio, mutate schedule/config/runtime from inside the job, or infer approval.
3. Let WF74 consume only safe telemetry.
   - Inputs may include WF55 outcome ledger summaries, validator failures, changed-file routing, timing ledgers, cron drift, and repeated friction.
   - Outputs are proposals or candidate queues only.
   - No self-modification, base-model modification, capture-depth expansion, authority expansion, or finance execution readiness interpretation.
4. Use WF71 as the helper-factory owner.
   - Every helper lane needs exact deliverables, stop lines, allowed writes, proof artifacts, and closeout.
   - Helper output is untrusted until main verifies live artifacts and validators.

Acceptance proof for autonomy-spine implementation should include an authority-flags-false promotion contract, WF55 neutral outcome ledger without predictive claims, readiness rollup that stays `continue_accrual` until empirical gates clear, cron freshness contract for scheduled proof jobs, workflow router/capsule update when routes changed, focused tests, `py_compile` when scripts changed, file-size governance when core workflow/control files changed, and a daily memory entry.

Stop when clean cron, clean validators, clean cards, clean scorecards, or threshold progress could be misread as owner approval. When thresholds clear, the only allowed final state is `ready_for_owner_review_of_paper_pilot`; Randall exact approval is still required before any paper execution.

## Autonomous Card Semantic Authority Audit

When hardening WF86/WF87, WF85 deployment cards, WF78 owner-card routing, morning paper recommendation cards, autonomous routing/deployment cards, or scheduled finance surfaces that use words like `clean`, `approval card`, `owner review`, `review-ready`, `deployment`, `paper`, or `autonomous`, run a separate semantic authority audit before treating the posture as cron-green or route-green.

The audit must verify:

- `clean` means Randall review only, not approval.
- `approval card` means an owner-review artifact, not owner approval.
- no source artifact has any forbidden authority flag true, including capital deployment, trade execution, paper/live execution, brokerage/account action, money movement, canon/portfolio mutation, import/apply, or owner approval inference.
- clean-card counts and owner-review-card counts are reported separately from execution authority.
- WF86/WF87 maturity blockers remain visible: shadow threshold, clean market sessions, daylight proof, and reconciliation maturity.
- cron contracts include the audit artifact if scheduled jobs rely on autonomous-card/card-readiness surfaces.

Current proof pattern:

```powershell
python scripts\autonomous_routing_deployment_cards.py --write --validate
python scripts\wf87_autonomy_command_center.py --refresh-routing-cards --write --write-md --validate
python scripts\autonomous_card_authority_audit.py --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\workflow_routing_index.py --write --write-db --validate
```

Expected proof artifact:

```text
tmp\autonomous-card-authority-audit.json
```

Expected clean posture:

- `validation.status == ok`
- `summary.source_forbidden_true_count == 0`
- `summary.execution_allowed_count == 0`
- `summary.autonomous_execution_allowed_now == false`

Warnings or metrics about weak source wording are not execution blockers by themselves, but they must not hide authority drift. Any forbidden true authority path is a blocking error.

If a cron job refreshes or reports WF87 command-center state, WF85 deployment-card readiness, morning paper recommendation cards, or autonomous routing/deployment cards, it must either generate or require `tmp\autonomous-card-authority-audit.json` in its freshness contract.

A WF87 command-center refresh pattern should run:

```powershell
python scripts\wf87_autonomy_command_center.py --refresh-routing-cards --write --write-md --validate
python scripts\autonomous_card_authority_audit.py --write --validate
```

After an autonomy-card hardening change, run at minimum:

```powershell
python scripts\test_autonomous_card_authority_audit.py
python scripts\autonomous_card_authority_audit.py --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\workflow_router.py WF87 --answer all --write-capsules --validate
```

If the change touches WF85 surfaces, also run:

```powershell
python scripts\workflow_router.py WF85 --answer all --write-capsules --validate
```

A clean semantic audit is evidence only. It is not approval and not execution readiness.

## Cron / Skill / SQL-Consumer Hardening Route

After major cron-load reductions, skill-routing changes, or SQL consumer-authority proof changes, run:

```powershell
python scripts\automation_stack_hardening_pass.py --write --validate
```

This pass is report-only. It may not mutate cron definitions, skill files, SQL/cache rows, canon, portfolio, customer surfaces, paper/live/account state, runtime config, or approval state.

## WF78 Tier-Funnel Hardening

For WF78 routing, monitoring, or finance-promotion work, use the local tier-funnel machinery as the owner path. Gate outputs create evidence queues and owner-decision packets only.

Hard rules:

- `eligible_for_admission` and `eligible_for_owner_approval` are eligibility verdicts, not approval.
- `A-DEPLOY` means approval-ready packet only and never order authority.
- No promotion from score, checklist completion, legacy label, macro overlay, or external pattern alone.
- No import/apply, canon/portfolio mutation, production answer-path expansion, paper/live/account action, or approval inference.

## Autonomous Trading Hardening Rules

When hardening WF86/WF87 or any finance workflow that could later influence paper/live execution, separate activity from maturity proof.

Required distinctions:

- Assisted paper attempt: owner-approved order attempt that may expire, reject, cancel, partially fill, or fill.
- Terminal attempt: attempted order with a broker-terminal status.
- Maturity rep: clean filled/reconciled round trip or explicitly scoped proof category accepted by the workflow.
- Shadow decision: review-only would-buy/would-block evidence; not order approval.
- Daylight runtime proof: market-hours proof that gates are clean while fresh quotes, bands, stops, guard, kill switch, and anomaly state are actually available.

Hardening requirements:

1. Do not promote autonomy from threshold counts alone. Require threshold, source freshness, gate cleanliness, and reconciliation maturity together.
2. Do not classify fail-closed nighttime or after-hours blockers as daytime runtime blockers unless a market-hours probe confirms the same failure.
3. Do not reclassify at-rest blocked gates as clean without daylight proof.
4. Do not count expired, unfilled, rejected, canceled, unresolved, or stale paper attempts as maturity reps.
5. Add aging thresholds for pending outcome observations so shadow logging becomes quality calibration instead of raw count accumulation.
6. Keep blocker taxonomy explicit: maturity blockers, fail-closed-at-rest blockers, runtime blockers, and binding blockers.
7. A clean validator or cron run is evidence only; it does not imply owner approval, order authority, phase promotion, or live readiness.

Blocked automation expansions:

- order resubmission automation
- cadence-triggered order creation or execution
- autonomous phase promotion
- kill-switch creation, clearing, or lifecycle automation
- paper-to-live promotion
- at-rest-to-clean inference
- treating an alert, card, score, or shadow decision as owner approval

Acceptance proof for an autonomy-hardening change should include focused tests for new gate semantics, live proof artifacts showing authority flags remain false, cron freshness registration when scheduled proof is added, workflow route/continuity update, and explicit remaining blockers.

## Mechanism Choice

Use this routing logic:

- heartbeat: lightweight vigilance only
- cron: exact recurring windows, reminders, scheduled artifact generation
- detached/helper lane: bounded work needing one owner context outside the main lane
- manual: weak trust, sparse validation, high consequence, or owner-gated work

Do not assume a mechanism is live or approved unless it is validated in current operator protocol.

## Output Format

When using this skill, report:

- workflow under review
- current phase
- recommended next phase
- safe automation boundary
- schedule recommendation
- owner layer
- review window
- stop lines
- trust gates still missing
- validation or evidence

## Stop Lines

This skill does not authorize config/auth/network/service changes, external/public action, destructive cleanup, cleanup/archive/delete, cron schedule/config/runtime mutation, SQL import/promotion, portfolio/canon/cash/sizing/risk mutation, paper/live execution, brokerage/account action, money movement, capital deployment, autonomous phase promotion, predictive finance claims, paper-to-live promotion, universe import/apply, or owner approval inference.
