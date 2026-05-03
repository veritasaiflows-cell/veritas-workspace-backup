# Workflow 18 - Spawn, Closeout, and Skills Governance Hardening

## Objective
- Harden the execution-governance layer that decides what should stay in the main session, what can be spawned for efficiency, what must remain blocked on human judgment, and what must be true before executive closeout.
- Turn the current good-but-scattered spawn and closeout rules into one explicit governance contract.
- Extend that contract into the skills most likely to shape spawn behavior, completion claims, and next-work routing.

## Current State
- **Closed on 2026-05-03.**
- The spawn / closeout governance matrix now exists as a live reusable standard in `06. Playbooks/Spawn and Closeout Governance Matrix.md`.
- Helper-lane authority, executive-summary timing, checkpoint posture, and next-work routing are now explicit instead of implied.
- Workflow 16 is no longer blocked on missing spawn / closeout governance rules.

## Phase 1 Findings - Spawn and Closeout Decision Audit

| Decision type | Live sources found | Gap judgment |
|---|---|---|
| Main-session reserve | `06. Playbooks/Automation Orchestration Protocol.md` | Strong, but exception rules needed tighter closeout/governance framing |
| Spawn read-only / distinct-output posture | `06. Playbooks/Automation Orchestration Protocol.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md` | Real, but not presented as one operational matrix |
| Blocked / operator-gated posture | multiple protocol docs | Real, but not standardized into explicit go / no-go rules |
| Executive-summary gate | partial in QA / completion / status rules | Missing as a named explicit gate |
| Checkpoint decision | ad hoc | Missing as a consistent governance requirement |
| Helper-lane authority for early automation | implied only | Missing explicit contract-building / QA posture |

## Phase 2 Deliverable - Governance Matrix
Landed:
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Skills Governance Index.md`

The matrix now standardizes:
- main-session only
- spawn read-only
- spawn distinct-output
- blocked / operator-gated
- helper-lane authority boundaries
- executive-summary gate
- closeout checklist
- checkpoint rule
- next-work recommendation rule
- canonical spawn decision source / decision tree

It also makes the current automation rule explicit:
- early research automation helper lanes are for **contract-building, QA, contradiction review, and bounded packet prep**, not freeform research swarm behavior

## Phase 3 Deliverable - Skills Integration
Reinforced in the workflow-driving skills:
- helper lanes do not own final truth
- closeout requires explicit integration and checkpoint posture
- major workflow closeout should name the next pass and bounded adjacent candidates when useful
- early automation lanes default to contract-building / QA unless the workflow contract explicitly widens authority
- the workspace skill layer now has a live governance index and no-skill-sprawl trigger

## Phase 4 Deliverable - Control-Surface Integration and QA
Updated live protocol / control documents:
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
- `06. Playbooks/Project Continuity/Research Automation - News, Geopolitics, and Thesis Drift Monitoring.md`

## Acceptance Evidence
- `openclaw skills check` passed after the skill/governance updates.
- The live governance layer now explicitly blocks executive-summary theater when acceptance, integration, checkpoint posture, or residual-risk naming is missing.
- Workflow 16 is now unblocked to a readiness-gate posture only; no research cron or canonical-note helper execution was opened prematurely.
- A standalone closeout artifact standard and skills governance index now exist instead of relying on convention.

## Checkpoint Decision
- **Checkpoint taken after Workflow 17 and Workflow 18 together** as one governance/skills hardening baseline.

## Residual / Deferred
- Workflow 16 remains an umbrella readiness gate, not the substantive implementation pass.
- Workflow 16A and 16B still need contract execution and pilot proof.
- No new research cron or canonical note helper should be scheduled until those downstream contracts are approved.

## Next Action
- Promote Workflow 16 to the active lane and run the readiness gate that converts Workflow 17 / Workflow 18 outputs into the research automation skeleton.

## Key Files
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Skills Governance Index.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
- `06. Playbooks/Project Continuity/Workflow 18 - Spawn, Closeout, and Skills Governance Hardening - Chain Log.md`
