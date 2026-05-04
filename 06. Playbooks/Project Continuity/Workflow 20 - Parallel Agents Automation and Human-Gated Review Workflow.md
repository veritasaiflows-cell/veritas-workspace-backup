# Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow

## Objective
- Build the next safe automation layer for parallel-agent support without letting helper lanes, cron, or status surfaces imply autonomous judgment they do not own.
- Create a cron-backed, human-gated review workflow that tells Randall exactly what operator actions are still required.
- Keep canonical finance note mutation, queue movement, thesis changes, deployment-state changes, and publication decisions fail-closed behind explicit review and approval.

## Current State
- **Queued / approved next** on 2026-05-03 behind Workflow 19.
- Existing finance refresh cron windows already exist and should remain the only recurring artifact-writing finance jobs until this workflow proves a safe review layer.
- No dedicated parallel-agents review cron exists yet.
- No unified operator-action status surface exists yet.

## Last Meaningful Progress
- Workflow 19 compacted the live queue and made this workflow the explicitly named next lane.
- Workflow 16 / 16A / 16B already proved the fail-closed research-automation contract that this workflow must inherit.
- Existing cron posture was rechecked during Workflow 19 planning: seven enabled jobs already exist, so this workflow must layer review windows on top of that posture instead of competing with it.

## Scope
- define the human-gated operator-action taxonomy
- define the review-surface contract and status reply contract
- define the smallest useful cron-backed review cadence
- decide which actions stay manual, which become gated patch/apply helpers later, and which remain blocked
- define helper-lane roles for review, contradiction, packet prep, and distinct-output work
- keep the workflow fail-closed until the status surface is honest and the action boundaries are explicit

## Out of Scope
- autonomous canonical finance note mutation
- autonomous queue movement by helper lanes or cron
- autonomous tracked-universe changes
- autonomous thesis/posture/deployment-state changes
- autonomous publication of decision-grade presentation, workbook, or PDF outputs
- broad freeform research swarms

## Preflight / Entry Checklist
- [x] Workflow 19 identified this as the next queued lane.
- [x] Existing cron posture was rechecked before widening automation.
- [x] Workflow 16 family fail-closed research-automation contract is already live.
- [x] Major-workflow, spawn/closeout, and closeout-artifact standards already exist.
- [ ] One compact operator-action taxonomy note or section exists.
- [ ] One status-surface contract exists.
- [ ] One cron design exists that does not compete with current finance writers.
- [ ] One explicit stop-line list exists for actions that must remain manual.

## Execution Posture
- **serial main-session** for action taxonomy, trust boundaries, cron design, and status contract
- helper-lane support allowed only for bounded read-only review, contradiction audit, and distinct-output draft prep after the contract is explicit

## Owner Layer
- action taxonomy / automation policy -> playbooks and workflow note layer
- cron design -> cron job definitions plus linked playbook references
- machine evidence / prep packets -> `tmp/` and bounded helper artifacts only
- canonical finance notes -> human-approved only
- final status / next required operator actions -> main-session control surface only

## Review Window
- daily control-plane review window after the finance refresh layer updates
- event-driven manual review when a catalyst or contradiction packet requires action
- Sunday weekly review window for action roll-up and priority reset
- no unsupervised canonical review window in v1

## Stop Lines
Stop the workflow instead of pretending success if:
- the status surface cannot distinguish evidence from action-required judgment
- a cron design would compete with existing finance writers or create overlapping note mutation windows
- helper-lane output starts behaving like final truth instead of review support
- operator actions are implied instead of explicitly named
- the workflow starts widening into autonomous thesis, deployment, or publication decisions

## Surface / Handoff Posture
- cron may produce **review surfaces and reminders only** in v1
- helper lanes may produce **review packets, contradiction checks, and distinct-output drafts only**
- status replies must surface **what Randall still needs to do** rather than claiming closure from machine artifacts alone
- canonical finance notes remain **manual-approval surfaces only**

## Canonical Mutation Posture
- **disallowed by automation in v1**
- any future patch/apply helper must remain human-gated and reviewable
- no silent note mutation, no autonomous posture changes, no autonomous publication

## Required operator-action taxonomy
The v1 status surface must explicitly track whether these actions are required, pending review, approved, blocked, or not needed:
1. review and approval of entry bands
2. running required local scripts until safe automation replaces them
3. adding a new machine-tracked name
4. promoting event-watch to daily execution
5. demoting daily execution
6. removing a name from the tracked universe
7. changing deployment state
8. changing thesis rating or posture
9. changing portfolio action language
10. applying any canonical note patch
11. publishing presentation / workbook / PDF output as decision-grade

## Acceptance Gates
Workflow 20 should not close unless all are true:
1. one compact operator-action taxonomy is explicit and linked from the right control surfaces
2. one status reply contract exists that surfaces required operator actions honestly
3. one cron-backed review design exists that does not compete with current finance refresh writers
4. manual-only versus future gated-helper actions are clearly separated
5. helper-lane authority is explicit and remains subordinate to main-session judgment
6. stop lines and reopen triggers are explicit
7. an independent audit confirms the status surface is not creating fake readiness or implied autonomy

## Exit / Closeout Checklist
- [ ] action taxonomy landed
- [ ] status surface contract landed
- [ ] cron design landed
- [ ] overlap with existing finance cron writers checked
- [ ] helper-lane authority named
- [ ] queue / registry / continuity alignment updated
- [ ] independent audit completed
- [ ] checkpoint decision made explicit

## Checkpoint Decision
- not yet opened

## Next Pass
- Open this workflow after Workflow 19 closes and start with the operator-action taxonomy plus status-surface contract.

## Next 1-2 Adjacent Candidate Workflows
1. A later gated patch/apply helper workflow only if Workflow 20 proves the status/review layer is honest
2. A later cron hardening workflow only if the review cadence shows repeated clean behavior without ownership drift

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
- `06. Playbooks/Cron Run Ledger.md`

## Automation / Refresh Path
- keep existing finance refresh jobs as the only recurring finance writers
- add only a review/reminder/status layer in v1
- prefer one post-refresh review surface over many overlapping review jobs
- widen autonomy only after repeated proof that the status surface stays honest and the action taxonomy does not blur ownership
