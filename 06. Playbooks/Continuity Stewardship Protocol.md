# Continuity Stewardship Protocol

## Purpose

Define the safe automation boundary for project-queue, registry, continuity-note, and orchestration-control maintenance.

This protocol is for scheduled stewardship.
It is not permission for broad autonomous rewriting.

## Stewardship objective

The stewardship layer should:
- keep the active workflow queue honest
- keep the project registry aligned to the real active work
- keep continuity notes fresh enough to resume work quickly
- archive clearly finished control-plane residue when the replacement path is already explicit
- trim bounded control-plane noise so the operator surface stays legible

## In scope

Automation may maintain only these control-plane surfaces by default:
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Automation Architecture Spec.md`
- `06. Playbooks/Project Continuity/*.md`
- `memory/YYYY-MM-DD.md`

## Out of scope by default

Do not silently modify:
- canonical finance judgment notes
- portfolio/risk/intelligence notes used for live investment judgment
- auth or model credentials
- network exposure settings
- gateway security posture
- broad workspace folder structure outside the continuity/control-plane lane

## Daily steward responsibilities

On a normal daily steward run:
1. read the queue, registry, active workflow continuity note, and today's daily note
2. determine the real current workflow, the real next approved workflow, and the real current category / parallel posture if delegation is relevant
3. confirm the queue, registry, and continuity note agree
4. if they disagree, make the smallest bounded correction
5. refresh stale or missing category / parallel-posture labels when that gap would misroute work
6. confirm whether the current workflow is truly complete before advancing the queue
7. if the next workflow is major, require a preflight review/QA pass before implementation
8. route the work by effort level and spawn posture only when the protocol allows it
9. append one short daily-note delta only if something materially changed and the same change is not already logged

## Synchronization truth rule

The daily steward must treat these as the control-plane synchronization set:
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- the continuity note for the active workflow or active project
- today's daily note when a material state change occurred

If one surface disagrees with the other two, fix the outlier rather than rewriting everything.

## Daily-note delta rule

When the steward touches `memory/YYYY-MM-DD.md`:
- write only material state changes
- use one short delta bullet, not a replay of queue, registry, or continuity-note detail
- if today's note already has the same workflow or topic, update or collapse that bullet instead of appending
- if an automated append path touched the note, run `python scripts/daily_note_dedupe.py memory/YYYY-MM-DD.md --apply` before finalizing so exact duplicate bullets cannot survive as accepted output
- routine proof runs, no-change checks, and repeated status echoes stay out of the daily note
- if the real detail belongs in the continuity note or run ledger, keep it there and leave the daily note thin

## Queue freshness rule

Keep the active and near-term queue fresh enough to delegate safely.

At minimum, the active item and next meaningful queued items should make clear:
- status
- owner
- next pass
- blocker if any
- category
- parallel posture when delegation is plausible

If those labels are stale enough to confuse routing, repair them before opening more helper lanes.

## Completion confirmation rule

Do not advance the queue just because a note sounds finished.

Treat a workflow or project as complete only when:
1. the continuity note says the implementation work is complete
2. the queue status does not still list a real outstanding deliverable
3. the acceptance target or verification gate was actually met, or a real blocker is recorded instead
4. no active registry row still depends on that note as the current phase unless the next phase is explicitly named

If completion is ambiguous, stop at review/QA and do not advance automatically.

## Auto-promotion rule

When final QC confirms the active workflow or project is honestly complete and the next approved item is already defined:
1. close the finished item in the queue and registry
2. activate the next approved item immediately
3. update its continuity note with the real starting state and next action
4. keep the chain moving unless a blocker, approval gate, or higher-priority trust issue says to stop

Do not leave the next project only implied in chat.

If the larger chain goal is still open, treat completion as a handoff point, not a stopping point.

## Major-work trigger

Treat the next item as major when it touches any of:
- trust semantics
- chain behavior
- automation policy
- multi-file control-plane logic
- archival decisions affecting multiple continuity files
- multi-file workspace implementation or contract hardening beyond a tiny bounded correction

When major:
- do review/QA/preflight first
- do not jump straight into implementation
- only spawn a detached worker after the preflight says the contract is clear enough

## Effort routing and spawn hardening

Route work like this:

### Low effort
Examples:
- queue status correction
- registry alignment
- continuity note freshness repair
- small bounded control-plane wording cleanup

Posture:
- do directly in the main day-job turn
- do not spawn a subagent

### Medium effort
Examples:
- read-heavy inspection across several files
- mechanical comparison or backlog classification
- bounded patch-prep where the contract is already clear

Posture:
- spawn only when it keeps the main session cleaner than doing it directly
- preferred model: `openai-codex/gpt-5.3-codex`
- use one bounded detached run, not an open-ended swarm

### High effort
Examples:
- multi-file implementation
- trust-sensitive protocol work
- chain or automation-policy changes
- major hardening passes with several dependent artifacts

Posture:
- require preflight review first
- if the work is cleared to proceed without fresh human input, spawn one bounded detached worker
- preferred model: `openai-codex/gpt-5.4`
- if a second-opinion judgment lane is needed rather than implementation labor, stop and record that need instead of faking unattended progress

## Secure subagent spawn rule

When the day-job steward spawns a detached OpenClaw worker, use this secure default posture:
- one active detached worker at a time for this control-plane lane
- `runtime="subagent"`
- `mode="run"`
- `cleanup="delete"`
- `streamTo="parent"` only when the runtime actually supports it
- explicit model chosen from the effort-routing rule above
- explicit bounded task contract
- explicit file-grounded handoff packet: active workflow, current truth, last meaningful progress, blocker/trust gap, next acceptance target, exact files, and out-of-bounds surfaces
- workspace inherited from the parent session
- no canonical finance note mutation unless separately approved
- if persistent thread-bound subagent sessions are unavailable in the current surface, rely on continuity notes plus resume keywords instead of pretending a live resumable worker exists

Do not use detached spawn when:
- the real blocker is human judgment
- the workflow would need auth, network, or destructive changes
- the contract is still ambiguous
- another active worker already owns the same artifact family

## Hardening insertion rule

If the next queue item is not truthfully ready for automation, do not force progress theater.

Instead:
1. record why it is not automation-ready
2. update the active continuity note or queue entry with the real hardening requirement
3. if the hardening work is bounded and safe, spawn one worker under the secure spawn rule
4. if the hardening work needs human input, stop there and update notes instead of guessing

## Archive policy

Archive only when all of the following are true:
1. the note is a control-plane continuity note, not a canonical finance note
2. the note is clearly completed, superseded, or no longer the active continuity target
3. the registry does not point to it as the active continuity note
4. a successor workflow/project note already exists, or the work is explicitly closed
5. moving it will not break an active chain log or active project master note

## Never auto-archive

Never auto-archive these without explicit approval:
- active project master notes
- active chain logs
- canonical finance notes
- anything outside the continuity/control-plane lane

## Preferred archive destinations

- completed continuity notes: `09. Archive\06. Project Continuity - Archived\`
- completed control-plane protocol snapshots if ever needed: `09. Archive\05. Plans - Archived\`

## Noise-cleanup rule

Allowed cleanup:
- stale status lines in control-plane notes
- duplicated next-action text in continuity notes
- obviously outdated queue labels after a workflow completes
- inconsistent live schedule wording in automation-control notes

Not allowed as autonomous cleanup:
- semantic rewriting of investment theses
- deleting historical rationale because it looks long
- collapsing ambiguity where the workspace still needs judgment

## Daily freshness minimum

A note is fresh enough when it clearly states:
- objective
- current state
- last meaningful progress
- blocker or trust gap if any
- next action

If one of those is missing in the active workflow note, the steward may repair it.

## Reporting standard

The steward should end with a compact result:
- active workflow
- current project status
- next queued item
- next action
- whether QA/preflight was required
- whether any note was updated or archived
- any blocker

## Control rule

Prefer one good daily steward plus one deeper weekly hygiene pass.
Do not create many overlapping continuity crons unless a specific real gap proves the need.
