# Workflow Routing Index Expansion

## Objective
- Build a validated workflow routing index that mirrors `06. Playbooks/Active Workflows.md`.
- Make every P0/P1/P2 workflow easier to resume, delegate, validate, and status-check without broad workspace search.

## Current State
- Active Workflows is the live workflow state authority.
- Phases 1-5 are DONE (Phase 1-2 2026-06-05; Phase 3-5 2026-06-05/06). `scripts/workflow_routing_index.py` builds `tmp/workflow-routing-index.json` (31 routes: 2 P0, 18 P1, 11 P2 monitors) and the integrated `--validate` emits `tmp/workflow-routing-index-validation.json`. Live proof: status `ok`, **0 critical, 0 warning**. Each route carries the 16 required fields plus a `primary_pending` flag and a derived `freshness` block; the validator resolves continuity-note and proof-artifact existence on disk.
- Concurrent lane MVP is DONE (2026-06-05/06). `scripts/concurrent_lane_manager.py` builds `tmp/concurrent-lane-register.json`, derives lane templates from `tmp/workflow-routing-index.json`, and validates active write leases before intentional multi-helper work. This is coordination-only: no spawning, no scheduler, no merge authority, no canon/portfolio/config/destructive/capital/trade/account authority.
- Parallel lane recommender is DONE (2026-06-05/06). `scripts/parallel_lane_recommender.py` writes `tmp/parallel-lane-recommendation.json`, ranks narrow one-output helper lanes from workflow/PM/WF78/hardening proof, rejects active write collisions and forbidden writes, and emits the exact lease command plus OpenClaw `sessions_spawn` args. It does not spawn helpers itself.
- Product-scale expansion on 2026-06-05 added WF80-WF83 to the route map: multi-product control plane, AI/opportunity product line, learning/teaching product line, and product packaging/readiness factory.
- Route capabilities: `--route WORKFLOW` (one route JSON), `--list` (compact id/tier/next), `--freshness` (per-route + summary freshness), `--handoff WORKFLOW [--write]` (bounded helper packet shaped to the Subagent Spawn Handoff Template; owner-gated lanes return mode `Main-session only` with a helper-lane warning).
- SQL route-control continuation Phase 6-7 is DONE (2026-06-05/06). `scripts/workflow_routing_index.py --write --write-db --validate` rebuilds `tmp/workflow-routing-index.sqlite` from the JSON route map, validates route-count/tier-count/freshness/authority parity, and exposes canned read-only SQL queries: `--sql-route WF##`, `--sql-list`, `--sql-freshness`, `--sql-next-actions`, `--sql-helper-safe`, and `--sql-owner-gated`. SQL is derived/rebuildable lookup only; it is not workflow authority, canon, approval, or execution state.
- Phase 8/9 SQL consumption and existing-cron refresh are DONE (2026-06-05/06). PM cockpit now exposes workflow route SQL status through `/api/workflows/routes` and the Workflows tab; SQL Coverage guard refreshes route JSON/validation/SQLite through the existing review-only guard chain. JSON proof and SQL parity fallback discipline remain required.
- Parallel efficiency sprint continuation is DONE (2026-06-06). Added `truth_surface_inventory.py`, `fast_path_qa.py`, and WF78 evidence-drag proof. `tmp/truth-surface-inventory.json` classifies 15 major surfaces into authority/router/proof/dashboard/legacy with a first-open route; `tmp/route-efficiency-scorecard.json` validates fast route reads and PM cockpit route endpoints; `tmp/fast-path-qa.json` validates route/PM/artifact/cron fast-path and encodes the closeout ordering chain.
- PM cockpit latency fix is DONE (2026-06-06). `/health` now uses lightweight registry metadata instead of full state build, and `/api/workflows/routes` reads route JSON plus validation proof instead of building the full PM/SMB/academy state or spawning repeated sqlite queries. Live scorecard after restart: `/health` about 0.024s and `/api/workflows/routes` about 0.017s, with route SQL probes below 1s.
- Repeatable orchestration continuation is DONE (2026-06-06). `scripts/parallel_repeatable_work_orchestrator.py --write --validate` runs the approved macro guard plus WF78 evidence/card-prep lanes in parallel and writes `tmp/parallel-repeatable-work-orchestration.json` plus lane artifacts. `scripts/repeatable_work_closeout.py --write --validate` wraps route rebuild, artifact scoring, event rerouting, truth inventory, fast-path QA, artifact index validation, and PM state refresh in one ordered chain. Latest closeout proof is `status=ok`, 9 steps run, 0 failed steps.
- `tmp/workflow-alias-index.json` exists, but it is stale and narrow: generated 2026-05-29 and covers only a small set of main WF aliases. The routing index supersedes it as the richer route map.
- Artifact indexing is healthy: routing index + validation are tracked in `scripts/artifact_index.py` truth-spine; `incremental` + `validate` pass with 28 checks, 0 failures, `not_indexed=0`, no stale content. PM status registers both `workflow_routing_index` and `workflow_routing_index_validation` source probes (`pm_program_state.py` validates `ok`; both probes exist + parseable, validation probe status `ok`).
- Presentation retrieval routing has a validated route-map pattern that was copied for workflows:
  - `tmp/presentation-retrieval-route-map.json`
  - `tmp/presentation-retrieval-enforcement.json`

## Phase 4 Repair (2026-06-06, all 8 Phase 2 warnings closed)
- Encoded confirmed (rc=0) validator commands into the 7 P1 lanes:
  - WF68 -> `wf68_runtime_wiring_plan_validator.py --write`
  - WF70/WF66 -> `wf70_wf66_official_evidence_spine.py --validate-only`
  - WF67 -> `chief_intelligence_promotion_gate.py --write --validate`
  - WF64/WF56 -> `test_portfolio_mutation_validators.py`
  - WF71 -> `openclaw skills check`
  - WF74 -> `wf74_rsi.py --validate-only`
  - WF69 -> `wf_v2_intelligence_stack_validator.py --write`
- Repointed WF-FINANCE-CHAINS `primary_route_artifact` from absent `tmp/current-window-artifacts.md` to present `tmp/current-window-artifacts.json`.
- Each validator command was run and confirmed rc=0 before encoding (the routing validator only checks the field is non-empty; it does not execute commands).
- Severity model: missing required field / empty stop_lines / authority widening / duplicate id = critical (blocks); declared-but-absent continuity note or proof artifact, and active-lane missing validator = warning (surfaces gap, stays `ok`).

## Phase 5 Freshness + Handoff (2026-06-06)
- Route freshness scoring: each route gets `freshness {score, continuity_note_age_hours, primary_artifact_age_hours, validator_count, has_next_action}`; thresholds fresh <72h, aging <336h, else stale; `missing` when a declared path is absent, `n/a` when no proof path is declared. Summary carries `freshness_counts`. Current spread after WF80-WF83: 17 fresh, 11 aging, 1 stale (WF62 canon-consolidation), 2 n/a.
- Helper handoff packet: `--handoff WORKFLOW` derives scope (next_action), current truth, read-first files, do-not-touch surfaces, validators, stop lines, acceptance proof (validators + routing `--validate`), freshness, and the review-only authority clamp. `safe_for_helper_lane=false` lanes return `Main-session only` + `helper_lane_warning`. On-demand output is rebuildable and intentionally outside the tracked truth spine.

## Concurrent Lane MVP (2026-06-05/06)
- Phased approach used:
  - Phase 1 register/schema: `tmp/concurrent-lane-register.json` with authority clamp, lane rows, summary, validation, and stop lines.
  - Phase 2 plan from route index: `--plan WF## --workstream ...` creates a planned lane from `tmp/workflow-routing-index.json` read-first files, validators, and stop lines.
  - Phase 3 lease/collision gate: `--lease WF## --workstream ... --allowed-write ...` records exact writable surfaces and fails validation on active write collisions, forbidden write paths, missing owners, stale leases, or leased/running lanes with no write surface.
  - Phase 4 complete/proof gate: `--complete WF## --workstream ... --proof ...` records completion and validates proof artifact existence.
  - Phase 5 discoverability: registered in artifact index, PM source probes, Startup Truth Index, Active Workflows, this continuity note, and `scripts/README.md`.
- Acceptance proof:
  - `python -m py_compile scripts\concurrent_lane_manager.py`
  - clean empty/default status: `python scripts\concurrent_lane_manager.py --status --write --validate`
  - positive plan/lease path on a WF78 smoke register passed.
  - duplicate active write-path smoke failed closed with validation error.
  - forbidden portfolio write-path smoke failed closed with validation error.
  - complete-with-proof smoke passed using existing WF78 proof artifact.
- Usage rule: use this before intentional multi-helper work or cross-workflow parallel work. It does not replace main-session merge/QC, workflow routing, PM queue, or helper handoff packets.

## Parallel Lane Recommender (2026-06-05/06)
- Purpose: answer quickly which different-session helper lane can run in parallel without colliding with current WF78/WF72 work.
- Script: `python scripts\parallel_lane_recommender.py --write --validate`
- Workflow-specific forms:
  - `python scripts\parallel_lane_recommender.py --workflow WF78 --out tmp\parallel-lane-recommendation-wf78.json --write --validate`
  - `python scripts\parallel_lane_recommender.py --workflow WF72 --out tmp\parallel-lane-recommendation-wf72.json --write --validate`
- Current default recommendation after validation: WF72 A2 support-readiness QA lane, writing only `tmp/parallel-lanes/wf72-a2-readonly-qa.json`.
- WF78-specific recommendation after validation: WF78 event-rerouting QA lane, writing only `tmp/parallel-lanes/wf78-event-rerouting-qa.json`.
- Operating sequence:
  1. run recommender
  2. run emitted `lease_command`
  3. call OpenClaw `sessions_spawn` with emitted `spawn_args`
  4. inspect returned proof artifact
  5. run emitted complete command
- Stop line: recommender is coordination/proposal only; no autonomous spawning, scheduling, merge authority, canon/portfolio/config/destructive/capital/trade/account/customer authority, or owner approval inference.

## Hardening Pass (2026-06-05/06)
- Hardened `workflow_routing_index.py --validate` beyond presence checks. It now blocks on schema-version drift, route-count drift, P0/P1/P2 tier-count drift, invalid route field types, empty required strings, freshness-shape drift, helper handoff mode drift, and handoff authority-clamp drift.
- `tmp/workflow-routing-index-validation.json` now carries the full route-index authority clamp instead of a narrower validation-only subset, so artifact-index authority rows prove the same boundary across both routing artifacts.
- Validation proof after hardening:
  - `python -m py_compile scripts\workflow_routing_index.py`
  - `python scripts\workflow_routing_index.py --write --validate` -> `ok`, 31 routes, 0 critical, 0 warning.
  - `python scripts\workflow_routing_index.py --freshness` -> 13 fresh, 11 aging, 1 stale, 2 n/a.
  - `python scripts\workflow_routing_index.py --handoff WF67` -> `Main-session only` + owner-gated helper warning.
  - `python scripts\workflow_routing_index.py --handoff WF73 --write` -> wrote `tmp/workflow-routing-handoff-wf73.json`.
  - `python scripts\artifact_index.py incremental`; then sequential `python scripts\artifact_index.py validate` -> 28 checks, 0 failed, `not_indexed=0`, no stale/orphaned rows.
  - `python scripts\pm_program_state.py --write --write-db --validate` -> `ok`.
- Operational note: do not run `artifact_index incremental` and `artifact_index validate` in parallel against the same SQLite file. A parallel test created a transient drift-fingerprint failure on `authority_flags`; rerunning sequentially validated clean. SQLite-dependent index writes/validations are sequential steps.

## Why This Matters
- New-session pickup still requires too much manual reading across Active Workflows, continuity notes, proof artifacts, and validators.
- Helper handoffs still need manual route reconstruction.
- Status answers are better when they come from a validated route object instead of reconstructed context.
- A workflow routing index should reduce pickup/search/handoff overhead by an estimated 20-40%, with 40-60% possible on coordination-heavy work once helper handoff and freshness scoring are wired in.
- The current fast path is now measured and green: source-open drilldown should happen only after the route/proof surfaces identify a material claim that needs owner-source confirmation.

## Target Scope
- Include all P0/P1/P2 workflow and monitor rows from Active Workflows.
- Each route row should include:
  - `workflow_id`
  - `display_name`
  - `tier`
  - `current_state`
  - `next_action`
  - `continuity_note`
  - `primary_route_artifact`
  - `secondary_artifacts`
  - `validator_commands`
  - `last_validated_at`
  - `blockers`
  - `stop_lines`
  - `authority_boundary`
  - `owner_action_required`
  - `safe_for_helper_lane`
  - `default_resume_command`

## Estimated Effort
- MVP route index: 3-5 focused hours.
- Full validated implementation across P0/P1/P2: 1-2 workdays.
- Max-capacity version with helper handoff generation, route freshness, and cockpit/status integration: 2-3 workdays.
- SQLite + PM/cockpit + existing-cron auto-refresh continuation: MVP DB 1-2 hours; query layer + validation 1-2 hours; PM/cockpit integration 2-4 hours; cron auto-refresh wiring 1-2 hours if reusing an existing review-only cron chain; full polished route 0.5-1 workday.

## Phased Plan

### Phase 1 - Route Object Builder [DONE 2026-06-05]
- Added `scripts/workflow_routing_index.py`.
- Encoded the P0/P1/P2 Active Workflows rows into `tmp/workflow-routing-index.json` (27 routes originally; 31 after WF80-WF83 product-scale expansion; 32 after WF84 internal canonical finance data-plane registration).
- Active Workflows stays authority; the JSON is a derived route map only (explicit `authority` clamp + `note`).
- Acceptance MET:
  - all P0/P1/P2 register + monitor rows represented.
  - workflow IDs and display names present.
  - no authority widening (validator enforces the clamp).

### Phase 2 - Route Validator [DONE 2026-06-05]
- Validation rules implemented (integrated `--validate`):
  - continuity note exists OR route explicitly null ("no dedicated note") -> declared-but-absent = warning.
  - primary proof artifact exists OR `primary_pending` true OR null -> declared-but-absent = warning.
  - validator command present for active build lanes (P0/P1) -> missing = warning.
  - stop lines present -> empty = critical.
  - authority flags stay review-only / no approval inference -> widening = critical.
  - also: required-field presence (critical), unique workflow_id (critical), authority_boundary string (critical), secondary-artifact existence (warning).
- Acceptance MET:
  - `tmp/workflow-routing-index-validation.json` is `ok` (0 critical).
  - missing/stale route fields produce warnings (8 surfaced); structural/authority problems would produce criticals.

### Phase 3 - Artifact Index / PM Wiring [DONE 2026-06-05]
- Added `workflow-routing-index.json` + `workflow-routing-index-validation.json` to `scripts/artifact_index.py` `TRUTH_SPINE_FILES` (tracked as file-state `unknown` type, same pattern as the presentation-retrieval route map).
- Added `workflow_routing_index` + `workflow_routing_index_validation` source probes to `pm_program_state.py` `source_artifacts()`; added `--route`/`--list` route lookup to the builder.
- Acceptance MET:
  - artifact index incremental + validate green (28 checks, 0 failed, `not_indexed=0`).
  - PM status identifies the route object (both probes exist + parseable; validation probe `ok`).

### Phase 4 - Repair And Coverage Pass [DONE 2026-06-06]
- Encoded confirmed-rc=0 validator commands for the 7 P1 lanes; repointed finance-chains primary artifact to the present `.json` (see "Phase 4 Repair" above).
- Acceptance MET:
  - no missing required route fields; status `ok`, 0 critical, **0 warning**.
  - stale or missing proof is explicit (Phase 5 freshness block).

### Phase 5 - Helper Handoff And Freshness Scoring [DONE 2026-06-06]
- Added `score_route_freshness` (continuity/artifact/validator/next-action signals) + `--freshness`; added `build_handoff` + `--handoff WORKFLOW [--write]` (see "Phase 5 Freshness + Handoff" above).
- Acceptance MET:
  - helper packet includes scope, files, artifacts, validators, stop lines, and acceptance proof (verified on WF73 write + WF67 owner-gated warning).
  - route freshness is visible via `--freshness` and the per-route `freshness` block without broad search.

## SQLite + Cron/PM Auto-refresh Continuation Plan

### Phase 6 - Derived SQLite Route Index [DONE 2026-06-05/06]
- Added `--write-db` and `--db tmp/workflow-routing-index.sqlite` to `scripts/workflow_routing_index.py`.
- Rebuilds the DB from the JSON route objects only; no hand editing, no SQL-first source of truth.
- Tables:
  - `workflow_routes`
  - `workflow_artifacts`
  - `workflow_validators`
  - `workflow_blockers`
  - `workflow_stop_lines`
  - `workflow_freshness`
  - `workflow_authority`
  - `workflow_runs`
- Acceptance MET:
  - JSON route count equals SQL route count.
  - P0/P1/P2 tier counts match.
  - Every route has authority rows proving review-only / no approval / no execution.
  - `PRAGMA integrity_check` and `PRAGMA foreign_key_check` pass.
  - `--validate` fails if DB was requested but count/authority/freshness parity fails.
- Boundary:
  - DB is derived/rebuildable lookup only. No canon/portfolio/SQL-canon mutation, no owner approval, no paper/live/account action, no customer/public output.

### Phase 7 - SQL Query Helpers + Fast Route Packets [DONE 2026-06-05/06]
- Added canned read-only query modes over the SQLite DB, not arbitrary SQL:
  - `--sql-route WF78`
  - `--sql-list`
  - `--sql-freshness`
  - `--sql-next-actions`
  - `--sql-helper-safe`
  - `--sql-owner-gated`
- Kept the JSON commands (`--route`, `--list`, `--freshness`, `--handoff`) as compatibility paths.
- Acceptance MET:
  - SQL route output matches JSON route output for sampled P0/P1/P2 routes.
  - SQL freshness summary matches JSON freshness summary.
  - canned query outputs are read-only and carry the same authority clamp.

### Phase 8 - PM/Cockpit Consumption [DONE 2026-06-05/06]
- `tmp/workflow-routing-index.sqlite` is registered in PM state and `state/pm-cockpit-source-registry.json` as a derived source artifact beside the JSON index and validation artifacts.
- PM cockpit now consumes workflow route SQL views in `apps/pm-control-cockpit/src/server.ts` and exposes:
  - `/api/workflows/routes`
  - `/workflows` / `/workflows/routes`
  - Workflows tab with route count, freshness counts, stale/aging routes, helper-safe lanes, owner-gated lanes, next actions by tier, authority flags, and source health.
- Acceptance MET:
  - endpoint smoke on patched server: 31 routes, 12 stale/aging, 18 owner-gated, validation `ok`, SQL workflow error `null`.
  - `npm run validate` passes for local cockpit; remaining cockpit warnings are existing stale WF78 source packets, not workflow-route blockers.
  - `pm_program_state.py --write --write-db --validate` passes.
  - UI/API labels route SQLite as derived/rebuildable status support, not authority.

### Phase 9 - Existing-Cron Auto-refresh [DONE 2026-06-05/06]
- Wired routing-index refresh into the existing review-only `sql_coverage_guard.py` chain; no new cron job was added.
- Refresh sequence now includes:
  - `python scripts\workflow_routing_index.py --write --write-db --validate`
  - artifact index incremental/validate
  - `python scripts\pm_program_state.py --write --write-db --validate`
  - optional `/api/workflows/routes` probe when the local cockpit is running.
- `cron_freshness_spine.py` now expects `tmp/sql-coverage-guard.json`, `tmp/workflow-routing-index.json`, `tmp/workflow-routing-index-validation.json`, and `tmp/workflow-routing-index.sqlite` for the existing SQL Coverage job.
- Acceptance MET:
  - `python scripts\sql_coverage_guard.py --write --validate` -> `ok`, 0 critical, 0 warnings.
  - `python scripts\cron_freshness_spine.py --write --validate` -> validation `ok`; SQL Coverage job is `fresh` / `NO_REPLY`.
  - `python scripts\cron_signal_scorecard.py --write --validate` -> `ok`.
  - `python scripts\escalation_trigger.py --write --validate` -> `ok`, no escalation.
  - no schedule/config/channel/runtime mutation and no concurrent SQLite writes.

### Phase 10 - Efficiency Scorecard + Rollback
- Add workflow-routing SQL posture to the runtime/operating leverage scorecard:
  - DB exists
  - DB route count
  - DB parity status
  - query latency for route/list/freshness
  - stale route count
- Rollback path:
  - delete/ignore the derived SQLite DB and continue using JSON route artifacts.
  - keep `Active Workflows.md` and exact continuity notes as authority.
- Acceptance:
  - status answers can use SQLite by default after DB parity is green.
  - if DB parity fails, answers fall back to JSON route index and report the SQL route as stale/unsafe.

## Next Action
- Use the Workflows cockpit tab and `/api/workflows/routes` for route status panes after the local cockpit process is restarted.
- Use the existing SQL Coverage guard as the route-refresh chain; do not add a new cron.
- Implement Phase 10 rollback/efficiency scorecard.

## Validation Ladder
- `python scripts\workflow_routing_index.py --write --write-db --validate`
- `python scripts\workflow_routing_index.py --sql-route WF80`
- `python scripts\workflow_routing_index.py --sql-freshness`
- `python scripts\sql_coverage_guard.py --write --validate`
- `python scripts\cron_freshness_spine.py --write --validate`
- `python scripts\cron_signal_scorecard.py --write --validate`
- `python scripts\escalation_trigger.py --write --validate`
- `python scripts\artifact_index.py incremental`
- `python scripts\artifact_index.py validate`
- PM/cockpit validation if PM wiring is touched.

## Stop Lines
- Do not let the workflow routing index outrank Active Workflows or exact continuity notes.
- Do not treat SQL/index/dashboard rows as canon, approval, apply authority, trade/account authority, or paper/live execution authority.
- Do not mutate canon/portfolio/ticker-card/SQL-canon surfaces from this index.
- Do not add or alter cron/config/auth/channel/service/runtime behavior in this lane.
- Do not infer owner approval from any route row.
