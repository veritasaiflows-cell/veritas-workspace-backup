---
name: "memory-continuity-manager"
description: "Manage memory logging, durable promotion, dedupe, and daily-note hygiene."
---

# Proposed Update: memory-continuity-manager

## Summary

Strengthen daily-note hygiene and audit-to-memory routing without creating a parallel memory system.

## Proposed Description

`Manage memory logging, durable promotion, dedupe, and daily-note hygiene. Use when logging meaningful work, handling remember-this or pre-compaction flushes, preventing duplicate daily headings, pruning memory bloat, or deciding whether audit lessons belong in memory, skills, procedures, or validators.`

## Add Section: Pre-Compaction Flush Discipline

When Randall requests a pre-compaction memory flush:
- write only durable facts that should survive context loss
- use the canonical daily file `memory/YYYY-MM-DD.md`
- append only if the file already exists
- do not create timestamped variants such as `YYYY-MM-DD-HHMM.md`
- treat bootstrap/reference files like `MEMORY.md`, `DREAMS.md`, `SOUL.md`, `TOOLS.md`, and `AGENTS.md` as read-only unless Randall explicitly instructs otherwise
- if nothing durable needs storing, reply `NO_REPLY`

## Add Section: Duplicate Heading Guard

Before appending to a daily note, check for repeated top-level date headings and repeated topic headings.

Rules:
- one daily file should have at most one primary date heading
- append entries under an existing date/topic section when practical
- do not add a new H1 for every flush or session
- if duplicate H1s already exist, report the hygiene issue or run the approved dedupe tool when the task includes cleanup

Suggested checks:
- search `^# ` in `memory/YYYY-MM-DD.md`
- search for the proposed topic phrase before appending
- run `python scripts\daily_note_dedupe.py memory\YYYY-MM-DD.md --apply` only when cleanup is safe and in scope

## Add Section: Audit Lesson Routing

After a full workspace audit or targeted finding review, route lessons as follows:
- one-time status result -> daily memory or audit note only
- repeated agent behavior -> skill proposal/update
- repeated operator steps -> operating procedure
- deterministic recurring check -> validator/script
- durable owner preference -> `USER.md` or curated durable memory
- workflow-specific current state -> workflow continuity note

Do not put full audit findings into daily memory if the durable audit note already owns them. Daily memory should record the short outcome and pointer, not duplicate the report.

## Add Section: Memory As Evidence Boundary

Memory can route work, but it does not prove current state by itself.

When answering status, audit, finance, cron, PM, route, or runtime questions:
- use memory as a pointer to relevant surfaces
- verify live artifacts before claiming current truth
- mark memory-only claims as stale or historical unless refreshed

## Acceptance Proof

After applying this proposal:
- `openclaw skills check` passes.
- Future pre-compaction flushes avoid duplicate daily headings, timestamp variants, and accidental edits to bootstrap/reference files.
- Audit closeouts route durable lessons to skills/procedures/validators instead of bloating daily memory.
