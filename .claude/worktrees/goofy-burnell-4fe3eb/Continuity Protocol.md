# Continuity Protocol

## Purpose

Keep Veritas continuous across sessions without turning the vault into noise.

## Memory layers

### 1. Daily raw memory
File: `memory/YYYY-MM-DD.md`

Use for:
- what happened today
- setup changes
- discoveries
- temporary context
- follow-ups
- rough notes worth reviewing later

Rule:
- write here often
- optimize for capture, not perfection

### 2. Curated long-term memory
File: `MEMORY.md`

Use for:
- durable facts
- Randall's preferences
- Veritas identity and mission
- long-term goals
- lessons that should change future behavior
- important recurring patterns

Rule:
- only promote what will still matter later
- keep it curated, not bloated

### 3. Operating rules
Files:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `USER.md`
- `IDENTITY.md`

Use for:
- identity
- behavior rules
- environment and tooling setup
- local conventions

Rule:
- these files define how Veritas should operate, not a daily event log

## Write rules

### Write to the daily note when
- meaningful work happened
- a tool or config changed
- a bug or constraint was discovered
- Randall gave a short-term instruction or preference
- there is a follow-up worth tracking

### Promote to MEMORY.md when
- the fact should persist across many sessions
- it changes how Veritas should make decisions
- it reflects Randall's durable preferences
- it defines mission, posture, or priorities
- it is a lesson that should not be relearned the hard way

### Update operating files when
- behavior rules change
- workflow standards change
- local setup changes
- a rule becomes important enough to formalize

## Session workflow

### At session start
1. Read `SOUL.md`
2. Read `USER.md`
3. Read today's and yesterday's daily notes
4. In main session, read `MEMORY.md`

### During the session
- do the work
- write notable developments to the current daily note

### At the end of meaningful work
- decide what belongs only in today's note
- promote durable items into `MEMORY.md` or an operating file

### Every few days
- review recent daily notes
- promote durable truths
- prune stale or duplicated long-term memory

## Hygiene rules

- No mental notes. If it matters, write it.
- Prefer short accurate notes over long vague notes.
- Avoid duplicating the same fact across too many files.
- `MEMORY.md` must stay curated.
- If a lesson changes future behavior, put it in `AGENTS.md`, `TOOLS.md`, or a skill, not only in a daily note.

## Recommended structures

### Daily notes
- What happened
- Decisions
- Follow-ups
- Worth promoting to MEMORY.md

### MEMORY.md
- Core identities
- Current priorities
- Working principles
- Preferences
- Tooling posture
- Important decisions
- Lessons learned

## Automation policy

Automation should support the protocol, not replace judgment.

Use later for:
- heartbeat-based memory maintenance
- periodic promotion reviews
- reminders for unfinished follow-ups

But keep the memory rules simple and human-readable first.
