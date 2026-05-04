# OpenClaw Parallel Pilot Queue

## Purpose

Define the live operator queue for deliberate parallel execution and workflow sequencing.

This note is the compact active control surface.
Detailed historical workflow entries now live in:
- `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md`

## Resource posture

### Main default
- `openai-codex/gpt-5.4`
- use for orchestration, integration, final judgment, and higher-trust workspace work

### Spawned worker default
- `openai-codex/gpt-5.4`
- use for bounded implementation, patch prep, and detached worker passes by default

### Lower-complexity helper posture
- No lower-complexity Veritas-routed Codex helper is currently on the approved live model list.
- For bounded cheap helper work, prefer scope reduction, lighter task contracts, or manual external evidence review instead of routing through removed or stale model posture.

Do not use reduced-trust helper posture for:
- final trust adjudication
- canonical-state judgment
- ambiguous architecture decisions
- final portfolio or OS calls

## Pilot success standard

The queue is succeeding only if:
- completion time drops
- main-session clutter drops
- reconciliation burden stays low
- artifact ownership stays clear
- the user gets more finished passes, not more chatter

## Queue structure

Each meaningful queued item should make clear:
- lane owner
- model posture or helper posture
- deliverable
- what not to touch
- acceptance check
- category
- parallel posture
- execution mode
- QC complete

## Current chain state

### Active workflow
**No active major workflow open**

Status:
- Workflow 19 is closed with follow-up
- Workflow 20 is the next approved lane, but it is not opened yet

Reason:
- Workflow 19 closeout is integrated and honest
- no new major lane is being opened automatically in the same turn

### Next approved queue item
**Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow**

Status:
- queued next
- held behind the deferred normal repo checkpoint from Workflow 19
- may open when the human-gated review workflow is intentionally started after that checkpoint is taken

Planned scope:
- cron-backed review-surface workflow only
- no autonomous canonical note mutation
- status replies must surface concrete operator actions still required
- helper lanes remain bounded to review, contradiction, packet prep, and distinct-output work until trust gates are proven

Required operator-action taxonomy for that lane:
- review and approval of entry bands
- run required local scripts until more of the chain is safely automated
- add a new machine-tracked name
- promote event-watch to daily execution
- demote daily execution
- remove a name from the tracked universe
- change deployment state
- change thesis rating or posture
- change portfolio action language
- apply a canonical note patch
- publish presentation / workbook / PDF output as decision-grade

### Recent completed item
**Workflow 16 family - Research Automation and Canonical Freshness Hardening**
- closed with follow-up
- no recurring research cron or auto-apply helper was opened
- canonical mutation remains fail-closed by automation in v1

## Compact execution order

1. Workflow 1 - policy target-range fail-closed hardening [completed]
2. Workflow 2 - residual atomic-write migration [completed]
3. Workflow 3 - external payload schema guards [completed]
4. Workflow 3B - independent workspace QA audit and QA-pass skill creation [completed]
5. Workflow 3C - canonical-note trust gate enforcement [completed]
6. Workflow 4 - sequential chain protocol [completed]
7. Workflow 4B - live cron shakedown + run ledger hardening [completed]
8. Workflow 4C - finance chain truth-sync hardening [completed]
9. Trust-grade reassessment / warning-residue gate [completed - closed with follow-up]
10. Workflow 5 - PDF/Excel workflow-fit pass [completed - closed with follow-up]
11. Workflow 6 - coverage tier framework [completed - closed with follow-up]
12. Workflow 7 - sector coverage expansion plan [completed - closed with follow-up]
13. Workflow 8 - command center chain readiness review [completed - historical no-go preserved; bounded reopen closed]
14. Workflow 9 - research department operating model [completed - closed with follow-up]
15. Workflow 9A - workspace structure and drift cleanup [completed]
16. Workflow 9B - surface alignment and drift-guard hardening [completed]
17. Workflow 10 - subagent/session lifecycle reliability review [completed]
18. Workflow 11 - coverage admission model [completed]
19. Workflow 12 - macro / policy trust repair [completed]
20. Workflow 13 - script and tmp hygiene hardening [completed]
21. Workflow 14 - operator script boundary and lifecycle cleanup [completed]
22. Workflow 15 - script performance and payload modularity backlog [deferred]
23. Workflow 17 - sequential workflow contract and skills hardening [completed]
24. Workflow 18 - spawn, closeout, and skills governance hardening [completed]
25. Workflow 16 - research automation and canonical freshness hardening [closed with follow-up]
26. Workflow 16A - research intake desk and parallel review packets [completed]
27. Workflow 16B - canonical freshness sync and gated note update helpers [completed]
28. Workflow 19 - playbooks retrieval and governance cleanup [closed with follow-up]
29. Workflow 20 - parallel agents automation and human-gated review workflow [queued]

## Capacity rule for this queue

At one time:
- 1 active OpenClaw subagent implementation lane
- 1 active Claude review lane
- 0 or 1 cheap helper lane

Do not open multiple cleanup or governance implementation lanes at once unless the merge cost is clearly lower than the speed gain.

## Queue hardening rule

- keep execution order explicit
- update this queue before opening a new major lane when real blockers or prerequisites change
- prefer a named workflow over chat-only residue
- do not widen scope mid-chain without updating the queue entry
- do not mark a workflow advanced unless execution mode and QC posture are visible here or in the registry

## History rule

Use `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md` for:
- detailed completed-workflow history
- long-form rationale from older completed items
- preserved historical proof context that no longer belongs in the active operator surface
