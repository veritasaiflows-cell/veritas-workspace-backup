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
- you need to decide whether a workflow should use cron, heartbeat, a spawned subagent / detached helper path, or stay manual

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
- a dedicated detached execution substrate when one is actually verified live

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

For major automation-facing workflows, also make these explicit:
- owner layer
- review window
- stop lines
- surface / handoff posture
- canonical mutation posture
- checkpoint decision
- next pass

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
- **detached helper lane** -> spawned subagent or other verified detached path when bounded work needs one owner context outside the main lane
- **manual** -> anything with weak trust, sparse validation, or high consequence

Do not assume `TaskFlow` is a live approved mechanism in this workspace unless it is explicitly validated in the current operator protocol. If that proof is absent, default to a spawned subagent or manual path instead.

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
- owner layer
- review window
- stop lines
- trust gates still missing
- validation or evidence

## Machine-readable trust block pilot

Workflow 29 Phase 4 bounded pilot:
- producer: `python scripts/automation_trust_block.py --input <trust-block-input.json> --write`
- default artifact: `tmp/automation-trust-block.json`

Required trust-block fields for this pilot:
- `workflow`
- `producer_skill`
- `reviewed_at_utc`
- `current_phase`
- `recommended_next_phase`
- `trust_level` (`unsafe` / `review_required` / `automation_ready`)
- `decision` (`approve` / `deny` / `defer`)
- `consumer_posture` (`read_only` / `review_only` / `blocked`)
- `safe_automation_boundary`
- `owner_layer`
- `review_window`
- `validation_evidence[]`
- `trust_gates_passed[]`
- `trust_gates_missing[]`
- `stop_lines[]`
- `notes[]`

Pilot approval rule:
- only `decision=approve` + `trust_level=automation_ready` + zero `trust_gates_missing` may produce `status=ok`
- pilot consumers may treat the block as permission for **read-only gating decisions only**
- this trust block does **not** authorize canonical note mutation, destructive apply steps, or broader scheduler autonomy

## Memory Update Rules

- log meaningful automation architecture decisions in `memory/YYYY-MM-DD.md`
- keep per-project rollout state in the relevant `06. Playbooks/Project Continuity/` note when the work spans sessions
- promote durable automation policy only when it is clearly stable enough to survive many sessions
