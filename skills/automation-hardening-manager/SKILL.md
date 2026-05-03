---
name: automation-hardening-manager
description: Harden the Veritas OS toward safer automation without forcing premature autonomy. Use when deciding what should run on schedule, what must remain human-gated, how to phase automation rollout, how to define trust gates and ownership boundaries, or when turning a partially manual workflow into a more automated operating path.
---

# Automation Hardening Manager

## Purpose

Move the OS toward better automation by improving architecture, contracts, review surfaces, and trust gates first.

This skill does not exist to maximize automation volume.
It exists to reduce unsafe ambiguity.

## Use This Skill For

Use this skill when:
- a workflow should become more automated over time
- cron windows need design or cleanup
- a manual workflow has become repetitive and should be hardened
- the OS needs a rollout path from manual -> semi-automated -> more autonomous
- an artifact or note layer needs clearer authority and ownership
- a proposed automation change may blur trust boundaries
- you need to decide whether a workflow should use cron, heartbeat, TaskFlow, or stay manual

Do not use this skill for simple one-off reminders.
Do not use it to justify removing review steps without evidence.

## What This Skill Owns

This skill owns the architecture judgment for automation hardening:
- workflow-window design
- authority boundaries
- artifact contracts
- review surfaces
- trust gates
- rollout phases
- validation expectations

It does not replace:
- `cron-automation-manager` for specific cron design
- `memory-continuity-manager` for memory routing
- `project-continuity-manager` for project pickup points
- `openclaw-operator` for general workspace/runtime hygiene
- `taskflow` for durable detached execution substrate

## Core Review Questions

For any workflow under consideration, answer these in order:

1. What is the real job?
2. What is the canonical truth layer?
3. What artifacts are generated versus authoritative?
4. What can run safely without human review?
5. What still requires approval?
6. What failures would be silent or dangerous?
7. What validation proves the automation is helping rather than drifting?

If those answers are vague, the workflow is not ready for more autonomy.

## Hardening Workflow

1. Define the workflow boundary.
2. Name the owner layer for each output.
3. Separate:
   - artifact generation
   - review surface generation
   - apply/update actions
   - canonical note or config mutation
4. Decide the current safe automation phase:
   - manual
   - scheduled artifact generation
   - scheduled review surfaces
   - gated apply helpers
   - higher-autonomy maintenance
5. Define trust gates before expanding autonomy.
6. Define the smallest useful schedule.
7. Validate outputs and downgrade confidence honestly when upstream inputs are stale, partial, or manual.
8. Record the result in the relevant project continuity note and daily memory.

## Safe Automation Preference Order

Prefer this progression:
1. stable script output
2. stable scheduled artifacts
3. stable review/checklist surfaces
4. gated patch/apply helpers
5. selective autonomous maintenance only where trust is repeatedly proven

Do not jump from manual directly to silent canonical rewrites.

## Mechanism Choice

Use this routing logic:

- **heartbeat** -> lightweight maintenance only
- **cron** -> exact recurring windows, reminders, scheduled artifact generation
- **TaskFlow** -> multi-step detached work that still needs one owner context and resumable state
- **manual** -> anything with weak trust, sparse validation, or high consequence

If a workflow mutates canonical notes or high-consequence config, default to manual or gated apply until proven otherwise.

## Trust Gates

Before widening autonomy, verify:
- upstream artifacts are fresh enough
- sources are not silently conflicting
- validation exists and is actually run
- the workflow has one clear owner per window
- note ownership is explicit
- failure states are visible
- the rollback or correction path is clear

If any of these are weak, keep the workflow in a harder-gated phase.

## Output Format

When using this skill, report in this order:
- workflow under review
- current phase
- recommended next phase
- safe automation boundary
- schedule recommendation
- trust gates still missing
- validation or evidence

## Memory Update Rules

- log meaningful automation architecture decisions in `memory/YYYY-MM-DD.md`
- keep per-project rollout state in the relevant `06. Playbooks/Project Continuity/` note when the work spans sessions
- promote durable automation policy only when it is clearly stable enough to survive many sessions
