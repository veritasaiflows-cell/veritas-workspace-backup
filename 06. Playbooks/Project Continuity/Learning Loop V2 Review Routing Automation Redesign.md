# Learning Loop V2 Review Routing Automation Redesign

## Current State

- Audit owner file: `08. Audits/Learning Loop V2 Review Routing Automation Redesign Audit - 2026-06-22.md`.
- Implementation lane: `RUNTIME::LEARNING-LOOP-V2-IMPLEMENTATION-2026-06-22::implementation`.
- Purpose: convert the audit recommendations into durable review/routing/automation improvements without widening finance, cron, runtime, or execution authority.

## Implemented V2 Changes

- Repaired the live P1 cron governance regression from the audit: the enabled one-shot `WF87 shadow threshold after-market check` job now has a cron freshness-spine contract at `state/cron-contracts/wf87-shadow-threshold-after-market-check.json`.
- Tightened PM cron quiescence proof so recursive summary artifacts are non-blocking context, while direct PM worker outputs remain blocking.
- Added `scripts/wf74_decision_docket.py` and `tmp/wf74-decision-docket.json/.md` as the WF74 V2 decision surface.
- Added `data/wf74-learning-loop-evals/cases.json` plus `scripts/wf74_learning_loop_eval_harness.py` so repeated classification failures become local regression cases.
- Updated workflow-maturity routing so completed implementation-routing work does not reopen on residual maturity-only blockers unless a new non-maturity blocker appears.
- Wired the WF74 decision docket into startup/status/future pickup surfaces so boot cards show fix-now, hard-stop, market-session-accrual, and monitor-only counts.
- Applied durable Skill Workshop updates to `cron-automation-manager`, `veritas-self-improvement`, `veritas-workspace-audit-orchestrator`, and `disciplined-implementation`; repaired the initial addendum-replacement issue with full-body merged proposals.

## Current Docket Interpretation

- `fix_now_count=0`.
- `hard_stop_count=0`.
- `skill_proposal_count=0`.
- `active_action_count=0`.
- Current rows are market-session accrual or monitor-only.
- Market-session accrual rows are primarily WF87/AUTONOMY-SPINE maturity proof waiting for valid Tuesday, 2026-06-23 regular-session evidence.
- Monitor-only rows should stay visible but should not open code, cron, finance, or runtime implementation work by themselves.

## Final Implementation Proof Snapshot

- Cron contract validator: `ok`, contracts `34`, drift `0`, missing `0`.
- Cron freshness spine: validation `ok`, blocked `0`, urgent `0`, unregistered enabled `0`, missing expected artifact contracts `0`; one stale enabled artifact remains monitor-only.
- Cron control packet: `ok`, escalation `0`.
- PM sidecar retirement guard: `ok`, errors `0`, warnings `0`.
- Repeatable work closeout: `ok`, steps `11`.
- WF74 decision docket: `ok`, rows `17`, active action `0`, fix-now `0`, hard-stop `0`, skill-proposal `0`, market-session-accrual `9`, monitor-only `8`.
- WF74 eval harness: `ok`, cases `6`, passed `6`, failed `0`.
- Go validator source patch: `scripts/go/internal/cronproof/lint.go` now supports object-shaped cron `expected_artifacts` by reading the `path` field, matching the Python cron freshness contract shape.
- Go proof: `go test .\...` passed; all Go validator binaries rebuilt; Go binary freshness `ok`; Go implementation profile `ok`, validators `11`, failed `0`, warnings `0`, critical `0`.
- Release proof: implementation release contract `ok`, `ready_to_close=true`, missing gates `0`, unknown warnings `0`; control closeout bundle `ok`, failed steps `[]`.
- Adjacent PM closeout cleanup: `PM::RELEASE-CONTRACT-HANDOFF-QUIESCENCE-CLEANUP-2026-06-22` patched `implementation_release_contract.py` so a drained PM implementation queue remains clean when a separate non-queue main-session handoff has just been dispatched; regression coverage still blocks completed PM-job selection. Final release contract after lane close is `ok`, surfaces `11`, missing gates `0`, unknown warnings `0`, `ready_to_close=true`.

## Acceptance Proof To Keep Current

Run after future WF74 or startup/status routing changes:

```powershell
python scripts\wf74_improvement_opportunity_queue.py --write --validate
python scripts\wf74_autonomy_work_router.py --write --validate
python scripts\wf74_auto_patch_proposer.py --write --validate
python scripts\wf74_decision_docket.py --write --write-md --validate
python scripts\wf74_learning_loop_eval_harness.py --write --validate
python scripts\future_session_enhancement_packet.py --write --write-md --validate
python scripts\startup_brief_packet.py --write --validate
python scripts\status_card_packet.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_bundle_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

## Stop Lines

- No auto-apply from WF74.
- No live cron add/edit/disable/delete without exact owner approval, rollback proof, and post-change freshness proof.
- No Skill Workshop apply/install/quarantine without explicit approval.
- No finance canon, portfolio, cash, sizing, risk, paper/live, brokerage, or account mutation.
- No config/auth/runtime/channel mutation, external delivery, destructive/archive work, or owner approval inference.

## Next Watchpoint

After the scheduled Tuesday, 2026-06-23 after-market WF87 check runs, rerun the WF87 scorecard, WF87 readiness rollup, AUTONOMY-SPINE rollup, and WF74 decision docket. If WF87 reaches threshold and child gates clear, the docket should move maturity rows out of market-session accrual. If not, keep them as accrual/monitor-only and do not promote execution readiness.
