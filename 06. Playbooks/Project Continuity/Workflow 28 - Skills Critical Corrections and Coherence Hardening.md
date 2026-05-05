# Workflow 28 - Skills Critical Corrections and Coherence Hardening

## Objective
- Close the highest-risk skill and protocol drift surfaced by the 2026-05-04 skills audit before the next board-sync, weekly-brief, or skills-expansion pass runs on stale assumptions.
- Remove contradictory state language, missing primary-input artifacts, missing trust disclosures, and dead or duplicated routing references from the active skill layer.
- Keep the skill layer aligned with Veritas doctrine: one canonical vocabulary, explicit trust boundaries, and no fake-green workflow claims.

## Why this lane exists
- The 2026-05-04 skills audit found three pre-execution critical fixes plus multiple high-severity coherence gaps across the active skill set.
- `technical-chart-pass` and `veritas-technical-pass` overlap in a way that can produce contradictory board-state language.
- Several core skills are missing `tmp/deployment-readiness-surface.json`, which means they can operate without the live machine deployment signal.
- `veritas-investment-deck` can currently polish uncertainty out of output because it lacks a trust-disclosure requirement.
- Skill count is already at the governance threshold, so overlap and drift need to be reduced before more skill sprawl happens.

## Current State
- opened on 2026-05-04 from the independent skills-and-protocols audit
- active downstream workflow after WF25 closed with follow-up on 2026-05-04
- should run before the next meaningful board-sync / weekly-brief execution that relies on the audited skills
- does not widen research autonomy; it hardens the control surface
- Phase 1 critical corrections are landed: the deployment-readiness surface was added to the audited workflow skills, the investment-deck disclosure contract was tightened, and the cron skill now points at the retrofit checklist
- `memory-continuity-manager` was checked against the audit finding and already had `USER.md` in its editable-file manifest, so no extra patch was required there
- Phase 2 coherence fixes are also landed in the working tree: `technical-chart-pass` is now explicitly deprecated into a narrow legacy fallback, `veritas-technical-pass` owns canonical state translation, `automation-hardening-manager` no longer treats TaskFlow as an assumed live path, and `ic-swarm-orchestrator` now defers routing doctrine to `Automation Orchestration Protocol.md`
- Phase 3 governance hooks are partially landed in the working tree: `workspace-qa-pass`, `veritas-self-improvement`, and `Skills Governance Index.md` now reflect skills-specific governance posture and honest validation-tier accounting

## Scope
- add missing critical input artifacts and trust-disclosure rules to active skills
- resolve the technical-analysis skill overlap decision
- remove dead or duplicated routing references from orchestration / automation skills
- tighten skill-governance references where trigger logic is incomplete
- update affected governance notes and indexes when the skill layer changes

## Out of Scope
- writing a full executable validation framework
- building new automation helpers unless they are required to close a critical coherence gap
- broad finance-note mutation or portfolio-state changes

## Sequential phase approach

### Phase 1 - Critical live-skill corrections
Required outputs:
- add `tmp/deployment-readiness-surface.json` to `veritas-positioning-pass`, `veritas-portfolio-update`, and `veritas-weekly-brief`
- add trust-disclosure requirements to `veritas-investment-deck`
- add `USER.md` to `memory-continuity-manager` editable-file manifest
- add `Cron Job Retrofit Checklist.md` to `cron-automation-manager` read-first inputs

### Phase 2 - Coherence and overlap resolution
Required outputs:
- deprecate `technical-chart-pass`, migrate any useful generic fallback rules into `veritas-technical-pass`, and update the governance index
- remove or explicitly caveat dead `TaskFlow` routing from `automation-hardening-manager`
- refactor `ic-swarm-orchestrator` to defer lane routing / fallback order to `06. Playbooks/Automation Orchestration Protocol.md`
- remove or define the undefined `ACP` reference

### Phase 3 - Governance trigger hardening
Required outputs:
- add skills-focused QA override to `workspace-qa-pass`
- add skill-governance references to `veritas-self-improvement`
- update `06. Playbooks/Skills Governance Index.md` to reflect the new overlap decision and honest count posture

### Phase 4 - Closeout and audit
Required outputs:
- independent audit note
- executive summary folder
- chain log and cross-surface sync

## Acceptance Gates
Workflow 28 should not close unless all are true:
1. the three critical fixes from the audit are landed
2. the technical-analysis overlap is resolved by explicit deprecation or equivalent removal of contradictory state language
3. dead routing references are removed or clearly fail-closed
4. governance notes and indexes reflect the post-fix skill layer honestly
5. an independent audit confirms the skill layer is more coherent, not just more verbose

## Next Action
- Verify the landed Phase 1–3 skill changes together, then record the Phase 1/2/3 chain progress and move WF28 into its independent audit / closeout-prep path.

## Key Files
- `08. Audits/Skills and Protocols Audit - 2026-05-04.md`
- `skills/veritas-positioning-pass/SKILL.md`
- `skills/veritas-portfolio-update/SKILL.md`
- `skills/veritas-weekly-brief/SKILL.md`
- `skills/veritas-investment-deck/SKILL.md`
- `skills/memory-continuity-manager/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `skills/automation-hardening-manager/SKILL.md`
- `skills/ic-swarm-orchestrator/SKILL.md`
- `skills/workspace-qa-pass/SKILL.md`
- `skills/veritas-self-improvement/SKILL.md`
- `06. Playbooks/Skills Governance Index.md`
