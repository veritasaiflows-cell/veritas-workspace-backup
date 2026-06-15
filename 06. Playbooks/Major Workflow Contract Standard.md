# Major Workflow Contract Standard

## Purpose

Provide one standard contract for major sequential or orchestrated workflows so entry, execution, QA, closeout, and handoff do not depend on scattered implied rules.

Use this standard when a workflow touches any of:
- automation policy
- trust semantics
- multi-file protocol or control-plane logic
- helper-lane governance
- canonical-surface mutation boundaries
- queue / registry / continuity state across several files

Do **not** require this full standard for every implementation task. Use `skills/disciplined-implementation/SKILL.md` to classify implementation size first:
- **Micro**: one-file/one-artifact fixes with one targeted proof command.
- **Narrow**: one owner plus one adjacent consumer/validator.
- **Major**: shared semantics, authority boundaries, workflow state, multi-file control-plane behavior, or cross-surface contracts.

This standard applies to **Major** implementation/workflow passes. Micro and Narrow passes should stay lean unless they reveal a shared contract change.

## Required sections in every major workflow continuity note

```md
## Objective
## Current State
## Last Meaningful Progress
## Scope
## Out of Scope
## Preflight / Entry Checklist
## Execution Posture
## Acceptance Gates
## Exit / Closeout Checklist
## Checkpoint Decision
## Next Pass
## Next 1-2 Adjacent Candidate Workflows
## Key Files
```

If the workflow is automation-facing, also include:

```md
## Owner Layer
## Review Window
## Stop Lines
## Surface / Handoff Posture
## Canonical Mutation Posture
```

## Preflight / Entry Checklist

Before meaningful implementation begins, confirm:
1. the active workflow is still the real active workflow
2. the owning continuity note is current enough to resume cleanly
3. the queue and registry agree on status, next pass, and execution posture
4. out-of-scope boundaries are explicit
5. acceptance gates are named
6. the checkpoint decision is named if the workflow is meaningful enough to justify one
7. if helper lanes may be used, their allowed role is explicit

If any of these are missing, fix the contract before labor starts.

## Execution Posture

Each workflow must name one of:
- `main-session exception`
- `serial main-session`
- `spawn read-only`
- `spawn distinct-output`
- `blocked / operator-gated`

If posture is unclear, default to `serial main-session` until clarified.

## Acceptance Gates

A major workflow is not complete because the note sounds finished.

Acceptance should name the smallest meaningful proof available, such as:
- direct inspection
- validator output
- `openclaw skills check`
- `openclaw config validate`
- targeted script run
- diff / artifact inspection
- bounded QA audit

If no meaningful proof can run, say why.

If a workflow changes shared schema, state vocabulary, JSON shape, truth-owner semantics, or execution order, acceptance must include:
- regenerating the dependent contract-bearing artifacts, summaries, or sidecars that embody that change
- rerunning the smallest downstream acceptance gate that consumes the changed contract

Do not treat code-only landing as sufficient closure when downstream proof still reflects the old contract.

For meaningful workflow closeout, default expectation is:
- a **fresh independent audit pass** spawned in a new session
- the auditor is not the implementation lane that just did the work
- the audit returns: acceptance verdict, real gaps, residue, reopen triggers, and 1-2 bounded next-work recommendations

If an independent spawned audit is intentionally skipped, the workflow note must say why and why a lower bar is still honest.

## Exit / Closeout Checklist

Before closing a major workflow, confirm:
1. implementation scope is actually complete or an explicit blocker is recorded
2. acceptance evidence exists and is named
3. queue / registry / continuity note agree on closure state
4. helper-lane work is fully integrated or explicitly abandoned
5. real residual debt is named instead of hidden
6. the next pass is explicit
7. 1-2 bounded adjacent workflow candidates are named when useful
8. an independent spawned audit was completed or an explicit honest exception is recorded
9. if later live checks overturned an earlier blocker or diagnosis, the closeout marks the earlier claim stale or superseded and points to the new truth source
10. if the workflow changed a shared contract, regenerated downstream proof artifacts and the smallest consuming acceptance gate are included in the acceptance evidence

## Checkpoint Decision

Every meaningful workflow closeout must make an explicit checkpoint decision:
- `checkpoint taken`
- `checkpoint deferred`
- `checkpoint not needed`

If deferred, say why and what event should trigger it.

## Commit checkpoint obligation

When a major workflow changes:
- protocol
- skills
- automation governance
- control-plane architecture
- or a meaningful multi-file execution contract

the workflow should not open the next major lane on an unstable uncommitted baseline.

Before the chain advances, one of these must be explicit:
- `commit checkpoint taken`
- `commit checkpoint deferred` with reason
- `commit checkpoint not needed` with reason

Default expectation for high-trust sequential chains: **commit checkpoint taken**.

## Next Pass

Each major workflow must end with one concrete next action.
Do not stop at vague “follow up later” language.

## Next 1-2 Adjacent Candidate Workflows

When a workflow closes or reaches a real handoff point, name up to two bounded adjacent candidates when useful.

This is for routing clarity, not backlog sprawl.
Do not invent filler candidates if the next pass is already singular and obvious.

## Owner Layer

Automation-facing workflows must name the authoritative layer for each output class:
- generated artifact
- review surface
- apply helper
- canonical note or control surface

If ownership is ambiguous, the workflow is not ready for autonomy expansion.

## Review Window

Automation-facing workflows must define the intended operating windows, such as:
- premarket
- post-close
- Sunday weekly
- event-driven manual only

Do not schedule a workflow whose real review window is not defined.

## Stop Lines

Every automation-facing workflow must name what causes it to stop instead of pretend success.
Examples:
- low-confidence / rumor-heavy evidence
- duplicate or conflicting signals
- unresolved owner-surface contradiction
- missing validation
- ambiguous canonical-mutation boundary

## Surface / Handoff Posture

Automation-facing workflows must say what may surface into:
- dashboard watch/review layer
- workbook staging
- weekly brief
- thesis-review queue
- patch proposal only

Do not let a workflow create a second truth layer by omission.

## Canonical Mutation Posture

Default posture:
- canonical mutation is **disallowed** unless the workflow contract explicitly permits a gated helper or manual approval path

If canonical mutation is allowed at all, the workflow must name:
- exact allowed mutation type
- approval requirement
- rollback path
- verifier or QA expectation

## Where the contract should live

- workflow-specific execution truth -> continuity note
- reusable procedure -> playbook or skill
- durable cross-workflow standard -> this document and linked protocol docs
- daily state change -> `memory/YYYY-MM-DD.md`

Related standards:
- `06. Playbooks/Skill Quality Standard.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`

## Status minimum for live control surfaces

Queue and registry should make these visible for the active item:
- status
- owner
- next pass
- blocker if any
- category
- parallel posture
- execution mode
- QC complete
