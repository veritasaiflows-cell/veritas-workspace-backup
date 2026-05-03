---
name: openclaw-troubleshooter
description: Diagnose OpenClaw runtime, config, skills, plugin, and Windows-environment problems. Use when the gateway, memory, skills, startup files, or local service behavior is broken, stale, or inconsistent with expected state.
---

# OpenClaw Troubleshooter

## Purpose

Find the real failure point before changing anything.

## When to Use

Use this skill for:
- gateway not starting or behaving oddly
- config validation failures
- skills not loading or being unexpectedly blocked
- plugin issues such as memory being unavailable
- Windows service, path, or environment drift
- contradictions between audit notes and live runtime

## Inputs to Check First

Start with live state:
- `openclaw status`
- `openclaw doctor`
- `openclaw security audit`
- `openclaw skills list`
- `openclaw skills check`

Then inspect:
- `~/.openclaw/openclaw.json`
- relevant daily notes in `memory/`
- relevant audits in `08. Audits/`
- local docs and official docs for field-level or runtime guidance

## Procedure

1. Reproduce or restate the symptom clearly.
2. Check live runtime instead of trusting memory or old notes.
3. Separate these buckets:
   - config problem
   - environment or binary problem
   - auth or plugin problem
   - stale note or false assumption
4. Find the smallest safe fix.
5. Apply one change at a time when the issue is live.
6. Re-run the smallest meaningful validation command.
7. Record the real lesson in the correct file.

## Safety Rules

- Do not stack speculative fixes.
- Do not trust old audit success without revalidation.
- Prefer exact evidence over guesses.
- Keep a rollback path for config changes.
- If the issue is not understood, stop at diagnosis and ask.

## Files This Skill May Read

- `~/.openclaw/openclaw.json`
- core files
- `memory/*.md`
- `08. Audits/*.md`
- local docs and official docs

## Files This Skill May Edit

- config
- `TOOLS.md`
- `migration-review.md`
- daily notes
- a skill or operating file when the fix changes future behavior

## Output Format

Use this structure:
- symptom
- evidence
- root cause
- safe fix
- validation
- durable lesson

## Memory Update Rules

- write one factual note about the incident in the daily note
- promote durable environment or config lessons to `TOOLS.md` or `MEMORY.md`
- if the same failure pattern repeats, update a skill instead of keeping the lesson only in chat
