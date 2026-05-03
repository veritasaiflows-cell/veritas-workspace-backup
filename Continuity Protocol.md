# Continuity Protocol

## Purpose

Keep Veritas continuous across sessions without turning the workspace into noise.

## Memory layers

### Daily memory
File: `memory/YYYY-MM-DD.md`

Use for:
- what happened today
- setup changes
- discoveries and follow-ups
- rough context that may or may not deserve later promotion
- session-level market or portfolio context

Rule:
- capture only meaningful deltas
- one bullet per material change
- if the same topic already exists today, update or merge it instead of appending another bullet
- let queue, registry, continuity notes, and audits own pass-by-pass detail
- optimize for usefulness, not perfection

### Durable memory
File: `MEMORY.md`

Use for:
- durable facts
- Randall's durable preferences
- lasting operating decisions
- major finance rules, posture, or policy
- lessons that should change future behavior

Rule:
- promote only what will still matter later
- keep it curated

### Operating files
Files:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `USER.md`
- `IDENTITY.md`

Use for:
- identity
- behavior rules
- environment facts
- stable conventions

Rule:
- these files define how Veritas operates
- they are not daily logs or procedural dump zones

## Routing rules

Write to the daily note when:
- a materially new fact or decision appeared
- meaningful work happened
- a tool or config changed
- a bug or constraint was discovered
- Randall gave a short-term instruction
- a follow-up is worth tracking

Do not write to the daily note when:
- the same state is already captured there
- the detail already lives cleanly in a continuity note, queue, registry, ledger, or audit
- the update is only "still active", "reran", "no change", or another status replay
- the note would become a chain log instead of a daily delta log

Promote to `MEMORY.md` when:
- the fact should persist across many sessions
- it changes future decision quality
- it reflects a durable preference or policy
- losing it would likely recreate the same mistake

Update an operating file or skill when:
- behavior rules changed
- environment posture changed
- a procedure became repeatable enough to deserve a skill

## Hygiene rules

- No mental notes
- Prefer short accurate notes over long vague notes
- Avoid duplicating the same rule across too many files
- Keep `MEMORY.md` curated
- If a lesson changes future behavior, update the right operating file or skill instead of burying it in a daily note

## Daily note compression rule

- Start daily bullets with a clear topic lead so duplicate detection is easy.
- Before appending, scan today's note for the same topic or opening phrase.
- If the topic is already present, update or collapse the existing bullet instead of adding another one.
- If automation or session-memory writes touched the note and duplicate bullets are suspected, run `python scripts/daily_note_dedupe.py memory/YYYY-MM-DD.md --apply` as the bounded cleanup step.
- If a workflow had many small actions, write one summary bullet and point to the owning continuity note or audit instead of replaying the full sequence.
- Daily notes are not queue copies, chain logs, or proof-run ledgers.

## Startup and heartbeat note

Session startup behavior lives in `AGENTS.md`.
Heartbeat behavior lives in `HEARTBEAT.md`.
Procedural continuity work belongs in `memory-continuity-manager`.
