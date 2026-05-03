# Workflow 4 - Sequential Chain Protocol

## Objective
- Turn the completed Workflow 1-3C trust-spine passes into a compact repeatable protocol for future chains.
- Define how Veritas, helper lanes, and the orchestration cron decide the next workflow without reconstructing context from chat.

## Current State
- Workflows 1-3C are complete.
- Workflow 4 is now the active control-plane workflow.
- The automation layer is being tightened so scheduled orchestration can read the queue, registry, continuity notes, and doctrine from one coherent control plane.

## Resume Keyword
- `continuity-queue`
- In this webchat environment, a thread-bound persistent subagent session is not currently available, so this keyword should launch a fresh bounded subagent run against this continuity note and the queue/control-plane files rather than assuming a resumable live worker.

## Last Meaningful Progress
- Queue status drift was corrected so the completed 1-3C passes no longer look merely queued.
- The automation architecture now reflects the live weekday morning/post-close schedules, a live Sunday rebuild schedule, and a new daily orchestration steward review window.
- The daily orchestration-control cron is now being hardened into a true day-job lane with synchronization checks, completion confirmation, effort routing, and secure detached-worker spawn rules.
- The first live day-job run confirmed a small synchronization drift: the queue still described Workflow 4 as merely queued while the registry and continuity note already treated it as active; that outlier was corrected.
- Added `06. Playbooks/Cron Job Protocol.md` as a concise cron-governance reference with job-card structure, spawn rules, current risks, and refinement actions.

## Sequential chain protocol draft

### Required reads
Before advancing the queue:
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- active workflow or project continuity note
- `06. Playbooks/Continuity Stewardship Protocol.md`
- today's daily note if any material state change was already logged

### Completion gate
Advance only when:
- the current workflow is actually complete
- the verification or acceptance check was met, or a real blocker is explicitly recorded
- the registry and continuity note no longer disagree about the active phase

### Reviewer-first trigger
Require preflight review/QA before implementation when the next item touches:
- trust semantics
- chain behavior
- automation policy
- multi-file control-plane logic
- major detached implementation work

### Required handoff packet for spawned lanes
Before spawning a worker, pass a compact file-grounded packet with:
- active workflow or project
- current truth
- last meaningful progress
- blocker or trust gap
- next acceptance target
- exact files to read first
- what not to touch
- any live environment constraint that changes session behavior

If that packet is vague, the spawn contract is not ready.

### Effort routing
- low effort -> main session direct
- medium effort -> detached subagent only if it keeps the control plane cleaner; prefer `openai-codex/gpt-5.3-codex`
- high effort -> detached subagent only after preflight clears the contract; prefer `openai-codex/gpt-5.4`

### Secure detached-worker rule
- one active worker at a time for this lane unless a bounded read-only swarm is explicitly justified
- bounded contract only
- no silent canonical finance note mutation
- no auth/config/network/destructive changes without approval
- if human judgment is the blocker, stop and record the blocker instead of guessing
- if persistent thread-bound subagent sessions are unavailable in the current surface, use continuity-note + resume-keyword relaunches instead of assuming a live resumable worker

### Hardening insertion rule
If the next queue item is not truthfully ready for automation:
- record the hardening requirement
- update the queue or continuity note with the real blocker
- spawn one bounded worker only if the hardening task is implementation-safe and judgment-light
- otherwise stop at the updated notes

## Outstanding
- Validate the protocol in live daily use through the hardened day-job cron.
- Decide whether any additional control-plane note should be archived once the first few day-job runs prove stable.
- Keep Workflow 10 visible as a control-surface trust limit until runtime/session reliability is better proven.
- Use the next cron-proof project (`Workflow 4B`) to turn the live scheduler into a more auditable closed loop before treating the cron layer as boringly reliable.

## Preflight Result
- Workflow 4 remains a major control-plane item because it governs chain behavior, automation policy, and detached-worker spawning rules.
- Preflight review was required and has now been performed in the main session.
- Current conclusion: the workflow is in progress but not complete; the remaining work is empirical validation and bounded refinement, not fresh large-scale implementation.
- No detached worker was spawned from this run because the real need is live protocol proof, not additional blind labor.

## Blockers / Trust Gaps
- Memory indexing is still broken and should not be mistaken for continuity loss.
- Workflow 10 remains open for runtime/session lifecycle reliability, so session-state claims still need artifact-level verification.
- Queue and registry drift can mislead automation unless control-plane files stay synchronized.

## Next Action
- Validate the Workflow 4 protocol through additional real day-job runs and only make bounded refinements if evidence shows drift, ambiguity, or unsafe spawn behavior.

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/Automation Architecture Spec.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/IC Project Registry.md`
- `memory/2026-05-01.md`

## Acceptance Target
- The next major workflow can be launched from the protocol with minimal reconstruction.
- Major/trust-sensitive work routes through a preflight review or QA pass before implementation.
- The orchestration cron can keep control-plane notes aligned without touching canonical finance judgment notes.
