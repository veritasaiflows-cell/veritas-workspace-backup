# Parallel Review Operator Action Taxonomy and Status Contract

## Purpose

Define the human-gated action classes and the exact status language the review layer may use.

This note exists so review cron, helper lanes, and status replies do not blur evidence, recommendation, and operator-required judgment.

## Core rule

The review layer may surface:
- what changed
- what evidence exists
- what contradiction or catalyst needs review
- what Randall still needs to decide or do

The review layer may **not** imply that a machine-prepared packet equals an approved action.

## Allowed status states

Every action tracked by the WF20 review surface must resolve to one of these states only:
- **required** - Randall action is needed now
- **pending review** - evidence exists but judgment is still open
- **approved** - Randall explicitly approved the action, but downstream manual execution may still be needed
- **blocked** - action cannot proceed because a trust gate, dependency, or policy rule is not satisfied
- **not needed** - no action is currently required

Disallowed status language:
- done
- handled
- auto-cleared
- implied approved
- green without named evidence

## Action taxonomy

### 1) Entry-band review and approval
Owner: Randall approval
Machine role: surface stale bands, proposal deltas, and contradiction checks
Automation boundary: no auto-apply to canonical notes in v1

### 2) Required local script execution
Owner: Randall or main-session operator pass
Machine role: name the exact script/window still needed and why
Automation boundary: no fake claim that a window is fresh if the required run did not happen

### 3) Add machine-tracked name
Owner: Randall approval
Machine role: prepare intake packet, evidence summary, and affected surfaces
Automation boundary: no autonomous universe expansion

### 4) Promote event-watch to daily execution
Owner: Randall approval
Machine role: flag catalyst/frequency change need
Automation boundary: no autonomous cadence widening

### 5) Demote daily execution
Owner: Randall approval
Machine role: surface the reason cadence no longer fits
Automation boundary: no autonomous cadence reduction

### 6) Remove tracked name from universe
Owner: Randall approval
Machine role: surface rationale, dependencies, and impacted notes/artifacts
Automation boundary: no autonomous removals

### 7) Change deployment state
Owner: Randall judgment
Machine role: surface deployability evidence and contradictions
Automation boundary: no autonomous state changes

### 8) Change thesis rating or posture
Owner: Randall judgment
Machine role: surface the contradiction or changed evidence packet
Automation boundary: no autonomous thesis mutation

### 9) Change portfolio action language
Owner: Randall judgment
Machine role: flag wording drift between evidence and note layer
Automation boundary: no autonomous action-language rewrites

### 10) Apply canonical note patch
Owner: Randall approval plus visible patch review
Machine role: prepare patch candidates only when later workflows explicitly allow it
Automation boundary: disallowed by automation in v1

### 11) Publish presentation / workbook / PDF output as decision-grade
Owner: Randall approval
Machine role: identify candidate output and proof status
Automation boundary: no autonomous publication

## Status reply contract

Every WF20 review reply should use this structure:
1. **window** - which refresh/review window this refers to
2. **evidence state** - what is fresh, partial, stale, manual, or contradictory
3. **actions required** - only the operator actions that are actually live now
4. **blocked actions** - only if a trust gate or missing dependency prevents action
5. **not-needed actions** - optional compact list when useful for clarity
6. **stop line** - one sentence when the system must fail closed instead of acting

## Reply rules

- If no operator action is required, say that explicitly.
- If evidence is partial or manual, downgrade confidence explicitly.
- If a helper lane prepared a packet, name it as packet support rather than final truth.
- If an action is approval-dependent, say approval-dependent.
- If a required action touches the canonical note layer, state that canonical mutation remains manual-only in v1.

## Escalation / blocked rules

Use **blocked** when:
- upstream evidence is stale, partial, missing, or unconfirmed in a way that matters
- two sources disagree and the contradiction is unresolved
- the requested action would widen automation beyond the approved boundary
- the required script/run window has not happened yet
- the action would mutate canonical notes, tracked universe, posture, or publication state without explicit approval

## Stop line

If the review surface cannot separate evidence from judgment, it must stop at `pending review` or `blocked` rather than implying readiness.

## Relationship to Workflow 20

This note is the phase-1 contract for:
- `06. Playbooks/Project Continuity/Workflow 20 - Parallel Agents Automation and Human-Gated Review Workflow.md`

Later WF20 phases may add:
- one cron-backed review cadence
- one helper-lane authority matrix for contradiction and packet-prep roles
- one explicit future-gated helper path for visible patch preparation

But they must inherit this taxonomy and status language rather than replace it.
