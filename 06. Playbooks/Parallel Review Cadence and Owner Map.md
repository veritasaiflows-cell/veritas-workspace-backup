# Parallel Review Cadence and Owner Map

## Purpose
Define the smallest honest cron-backed review cadence for Workflow 20 and make output ownership explicit so review jobs do not compete with finance writers.

## Core decision
The WF20 review layer owns **review surfaces and operator-action replies only**.
It does not own canonical finance notes, tracked-universe changes, thesis changes, deployment-state changes, or decision-grade publication.

## Window design

### 1. Daily post-refresh review window
Use one review window after the relevant finance refresh chain has completed and written its proof surfaces.

Allowed anchors:
- morning -> `tmp/run-summary-morning.json`
- post-close -> `tmp/run-summary-post-close.json`

Required read order:
1. `06. Playbooks/Automation Orchestration Protocol.md`
2. `06. Playbooks/Cron Job Protocol.md`
3. `06. Playbooks/Parallel Review Operator Action Taxonomy and Status Contract.md`
4. the current run summary for the window
5. supporting proof artifacts named by that run summary

Output:
- one review/status reply that follows the WF20 status contract
- optional intake packet or distinct-output review artifact when a bounded helper lane is explicitly allowed

### 2. Event-driven manual review path
Use this only when a catalyst, contradiction, failed run, or timing-sensitive change needs review before the next scheduled daily review window.

Trigger examples:
- failed or blocked finance chain
- warning/partial run that names operator action
- major catalyst packet that could affect active names or weekly posture
- contradiction between machine artifacts and live control notes

Output:
- manual main-session review or one bounded spawned contradiction/packet-prep pass
- no autonomous schedule widening

### 3. Sunday weekly roll-up review window
Use one weekly roll-up after the Sunday refresh chain has completed and written its proof surfaces.

Primary purpose:
- weekly operator summary
- unresolved truth handoff
- next-week review queue shaping

## Owner map

| Surface / output family | Owner window | Notes |
|---|---|---|
| Morning machine artifacts | Morning finance refresh chain | existing writer layer only |
| Post-close machine artifacts | Post-close finance refresh chain | existing writer layer only |
| Sunday weekly artifacts | Sunday finance refresh chain | existing writer layer only |
| Review/status reply | WF20 review layer | read-only synthesis of proof surfaces |
| Intake packet / contradiction packet | WF20 review helper lane when explicitly allowed | review object only; not canonical truth |
| Canonical finance notes | Randall + main-session approval flow | manual-only in v1 |
| Queue / registry movement | Veritas main session | cannot be owned by background helper lanes |

## Dependency chain
1. finance writer window completes
2. run summary exists and is readable
3. supporting proof artifacts exist
4. review layer classifies evidence state
5. review layer maps only real operator actions to taxonomy states
6. if the run ends partial/warning/manual, downgrade explicitly
7. if evidence and judgment cannot be separated, stop at `pending review` or `blocked`

## Downgrade rules

### Blocked
Use `blocked` when:
- run summary is missing
- `stop_line` is true
- required supporting artifact is missing
- upstream evidence is stale/partial in a way that matters
- the next action would widen automation beyond the approved boundary

### Pending review
Use `pending review` when:
- evidence exists but judgment is still required
- a helper lane prepared a packet but no approval decision exists yet
- a warning/partial state is informative but not action-clearing

### Required
Use `required` only when:
- a real operator action exists now
- the owner of that action is explicit
- the action is stated without implying it was already approved or applied

### Not needed
Use `not needed` only when:
- no live operator action exists for that taxonomy item in the current window

## Overlap rule
- the review layer must not run as a competing writer against the same artifact family while a finance refresh chain still owns that window
- one review window per source window is the default
- event-driven manual review is an exception path, not a second overlapping daily writer

## Stop line
If the review layer cannot point to a finished writer window plus named proof artifacts, it must stop instead of fabricating a review-ready state.

## Relationship to Workflow 20
This note is the Phase 2 owner-map and cadence output for:
- `06. Playbooks/Project Continuity/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow.md`

It complements, and does not replace:
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Parallel Review Operator Action Taxonomy and Status Contract.md`
