# Workflow 4 - Sequential Chain Protocol

## Objective
- Turn the completed Workflow 1-3C trust-spine passes into a compact repeatable protocol for future chains.
- Define how Veritas, helper lanes, and the orchestration cron decide the next workflow without reconstructing context from chat.

## Current State
- Workflows 1-3C are complete.
- Workflow 4 completed on 2026-05-02.
- The automation layer now has a validated sequential-chain protocol that the day-job orchestrator can use to keep queue, registry, and continuity state aligned before opening the next workflow.

## Resume Keyword
- `continuity-queue`
- In this webchat environment, a thread-bound persistent subagent session is not currently available, so this keyword should launch a fresh bounded subagent run against this continuity note and the queue/control-plane files rather than assuming a resumable live worker.

## Last Meaningful Progress
- Queue status drift was corrected so the completed 1-3C passes no longer look merely queued.
- The automation architecture now reflects the live weekday morning/post-close schedules, a live Sunday rebuild schedule, and a new daily orchestration steward review window.
- The daily orchestration-control cron was hardened into a true day-job lane with synchronization checks, completion confirmation, effort routing, and secure detached-worker spawn rules.
- The first live day-job run confirmed a real synchronization drift: the queue still described Workflow 4 as merely queued while the registry and continuity note already treated it as active; that outlier was corrected.
- A bounded read-only QA/audit review then confirmed Workflow 4 was not honestly closable from one live run alone.
- The second live day-job pass found queue, registry, and continuity already synchronized, needed no further control-plane correction, and provided the clean repeat-pass evidence required to close Workflow 4 honestly.
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
- medium effort -> detached subagent only if it keeps the control plane cleaner; use an approved live default model with tighter scope rather than a removed cheap helper model
- high effort -> detached subagent only after preflight clears the contract; prefer `openai-codex/gpt-5.5` high-thinking posture when available
- fallback -> if `openai-codex/gpt-5.5` is unavailable, keep the same bounded contract and record the fallback explicitly

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

## Completion Evidence
- The protocol now exists in the governing control-plane files: `06. Playbooks/Continuity Stewardship Protocol.md`, `06. Playbooks/Cron Job Protocol.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md`, and `06. Playbooks/Automation Architecture Spec.md`.
- Workflow 4's acceptance target is met: the next major workflow can be launched from the protocol with minimal reconstruction.
- Reviewer-first / QA-before-implementation rules are now explicit across the control-plane docs for trust-sensitive or major work.
- Live day-job validation now includes both:
  - one corrective pass that caught and fixed a real queue/registry/continuity mismatch without falsely advancing the chain
  - one clean confirmatory pass that found the control-plane surfaces already aligned and allowed honest advancement to Workflow 4B

## Outstanding
- Keep Workflow 10 visible as a control-surface trust limit until runtime/session reliability is better proven.
- Use the next cron-proof project (`Workflow 4B`) to turn the live scheduler into a more auditable closed loop before treating the cron layer as boringly reliable.

## QA / Audit Result
- Workflow 4 was a major control-plane item because it governs chain behavior, automation policy, and detached-worker spawning rules.
- Preflight review was required and was performed.
- A bounded read-only QA/audit then challenged the first live proof and correctly refused premature closure.
- After the second live day-job validation pass, the honest conclusion is that Workflow 4 is complete.
- No detached worker was needed for Workflow 4 itself because the missing proof was validation evidence, not detached implementation labor.

## Blockers / Trust Gaps
- Memory indexing is still broken and should not be mistaken for continuity loss.
- Workflow 10 remains open for runtime/session lifecycle reliability, so session-state claims still need artifact-level verification.
- Queue and registry drift can mislead automation unless control-plane files stay synchronized.

## Next Action
- Open `Workflow 4B - Live Cron Shakedown + Run Ledger Hardening` as the active follow-on.
- Use Workflow 4B to prove the broader cron layer, add the compact run-ledger/operator surface, and make blocked/error follow-up behavior explicit.

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

## Completion Decision
- Workflow 4 is complete as of 2026-05-02.
- Queue advancement to Workflow 4B is justified.
