# Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow

## Objective
- Build the next safe automation layer for parallel-agent support without letting helper lanes, cron, or status surfaces imply autonomous judgment they do not own.
- Create a cron-backed, human-gated review workflow that tells Randall exactly what operator actions are still required.
- Keep canonical finance note mutation, queue movement, thesis changes, deployment-state changes, and publication decisions fail-closed behind explicit review and approval.

## Current State
- **Closed with follow-up** on 2026-05-04.
- The review-layer doctrine is now explicit enough to support downstream cron-build hardening without widening autonomy.
- Live finance runtime proof was revalidated in the same workstream: `FRED_API_KEY` is restored into the live runtime path and both morning and post-close finance chains were rerun to clean completion.
- No dedicated parallel-agents review cron is live yet.
- Canonical finance note mutation remains manual-only and fail-closed.

## Last Meaningful Progress
- Hardened `06. Playbooks/Cron Job Protocol.md` so non-trivial cron jobs must carry explicit run packets, proof surfaces, response contracts, and spawn rules.
- Landed `06. Playbooks/Parallel Review Cadence and Owner Map.md` as the Phase 2 output.
- Landed `06. Playbooks/Parallel Review Helper-Lane Authority Matrix.md` as the Phase 3 output.
- Ran an independent audit, which first blocked closeout until the chain-log, executive-summary, checkpoint, and cross-surface sync layer were completed.

## Scope
- define the human-gated operator-action taxonomy
- define the review-surface contract and status reply contract
- define the smallest useful cron-backed review cadence
- decide which actions stay manual, which become gated patch/apply helpers later, and which remain blocked
- define helper-lane roles for review, contradiction, packet prep, and distinct-output work
- keep the workflow fail-closed until the status surface is honest and the action boundaries are explicit

## Sequential phase approach

### Phase 1 - Operator-action taxonomy and status contract
Status:
- **completed** via `06. Playbooks/Parallel Review Operator Action Taxonomy and Status Contract.md`

### Phase 2 - Review cadence and cron design
Status:
- **completed** via:
  - `06. Playbooks/Cron Job Protocol.md`
  - `06. Playbooks/Parallel Review Cadence and Owner Map.md`

### Phase 3 - Helper-lane authority and stop-line hardening
Status:
- **completed** via:
  - `06. Playbooks/Parallel Review Helper-Lane Authority Matrix.md`
  - `06. Playbooks/Research Automation Intake Packet Contract.md`

### Phase 4 - Independent audit and closeout
Status:
- **completed** via independent audit plus cross-surface closeout synchronization

## Out of Scope
- autonomous canonical finance note mutation
- autonomous queue movement by helper lanes or cron
- autonomous tracked-universe changes
- autonomous thesis/posture/deployment-state changes
- autonomous publication of decision-grade presentation, workbook, or PDF outputs
- broad freeform research swarms

## Preflight / Entry Checklist
- [x] Workflow 19 identified this as the next queued lane.
- [x] Cron posture was rechecked before widening automation.
- [x] Workflow 16 family fail-closed research-automation contract is already live.
- [x] Major-workflow, spawn/closeout, and closeout-artifact standards already exist.
- [x] One compact operator-action taxonomy note or section exists.
- [x] One status-surface contract exists.
- [x] One cron design exists that does not compete with current finance writers.
- [x] One explicit stop-line list exists for actions that must remain manual.

## Execution Posture
- main-session ownership for queue movement, final judgment, and closeout
- helper-lane support remains bounded to review, contradiction, packet prep, distinct-output drafting, and independent audit
- no canonical finance note mutation or final approval claims by background lanes

## Review Window
WF20 now defines the smallest honest design:
- one post-refresh daily review window
- one event-driven manual review path
- one Sunday weekly roll-up
- one-owner-per-surface rule so review jobs do not compete with finance writers

Owner-map details live in:
- `06. Playbooks/Parallel Review Cadence and Owner Map.md`

## Stop Lines
Stop instead of pretending success if:
- the status surface cannot distinguish evidence from action-required judgment
- a review cron would compete with finance writers or create overlapping note-mutation windows
- helper-lane output behaves like final truth instead of review support
- operator actions are implied instead of explicitly named
- the workflow widens into autonomous thesis, deployment, queue, or publication decisions

## Surface / Handoff Posture
- cron may produce **review surfaces and reminders only** in v1
- helper lanes may produce **review packets, contradiction checks, and distinct-output drafts only**
- status replies must surface **what Randall still needs to do** instead of claiming closure from machine artifacts alone
- canonical finance notes remain **manual-approval surfaces only**

## Canonical Mutation Posture
- **disallowed by automation in v1**
- any future patch/apply helper must remain human-gated and reviewable
- no silent note mutation, no autonomous posture changes, no autonomous publication

## Acceptance Gates
Workflow 20 closes only because all are now true:
1. one compact operator-action taxonomy is explicit and linked from the right control surfaces
2. one status reply contract exists that surfaces required operator actions honestly
3. one cron-backed review design exists that does not compete with current finance refresh writers
4. manual-only versus future gated-helper actions are clearly separated
5. helper-lane authority is explicit and remains subordinate to main-session judgment
6. stop lines and reopen triggers are explicit
7. an independent audit exists and is integrated into the closeout layer

## Exit / Closeout Checklist
- [x] action taxonomy landed
- [x] status surface contract landed
- [x] cron design landed
- [x] overlap with existing finance cron writers checked
- [x] helper-lane authority named
- [x] queue / registry / continuity alignment updated
- [x] independent audit completed
- [x] checkpoint decision made explicit

## Named Residue
- no dedicated WF20 review cron is live yet
- canonical finance note mutation remains manual-only and fail-closed in v1
- recurring source-bundle widening has not started and is intentionally deferred into WF24 then WF21

## Reopen Triggers
Reopen Workflow 20 if:
1. review language starts implying approval, completion, or autonomous judgment beyond the taxonomy contract
2. a review cron or helper lane begins competing with finance writers or mutating canonical surfaces
3. queue, registry, continuity, and audit surfaces drift out of agreement on WF20 state
4. review-window proof can no longer point to finished writer windows plus named artifacts
5. helper-lane authority widens without an explicit approved follow-on workflow

## Checkpoint Decision
- **Deferred with reason**, not skipped.
- Reason: WF24 is the immediate same-family downstream lane, so the better checkpoint is one batched governance checkpoint after the first WF24 pass instead of two near-adjacent control-plane checkpoints.

## Next Pass
- Promote `Workflow 24 - Cron Job Build Contract and Session Handoff Hardening` as the active downstream lane.
- Use the WF20 doctrine outputs to build the sibling retrofit checklist before Workflow 21 opens.

## Next 1-2 Adjacent Candidate Workflows
1. `Workflow 24 - Cron Job Build Contract and Session Handoff Hardening`
2. `Workflow 21 - Recurring Source Bundle and Review Window Pilot` only after WF24 lands the reusable builder/retrofit layer

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Parallel Review Operator Action Taxonomy and Status Contract.md`
- `06. Playbooks/Parallel Review Cadence and Owner Map.md`
- `06. Playbooks/Parallel Review Helper-Lane Authority Matrix.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Project Continuity/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow - Chain Log.md`
- `08. Audits/Workflow Executive Summaries/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow/Independent Audit.md`
- `08. Audits/Workflow Executive Summaries/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow/Executive Summary.md`

## Automation / Refresh Path
- keep existing finance refresh jobs as the only recurring finance writers
- add only a review/reminder/status layer in v1
- prefer one post-refresh review surface over many overlapping review jobs
- use the intake-packet prototype immediately as a manual review object before promoting any recurring research-source cron
- widen autonomy only after repeated proof that the status surface stays honest and the action taxonomy does not blur ownership
