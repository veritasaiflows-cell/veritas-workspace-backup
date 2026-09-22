---
name: "veritas-self-improvement"
description: "Route repeated friction into prompt-book candidates and eval gaps."
---

# Veritas Self-Improvement

## Purpose

When WF74 detects repeated implementation friction, alert noise, stale procedures, validator drag, finance-response quality repair debt, or WF74/WF88 learning-loop gaps, route the finding into a gated patch plan, skill-update proposal, owner packet, validator ticket, PM job, or monitor-only state instead of leaving it in chat memory.

## WF74 Gated Auto-Patch Flow

1. Refresh WF74 evidence surfaces:
   - `python scripts\wf74_improvement_opportunity_queue.py --write --write-md --validate`
   - `python scripts\wf74_reflection_to_proposal_autopilot.py --write --write-md --validate`
   - `python scripts\wf74_auto_patch_proposer.py --write --write-md --validate`

2. Classify each proposal by route:
   - `patch_plan` for low-risk implementation metadata, validator routing, alert wording/dedupe, tests, or non-authority proof metadata.
   - `skill_workshop_request` for repeated procedural friction that belongs in a reusable skill.
   - `owner_config_decision` for collector/runtime/config/capture-depth questions.
   - `finance_repair_review` for finance-answer quality and source/freshness repair.
   - `execution_guardrail_review` for paper/live/account/action surfaces.

3. Before any code patch is applied:
   - lease exact files through `concurrent_lane_manager.py`
   - set the lane to `running` with available runtime metadata
   - inspect the generated patch plan in `tmp/wf74-auto-patch-proposer.json`
   - apply only a scoped diff
   - run the plan's validation commands plus `python scripts\changed_file_validator_router.py --write --validate`
   - close the lane with proof artifacts

4. For skill updates:
   - create or update a Skill Workshop proposal from generated `skill_workshop_requests`
   - keep the proposal pending by default
   - apply a skill only when Randall explicitly approves that specific proposal

## WF74/WF88 Loop Trace Requirement

When reviewing or advancing WF74/WF88 learning-loop work, start from the stitched trace packet instead of manually chasing disconnected artifacts.

Required first-hop artifacts:

```powershell
python scripts\wf74_wf88_loop_trace_packet.py --write --write-md --validate
python scripts\wf88_os2_control_packet.py --write --write-md --validate
python scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate
```

The loop trace should connect, when available:

- OTEL/runtime/failure/token metadata
- model-learning metadata ledger rows
- WF74 improvement opportunities
- WF74 router and decision docket rows
- PM job, validator ticket, Skill Workshop proposal, owner packet, or monitor-only state
- lane-register rows
- closeout proof artifacts
- memory or continuity pointers
- WF88 OS2/wiki consumer state

A learning-loop claim is weak when it cannot identify the current route state for an item. Treat missing links as routing debt, not as proof the item is handled.

## Route State Interpretation

Use route states consistently:

- PM job: deterministic implementation or proof task exists.
- Validator ticket: deterministic guard/test/validator gap exists.
- Skill Workshop proposal: repeated behavior/procedure change exists; pending is not applied doctrine.
- Owner packet: runtime/config/cron/external/finance/paper/live or other gated decision needs Randall.
- Monitor-only: visible, no immediate action.
- Blocked/hard stop: forbidden or ambiguous authority surface.

## Long-Work Integration

If a WF74/WF88 item requires a long local script, provider-backed index, broad finance refresh, or heavy validator run, route it through the long-work status runtime before claiming it is complete.

Canonical status refresh:

```powershell
python scripts\long_work_job_status_packet.py --write --write-md --validate
```

WF88 should consume the long-work status packet so future sessions know whether a job is active, resumable, complete, warning, blocked, or stale.

Do not rerun an expensive full job blindly when a resumable job exists. Check the status packet first, then resume by job id if appropriate.

## Closure Rule

A WF74/WF88 improvement loop item is closed only when one of these is true:

- trace row links to completed proof and lane closeout
- trace row links to an accepted monitor-only state
- trace row links to an owner packet and no autonomous action is allowed
- trace row links to a pending Skill Workshop proposal and is explicitly reported pending, not applied
- trace row links to a blocked/hard-stop state with reason

Do not close an item only because the chat response discussed it.

## Auto-Apply Boundary

WF74 may automatically detect, rank, propose, and prepare patch plans. It must not directly auto-apply code, skills, collector config, finance canon/portfolio state, paper/live/account actions, credential/auth/network changes, or doctrine changes.

Standing auto-apply may be considered only for explicitly approved low-risk classes, such as non-authority test fixture refresh, validator routing metadata, alert wording/dedupe, and cron freshness expected-artifact metadata. Even then, require lane lease, exact diff, validator proof, rollback path, and no authority expansion.

## Hard Blocks

Never auto-apply:

- `SOUL.md`, `AGENTS.md`, `TOOLS.md`, or `MEMORY.md`
- finance canon, portfolio, cash, sizing, sleeve, or risk-rule surfaces
- trade/order/paper/live/account/brokerage actions
- credentials, auth, network exposure, runtime config, startup/service/plugin config
- OTEL collector capture-depth, logs pipeline, or file exporter changes
- Skill Workshop apply/install/approval without Randall's explicit request
- anything that infers owner approval

## Validation

After implementing or reviewing this path, run relevant checks:

```powershell
python scripts\wf74_auto_patch_proposer.py --write --write-md --validate
python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate
python scripts\pm_control_packet.py --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\wf74_rsi.py --validate-only
python scripts\wf74_wf88_loop_trace_packet.py --write --write-md --validate
python scripts\long_work_job_status_packet.py --write --write-md --validate
```

## Response Contract

Report generated plan counts, patch-plan counts, Skill Workshop request counts, owner-gated plan counts, auto-apply candidate count, and `auto_apply_count`. If `auto_apply_count` is not zero, stop and treat it as a blocker.

For WF74/WF88 learning-loop work, report whether the trace links the item to proof, monitor-only state, owner packet, pending skill proposal, or blocked/hard-stop reason.

## Boundary

This contract is review/proof/routing only. It must not apply skills, mutate code without lane lease and validators, mutate cron schedules, mutate runtime/config/auth/channel state, mutate finance/canon/portfolio/cash/sizing/risk state, submit paper/live/account/brokerage actions, send external/customer output, capture raw prompt/response/tool payloads, or infer owner approval.

For migrated/user-authored skills, agent-side apply may refuse `does not own this skill path`; the operator CLI works: `openclaw skills workshop apply <id>`. Judge success by the "Applied" line, not the exit code. Stale proposals are terminal — recover via `propose-update` with a merged `PROPOSAL.md`. After apply, verify containment and clean check.

## Prompt Book Candidate Routing, prompt friction, helper-lane packet defect, self-prompt weakness, stop-line miss, or eval failure recur three or more times, classify it as `prompt_book_candidate` before creating a new patch lane.

Route order:

1. Refresh `python scripts\prompt_book_registry.py --write --write-md --validate`.
2. Refresh `python scripts\prompt_book_eval_fixtures.py --write --write-md --validate`.
3. Run `python scripts\prompt_book_linter.py --write --validate`.
4. Run `python scripts\prompt_book_eval_gap_packet.py --write --write-md --validate`.
5. If gaps remain, route PM candidates through `python scripts\prompt_book_pm_job_packet.py --write --write-md --validate`.
6. If reusable doctrine should change, create or revise a pending Skill Workshop proposal.
7. Keep proposals pending unless Randall explicitly approves apply.

A zero-gap prompt-book packet means fixture coverage is complete for current registry entries. It does not imply AGI/ASI capability, model training, external action, finance authority, or automatic doctrine promotion.

Stop lines: no raw prompt/response/tool payload capture, no skill/doctrine auto-apply, no finance/canon/portfolio/cash/sizing/risk mutation, no paper/live/account action, no cron/runtime/config/channel mutation, no external delivery, and no owner approval inference.

## Implementation Token Attribution Triage

Before running any lane `--complete` stamping to close attribution gaps, classify every gap with the exact bridge logic first, then act only on the actionable class:

1. Scan completed model lanes with the bridge's own functions (`token_stamp_assessment`, `inferred_missing_usage_classification`, `gap_model_capacity`, `completion_cohort`, receipt verification) and sort each gap into `stamp_missing`, `receipt_credit_blocked`, or `historical_terminal`.
2. Leave `historical_terminal` gaps (pre-cutover, counters never existed) as audit context; never backfill or reconstruct their counters — verify the bridge still reports them classified, then stop.
3. For `receipt_credit_blocked` gaps (valid stamp plus matching source receipt and dispatch binding, but the live session index aged out), refuse closed-lane mutation and route a receipt-anchored credit-grace or retention-extension owner packet instead of re-stamping.
4. Stamp only `stamp_missing` lanes that carry provider-exposed counters, then rerun `token_usage_ledger.py` and `implementation_token_attribution_bridge.py` and confirm the actionable count fell with no new gaps added.
