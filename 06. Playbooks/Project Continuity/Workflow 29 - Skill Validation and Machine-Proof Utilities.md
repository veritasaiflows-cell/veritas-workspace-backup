# Workflow 29 - Skill Validation and Machine-Proof Utilities

## Objective
- Move the skill layer from markdown-only trust toward executable proof where the contract is fragile enough to justify it.
- Replace manual vibe-tracking with machine-readable gates for swarm completion, skill prerequisites, and automation trust outputs.
- Establish a realistic validation-tier posture instead of pretending all active skills are equally validated.

## Why this lane exists
- The 2026-05-04 audits found that the Skill Quality Standard defines validation tiers, but the live governance index does not record them honestly.
- `ic-swarm-orchestrator` relies on a manual completion handshake that is race-prone.
- No active skill with external file dependencies has a sidecar validator proving its upstream contract still exists.
- Automation-hardening outputs remain prose-only, which prevents downstream scheduling logic from reading trust approval mechanically.

## Current State
- opened on 2026-05-04 from the independent skills-and-protocols audits
- active downstream workflow after Workflow 28 closed with follow-up on 2026-05-04
- inherits the cleaned skill/governance layer from Workflow 28, so this lane can focus on executable proof instead of wording cleanup
- should stay bounded: build proof utilities only where the trust value is real

## Scope
- define honest validation-tier labeling in the governance index
- design and implement a swarm completion handshake utility
- design and pilot sidecar skill validators for file-contract skills
- standardize a machine-readable trust-gate output block for automation-hardening decisions
- define what, if anything, must change in startup/bootstrap or `openclaw skills check` to respect the new proof layer

## Out of Scope
- converting every skill into a scripted product
- building autonomous scheduling based on weak trust signals
- widening skill count without first reducing overlap debt

## Sequential phase approach

### Phase 1 - Validation tier truth
Required outputs:
- add a validation-tier column to `06. Playbooks/Skills Governance Index.md`
- classify the active skills honestly (Tier 1 / Tier 2 / Tier 3)
- identify the first narrow pilot set for Tier 2 proof

### Phase 2 - Swarm handshake utility
Required outputs:
- lightweight script for blocking synthesis until expected lane outputs exist and are finalized
- `ic-swarm-orchestrator` instructions updated to use it
- fail-closed behavior when required outputs are missing

### Phase 3 - Sidecar validator pilot
Required outputs:
- define the standard sidecar validator contract (`validate.ps1` or equivalent)
- pilot it on at least one file-contract-heavy skill such as `veritas-technical-pass`
- decide whether and how `openclaw skills check` or adjacent bootstrap/runtime notes should invoke or reference the validators

### Phase 4 - Machine-readable automation trust block
Required outputs:
- standard YAML or JSON output block for `automation-hardening-manager`
- downstream read/use rule for `cron-automation-manager`
- explicit fail-closed behavior when the trust block is missing or unsafe

### Phase 5 - Closeout and audit
Required outputs:
- independent audit note
- executive summary folder
- chain log and cross-surface sync

## Acceptance Gates
Workflow 29 should not close unless all are true:
1. validation-tier posture is explicit and honest in the governance index
2. the swarm completion handshake no longer depends only on human memory
3. at least one real sidecar validator pilot exists and is proven locally
4. automation trust outputs can be read mechanically instead of only as prose
5. runtime/bootstrap implications are explicit instead of silently assumed

## Next Action
- Start Phase 1: verify the governance index's new validation-tier posture, then design the bounded swarm-handshake utility before touching broader skill-check integration.

## Key Files
- `08. Audits/Skills and Protocols Audit - 2026-05-04.md`
- `skills/ic-swarm-orchestrator/SKILL.md`
- `skills/veritas-technical-pass/SKILL.md`
- `skills/automation-hardening-manager/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `06. Playbooks/Skill Quality Standard.md`
- `06. Playbooks/Skills Governance Index.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `AGENTS.md`
- `TOOLS.md`
