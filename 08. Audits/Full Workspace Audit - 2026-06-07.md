# Full Workspace Audit - 2026-06-07

## Retrieval Notes

- Status: current audit, completed 2026-06-07 MST
- Owner: Veritas main session
- Scope: workspace structure, truth-routing surfaces, PM/control plane, cron/heartbeat signals, SQL/database lifecycle, skill health, harness/QA, finance automation boundaries
- Archive posture: keep in `08. Audits/`; do not archive until superseded by a newer full workspace audit
- Key artifacts: `tmp/cron-freshness-spine.json`, `tmp/escalation-trigger.json`, `tmp/db-lifecycle-manifest.json`, `tmp/sql-coverage-guard.json`, `tmp/control-closeout-bundle.json`, `tmp/pm-program-state.json`, `tmp/automation-stack-hardening-pass.json`

## Executive Conclusion

The workspace is operational but not clean. Core routing, skills, harness, dashboard truth boundaries, workflow routing, PM job queue, and artifact indexing are usable. The main live weakness is a control-plane failure chain rooted in one unclassified backup SQLite database under `tmp/backups/20260606-otel-warning-fix/state/openclaw.sqlite`. That single classification gap is now cascading into DB lifecycle validation failure, WF75 closeout failure, SQL coverage critical status, morning/security cron blocks, fast-path QA block, repeatable closeout block, and control-closeout block.

No audit evidence showed capital deployment approval, trade/order authority, paper/live execution authority, customer/public output authority, or portfolio/canon mutation authority. Those boundaries held.

## Scope Audited

- Root workspace structure and allowed top-level surfaces
- Numbered knowledge domains and audit folder freshness
- `memory/`, `scripts/`, `skills/`, `tmp/`, `data/`, `state/`, `apps/`, `training/`, and backup surfaces at a high level
- Startup/control truth surfaces: `SOUL.md`, `USER.md`, `TOOLS.md`, `Startup Truth Index`, `Active Workflows`, `MEMORY.md`, current and prior daily memory
- PM/control-plane proof, workflow routing, artifact index, cron freshness, cron signal scoring, escalation trigger
- SQL/DB lifecycle and SQL coverage guard
- Security proof, dashboard truth lint, workspace boundary lint, fast-path QA, harness scorecard, skills check

## Commands And Proof

| Surface | Command | Result |
|---|---|---|
| Workspace boundary | `python scripts\workspace_boundary_check.py` | warning: 2 `tmp/*.py` helpers |
| Dashboard truth | `python scripts\dashboard_truth_lint.py` | ok |
| Truth inventory | `python scripts\truth_surface_inventory.py --write --validate` | ok; route scorecard warning |
| Fast-path QA | `python scripts\fast_path_qa.py --write --validate` | blocked after cron block |
| Workflow routes | `python scripts\workflow_routing_index.py --write --write-db --validate` | ok, 31 routes |
| PM state | `python scripts\pm_program_state.py --write --write-db --validate` | ok/yellow |
| PM job queue | `python scripts\pm_implementation_job_queue.py --write --write-db --validate` | ok, 10 ready jobs |
| DB lifecycle | `python scripts\db_lifecycle_manifest.py --write --validate` | validation_error |
| Cron freshness | `python scripts\cron_freshness_spine.py --write --validate` | blocked, 3 blocked jobs |
| Cron signal scorecard | `python scripts\cron_signal_scorecard.py --write --validate` | ok with blocked signals |
| Escalation trigger | `python scripts\escalation_trigger.py --write --validate` | ok; `should_wake_main_session=true` |
| Automation hardening | `python scripts\automation_stack_hardening_pass.py --write --validate` | blocked; 1 critical |
| Artifact index | `python scripts\artifact_index.py incremental` | rebuilt; 129 source files |
| Harness fast lane | `python scripts\veritas_harness_scorecard.py --fast --write --validate` | ok, 75/75 |
| SQL coverage | `python scripts\sql_coverage_guard.py --write --write-md --validate` | critical |
| Control closeout | `python scripts\control_closeout_bundle.py --write --validate` | blocked |
| Skills | `openclaw skills check` | healthy: 92 total, 50 visible, 0 missing requirements |

## Findings

### F1 - Critical - Control Plane Is Blocked By A DB Lifecycle Classification Gap

Evidence:
- `tmp/db-lifecycle-manifest.json` status is `validation_error`.
- Validation error: `tmp/backups/20260606-otel-warning-fix/state/openclaw.sqlite is unclassified`.
- Manifest summary: 31 databases, 1 unknown, 0 integrity errors, 1 archive-ready candidate, 0 delete-ready.
- The unclassified DB has SQLite integrity `ok`, 64 tables, 8 total references, and 1 active reference from `memory/2026-06-07.md`.

Why it matters:
- This is not just cleanup noise. It blocks `wf75-closeout-refresh`, which blocks `sql-coverage-guard`, which then blocks cron/security/fast-path closeout surfaces.
- Because it is an OpenClaw state backup, it may contain runtime/control-plane history. It should be classified, not deleted casually.

Recommended fix:
- Add an explicit lifecycle classification for this rollback/provenance backup path, or move it into a documented backup class only after reference review.
- Do not archive/delete it without explicit owner approval, hash/provenance confirmation, and rollback understanding.

Acceptance proof:
- `python scripts\db_lifecycle_manifest.py --write --validate` returns ok.
- `python scripts\wf75_closeout_refresh.py` or the owning WF75 closeout route no longer fails on DB lifecycle.
- `python scripts\sql_coverage_guard.py --write --write-md --validate` returns non-critical.

### F2 - Critical - Cron Freshness Has 3 Blocked Enabled Jobs

Evidence:
- `tmp/cron-freshness-spine.json`: 43 jobs, 25 enabled, 18 disabled, 0 stale, 7 attention, 3 blocked.
- Blocked enabled jobs:
  - `Finance - Morning Control Digest Proof Refresh`
  - `Security Audit - Daily Bounded Hardening`
  - `SQL Coverage - Daily Control Plane Guard`
- `tmp/escalation-trigger.json`: `should_wake_main_session=true`, 3 escalation signals.
- `tmp/automation-stack-hardening-pass.json`: status `blocked`, 159 checks, 1 critical, error `cron_freshness_spine_no_blocked_jobs`.

Why it matters:
- Heartbeat/cron are doing the right thing by escalating, but the workspace should not be treated as clean while those enabled jobs are blocked.
- SQL coverage and security audit blocks reduce trust in automated closeout and morning handoff.

Recommended fix:
- Fix F1 first, then rerun the dependent chain in order: DB lifecycle -> WF75 closeout refresh -> SQL coverage guard -> cyber security audit -> cron freshness spine -> cron signal scorecard -> escalation trigger -> fast-path QA -> control closeout bundle.

Acceptance proof:
- `cron_freshness_spine` reports blocked_count 0.
- `escalation_trigger` reports `should_wake_main_session=false` unless there is a fresh independent issue.
- `automation_stack_hardening_pass` is not blocked.

### F3 - High - Repeatable Closeout And Control Closeout Are Currently Blocked

Evidence:
- `tmp/control-closeout-bundle.json`: status `blocked`, failed step `repeatable_work_closeout`.
- `tmp/repeatable-work-closeout.json`: status `blocked`, failed step `fast_path_qa`.
- `tmp/fast-path-qa.json`: status `blocked`, error `cron_freshness_not_blocked`.

Why it matters:
- Closeout is the mechanism that tells Veritas the operating loop is safe to hand off. It is correctly failing closed because cron freshness is blocked.

Recommended fix:
- Do not treat PM/cron closeout as green until F1/F2 are repaired.
- After cron block clears, rerun `python scripts\control_closeout_bundle.py --write --validate`.

Acceptance proof:
- Control closeout bundle status `ok`.
- Repeatable closeout status `ok`.
- Fast-path QA status `ok`.

### F4 - Medium - PM State Is Yellow With Two Blocked Lanes

Evidence:
- `tmp/pm-program-state.json`: readiness band `yellow`, average score 70.0, 14 lanes, 8 ready/complete, 2 blocked, 1 stale, 3 needs validation.
- PM blockers show:
  - `retail_truth_routing` blocked by `tmp/automation-stack-hardening-pass.json`.
  - `wf78_scaleout` blocked by `tmp/repeatable-work-closeout.json`.
- PM implementation job queue itself is ok: 10 ready jobs, 0 blocked jobs, top job `pm-01-retail-truth-routing-refresh-artifact`.

Why it matters:
- PM is functioning as a queue, but the top two active lanes are blocked by control-plane proof, not by missing business logic.

Recommended fix:
- Treat PM as usable for routing, not green for completion.
- Clear the control-plane chain before advancing new PM work.

Acceptance proof:
- PM state returns green or at least yellow without blocked lanes.
- Retail truth routing and WF78 scaleout blockers disappear from `tmp/pm-blocker-register.json`.

### F5 - Medium - Workspace Structure Policy Does Not Fully Match Live Root

Evidence:
- Live root includes `apps/`, `training/`, `state/`, and `GEMINI.md`.
- `TOOLS.md` references `apps\pm-control-cockpit`, `state\pm-cockpit-source-registry.json`, `state\finance\finance-canon.sqlite`, and WF75 training assets.
- `skills/workspace-governor/references/workspace-standards.md` does not list `apps/`, `training/`, `state/`, or `GEMINI.md` as allowed root surfaces.
- `workspace_boundary_check.py` did not flag those policy mismatches, so the validator is less strict than the written standard.

Why it matters:
- This is not an immediate runtime failure, but it weakens the structure audit. Either those root surfaces are legitimate and should be documented, or the validator should flag them.

Recommended fix:
- Update workspace standards to document `apps/`, `state/`, and `training/` with authority boundaries, if they are approved active roots.
- Decide whether `GEMINI.md` is compatibility-retained like `CLAUDE.md`; document it or archive it after explicit approval.
- Strengthen `workspace_boundary_check.py` to detect undocumented root exceptions.

Acceptance proof:
- Workspace standards and boundary check agree on all root surfaces.
- Boundary check flags no undocumented active roots.

### F6 - Medium - Route Efficiency Scorecard Cannot Reach PM Cockpit Probes

Evidence:
- `tmp/route-efficiency-scorecard.json`: status `warning`, 5 probes, 2 failed/unavailable.
- Failed/unavailable probes:
  - `pm_cockpit_health`
  - `pm_cockpit_workflow_routes`

Why it matters:
- The cockpit is not part of canonical truth, but it is the local review UI. If it is down or unavailable, dashboard-dependent review work is degraded.

Recommended fix:
- If cockpit is expected to be running, start/validate it and rerun truth inventory.
- If cockpit is intentionally stopped, keep this as warning-only and do not claim cockpit readiness.

Acceptance proof:
- `truth_surface_inventory.py --write --validate` still ok.
- `tmp/route-efficiency-scorecard.json` has 0 failed/unavailable probes when cockpit readiness is claimed.

### F7 - Medium - Ticker Card Freshness Debt Remains Broad

Evidence:
- `tmp/automation-stack-hardening-pass.json` reports ticker card refresh gate `ok_with_stale_cards`.
- Card count 200, stale_count 200, decision_ready_card_count 0.
- WF78 routing remains review-only; automation hardening confirms no execution/approval authority.

Why it matters:
- This is expected in the WF78 repair model, but it means ticker cards should not be treated as decision-ready without source-open or freshness repair.

Recommended fix:
- Continue the WF78 repair queue; do not shortcut stale-card debt into Tier A/B readiness.
- Use answer packets and exact source-open artifacts for material finance claims.

Acceptance proof:
- Stale-card count declines through repair loops, or tier-weighted freshness explicitly resolves rows at the proper depth.

### F8 - Low/Medium - Two Executable Helpers Still Live In `tmp/`

Evidence:
- `workspace_boundary_check.py` warning:
  - `tmp/health_detail.py`
  - `tmp/parity_diag.py`

Why it matters:
- `tmp/` can hold throwaway proof scripts, but recurring executable helpers belong in `scripts/` or should be deleted/archived after approval if no longer needed.

Recommended fix:
- Classify each as throwaway, durable, or expired.
- Promote to `scripts/` only if recurring; otherwise include in a cleanup approval packet.

Acceptance proof:
- Workspace boundary check has no warning for durable executable helpers in `tmp/`.

### F9 - Low - Spark Cron Canary Is Configured But Not Proven

Evidence:
- `tmp/cron-spark-canary-monitor.json`: status `warning`, configured 2/2, pending first canary run 2, errors 0.

Why it matters:
- This is a planned waiting state, not a breakage. Do not expand Spark cron usage until first natural run proof is reviewed.

Recommended fix:
- Review after the 2026-06-08 scheduled canary windows.

Acceptance proof:
- Canary monitor reports ok runs and no duration/error regression.

### F10 - Low - Security Audit Warnings Are Mostly Posture Warnings, Not New Breaches

Evidence:
- `tmp/cyber-security-daily-audit.json`: status critical only because workspace governance truth check returns critical from DB lifecycle.
- Other warnings include loopback/trusted proxy posture, personal-assistant trust model warning, and unpinned `codex` plugin install spec.
- Gateway bind remains loopback; approved chat channel posture is active; browser plugin disabled/excluded; skills check is healthy.

Why it matters:
- The critical security stop line should be respected, but the root cause is the DB lifecycle classification gap, not a newly observed credential leak in this audit.

Recommended fix:
- Resolve DB lifecycle classification first.
- Treat proxy/plugin warnings as separate hardening opportunities, not emergency blockers, unless network exposure changes.

Acceptance proof:
- Security cron proof no longer reports audit stop line active.

## Healthy Surfaces

- `openclaw skills check`: 92 total skills, 50 visible, 49 command-callable, 0 missing requirements.
- Harness fast lane: 75/75 checks passed.
- Workflow routing index: 31 routes, 0 critical, 0 warning.
- Dashboard truth lint: ok; canonical owner note boundaries remain explicit.
- Artifact index: incremental rebuild completed across 129 source files.
- PM implementation job queue: ok, 10 ready jobs, no collision groups.
- Truth-surface inventory: ok, 20 surfaces, no missing non-legacy surfaces.
- DB integrity itself: DB lifecycle manifest reports 0 SQLite integrity errors.
- Finance authority boundaries: no evidence of capital deployment approval, trade/order authority, owner approval inference, paper/live authority, or canon/portfolio mutation authority.

## Recommended Repair Order

1. Classify `tmp/backups/20260606-otel-warning-fix/state/openclaw.sqlite` in the DB lifecycle manifest path.
2. Rerun `python scripts\db_lifecycle_manifest.py --write --validate`.
3. Rerun the WF75 closeout refresh path that currently calls DB lifecycle.
4. Rerun `python scripts\sql_coverage_guard.py --write --write-md --validate`.
5. Rerun the security daily audit/proof path.
6. Rerun `python scripts\cron_freshness_spine.py --write --validate`, `python scripts\cron_signal_scorecard.py --write --validate`, and `python scripts\escalation_trigger.py --write --validate`.
7. Rerun `python scripts\fast_path_qa.py --write --validate` and `python scripts\control_closeout_bundle.py --write --validate`.
8. Then refresh PM state and inspect whether Retail Truth Routing and WF78 Scaleout clear their blocked lane status.

## Deferred Items

- Do not archive/delete the unclassified backup DB without explicit owner approval.
- Do not change config/auth/network/proxy/plugin/runtime posture inside this audit.
- Do not advance paper/live execution, capital deployment, portfolio/canon mutation, or customer/public output.
- Do not clean the large dirty git worktree in this pass; classify it separately before any revert/delete/archive action.
- Do not expand Spark cron canary until first-run proof is reviewed.

## Bottom Line

The workspace is not broken at the mission layer, but the control plane is currently blocked. The fastest high-value fix is narrow: classify the OTEL-fix backup SQLite in DB lifecycle, then rerun the dependent control/cron/security/closeout chain. After that, the remaining debt is mostly known operational hygiene: cockpit availability, PM yellow lanes, ticker-card freshness repair, root-policy alignment, and `tmp/` helper classification.

## Remediation Pass - 2026-06-07 17:47 MST

### What Was Fixed

- Classified `tmp/backups/20260606-otel-warning-fix/state/openclaw.sqlite` as a rollback/provenance backup in `scripts/db_lifecycle_manifest.py`.
- Documented the two `tmp/` Python helpers as audited one-off diagnostic/proof exceptions in `scripts/workspace_boundary_check.py`.
- Updated workspace-governor root standards for known durable roots: `state/`, `apps/`, `training/`, plus the documented `GEMINI.md` external-process compatibility exception.
- Updated `TOOLS.md` so the governance truth check recognizes the DB lifecycle route and the approved Telegram/local-control channel posture.
- Refreshed the stale WF78 Phase 2 eval artifact at `tmp/wf78-tier-b-research-packet-phase2-eval.json`.
- Started/validated the local PM cockpit health endpoint at `http://127.0.0.1:8765`.

### Validation Proof After Fixes

- `python scripts\db_lifecycle_manifest.py --write --validate`
  - Result: ok.
  - `unknown_count=0`, `integrity_error_count=0`.
  - Remaining `archive_ready_count=1` is owner-decision debt only; no archive/delete was performed.
- `python scripts\workspace_boundary_check.py`
  - Result: ok, warnings 0.
- `python scripts\sql_coverage_guard.py --write --write-md --validate`
  - Result: ok, critical 0, warnings 0.
- `python scripts\cyber_security_daily_audit_cron_runner.py`
  - Result: proof status ok, audit stop line false.
- `python scripts\cron_freshness_spine.py --write --validate`
  - Result: warning only, blocked count 0, enabled 25, stale 0, requires attention 9.
- `python scripts\cron_signal_scorecard.py --write --validate`
  - Result: ok, blocked count 0.
- `python scripts\escalation_trigger.py --write --validate`
  - Result: no main-session wake signal.
- `python scripts\automation_stack_hardening_pass.py --write --validate`
  - Result: warning only, critical 0, warnings 1.
  - Remaining warning: morning handoff retirement must wait for a clean weekday digest.
- `python scripts\fast_path_qa.py --write --validate`
  - Result: ok, 10 checks.
- `python scripts\repeatable_work_closeout.py --write --validate`
  - Result: ok, 9 steps.
- `python scripts\control_closeout_bundle.py --write --validate`
  - Result: ok, 4 steps, failed 0.
- `python scripts\pm_program_state.py --write --write-db --validate`
  - Result: ok, PM blocker register clear.
  - Readiness: 79.6, yellow; blocked lanes 0, stale lanes 0, needs-validation lanes 5.

### Remaining Warnings / Debt

- DB lifecycle still has one archive-ready candidate, but this requires explicit owner approval before any archive/delete action.
- PM remains yellow because five lanes are warning-status or validation-debt lanes, not blocked lanes:
  - `retail_truth_routing`: inherits automation hardening warning.
  - `ticker_card_refresh`: 200 ticker cards still need evidence repair.
  - `tier_promotion_review`: inherits ticker-card stale-card warning.
  - `finance_engine`: inherits ticker-card and Go/SQL policy warnings.
  - `sql_index`: inherits Go/SQL policy warnings.
- `tmp/finance-ticker-card-refresh-gate.json` still reports `ok_with_stale_cards`; this is the real finance evidence-repair queue, not a control-plane failure.
- `tmp/python-sql-contract-lint.json` remains warning-only with 1 warning: `scripts/finance_intelligence_state.py` lacks obvious backup/rollback language on a durable finance write path.
- `tmp/python-go-sql-helper-demotion-readiness-gate.json` remains warning-only with `ready_spike_count_visible=13`; `retire_python_now=0`, so this is a migration queue, not a demotion action.
- Spark cron canary is still pending first natural run proof.
- Security audit still has posture warnings, but no critical stop line after the DB lifecycle fix.

### Updated Bottom Line

The control-plane block found in the audit has been fixed. The workspace is now operational with warning-level debt, not blocked control state. The next highest-value work is not more broad audit scanning; it is targeted evidence repair for stale ticker cards, plus an owner decision on the one DB lifecycle archive-ready candidate if cleanup is desired.
