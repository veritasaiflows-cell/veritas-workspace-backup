---
name: "veritas-self-improvement"
description: "Add WF74 gated auto-patch proposal contract."
---

# WF74 Gated Auto-Patch Proposer Contract

## Purpose

When WF74 detects repeated implementation friction, alert noise, stale procedures, validator drag, or finance-response quality repair debt, route the finding into a gated patch or skill-update plan instead of leaving it in chat memory.

## Required Flow

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
   - create or update a Skill Workshop proposal from the generated `skill_workshop_requests`
   - keep the proposal pending by default
   - apply a skill only when Randall explicitly approves that specific proposal

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

After implementing or reviewing this path, run:

```powershell
python scripts\wf74_auto_patch_proposer.py --write --write-md --validate
python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate
python scripts\pm_control_packet.py --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\wf74_rsi.py --validate-only
```

## Response Contract

Report generated plan counts, patch-plan counts, Skill Workshop request counts, owner-gated plan counts, auto-apply candidate count, and `auto_apply_count`. If `auto_apply_count` is not zero, stop and treat it as a blocker.
