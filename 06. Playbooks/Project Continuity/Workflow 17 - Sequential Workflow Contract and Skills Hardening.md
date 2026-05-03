# Workflow 17 - Sequential Workflow Contract and Skills Hardening

## Objective
- Standardize how major sequential and orchestrated workflows are opened, preflighted, executed, QAed, and closed.
- Remove the current scatter where preflight, acceptance, exit, checkpoint, and next-pass expectations exist in pieces across multiple protocols but not as one explicit contract.
- Harden the relevant skills so workflow-driving skills follow the same contract instead of drifting into inconsistent assumptions.

## Why this workflow exists
- The workspace already has strong pieces: preflight rules, spawn rules, acceptance checks, queue freshness rules, and QA ownership.
- What is still weak is consistency.
- Right now the operating truth is distributed across doctrine, playbooks, queue entries, and skills. That works, but it leaves avoidable ambiguity around:
  - entry checklist vs implicit setup
  - exit / closeout checklist vs implied completion
  - checkpoint / commit decision timing
  - when next-work recommendations are required
  - what a workflow-driving skill must explicitly say before labor starts

## Current State
- `AGENTS.md` enforces sequential completion and real blocker handling.
- `06. Playbooks/Continuity Stewardship Protocol.md` requires preflight review for major work and defines completion confirmation.
- `06. Playbooks/Automation Orchestration Protocol.md` defines main-lane reserve, spawn-first advancement, completion handshake, and queue freshness.
- `06. Playbooks/OpenClaw Parallel Work Plan.md` defines lane ownership and required handoff packets.
- Workflow 16 is now the first immediate consumer of this hardening pass: the automation lane needs explicit contract expectations for approved source bundle, ownership boundary, review window, dashboard/workbook handoff, stop lines, and canonical-drift protection before research cron expands.
- The missing layer is one explicit workflow contract standard that ties those together and pushes the same expectations into the skills that steer orchestrated work.

## Scope
### In scope
- major sequential workflow contract structure
- preflight / entry checklist standard
- acceptance / verification gate standard
- exit / closeout checklist standard
- checkpoint / commit-decision rule
- required next-pass and next-1-to-2-candidate recommendation rule
- skill hardening for workflow-driving skills

### Out of scope
- broad automation execution design for Workflow 16 itself
- canonical finance-note mutation policy beyond already-approved boundaries
- large skill rewrites unrelated to workflow orchestration or hardening

## Skills hardening surface
Prioritize these skills because they directly shape orchestrated work:
- `skills/automation-hardening-manager/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `skills/project-continuity-manager/SKILL.md`
- `skills/ic-swarm-orchestrator/SKILL.md`
- `skills/workspace-qa-pass/SKILL.md`
- `skills/openclaw-operator/SKILL.md` where protocol / checkpoint expectations touch operator work

## Proposed phases

### Phase 1 - Contract inventory and gap map
Goal:
- trace where the current protocol already defines entry, spawn, acceptance, closeout, checkpoint, and next-pass expectations

Deliverables:
- source-of-truth table
- gap map for missing or inconsistent workflow-contract expectations
- short skill-gap table for the priority skills above

Acceptance:
- we can point to exactly where each contract element lives today or name it as missing

### Phase 2 - Workflow contract standard
Goal:
- create one explicit standard for major sequential/orchestrated workflows

Deliverables:
- standard sections for:
  - objective
  - current truth
  - preflight / entry checklist
  - spawn posture
  - acceptance gates
  - exit / closeout checklist
  - checkpoint / commit decision
  - next pass
  - next 1-2 bounded candidate workflows
- explicit rule for automation-facing workflows to state:
  - owner layer
  - review window
  - stop lines
  - dashboard/workbook/weekly-brief handoff posture
  - canonical mutation posture
- clear rule for when the contract belongs in a continuity note vs a playbook vs a skill

Acceptance:
- a new workflow can be opened from the standard without reconstructing protocol from scattered files

### Phase 3 - Skills hardening
Goal:
- align the key workflow-driving skills with the new contract

Deliverables:
- skill updates so they explicitly reinforce:
  - preflight-first behavior for major work
  - bounded spawn posture
  - acceptance and QA gates
  - exit / closeout expectations
  - next-pass and adjacent-work recommendation expectations where relevant

Acceptance:
- the priority skills no longer leave the workflow contract implicit or inconsistent

### Phase 4 - Control-surface integration and closeout
Goal:
- update the live queue / registry / protocol references so the new contract is not trapped in one note

Deliverables:
- control-surface updates
- bounded QA note
- explicit handoff to Workflow 18

Acceptance:
- Workflow 18 can start from a clear standardized contract baseline

## Success Standard
- major workflow starts become more boring and explicit
- major workflow closures become harder to fake
- skills that steer orchestration stop drifting from the live protocol
- next-step routing becomes clearer without needing chat reconstruction

## Blockers / Trust Gaps
- current protocol truth is real but distributed
- checkpoint expectations are still partly doctrine-level and partly workflow-specific
- next-1-to-2-candidate recommendation behavior is useful but not yet formalized as a standard requirement

## Next Action
- Run Phase 1 inventory first.
- Make the first pass concrete enough that Workflow 16A / 16B can inherit one consistent contract skeleton instead of improvising automation-specific sections later.
- Treat Workflow 18 as the follow-on governance hardening pass, not a parallel rewrite of the same contract.

## Key Files
- `AGENTS.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- priority skills listed above
