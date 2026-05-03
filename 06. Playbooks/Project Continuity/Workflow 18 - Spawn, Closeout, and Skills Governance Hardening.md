# Workflow 18 - Spawn, Closeout, and Skills Governance Hardening

## Objective
- Harden the execution-governance layer that decides what should stay in the main session, what can be spawned for efficiency, what must remain blocked on human judgment, and what must be true before executive closeout.
- Turn the current good-but-scattered spawn and closeout rules into one explicit governance contract.
- Extend that contract into the skills most likely to shape spawn behavior, completion claims, and next-work routing.

## Why this workflow exists
- The workspace already knows that helper lanes cannot own final truth.
- It also already knows that major work should preflight first and that final QC must happen before queue advancement.
- What is still weak is the explicit decision matrix for:
  - spawn vs main-session exception
  - read-only vs distinct-output vs blocked/gated work
  - when executive summary is allowed
  - when a checkpoint / commit decision must be made
  - when the workflow owner must surface additional next-work ideas
- Without that hardening, the OS can still drift into inconsistent closeout behavior even with otherwise strong queue discipline.

## Current State
- `06. Playbooks/Automation Orchestration Protocol.md` already defines main-lane reserve, spawn-first advancement, completion handshake, and runtime-proof posture.
- `06. Playbooks/OpenClaw Parallel Work Plan.md` already defines lane ownership and safe/unsafe parallel splits.
- `06. Playbooks/Cron Job Protocol.md` already defines effort routing and secure spawn defaults.
- Workflow 16 now sets a sharper requirement for this pass: parallel agents should act as a contract-building and QA layer, not as a freeform research swarm.
- What is still missing is one explicit governance contract that merges those rules into operational yes/no decisions and carries them into the relevant skills.

## Scope
### In scope
- spawn decision matrix
- main-session exception rule hardening
- read-only vs distinct-output vs blocked/gated matrix
- contract-building / QA lane rule versus substantive research-judgment lane rule
- executive-closeout gate
- checkpoint / commit-decision gate
- required recommendation of 1 immediate next pass plus 1-2 bounded adjacent workflow candidates when a major workflow closes
- skill hardening for spawn / closeout / QA governance

### Out of scope
- provider-specific ACP harness implementation work
- broad research automation design details from Workflow 16
- finance-thesis or portfolio-note semantics

## Skills hardening surface
Prioritize these because they influence execution posture directly:
- `skills/ic-swarm-orchestrator/SKILL.md`
- `skills/automation-hardening-manager/SKILL.md`
- `skills/cron-automation-manager/SKILL.md`
- `skills/project-continuity-manager/SKILL.md`
- `skills/workspace-qa-pass/SKILL.md`
- `skills/openclaw-operator/SKILL.md`

## Proposed phases

### Phase 1 - Spawn and closeout decision audit
Goal:
- inventory the existing rules across playbooks and identify where decisions are still implied rather than explicit

Deliverables:
- spawn decision inventory
- closeout / executive-summary gate inventory
- checkpoint-rule inventory
- skill-gap table for execution-governance skills

Acceptance:
- each major decision type has a source rule or is named missing

### Phase 2 - Governance contract
Goal:
- define the explicit operational matrix for spawned work and workflow closeout

Deliverables:
- decision matrix for:
  - main-session only
  - spawn read-only
  - spawn distinct-output
  - blocked / operator-gated
- explicit rule that early automation parallel lanes are for contract-building, bounded packet prep, audit, contradiction, and QA unless a workflow contract explicitly widens authority
- executive summary gate
- closeout checklist
- checkpoint / commit-decision rule
- required next-work recommendation rule

Acceptance:
- for a new workflow, the spawn and closeout decision path can be determined without interpretive guesswork

### Phase 3 - Skills hardening
Goal:
- align the key governance-driving skills to the new matrix and closeout gate

Deliverables:
- skill updates that reinforce:
  - no final-truth ownership by helper lanes
  - explicit completion handshake
  - checkpoint decision before executive closure when the workflow is meaningful
  - recommendation of immediate next pass plus bounded adjacent ideas when useful

Acceptance:
- helper-lane and closeout behavior becomes more consistent across skills and workflows

### Phase 4 - Control-surface and doctrine integration
Goal:
- integrate the new governance contract into live control-plane references without widening into unrelated doctrine churn

Deliverables:
- protocol updates where needed
- queue / registry language updates if the contract changes what must be shown live
- bounded QA note
- handoff back to Workflow 16 readiness

Acceptance:
- Workflow 16 can start from a cleaner execution-governance layer instead of relying on implied habits

## Success Standard
- spawn choices become easier to justify and audit
- executive summaries become harder to issue before real closeout
- checkpoint behavior becomes explicit instead of half-assumed
- skills stop drifting on completion claims and next-work routing
- the research automation lane cannot quietly slide into freeform swarm behavior without an explicit contract change

## Blockers / Trust Gaps
- commit/checkpoint behavior is still partly doctrine-level and partly per-workflow
- the current system supports next-pass visibility but does not yet formally require 1-2 adjacent workflow ideas at closeout
- helper-lane safety is strong in spirit but still too distributed across documents

## Next Action
- Start after Workflow 17 defines the base workflow contract.
- Use Workflow 17 output as input rather than re-litigating the same entry/exit structure.

## Key Files
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- priority skills listed above
