# Workflow 74 - Veritas Recursive Self-Improvement Loop

## Objective
- Build a bounded recursive self-improvement loop for Veritas: analyze outputs, corrections, code/workflow friction, validators, architecture, and continuity; convert the highest-leverage lessons into skills, validators, scripts, SOPs, queue items, or canonical memory updates.
- Improve operational intelligence and reliability without claiming base-model self-modification, autonomous authority expansion, or a second memory system.

## Current State
- Opened 2026-05-23 after Randall asked for an iterative RSI system that compounds Veritas capability over time.
- Current-state audit completed: `skills/veritas-self-improvement/SKILL.md` already provides trigger detection, lesson classification, routing, reflection template, audit-to-contract rule, and automation/SOP candidate routing.
- Architecture helper lane timed out before producing usable proof, so the initial plan uses the completed audit plus existing WF71/WF73/self-improvement machinery.
- Phase plan artifacts created: `tmp/wf74-rsi-phase-plan.json` and `tmp/wf74-rsi-phase-plan.md`.

## Bounded RSI Definition
- Allowed: file-backed reflection, correction trend reports, lesson routing, skill/playbook updates, validator/script proposals, answer-quality regression fixtures, and periodic review packets.
- Not allowed: base-model self-modification, self-preservation/replication/resource acquisition, authority expansion, config/auth/channel/service mutation without approval, second memory tree, owner-approval inference, or portfolio/trade/account/paper/live authority.

## Phased Approach

### Phase 0 - RSI contract and workflow opening
- Create this workflow note, Active Workflows row, and phase plan artifacts.
- Acceptance: purpose, stop lines, and parallel lanes are explicit.

### Phase 1 - Meaningful-work closeout gate
- Produce a lightweight checklist/schema for outcome, gap, lesson, destination, structural fix, and proof.
- Acceptance: useful for meaningful work only; no ritual bloat; routes to canonical destinations.

### Phase 2 - Lesson/correction trend report
- Generate review-only trend reports from daily memory, durable memory, workflow notes, and safe indexed session/memory sources.
- Acceptance: no new canon; cited evidence; repeated friction classified.

### Phase 3 - RSI validator pilot
- Add local proof that lessons were routed, duplicate-memory risk is controlled, repeated friction became queue/SOP/validator/skill candidates, and forbidden authority language is absent.
- Acceptance: validator/check is local and review-only; no authority expansion.

### Phase 4 - Periodic promotion review design
- Design weekly/monthly read-only review packet and cron/report contract.
- Acceptance: no schedule created without explicit approval; promotion remains main-session reviewed.

### Phase 5 - Answer/output quality regression suite
- Build a small fixture/rubric set for truthfulness, evidence, boundary discipline, concision, and actionability.
- Acceptance: improves decision quality without optimizing for flattery or verbosity.

### Phase 6 - Integration and compounding loop closeout
- Integrate the top 1-3 system improvements, run QA, update continuity, and set next-cycle cadence.
- Acceptance: real system changes land in skills/validators/scripts/playbooks/memory, not just chat.

## Parallel Completion Design
- Lane A: Closeout gate + `veritas-self-improvement` skill patch proposal.
- Lane B: Lesson/correction trend report prototype.
- Lane C: RSI validator design/pilot.
- Lane D: Periodic cadence contract, no scheduling.
- Lane E: Independent QA/challenge after lanes A-D.
- Veritas main: final integration, queue state, authority boundaries, and any durable memory/policy promotion.

## Outstanding
- Run independent QA over the Phase 1-3 WF74 scaffold artifacts before applying any skill/script/control changes beyond review artifacts.
- Decide whether Phase 3 validator should live as a standalone script, an `artifact_index.py` command, or a lightweight skill-owned checker.
- Decide whether Phase 4 cadence should be weekly, biweekly, or milestone-triggered before any cron scheduling.

## Blockers / Trust Gaps
- RSI can easily become theater if it does not write to files or validators.
- RSI can bloat memory if every lesson is promoted globally instead of routed to owning notes/skills.
- RSI can become unsafe if framed as autonomous self-modification or authority expansion. Keep it bounded to workspace improvement and main-session reviewed changes.

## Next Action
- Run lane E independent QA over `tmp/wf74-rsi-*`, `tmp/wf74-clawhub-*`, and `tmp/wf74-reflection-*`; after QA, decide whether to patch `skills/veritas-self-improvement/SKILL.md` and/or create a small validator entrypoint.

## Key Files
- `skills/veritas-self-improvement/SKILL.md` - current RSI procedure.
- `skills/memory-continuity-manager/SKILL.md` - memory routing guard.
- `AGENTS.md` - update-after-meaningful-work and orchestration rules.
- `MEMORY.md` - durable lessons and user preferences.
- `06. Playbooks/Active Workflows.md` - live queue state.
- `06. Playbooks/Project Continuity/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md` - staff/QA routing.
- `06. Playbooks/Project Continuity/Workflow 73 - Queue Index and Boot Surface Optimization.md` - control-plane/boot routing.
- `tmp/wf74-rsi-phase-plan.json` / `.md` - implementation-ready phase plan.

## Automation / Refresh Path
- Early phases are review/proposal and local validation only.
- Cron cadence is design-only until Randall explicitly approves a schedule and delivery/report target.

## Phase 1-3 scaffold implementation - 2026-05-23 20:39 MST
- Randall approved continuing WF74 with research integration, ClawHub evaluator inspection, reflection-to-proposal pipeline, lesson/correction trend report, validator/evaluation harness, independent QA before improvements, and file-backed/test-backed/reversible changes.
- Research integrated at `tmp/wf74-rsi-research-brief.json/.md`: strongest support is bounded critique -> revise -> evaluate -> retain loops, not open-ended autonomous self-modification.
- ClawHub inspection queue created at `tmp/wf74-clawhub-rsi-inspection-queue.json/.md`; first inspection batch is evaluator-focused: `agent-evaluation` and `agent-qa-gates`. Goal is to design WF74's evaluation harness, not install more skills.
- Reflection-to-proposal pipeline created at `tmp/wf74-reflection-to-proposal-pipeline.json/.md`: capture, classify, evidence-bind, propose, evaluate, apply/defer, monitor.
- Lesson/correction trend report pilot created at `tmp/wf74-rsi-trend-report.json/.md` from May daily-memory notes; it is review-only and creates no new canon.
- Evaluation harness seeded at `tmp/wf74-rsi-evaluation-harness.json/.md` with dimensions for truthfulness, boundary safety, continuity routing, actionability, regression proof, and signal/noise.
- Validator artifact created at `tmp/wf74-rsi-validation.json/.md`; independent QA is required before applying skill/script/control changes beyond review artifacts.
- Boundary remains unchanged: no base-model self-modification, no autonomous authority expansion, no second memory tree, no config/auth/channel/service mutation without approval, no owner-approval inference, and no portfolio/trade/account/paper/live authority.


## Phase 1-3 independent QA - 2026-05-23 20:39 MST
- Independent read-only QA passed with no blockers after inspecting the WF74 scaffold artifacts, `scripts/wf74_rsi.py`, `skills/veritas-self-improvement/SKILL.md`, Active Workflows, this continuity note, and daily memory.
- Proof: `python -m py_compile scripts\wf74_rsi.py` passed; `python scripts\wf74_rsi.py` passed with `status=ok checks=20 failed=0`.
- Confirmed: research brief captures bounded RSI; ClawHub evaluator skills are first inspection batch and installs are blocked; reflection-to-proposal pipeline exists; trend report is review-only / no new canon; evaluation harness covers truthfulness, boundary safety, continuity routing, actionability, regression proof, and signal/noise; independent QA before apply is required.
- Non-blocking residue: `scripts/wf74_rsi.py` regenerates timestamps/artifacts and is not pure read-only, validation is narrow, trend report is May daily-note keyword pilot only, and the evaluation harness is seeded rather than a full scoring suite.
- Next repair: add `--validate-only` to `scripts/wf74_rsi.py` before treating it as the stable Phase 3 validator entrypoint.


## Node/Go OS upgrade chain planning - 2026-05-23 21:18 MST
- Randall asked how to add Node and Go scripts to the current OS and where to inject them into active workflows.
- Research lanes completed for Go, Node, and full OS orchestration. Result: keep Python as the core workflow/finance/SQL/artifact/validator spine; add Node only as a thin OpenClaw/ClawHub inspection helper layer; add Go later only as hardened standalone validators after Python contracts stabilize.
- Planning artifacts created: `tmp/wf74-node-go-os-upgrade-chain.json` and `tmp/wf74-node-go-os-upgrade-chain.md`.
- Active workflows to act on now: WF74 first (`--validate-only`), WF72 second (refresh/rebuild `tmp/workspace-index.sqlite` before broad stale checks), WF70/WF66 third (next duplicated Q1 consumer migration), WF73/WF71 as governance/load-budget routing, and WF68 remains P0 advisor goal lock.
- Node first candidate: `scripts/wf74_clawhub_inspect.mjs` to inspect evaluator skills from `tmp/wf74-clawhub-rsi-inspection-queue.json` and write review-only `tmp/wf74-clawhub-inspection-results.json/.md`; no install/update/login/publish, no npm/package sprawl, and no config/auth/channel/service mutation.
- Go first candidate: `scripts/go/cmd/wf74-boundary-lint` with generated binary only under `tmp/go-build/`; it scans WF74 artifacts for forbidden authority language and boundary flags after Python validate-only proof is stable.
- Next concrete action: implement WF74 Phase 1 validator hardening by adding true `--validate-only` to `scripts/wf74_rsi.py`, then run py_compile, validate-only, normal generation/validation if needed, and independent QA before Node/Go implementation.


## WF74 V1 implementation pass - 2026-05-23 21:55 MST
- Implemented true `--validate-only` for `scripts/wf74_rsi.py`; validation can now read existing WF74 artifacts without rewriting tracked WF74 artifacts/timestamps. Proof: `python -m py_compile scripts\wf74_rsi.py`; `python scripts\wf74_rsi.py --validate-only` returned `status=ok checks=22 failed=0`.
- Implemented Node ClawHub evaluator inspection helper `scripts/wf74_clawhub_inspect.mjs`; inspected batch 1 (`agent-evaluation`, `agent-qa-gates`) and wrote review-only `tmp/wf74-clawhub-inspection-results.json/.md`. Proof: `node --check`, JSON parse, `install_allowed=false`, `mutations_performed=false`, `.clawhub/lock.json` unchanged.
- Implemented Go boundary lint pilot under `scripts/go/` with generated binary `tmp/go-build/wf74-boundary-lint.exe`; report `tmp/wf74-boundary-lint-report.json` returned `status=ok checks=13 failed=0`. Proof: `go -C scripts\go test ./...`; Go build; boundary-lint run.
- WF74 validator now recognizes Node inspection and Go boundary-lint proof when present; current `tmp/wf74-rsi-validation.json` is `status=ok` with 22 checks / 0 failed.
- Opened WF75 as the broader opportunity-intelligence expansion lane so Veritas can scale beyond finance into AI technology, productivity/workflow, business/monetization, learning/teaching, and broader monetary-opportunity discovery without creating a second control plane or widening external/finance authority.
- Final independent QA is running; if PASS, WF74 V1 can close and the next priority action is WF72 workspace-index refresh/rebuild.

## Sequential Phase 0-7 closeout - 2026-05-23 22:58 MST
- Randall requested sequential completion of Phase 0 through Phase 7. Main-session reconciliation found Phase 0/1/3/4/5/6 largely implemented already; Phase 2 needed stronger explicit fixture/rubric coverage and was patched in `scripts/wf74_rsi.py`.
- Phase 1 proof: `--validate-only` reads existing WF74 artifacts without writing refreshed timestamps; `python scripts\wf74_rsi.py --validate-only` returned `status=ok checks=24 failed=0 mode=validate-only` after regeneration.
- Phase 2 proof: `tmp/wf74-rsi-evaluation-harness.json/.md` now includes explicit fixture rubrics for stale current-state claims, approval inference from green/validator states, chat-only corrections, and untested skill/validator patches, each with required checks plus pass/fail examples.
- Phase 3 proof: `scripts/wf74_clawhub_inspect.mjs` inspected `agent-evaluation` and `agent-qa-gates` only; `tmp/wf74-clawhub-inspection-results.json/.md` has `install_allowed=false`, `mutations_performed=false`, and `lock_unchanged=true`; no install/update/login/publish/package-sprawl path was used.
- Phase 4 proof: `scripts/workspace_index.py` refreshed `tmp/workspace-index.sqlite` / `tmp/workspace-index-report.json` at `2026-05-24T05:53:25Z` with documents=737, artifacts=367, freshness=1104; `python scripts\artifact_index.py incremental` and `python scripts\artifact_index.py validate` passed 27/0.
- Phase 5 proof: WF70 Phase 5 bridge/reconciliation registry migration is complete across `current_window_artifact_index.py`, `run_summary_refresh.py`, `chain_manifest.py`, `fundamental_ir_reconciliation_packets.py`, and `official_earnings_bridge.py`; `tmp/wf70-phase5-bridge-recon-registry-migration.json` shows `bridge_match=true`, `recon_match=true`, and no known Q1 path consumer residue. Validators passed for official captures, fundamental reconciliation, and official earnings bridge.
- Phase 6 proof: Go boundary lint under `scripts/go/cmd/wf74-boundary-lint` passed `go -C scripts\go test ./...`; generated binary is only under `tmp/go-build/wf74-boundary-lint.exe`; `tmp/wf74-boundary-lint-report.json` shows `status=ok checks=13 failed=0`.
- Phase 7 proof: independent read-only QA passed with no blockers. Residue before closeout was only stale control-surface wording, repaired in `06. Playbooks/Active Workflows.md`.
- Boundary remains unchanged: no base-model self-modification, autonomous authority expansion, second memory tree, config/auth/channel/service mutation, owner-approval inference, portfolio/canon mutation, trade/account action, paper/live order authority, blind ClawHub install, npm package sprawl, or Go control plane. WF74 V1 is complete and should now be used as a monitor/gate on meaningful corrections, completed work, validator failures, and repeated friction rather than run as ritual.



## Next-level workspace intelligence audit synthesis - 2026-05-24 16:10 MST

- Completed four no-mutation audit lanes: workspace organization, RSI/model optimization web scout, finance intelligence pipeline, and automation/runtime efficiency. Synthesis written to `tmp/next-level-workspace-intelligence-roadmap.*`.
- Main verdict: next-level upgrade should prioritize eval/outcome/trust coherence and narrow cleanup, not more candidate generation, broad archive sweeps, generic reflection, or new KG/vector memory. Top priorities: WF74 outcome eval suite v2 + finance-boundary fixtures; WF55 owner-decision/outcome retention ledger; advisor packet trust-coherence gate; narrow WF72 cleanup packets; prove WF76 before adding lean-OS cron; official-source reconciliation readiness queue; retrieval-quality scorecard before KG/vector expansion.
- Current blockers/trust limits: all current capital packets remain partial/action-blocked; WF55 remains NOT_READY; deployment presentation is degraded; cron has one red morning finance lane; archive suggestions remain apply_allowed=false; workspace boundary warning-only residue is `.claude/` and proof-critical `tmp/sql-canon-cache-rollback-phase3c.py`.
- Boundary preserved: no moves/deletes, no cron/config/auth/channel/service/runtime mutation, no canon/portfolio/trade/account/paper/live action, no money movement, no owner approval inference.

## Outcome eval suite v2 implementation - 2026-05-24 16:30 MST

- Implemented validate-only/report-only WF74 outcome eval suite v2 inside `scripts/wf74_rsi.py` rather than creating a parallel control plane.
- Coverage now includes seven failure modes with at least one valid and one invalid fixture each: stale current-state claim, owner-approval inference, helper overload/missing proof, patch without validation/rollback, archive no-loss proof gap, retrieval stale-vs-current miss, and finance recommendation missing source freshness/authority boundary.
- Added `python scripts/wf74_rsi.py --outcome-eval-v2` to write `tmp/wf74-outcome-eval-suite-v2.json/.md`; added `scripts/test_wf74_rsi_outcome_eval_v2.py`; documented commands/boundaries in `scripts/README.md`.
- Proof: `python -m py_compile scripts\wf74_rsi.py scripts\test_wf74_rsi_outcome_eval_v2.py`; `python scripts\wf74_rsi.py --outcome-eval-v2` returned status ok / 7 categories / 14 fixtures / 0 failed classifications; `python scripts\test_wf74_rsi_outcome_eval_v2.py` passed; existing `python scripts\wf74_rsi.py --validate-only` returned status ok / 29 checks / 0 failed.
- Additional gates: `python scripts\artifact_index.py validate` passed 28/0; `python scripts\dashboard_truth_lint.py` passed with one informational finding; `python scripts\workspace_boundary_check.py` still exits warning for pre-existing `.claude/` and proof-critical `tmp/sql-canon-cache-rollback-phase3c.py` residues.
- Boundary preserved: report-only classifier coverage; no canon/portfolio mutation, owner approval, finance authority expansion, config/auth/channel/service/runtime mutation, destructive cleanup, external action, or trade/account/paper/live authority.

## 2026-06-06 RSI + OTEL finance-learning handoff

Randall approved the next direction for RSI in the finance stack. The conclusion is that WF74 should not try to "learn" from vibes or runtime metrics alone. It should consume two validated inputs:
- WF55 semantic outcome grades: whether a finance recommendation, no-chase call, owner-card prep, or WF67 paper-card setup held up against later evidence.
- OpenClaw native OTEL operational telemetry: model/tool/script/cron cost, latency, token usage, failover/error, blocked-tool, stuck-session, and harness-friction signals.

Current OTEL posture:
- `diagnostics-otel` is installed, loaded, and pinned at `@openclaw/diagnostics-otel@2026.6.1`.
- The stale legacy plugin install index was moved aside on 2026-06-06.
- `diagnostics.otel.enabled=false` because the configured local receiver `http://127.0.0.1:4318` is not running; OpenClaw provides the native exporter/plugin, not a built-in OTLP receiver/backend.
- Content capture and logs must remain off unless separately approved.

Next-lane target:
- Extend the WF74/model-quality layer only after WF55 captures finance decision outcomes.
- Build a review-only `model-quality-scorecard` that joins WF55 outcome quality with OTEL-style runtime dimensions: cost, latency, reliability, failover/errors, blocked tools, harness failures, and session friction.
- Treat OTEL as operational evidence only; do not use OTEL alone to score investment correctness.

Acceptance proof:
- WF55 preview/validator proof is clean.
- WF74 validate-only and outcome-eval-v2 are clean.
- Any OTEL backend addition is standard collector/backend work with config/runtime approval, privacy proof, logs/content capture off, and no custom local receiver revival unless explicitly justified.

Boundary:
- No base-model self-modification, autonomous authority expansion, second memory tree, owner approval inference, finance authority expansion, portfolio/canon mutation, capital deployment, paper/live/account action, or raw prompt/tool/system-content telemetry capture.

## 2026-06-06 evaluator and skill-sprawl hardening

Randall asked to proceed after the skill evaluation concluded that WF74 should tighten existing owner surfaces before adding new skill directories.

Implemented:
- Expanded `scripts/wf74_rsi.py` outcome-eval coverage from 10 categories / 20 fixtures to 14 categories / 28 fixtures.
- Added real-observed failure families: Windows/PowerShell shell mismatch, taxonomy alias mapping gaps, post-compaction recovery discipline, and skill-sprawl governance.
- Updated `scripts/test_wf74_rsi_outcome_eval_v2.py` to enforce the new fixture count and required category presence.
- Updated `skills/veritas-self-improvement/SKILL.md` so current evaluator hardening prioritizes those observed failure modes before any new skill creation.
- Updated `scripts/README.md`, Active Workflows, and the Skills Governance Index.

Proof:
- `python -m py_compile scripts\wf74_rsi.py scripts\test_wf74_rsi_outcome_eval_v2.py`
- `python scripts\wf74_rsi.py --outcome-eval-v2` -> `status=ok categories=14 fixtures=28 failed_classifications=0`
- `python scripts\test_wf74_rsi_outcome_eval_v2.py` -> ok
- `python scripts\wf74_rsi.py --validate-only` -> `status=ok checks=29 failed=0`
- `python scripts\wf74_rsi.py` -> regenerated WF74 artifacts with `status=ok checks=29 failed=0`
- `openclaw skills check` -> 92 total, 50 visible, 0 missing requirements
- `python scripts\automation_stack_hardening_pass.py --write --validate` -> status ok, validation ok, 159 checks, 0 critical, 0 warnings
- `python scripts\artifact_index.py incremental` and `python scripts\artifact_index.py validate` -> validate ok, 28 checks, 0 failed

Boundary:
- No new skill directories.
- No config/auth/channel/service/runtime mutation.
- No cron mutation by this pass.
- No canon/portfolio mutation, capital deployment, paper/live/account action, money movement, or owner approval inference.
- One unrelated observed posture difference remains: automation hardening currently reports 25 enabled cron jobs, while older written posture referenced 24; this pass did not mutate cron definitions.

## 2026-06-06 decision-context RSI upgrade handoff

Randall approved upgrading finance intelligence objects now that ticker freshness, post-close quote overlay, WF55, WF78, and the automation trust spine are stronger. WF74 should use this as evidence for better evaluation, not as authority expansion.

Next-lane target:
- Extend model/decision-quality scoring only after WF55 exposes stable outcome tracking IDs and preview grades.
- Join semantic outcome quality from WF55 with operational dimensions from OpenClaw OTEL-style evidence: cost, latency, token use, failover/errors, blocked tools, harness failures, and session friction.
- Add a review-only `model-quality-scorecard` scaffold that can compare recommendation quality across model/session/workflow paths without claiming investment correctness from runtime metrics alone.
- Add evaluator fixtures for stale weekend price use, missing post-close overlay, stale order-card approval attempt, and recommendation without outcome-tracking ID.

Acceptance proof:
- `python scripts\wf74_rsi.py --validate-only`
- `python scripts\wf74_rsi.py --outcome-eval-v2`
- `python scripts\veritas_harness_scorecard.py --fast --write --validate`
- WF55 preview/validator proof remains clean.

Boundary:
- Review-only evaluation and scoring.
- No base-model self-modification, no autonomous authority expansion, no OTEL backend/config enablement in this lane, no raw prompt/content telemetry capture, no finance authority expansion, no portfolio/canon mutation, no capital deployment, no paper/live/account action, and no owner approval inference.

## 2026-06-07 model-quality-scorecard scaffold built

Randall asked to also measure model implementation quality and performance, and approved continuing the implementation. Built the review-only scaffold called for above.

Owner/entrypoint: `python scripts\model_quality_scorecard.py --write --write-md --validate` -> `tmp\model-quality-scorecard.json` (+ optional `.md`), append-only history `data\state-history\model-quality-scorecard.jsonl`. Schema `wf74.model_quality_scorecard.v1`.

Design - three tracks plus an attribution gap:
- `implementation_quality` (readiness: active now, no WF55 dependency): joins behavior-eval discipline (`wf74-outcome-eval-suite-v2.json`: 14 categories / 28 fixtures / 0 failed classifications / pass_rate 1.0), validator pass rate (`runtime-performance-scorecard.json`: 42/42 ok), and surface-readiness pass rate (`veritas-harness-scorecard.json`).
- `performance` (readiness: partial): runtime/build latency is live from the runtime performance scorecard; the seven OTEL operational dimensions (cost, token_use, latency, failover_errors, blocked_tools, harness_failures, session_friction) report `pending_otel_backend` because `diagnostics.otel.enabled=false` and no backend is enabled in this lane.
- `decision_quality` (readiness: blocked_on_wf55): reads `recommendation-outcome-ledger-current.json` (15 tracking rows, 0 graded, durable_append_allowed=false). Validator forces this track to stay blocked while WF55 durable append is not allowed.
- `model_attribution` (readiness: missing, coverage 0.0): no producing surface stamps model/session today, so cross-model comparison is impossible. Scaffold defines schema slots (`model_path`, `session_id`, `workflow`, `produced_at_utc`) and names the next step.

Proof: `python -m py_compile scripts\model_quality_scorecard.py` (COMPILE_OK); `--write --write-md --validate` returns `status=scaffold_active validation=ok active_tracks=implementation_quality,performance critical=0 warnings=0`; JSON/MD/history artifacts verified.

Next-lane targets to make model-vs-model comparison real (in priority order):
1. Stamp model/session attribution on producing surfaces (WF55 ledger rows, PM job queue, runtime scorecard command rows), then join here.
2. Revive WF55 outcome grading to unblock `decision_quality`.
3. Plan an OTEL backend in a separate config/runtime/privacy lane for the `performance` dimensions.

Boundary unchanged: review-only scaffold, not a deployed model ranker; authority_boundary flags assert no model-ranking claim, no investment-correctness-from-runtime-metrics, no base-model self-modification, no OTEL enablement here, no owner-approval inference, no portfolio/canon mutation, no paper/live/account action.

## 2026-06-07 control-surface sprawl lesson

Randall challenged the overhead created by workflow routing, PM state, heartbeat, cron, validator, and closeout surfaces. The implementation passes proved a durable WF74 lesson: compression can become new sprawl unless every new packet/router/index has a primary-route contract and an explicit relationship to the old surfaces.

Rule captured in WF74:
- Every new control/proof surface must name its owner and first-hop route.
- Old surfaces must be marked retired, compatibility-only, or drill-in-only; they cannot remain equal peers by accident.
- Every implementation/change path must carry a validation budget so heavy validators do not return to the normal path.
- A fast-path or regression check must prove the route, because prose-only instructions decay.

Applied examples from this pass:
- PM state, queue, heartbeat, and handoff now route through `pm_control_packet.py`; legacy sidecars are explicit `--write-compat`.
- Cron freshness, scorecard, and escalation now route through `cron_control_packet.py`.
- Changed files route through `changed_file_validator_router.py`; timing proof lives in `validator_timing_ledger.py`.
- DB lifecycle and WF75 major closeout stay reserved for major/shared routes instead of normal validation.

WF74 hardening:
- Added outcome-eval category `control_surface_sprawl_gate`.
- Added valid/invalid fixtures to catch compression passes that add new peer packets without owner, retirement/drill-in status, validation budget, and fast-path proof.

## 2026-06-09 efficiency-loop scorecard integration

- Randall asked to continue implementing the most efficient plan so coding, models, implementation, and routing have feedback/efficiency loops until the system reaches a more enhanced state.
- Implemented the loop inside the existing WF74 scorecard instead of adding a new peer control packet. `scripts/model_quality_scorecard.py` now writes `efficiency_loops` with five domains: coding validation, model quality, implementation queue, routing efficiency, and cron/OTEL operations.
- The loop joins existing proof only: `runtime-performance-scorecard`, `changed-file-validator-router`, `model-run-ledger`, finance correctness ledger, Spark canary monitor, OTEL ops, PM control packet, route-efficiency scorecard, WF73 audit, and cron control packet.
- Added `scripts/test_model_quality_scorecard.py` to enforce loop domains, owner surfaces, next actions, proof sources, enhancement queue, and false authority flags.
- Wired `changed_file_validator_router.py` so model-quality/OTEL edits route to `test_model_quality_scorecard.py`; documented the scorecard as the efficiency-loop owner in `scripts/README.md`.
- Current generated state: `tmp/model-quality-scorecard.json` validation `ok`, `efficiency_loops.status=active_partial`, `loop_count=5`, domains `coding, implementation, models, operations, routing`.
- Main-session follow-up hardened the scorecard schema with standing interpretation rules: input drift is monitor/review context unless proof is missing/invalid/blocked; producers refresh before consumers; OTEL remains operational telemetry, not coding-skill or model-rank proof; freshness warnings require an explicit window before becoming blockers; stale external source data must be labeled instead of hidden.
- Current loop interpretation:
  - Coding validation loop active with warning because the worktree has broad pre-existing residue; diff-size is a routing aid, not clean-state proof.
  - Model-quality loop active with known gates: model/session applicable coverage is clean for stamped agent/cron rows, Spark canaries are OK, ex-ante finance rule checks are OK, but WF55 outcome grades are still 0 and OTEL lacks detailed model/tool/cost fields.
  - Implementation loop active: PM packet green, 0 stale lanes, 0 blocked lanes, top next action remains WF85.
  - Routing loop active with warnings: route probes are OK/fast, but WF73 still reports boot-size guard and cron main-review queue warnings.
  - Cron/OTEL loop active with warnings: cron control is OK with escalation 0, OTEL collector is healthy, but detailed field capture remains a separate local-only privacy/config design gate.
- Proof passed: Python compile for touched scripts, `test_model_quality_scorecard.py`, direct `model_quality_scorecard.py --write --write-md --validate`, full `wf74_model_quality_collection_cron_runner.py --write --validate --include-harness` with 12/12 OK, scoped changed-file validator route, `fast_path_qa.py --write --validate --no-probes`, `repeatable_work_closeout.py --validation-budget narrow --write --validate`, `training_dataset_candidate_builder.py --write --write-md --validate`, `cron_control_packet.py`, `pm_control_packet.py`, `wf73_control_plane_audit.py` warning-only for known review surfaces, and artifact index incremental/validate.
- Boundary preserved: review-only efficiency/feedback proof only; no model ranking claim, no investment-correctness-from-runtime claim, no base-model self-modification, no OTEL capture-depth/config/runtime change, no WF55 grade assignment, no canon/portfolio mutation, no capital approval/deployment, no paper/live/account action, no external/customer action, and no owner approval inference.
- Updated `scripts/test_wf74_rsi_outcome_eval_v2.py` expected coverage to 17 categories / 34 fixtures.

Boundary:
- This is workflow/control-plane learning only. It grants no canon/portfolio mutation, finance authority expansion, cron schedule/runtime/config mutation, archive/delete authority, customer/external action, paper/live/account action, or owner approval inference.

## 2026-06-07 queryable OTEL ops loop

Randall approved turning local OpenClaw OTEL from collector-log counts into queryable operational evidence. Implemented one owner path, `scripts\otel_ops_control.py`, instead of adding separate parsers to model-quality, cron, QA, and closeout scripts.

Current route:
- `python scripts\otel_ops_control.py --write --write-db --multi-window --validate`
- Outputs: `tmp\otel-ops-control.json`, `tmp\otel-ops-window-summary.json`, `tmp\otel-ops-events.jsonl`, `tmp\otel-ops.sqlite`.
- Consumers: `cron_control_packet.py`, `fast_path_qa.py`, `model_quality_scorecard.py`, `validator_timing_ledger.py`, `repeatable_work_closeout.py`, and changed-file validator routing.
- Daily cron: `Ops - OTEL Local Digest`, isolated/no-delivery, `45 21 * * *` America/Phoenix; first natural run completed ok in ~56.8s.

What it can prove now:
- Official collector health and loopback binding.
- Metric batch count, datapoint count, trace batch count, span count, warning/error lines, and legacy receipt rows when present.
- Multi-window operational posture: 1h and 6h intraday/post-change checks, 24h daily control, 7d trend review, and 30d baseline review in a single owner artifact.
- Action candidates such as missing model/token/tool/session dimensions and daily digest readiness.

What it cannot prove from the current basic debug collector:
- Model/provider, token use, cost, tool names/failures, session/workflow IDs, or request-level latency. Those require a separate runtime/config/privacy lane and must not be inferred from counts.

Sprawl lesson:
- Observability surfaces must have exactly one owner packet and named consumers.
- Cron/reminder paths should refresh the owner packet and route action candidates, not independently parse raw telemetry.
- OTEL is operational evidence only; it does not score investment correctness, grant model-ranking authority, or widen content logging.

2026-06-09 follow-up:
- Implemented the multi-window summary inside `otel_ops_control.py` rather than adding four separate scorecards.
- `tmp/otel-ops-control.json` remains the default 24h cron/PM control packet; `tmp/otel-ops-window-summary.json` is the follow-up artifact for intraday, weekly trend, and monthly baseline review.
- `wf74_model_quality_collection_cron_runner.py` now runs OTEL with `--multi-window`, cron freshness expects the window-summary artifact, artifact index discovers it, and changed-file validation routes OTEL/model-quality edits through the multi-window command.
- Boundary unchanged: no collector config mutation, runtime config mutation, telemetry capture-depth expansion, model ranking, coding-skill inference, WF55 outcome grading, finance canon/portfolio mutation, capital deployment, paper/live/account action, or owner approval inference.

2026-06-10 hardening follow-up:
- Reconciled the challenger review against live state. WF84/WF85 fast routing and DB lifecycle intent labels are already implemented and validated; the remaining safe local gaps were regression coverage and an OTEL compatibility bridge.
- Added `tmp/otel/control-loop.json` as a legacy audit bridge written by `otel_ops_control.py`. It points to `tmp/otel-ops-control.json` as canonical owner and exists only so older audit language does not falsely report the main OTEL loop missing.
- Added `scripts/test_otel_ops_control.py` to protect the 1h/6h/24h/7d/30d window contract and the legacy bridge's non-owner role.
- Added `scripts/test_full_intelligence_answer_parity.py` to protect the band-status drift taxonomy: raw legacy band labels such as above-band/no-chase or below-band/repair normalize semantically, while material states such as `BELOW_STOP` stay explicit.
- Changed-file routing now runs the OTEL regression for OTEL/model-quality edits and the parity semantic regression for full-answer parity edits.
- Remaining recommendations still owner-gated or separate lanes: archive candidates require exact approval and gated archive apply; git hygiene/checkpoint strategy needs a separate classification pass; root exception safety remains documented governance plus current boundary checks, not proof that every future file under those paths is safe.

## 2026-06-08 Spark cron canary scorecard join

Randall asked whether the first natural Spark cron canary result was being logged in WF74. It was only captured in `tmp\cron-spark-canary-monitor.json`, not in the WF74 model-quality scorecard.

Implemented a narrow scorecard join:
- `scripts\model_quality_scorecard.py` now consumes `tmp\cron-spark-canary-monitor.json`.
- The `performance.spark_cron_canary` section records model under test, required thinking level, configured/xhigh counts, ok run count, pending first-run count, error count, duration regression count, and successful natural run summaries.
- First logged natural run: `Finance - Morning Control Digest Proof Refresh`, `codex/gpt-5.3-codex-spark`, `xhigh`, status `ok`, duration `21806ms`, duration ratio `0.738` vs baseline.

Proof:
- `python -m py_compile scripts\model_quality_scorecard.py`
- `python scripts\model_quality_scorecard.py --write --write-md --validate` -> `validation=ok`, `critical=0`, `warnings=0`

Boundary unchanged:
- This is operational canary evidence only. It does not create a model-ranking claim, finance-correctness claim, base-model self-modification, owner-approval inference, portfolio/canon mutation, or paper/live/account authority.

## 2026-06-08 performance/model-quality/finance-correctness collection implementation

Randall approved full implementation for continuing performance, model quality, and finance correctness collection. Implemented the collection layer as WF74 review-only proof surfaces instead of extending OTEL beyond its current local/privacy boundary.

New owner surfaces:
- `scripts\wf74_model_quality_collection_cron_runner.py` -> `tmp\wf74-model-quality-collection-cron-runner.json` / `.md`.
- `scripts\model_run_ledger.py` -> `tmp\model-run-ledger-current.json` / `.md`, history `data\state-history\model-run-ledger.jsonl`.
- `scripts\finance_recommendation_correctness_ledger.py` -> `tmp\finance-recommendation-correctness-ledger-current.json` / `.md`, history `data\state-history\finance-recommendation-correctness-ledger.jsonl`.
- `scripts\model_quality_scorecard.py` now consumes both ledgers in addition to OTEL ops, runtime performance, Spark canary, and WF55 recommendation outcome preview.
- `scripts\artifact_index.py` now indexes the OTEL/model-run/finance-correctness/model-quality surfaces as truth-spine proof artifacts.

Cron integration:
- Existing job `Ops - OTEL Local Digest` now runs the WF74 collection runner at `40 7,15,21 * * *` America/Phoenix.
- The job is isolated/no-delivery and returns `NO_REPLY` on clean proof.
- `scripts\cron_freshness_spine.py` registers the runner, OTEL ops, model-run ledger, finance-correctness ledger, and model-quality scorecard as expected artifacts.
- Forced proof run completed ok: run ID `manual:b911d479-13aa-48fe-b662-937e08450363:1780933771258:5`, duration 45440ms, model `openai/gpt-5.4`, session ID captured by cron history.

Current measured state:
- Model/run ledger: 17 rows, model attribution coverage 0.7647, session attribution coverage 0.6471. Cron run history is now included for provider/model/session/token/duration attribution when present.
- Finance correctness ledger: 7 current recommendation rows, 7 ok, 0 warning, 0 blocked. Rows are ex-ante rule/boundary checks only; later outcome grades remain unassigned.
- WF74 model-quality scorecard: active tracks now include `implementation_quality`, `performance`, and `decision_quality`; model attribution is `partial`; decision quality is `partial_ex_ante_active_outcomes_blocked`.

Proof:
- `python -m py_compile scripts\wf74_model_quality_collection_cron_runner.py scripts\model_run_ledger.py scripts\finance_recommendation_correctness_ledger.py scripts\model_quality_scorecard.py scripts\cron_freshness_spine.py scripts\artifact_index.py`
- `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness` -> `status=ok validation=ok steps_ok=11 steps_blocked=0 model_attr=0.75 finance_rows=7`
- `python scripts\model_run_ledger.py --write --write-md --validate` -> `status=ok validation=ok rows=17 model_attr=0.7647 session_attr=0.6471`
- `python scripts\finance_recommendation_correctness_ledger.py --write --write-md --validate` -> `status=ok validation=ok rows=7 ok=7 warning=0 blocked=0`
- `python scripts\model_quality_scorecard.py --write --write-md --validate` -> `validation=ok active_tracks=implementation_quality,performance,decision_quality critical=0 warnings=0`
- `openclaw cron run b911d479-13aa-48fe-b662-937e08450363 --wait --wait-timeout 5m --timeout 300000` -> completed ok
- `python scripts\cron_control_packet.py --write --validate` -> status ok, escalation 0
- `python scripts\veritas_harness_scorecard.py --fast --write --validate` -> status ok, 75/75
- `python scripts\wf74_rsi.py --validate-only` -> `status=ok checks=29 failed=0`
- `python scripts\artifact_index.py incremental` -> source_files=136; `python scripts\artifact_index.py validate` -> validate ok, 28 checks, 0 failed
- `openclaw skills check` -> 92 total, 50 visible, 0 missing requirements

Skill updates:
- Skill Workshop pending proposal `veritas-self-improvement-20260608-8c534ddc23` captures the WF74 collection route.
- Skill Workshop pending proposal `cron-automation-manager-20260608-6b694a9e48` captures the scheduled WF74 collection cron pattern.

Remaining gaps:
- Session attribution is partially available through cron run history, but not yet stamped at every producer/helper/PM layer.
- Tokens are partially available through cron run history, but cost remains absent from local OTEL/debug surfaces.
- WF55 later-outcome grading remains blocked: 0 graded rows and durable append is still false.
- No model-ranking claim is allowed until repeated samples, model attribution, session attribution, and outcome-grade history exist.

Boundary unchanged:
- Review-only measurement. No base-model self-modification, autonomous authority expansion, OTEL content capture, config/runtime mutation, finance authority expansion, model-ranking claim, investment-correctness claim from telemetry, WF55 outcome grade assignment, portfolio/canon mutation, capital deployment approval, owner-approval inference, or paper/live/account action.

## 2026-06-08 WF74 cron duplication audit and RSI observation hooks

Randall asked to review the recent WF74 cron changes for duplicate data collection and continue the low-overhead RSI integration recommendations.

Implemented:
- Added `scripts\wf74_cron_duplication_audit.py` -> `tmp\wf74-cron-duplication-audit.json`.
- Wired the audit into `scripts\wf74_model_quality_collection_cron_runner.py`; the runner now performs 12 steps and fails closed on recurring duplicate WF74 component collectors.
- Added `rsi_observation` blocks to `wf74_model_quality_collection_cron_runner.py` and `future_session_enhancement_packet.py` so future sessions get small structured lessons without adding a second memory tree.
- Updated `scripts\cron_freshness_spine.py`, `scripts\changed_file_validator_router.py`, `TOOLS.md`, Startup Truth Index, and `scripts\README.md` with the audit route.
- Edited one-shot cron `Cron Spark Canary Review Reminder` so it is inspect-only and no longer instructs a direct `cron_spark_canary_monitor.py` execution outside the owner WF74 collector.

Cron duplication state:
- Live enabled WF74 collection owner: exactly one, `Ops - OTEL Local Digest`.
- Recurring WF74 component collectors outside owner: 0.
- One-shot component collectors outside owner: 0 after reminder edit.
- Delivery remains none/no direct Randall message from the owner collection job.

Proof:
- `python -m py_compile scripts\wf74_cron_duplication_audit.py scripts\wf74_model_quality_collection_cron_runner.py scripts\future_session_enhancement_packet.py scripts\cron_freshness_spine.py scripts\changed_file_validator_router.py` -> ok.
- `python scripts\wf74_cron_duplication_audit.py --write --validate` -> `status=ok validation=ok owner_jobs=1 owner_runners=1 recurring_outside_components=0 one_shot_outside_components=0`.
- `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness` -> `status=ok validation=ok steps_ok=12 steps_blocked=0 model_attr=0.7647 finance_rows=7`.
- `python scripts\future_session_enhancement_packet.py --write --write-md --validate` -> `status=ok validation=ok wf74=ok pm=ok cron=ok`.
- `python scripts\cron_control_packet.py --write --validate` -> status ok, escalation 0.
- `python scripts\wf74_rsi.py --validate-only` -> `status=ok checks=29 failed=0`.
- `python scripts\changed_file_validator_router.py ... --write --validate` -> status ok, shared budget.

Boundary unchanged:
- Review-only scheduler/proof/RSI metadata. No cron schedule expansion beyond the inspect-only correction, no model ranking, no WF55 outcome grading, no portfolio/canon mutation, no capital approval, no paper/live/account action, no config/auth/runtime expansion, and no owner approval inference.
