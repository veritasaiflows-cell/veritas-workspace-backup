---
name: memory-continuity-manager
description: Manage daily notes, durable memory, and continuity promotion. Use when logging meaningful work, deciding what belongs in daily memory versus durable memory, pruning memory bloat, handling remember-this requests, or performing heartbeat continuity maintenance.
---

# Memory Continuity Manager

## Purpose

Keep continuity strong without turning memory into clutter.

## When to Use

Use this skill when:
- meaningful work needs to be logged in today's note
- Randall says to remember something
- recent daily notes need promotion review
- `MEMORY.md` is growing procedural bloat
- heartbeat maintenance should update memory or operating files
- you need to decide whether something belongs in a daily note, `MEMORY.md`, or an operating file

## Inputs to Check First

Read only what matters:
- today's daily note in `memory/YYYY-MM-DD.md`
- yesterday's daily note when continuity matters
- `MEMORY.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md` when responding to a heartbeat
- any core file that might need the promoted lesson

## Procedure

1. Capture only material factual deltas in the daily note.
2. Before appending, check whether today's note already contains the same topic or opening phrase; merge or update instead of duplicating.
3. If automation or session-memory writes already touched the note and exact duplicate bullets exist, run `python scripts/daily_note_dedupe.py memory/YYYY-MM-DD.md --apply` as the smallest cleanup guard.
4. Classify each candidate lesson:
   - daily context
   - durable memory
   - operating rule
   - environment rule
   - domain rule
   - automation candidate
5. Promote only what should survive many sessions.
6. Keep `MEMORY.md` curated.
7. If a lesson changes behavior, update the operating file or skill instead of only logging it.
8. Remove duplication when promoting.

## Daily Note Discipline

- Daily notes are delta logs, not pass-by-pass transcripts.
- One short bullet is enough for one material state change.
- If queue, registry, continuity notes, or audits already own the detail, write only the short outcome or skip the daily note entirely.
- Do not log repeated "still active", "reran", or "no change" updates.
- Keep bullets topic-led so duplicates are easy to spot and collapse.
- When several small actions belong to one workflow, prefer one summary bullet plus a pointer to the owning continuity note.
- Treat exact duplicate bullets as a hygiene failure to remove, not as acceptable history.

## Routing Rules

- today-only facts -> `memory/YYYY-MM-DD.md`
- durable user preference -> `USER.md` or `MEMORY.md`
- durable operator or mission rule -> `MEMORY.md`
- behavior rule -> `AGENTS.md`
- tool or environment rule -> `TOOLS.md`
- repeatable workflow -> a skill
- uncertain item -> leave in the daily note or send to `migration-review.md`

## Safety Rules

- No mental notes for important facts.
- Do not promote weak or temporary conclusions.
- Do not build a second memory system.
- Avoid copying the same rule into multiple files.

## Files This Skill May Read

- `memory/*.md`
- `MEMORY.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md`
- core files when routing a lesson

## Files This Skill May Edit

- `memory/*.md`
- `MEMORY.md`
- `USER.md`
- `TOOLS.md`
- `AGENTS.md`
- `Continuity Protocol.md`
- a relevant skill when the lesson is procedural

## Output Format

Use this structure when reporting memory work:
- what happened
- what was logged
- what was promoted
- what stayed daily-only
- any open review items

## Memory Update Rules

This skill owns the routing decision.
Always prefer a small accurate note over a bloated durable file or bloated daily log.
