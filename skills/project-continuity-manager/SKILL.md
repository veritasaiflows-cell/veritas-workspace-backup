---
name: project-continuity-manager
description: Keep thin, high-signal continuity for active but unfinished projects. Use when a project has meaningful progress, changing priorities, blockers, or a likely resume-later handoff and needs a compact pickup point with current state, outstanding items, key files, and next action.
---

# Project Continuity Manager

## Purpose

Preserve pickup points for real projects without turning the workspace into a bloated PM system.

This skill complements `memory-continuity-manager`.
- `memory-continuity-manager` decides what belongs in daily memory versus durable memory.
- `project-continuity-manager` keeps a project resumable when work is partial, paused, or priority-shifted.

## Use When

Use this skill when:
- a project has moved meaningfully but is not finished
- priorities are shifting and a clean resume point matters
- several projects are active at once
- a project has blockers, dependencies, or trust gaps worth tracking
- Randall asks how to remember where to pick back up
- the current state is spread across too many notes or chat turns

Do not use this skill for trivial one-shot tasks.
Do not use it to duplicate canonical truth that already lives cleanly in an owning note.

## Thin Continuity Standard

Prefer a compact project checkpoint, not a project bureaucracy layer.

Each project checkpoint should answer only:
1. what this project is
2. current state
3. what changed recently
4. outstanding items
5. blockers or trust issues
6. next concrete action
7. key files or artifacts
8. automation or refresh path when workflow cadence matters

For major workflows, also keep explicit if they are live issues:
9. acceptance gate
10. checkpoint decision
11. next 1-2 adjacent workflow candidates when useful

If a checkpoint grows into a long memo, it is drifting.

## Canonical Homes

Use the smallest correct home:

- daily progress and session checkpoints -> `memory/YYYY-MM-DD.md`
- durable cross-project rules -> `MEMORY.md` or another operating file via `memory-continuity-manager`
- project-specific continuity note -> create or update only when the project spans sessions and needs a dedicated pickup point

Preferred dedicated project-note location:
- `06. Playbooks/Project Continuity/<Project Name>.md`

But if a project already has a natural owning note, keep continuity there instead of creating a duplicate project note.

## Project Checkpoint Template

Use this structure when a dedicated project continuity note is warranted:

```md
# <Project Name>

## Objective
- <one or two lines>

## Current State
- <current truth>

## Last Meaningful Progress
- <recent completed step>

## Outstanding
- <open item 1>
- <open item 2>

## Blockers / Trust Gaps
- <real blocker or data-quality issue>

## Next Action
- <single best next move>

## Key Files
- `<path>` - <why it matters>
- `<path>` - <why it matters>

## Automation / Refresh Path
- <only include when the project depends on scripts, chains, cron, or recurring refresh windows>
```

Keep bullets short.
Prefer one next action, not a vague backlog.
Only include the automation section when it materially improves resumability.
If the project is a major workflow, keep its contract compatible with `06. Playbooks/Major Workflow Contract Standard.md`.

## Workflow

1. Identify the real project boundary.
2. Decide whether daily memory alone is enough.
3. If not, create or update a dedicated project checkpoint.
4. Capture only the minimum needed to resume cleanly.
5. Link to canonical notes, scripts, skills, or artifacts instead of copying them.
6. If a lesson is truly durable, route it through `memory-continuity-manager`.

## Anti-Patterns

Avoid:
- duplicating full research notes into project checkpoints
- turning project notes into diaries
- copying large task lists from other notes
- inventing status language that obscures reality
- keeping multiple conflicting pickup points for the same project

## Output Format

When reporting project continuity work, use:
- project
- continuity action taken
- where the pickup point now lives
- next action
- any blockers
