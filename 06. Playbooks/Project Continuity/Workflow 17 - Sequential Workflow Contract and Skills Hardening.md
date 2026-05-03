# Workflow 17 - Sequential Workflow Contract and Skills Hardening

## Objective
- Standardize how major sequential and orchestrated workflows are opened, preflighted, executed, QAed, and closed.
- Remove the current scatter where preflight, acceptance, exit, checkpoint, and next-pass expectations existed in pieces across multiple protocols but not as one explicit contract.
- Harden the relevant skills so workflow-driving skills follow the same contract instead of drifting into inconsistent assumptions.

## Current State
- **Closed on 2026-05-03.**
- The major-workflow contract skeleton now exists as a reusable live standard in `06. Playbooks/Major Workflow Contract Standard.md`.
- Relevant protocol docs and workflow-driving skills were aligned to that contract.
- Workflow 18 inherited a cleaner baseline instead of re-litigating workflow structure from scratch.

## Phase 1 Findings - Contract Inventory and Gap Map

| Contract element | Live sources found | Gap judgment |
|---|---|---|
| Entry / preflight | `06. Playbooks/Continuity Stewardship Protocol.md`, `06. Playbooks/Automation Orchestration Protocol.md` | Real but scattered; no one universal workflow skeleton |
| Spawn posture | `06. Playbooks/Automation Orchestration Protocol.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md`, `06. Playbooks/Cron Job Protocol.md` | Real but not tied into a standard continuity-note structure |
| Acceptance / verification | completion-confirmation rules, QA rule, `skills/workspace-qa-pass/SKILL.md` | Missing explicit universal acceptance-gate section |
| Exit / closeout | completion confirmation, queue movement, auto-promotion logic | Missing one explicit closeout checklist |
| Checkpoint decision | ad hoc workflow handling, operator skill guidance | No universal rule requiring explicit checkpoint posture |
| Next pass visibility | queue freshness, project continuity, status contract | Real but not standardized across major workflows |
| Adjacent workflow recommendation | partial / ad hoc only | Missing as a standard requirement |
| Automation-facing sections (owner layer, review window, stop lines, handoff, canonical mutation posture) | partial in scattered automation notes | Missing from the base workflow contract |

## Phase 2 Deliverable - Standard Contract
Landed:
- `06. Playbooks/Major Workflow Contract Standard.md`

The standard now requires major workflows to make explicit:
- preflight / entry checklist
- execution posture
- acceptance gates
- exit / closeout checklist
- checkpoint decision
- next pass
- next 1-2 adjacent candidate workflows when useful

Automation-facing workflows must also name:
- owner layer
- review window
- stop lines
- surface / handoff posture
- canonical mutation posture

## Phase 3 Deliverable - Skills Hardening
Updated:
- `skills/automation-hardening-manager/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `skills/project-continuity-manager/SKILL.md`
- `skills/ic-swarm-orchestrator/SKILL.md`
- `skills/workspace-qa-pass/SKILL.md`
- `skills/openclaw-operator/SKILL.md`

Skill hardening added or reinforced:
- explicit owner/review-window/stop-line posture for major automation work
- checkpoint visibility
- next-pass expectations
- closeout honesty
- helper-lane limits for early automation work

## Phase 4 Deliverable - Integration and QA
Updated live protocol / control documents:
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/OpenClaw Model Deployment Plan.md`
- `06. Playbooks/Project Continuity/Workflow 4 - Sequential Chain Protocol.md`

## Acceptance Evidence
- `openclaw skills check` passed after the skill updates.
- Live protocol docs now reference the major-workflow contract standard instead of relying only on distributed implied rules.
- Removed-model routing residue was tightened in the live protocol layer so workflow guidance no longer depends on `gpt-5.3-codex` being available.

## Checkpoint Decision
- Workflow-level checkpoint was deferred until Workflow 18 closed, because both passes touched the same governance surface and a combined checkpoint is cleaner than splitting one protocol-hardening change into two commits.

## Residual / Deferred
- Historical notes and backups may still mention removed 5.3 Codex helper posture as records of past state; the live governance layer is the source of truth.
- Workflow 16 still required Workflow 18 before it could be honestly unblocked.

## Next Action
- Execute Workflow 18 sequentially from this standardized baseline.

## Key Files
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- skill files listed above
