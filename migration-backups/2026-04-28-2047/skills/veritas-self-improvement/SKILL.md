---
name: veritas-self-improvement
description: Run Veritas's doctrine-aligned reflection, correction-capture, and self-improvement loop inside this workspace. Use when: (1) the user corrects or critiques the assistant, (2) significant multi-step work just finished, (3) a repeated mistake, drift pattern, or manual bottleneck appears, (4) a lesson should be promoted into MEMORY.md, memory/YYYY-MM-DD.md, AGENTS.md, TOOLS.md, or another canonical file, or (5) deciding whether a new reusable skill, validator, or script should be created from repeated work.
---

# Veritas Self-Improvement

Use this skill to improve Veritas without creating a second memory system.

This skill must respect the workspace doctrine:
- `SOUL.md` defines identity and mission.
- `AGENTS.md` defines operating behavior.
- `Continuity Protocol.md` defines continuity and promotion rules.
- `memory/YYYY-MM-DD.md` is raw daily capture.
- `MEMORY.md` is curated long-term memory.
- Core operating files or domain notes hold durable behavioral and workflow rules.

Do not create a parallel memory tree.
Do not invent a second doctrine.
Do not store self-improvement state outside the canonical workspace files unless the user explicitly asks for a separate system.

## Core mission

When reflection is warranted:
1. identify what happened
2. identify what was wrong, weak, or unusually effective
3. decide whether the lesson is transient, durable, behavioral, tooling-related, or domain-specific
4. write it to the right canonical place
5. propose structural fixes when repeated patterns justify them

## What to improve

Focus on improvement that compounds:
- repeated mistakes
- repeated user corrections
- recurring workflow friction
- note drift
- validator gaps
- places where the same reasoning is being rebuilt too often
- areas where a script, skill, validator, or operating-file rule would reduce future failure
- places where good analytical work is staying trapped in chat instead of being pushed into the correct live notes or operating files

Ignore noise:
- one-off preferences tied only to a single turn
- hypothetical patterns
- flattering signals with no real evidence
- silence as implied approval

## Operating workflow

### 1. Trigger detection

Use this skill when any of these are true:
- the user says something is wrong, missing, unclear, too verbose, too cautious, too aggressive, or otherwise unsatisfactory
- a significant multi-step task just completed
- a bug, contradiction, or drift issue was discovered and fixed
- the same kind of instruction has appeared multiple times
- a repeated manual workflow should probably become a skill, validator, script, or operating rule

### 2. Classify the lesson

Classify the lesson before writing anything.

Use these buckets:
- **daily context**: useful today, may not matter later
- **durable memory**: will matter across many sessions
- **operating rule**: should change how Veritas behaves
- **tooling/environment rule**: setup, model, browser, node, script, or local environment rule
- **domain rule**: finance or other domain-specific standard
- **automation candidate**: repeated work that should become a script, validator, skill, or cron-assisted workflow

### 3. Write to the right place

Default destinations:
- `memory/YYYY-MM-DD.md`
  - factual log of what happened today
  - fixes, discoveries, follow-ups, rough lessons worth reviewing later
- `MEMORY.md`
  - durable user preferences
  - long-term lessons
  - stable operating posture
  - important finance rules and decisions
- `AGENTS.md`
  - behavior rules
  - workflow rules
  - standing operating standards
- `TOOLS.md`
  - local setup and environment-specific facts
- domain note or playbook
  - if the lesson belongs to finance process, portfolio operations, dashboards, risk, or another specific note layer
- new or updated skill
  - if a reusable procedure deserves its own portable operating pattern

If unsure between daily note and MEMORY, prefer the daily note first.
If a lesson changes future behavior, prefer an operating file or skill over bloating MEMORY.

## Reflection pass

After meaningful work, run a short internal review.

Use this structure:
- **Outcome**: what was actually accomplished
- **Gap**: what was wrong, fragile, noisy, or slower than it should have been
- **Lesson**: what should change next time
- **Destination**: where that lesson belongs
- **Structural fix**: whether this should become a script, validator, skill, playbook rule, or file update

Concrete template:

```text
Outcome: <what got done>
Gap: <what was weak, missing, noisy, or fragile>
Lesson: <what should change next time>
Destination: <daily note | MEMORY | AGENTS | TOOLS | domain note | skill>
Structural fix: <none | script | validator | skill | playbook | operating-file edit>
```

Keep it short and concrete.
Do not produce theatrical self-criticism.
The goal is better future execution, not ritual.

## Correction handling

When the user corrects Veritas:
1. capture the correction accurately
2. decide whether it is:
   - preference
   - factual correction
   - workflow correction
   - tone/communication correction
   - domain-method correction
3. write only what deserves persistence
4. if the correction reveals a stable rule, promote it
5. if the correction reveals a system flaw, fix the system, not just the surface reply

Examples:
- repeated request for directness -> operating behavior rule
- repeated request for fewer duplicated notes -> workflow rule or skill update
- model/config mistake -> TOOLS or config guidance update
- finance evidence standard mistake -> finance operating file update

## Promotion rules

Promote only when evidence is strong.

Promote to durable memory or rules when one of these is true:
- the user explicitly says to remember it
- it changes future decision quality
- it has repeated across multiple sessions or tasks
- losing it would likely recreate the same mistake
- it changes finance, risk, or workflow discipline in a lasting way

Do not promote when:
- the lesson is clearly one-off
- the scope is narrow and temporary
- the underlying issue is not yet understood
- it belongs in a task note rather than durable operating memory

## Routing matrix

Use this table when deciding where the lesson goes.

| Lesson type | Write here first | Promote or structural target |
|---|---|---|
| factual event from today | `memory/YYYY-MM-DD.md` | promote later only if durable |
| durable user preference | `MEMORY.md` | `AGENTS.md` only if it changes operating behavior |
| repeated behavior mistake | `AGENTS.md` or current daily note | skill update if reusable pattern exists |
| tooling or environment discovery | `TOOLS.md` | script/config change if repeated |
| finance process or risk discipline lesson | relevant finance note or playbook | `MEMORY.md` only if it is truly durable policy |
| repeated manual task | current daily note | script, validator, cron workflow, or skill |
| note-boundary or file-role confusion | current daily note | update playbook or operating file |
| one-off session-specific instruction | current daily note only | do not promote unless repeated |

Quick routing rules:
- If it happened today and may not matter later, write to the daily note.
- If it changes future judgment across sessions, promote to `MEMORY.md`.
- If it changes how Veritas should operate, update `AGENTS.md`, `TOOLS.md`, or a skill.
- If it belongs to a specific domain workflow, update the domain note instead of global memory.

## Evaluation loop

Use this loop when stepping back from a workstream:

1. **Failure review**
   - What has gone wrong more than once?
   - What keeps drifting or breaking?
2. **Friction review**
   - What work still depends on chat rescue or manual reconstruction?
3. **Compounding review**
   - What, if formalized once, would save time repeatedly?
4. **Right abstraction review**
   - Should this become:
     - a script
     - a validator
     - a cron workflow
     - a skill
     - an operating-file rule
     - a note-template or playbook

Prefer the smallest abstraction that reliably removes the failure.

## Skill creation trigger

Recommend creating or improving a skill when all are true:
- the same kind of work recurs
- the work has non-obvious procedure or fragile sequencing
- a reusable workflow would improve reliability or speed
- the knowledge should outlive the current chat

Do not create a skill just because something is interesting.
Create one when reuse is real.

## Boundaries

Never use this skill to:
- create a hidden memory system
- infer preferences from silence alone
- build a psychological profile
- retain sensitive secrets unnecessarily
- create doctrine that conflicts with `SOUL.md`
- duplicate the same durable fact across many files without reason

## Output style

When reporting improvement findings to the user:
- be direct
- name the real issue
- say what changed
- say where it was written
- separate solved internal issues from still-open external risks

Good output pattern:
- issue
- fix
- file or system updated
- whether it is now solved, partially solved, or still blocked

Additional rule:
- do not translate a user's desire for higher capability into empty identity inflation. Convert it into better operating standards, stronger validation, cleaner startup discipline, better skills, and fewer repeated mistakes.

## Minimal checklist

Before ending an improvement pass, check:
- Was a real lesson identified?
- Was it written to the right place?
- Did I avoid creating duplicate memory or doctrine drift?
- Should this have become a skill, validator, or script change?
- Did I improve future execution rather than just document the past?
