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
- closed with follow-up on 2026-05-04 after bounded proof pilots for handshake gating, sidecar validation, and automation trust blocks all landed with local proof and independent audit
- inherits the cleaned skill/governance layer from Workflow 28, so this lane can focus on executable proof instead of wording cleanup
- should stay bounded: build proof utilities only where the trust value is real
- Phase 1 is partially pre-landed because `06. Playbooks/Skills Governance Index.md` already carries the validation-tier column and honest Tier 1 baseline posture from Workflow 28
- first bounded Tier 2 pilot set selected:
  - `ic-swarm-orchestrator` -> swarm completion handshake utility / expected-output proof
  - `veritas-technical-pass` -> first sidecar validator pilot for a file-contract-heavy workflow skill
  - `automation-hardening-manager` plus `cron-automation-manager` -> machine-readable automation trust block producer/consumer path
- Phase 2 pilot is now landed and locally verified:
  - `scripts/swarm_completion_handshake.py`
  - sample manifests: `scripts/testdata/swarm-handshake-sample.json` and `scripts/testdata/swarm-handshake-fail.json`
  - fail-closed proof: unresolved verifier lane + missing artifact blocked synthesis with `EXIT=2`
  - success proof: completed reasoner/verifier lanes plus artifacts allowed synthesis and wrote `tmp/swarm-handshake-status.json`
- Phase 3 pilot is now landed and locally verified:
  - `scripts/veritas_technical_pass_validate.py`
  - `skills/veritas-technical-pass/SKILL.md` now carries an explicit sidecar-validator pilot section
  - proof result: `python scripts/veritas_technical_pass_validate.py --write` -> `status=ok`, wrote `tmp/veritas-technical-pass-validation.json`
  - governance impact: `veritas-technical-pass` is now recorded as Tier 2 functional local proof in `06. Playbooks/Skills Governance Index.md`
- Phase 4 pilot is now landed and locally verified:
  - `scripts/automation_trust_block.py`
  - `scripts/cron_trust_block_consumer.py`
  - approved proof result: normalized trust block wrote `tmp/automation-trust-block.json` and the consumer allowed only `read_only`
  - blocked proof result: invalid approval posture failed closed with `EXIT=2`
  - governance impact: `automation-hardening-manager` and `cron-automation-manager` are now recorded as Tier 2 functional local proof in `06. Playbooks/Skills Governance Index.md`
- Runtime/bootstrap implication is now explicit for pilot scope: no `openclaw skills check` integration and no startup hook were added; these proof utilities remain manual bounded validators until a later workflow intentionally widens enforcement

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

Current bounded implementation pilot:
- `scripts/swarm_completion_handshake.py`
- contract: read a small JSON manifest with `expected_lanes[]`, lane status, optional verdict, and required artifacts
- output: machine-readable handshake result with `synthesis_allowed`, `blocking_lanes`, and per-lane artifact checks
- exit behavior: `0` only when every expected lane is resolved and ready; otherwise fail-closed non-zero

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
- No further action inside WF29 unless a named reopen trigger fires. Promote Workflow 21 active so the next real downstream lane can use the new proof surfaces instead of leaving them unused.

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
