# Operating Procedure Repository Audit - 2026-05-06

## Purpose
Start the operating-procedure repository on an honest baseline instead of pretending the OS already has one coherent operator manual.

## Branch posture
- created branch: `operating-procedure-spine`
- branch purpose: build a repository of operator-facing procedures without mixing that work into the claim that the procedures are already complete

## What already behaves like procedure doctrine
These notes already function like operating procedures or protocol docs:
1. `06. Playbooks/Automation Orchestration Protocol.md`
2. `06. Playbooks/Cron Job Protocol.md`
3. `06. Playbooks/Spawn and Closeout Governance Matrix.md`
4. `06. Playbooks/Workspace Structure Protocol.md`
5. `06. Playbooks/Notes Layer Governance Protocol.md`

Strong alternates:
- `06. Playbooks/Operating Model.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`

## What is still missing
Top repository gaps:
1. a canonical procedure index / map that separates procedures from contracts, standards, continuity, and audits
2. a concise procedure classification rubric
3. a skill-to-procedure ownership map
4. a startup / session-opening operating checklist
5. a degraded-run / incident response procedure for scheduled windows

## What was created in this pass
- `06. Playbooks/Operating Procedures/README.md`
- `06. Playbooks/Operating Procedures/Procedure Index.md`
- `06. Playbooks/Operating Procedures/Procedure Classification Rubric.md`
- `06. Playbooks/Operating Procedures/Skill-to-Procedure Ownership Map.md`
- `06. Playbooks/Operating Procedures/Daily Summary Review-Only Brief Procedure.md`

## Skill audit
Current relevant workspace skills already cover:
- implementation: `disciplined-implementation`
- cron design: `cron-automation-manager`
- continuity: `memory-continuity-manager`
- control-plane operations: `openclaw-operator`
- workspace organization: `workspace-governor`
- orchestration posture: `ic-swarm-orchestrator`

Audit conclusion:
- the bigger gap is retrieval / classification hardening, not a broad new governance skill
- if a repository skill exists at all, it should stay narrow and index-focused

## Recommendation
Keep one narrow repository skill only:
- **name:** `operating-procedure-repository-manager`
- **scope:** classification, repository indexing, ownership mapping, and overlap/gap detection only
- **not allowed to own:** cron design, workspace cleanup, broad skill governance, or general control-plane adjudication

## Honest limit
This pass starts the repository spine. It does not finish the operator manual.
The next useful work is deliberate curation, not mass document creation.
