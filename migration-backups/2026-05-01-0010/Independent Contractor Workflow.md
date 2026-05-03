# Independent Contractor Workflow

## Purpose

Define how external or parallel AI contractors such as Claude and Gemini should be used inside the Veritas OS.

This workflow exists to prevent three failure modes:
- repeated handoff reconstruction in chat
- cosmetic implementation that ignores upstream contracts
- multiple contractors creating drift across notes, scripts, trust layers, and surfaces

## When to use ICs

Use an IC when one or more are true:
- the work is implementation-heavy across several files
- the work benefits from an independent pass with a different reasoning style
- the project is phaseable and can be advanced without constant back-and-forth
- the task is narrow enough to bound but large enough to justify detached execution
- Veritas needs a second pair of eyes on contract, trust, or orchestration issues

Do not use an IC just to create more motion.
If the work is small and local, Veritas should usually do it directly.

## What ICs are good for

Strong IC fits:
- script refactors
- dashboard/workbook plumbing
- validator creation
- contract normalization
- universe/lane-model migrations
- repeatable code cleanup with explicit acceptance criteria
- broad but phase-bounded note or playbook cleanup

Weak IC fits:
- vague strategic direction without a defined problem
- high-consequence canonical note rewrites without a review path
- tasks that still lack ownership semantics
- work where the real blocker is operator judgment, not implementation labor

## Shared contractor standards

All ICs must follow these standards:
- fix contracts before surfaces
- declare one owner per artifact or surface
- do not create fake green states
- prefer normalized models over boolean sprawl
- do not silently rewrite canonical notes
- separate machine truth from human prose when needed
- keep degraded trust visible
- report by completed phase or bounded sub-pass

Reference files:
- `CLAUDE.md`
- `GEMINI.md`

## Handoff packet

Every meaningful IC kickoff should include these items.

When the project is multi-pass, keep a thin chain log next to the continuity note so a simple "continue next pass" instruction has an execution ledger behind it.

### Required reads
- `SOUL.md`
- `AGENTS.md`
- active project continuity note
- most relevant audit/review note
- contractor-specific file (`CLAUDE.md` or `GEMINI.md`)

### Required context
- project objective
- current phase or sub-pass
- non-negotiables
- operator decisions still open
- what changed most recently
- what not to touch yet
- chain-log path when one exists

### Required report format
Every IC update should include:
1. phase or sub-pass completed
2. files changed
3. whether ownership, trust, or semantics became clearer or blurrier
4. surface-visible behavior changes
5. blockers or operator decisions still needed
6. short summary

## Preferred execution pattern

### Sequential by phase
ICs should work:
- phase by phase
- or bounded sub-pass by bounded sub-pass within a phase

Good pattern:
- complete one phase or bounded sub-pass
- validate it
- report once cleanly
- wait for acknowledgment before crossing into a riskier or conceptually different phase

Bad pattern:
- half-finish multiple phases
- mix architecture, note mutation, and surface work together
- report a blended pile at the end

## Phase 0 rule

For architecture-heavy projects, Phase 0 should usually be a contract-definition pass before broad code changes.

Preferred Phase 0 deliverable shape:
1. ticker-lane or entity-lane table
2. lane-definition / surface-entitlement table
3. source-owner-reader-cadence table

If those tables cannot be filled in cleanly, the model is not ready for broad implementation.

## Publication and trust rule

ICs must not treat rendered surfaces as proof of success.

Before calling work healthy, they should check:
- validation state
- run-summary or equivalent workflow trust state
- required output presence
- fallback/manual dependency status
- whether the publication path can still imply fake readiness

If those disagree, the disagreement itself is the work.

## Canonical note rule

ICs may help with note-related tooling, but canonical note mutation must remain controlled.

Approved posture:
- dry-run-first apply helpers
- explicit reviewable patch surfaces
- clear rollback path

Disallowed posture:
- silent auto-rewrites of important canonical notes
- broad note churn just to match machine surfaces cosmetically

## Future IC handoffs for coverage expansion

When using ICs to add more portfolio or macro coverage, do not start by adding names blindly.

Use this order:
1. decide why the coverage expansion is needed
2. decide which lane or research bucket each new name belongs to
3. decide whether it belongs in:
   - thesis universe
   - execution universe
   - macro sleeve
   - watch-only research universe
4. define required supporting notes, artifacts, and trust rules
5. only then expand scripts or surfaces

Coverage expansion without lane semantics is just future drift.

## Research unit question

Should Veritas start thinking about a research unit?

Yes, but only as a **thin operating concept** first.
Do not build a big org chart in notes.

The likely future shape is:
- **Veritas** = operating principal and final integrator
- **ICs like Claude/Gemini** = bounded implementation or independent review contractors
- **Research unit** = a future coordinated layer for expanding coverage, macro tracking, and thesis maintenance across more names or sleeves

A research unit becomes justified when one or more are true:
- the active tracked universe expands beyond what one main operating loop can maintain cleanly
- macro, portfolio, and thesis maintenance start competing for attention
- repeated deep-dive / coverage-initiation work becomes common
- there is a clear need for separate lanes such as:
  - coverage initiation
  - thesis maintenance
  - post-earnings interpretation
  - macro regime maintenance
  - portfolio-positioning review

Do not formalize a research unit too early.
First prove the workflow pressure exists.

## Recommended next step on research unit

Do not create a new research unit project tonight.
Instead, use future IC handoffs to observe:
- what work repeats
- what coverage expansions are genuinely needed
- which workstreams deserve dedicated ownership

When those patterns become obvious, create a thin playbook or project note for a research unit.

Reference concept note:
- `06. Playbooks/Research Unit Concept.md`

## Gemini prompt rule after workflow work finishes

When handing off to Gemini after workflow setup, the prompt should include:
- required reads
- current project note
- exact phase/sub-pass
- operator gates still open
- explicit statement of what constitutes success for the next pass
- chain-log path when available

Do not rely on chat memory alone.

## Minimal kickoff template

```text
You are acting as an independent contractor inside the Veritas workspace.

Read first:
- SOUL.md
- AGENTS.md
- contractor file relevant to you
- active project continuity note
- most relevant audit/review note

Current phase/sub-pass:
<fill in>

Objective:
<fill in>

Non-negotiables:
- fix contracts before surfaces
- one owner per artifact
- no fake green states
- no silent canonical note rewrites
- keep degraded trust visible

Open operator decisions:
<fill in>

Deliverable for this pass:
<fill in>

Report only when the pass is complete.
Use this format:
- phase/sub-pass completed
- files changed
- whether ownership/trust/semantics became clearer or blurrier
- surface-visible behavior change
- blockers or operator decisions still needed
- short summary
```
