# Independent Contractor Workflow

## Purpose

Use bounded helper lanes for substantial, separable work while Main retains strategy, write coordination, truth integration, acceptance, and user-facing judgment.

## Open a helper lane when

- the subtask is concrete and independently verifiable
- parallel work materially reduces elapsed time
- exact read/write scope and stop lines are known
- another writer does not hold the same files
- the expected proof is clear

Keep tiny lookups and tightly coupled edits in Main.

## Handoff contract

Every lane states:

- objective and why it matters
- exact read-first owners
- exact files it may inspect or change
- files and actions it must not touch
- expected output and validators
- stop lines and escalation conditions
- lane/lease identity when writes are allowed

Helper output is untrusted until Main verifies it.

## Finance helper scope

Finance lanes may gather evidence, repair provenance or freshness, inspect thesis/catalyst/risk context, validate alert bands, and draft non-executing recommendations. They may not maintain portfolio or simulated-account state, change alert canon without its exact gate, create order packages, access brokerage/account routes, infer approval, or perform paper/live execution.

Use market theme, industry, risk horizon, and recommendation label to describe research context. Do not create system-owned finance action-state categories.

## Write coordination

Before a material edit, acquire the exact lane lease and name the files. Do not permit overlapping writers. Preserve user-owned changes and integrate only the verified diff.

## Closeout

The helper reports outcome, changed files, proof, limitations, rollback, and recommended next safe action. Main inspects the diff and proof, integrates continuity when needed, and closes or advances the lane.
