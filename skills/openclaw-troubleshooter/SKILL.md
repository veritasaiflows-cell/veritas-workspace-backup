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

For config changes, inspect in this order before editing:
- active config file: `~/.openclaw/openclaw.json`
- schema: `openclaw config schema`
- current live value: `openclaw config get <path>`
- per-agent overrides when relevant: `openclaw config get agents.list --json`

Then inspect:
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
4. For config work, do not assume similar names mean the same thing.
5. Use schema plus current value before editing:
   - `openclaw config schema | Select-String -Pattern "<term>" -Context 3,5`
   - `openclaw config get <path>`
6. Prefer CLI config writes when possible:
   - `openclaw config set path.to.setting "value"`
   over manual JSON editing.
7. Ask for approval before changing auth, network exposure, permissions, or destructive settings.
8. Apply one change at a time when the issue is live.
9. Validate after every meaningful config change:
   - `openclaw config validate`
   - restart gateway if runtime-sensitive: `openclaw gateway restart`
   - verify with `openclaw config get <path>` and `openclaw status`
10. If runtime does not match the default setting, inspect override surfaces before guessing:
   - `openclaw config get agents.list --json`
11. Record the real lesson in the correct file.

When the issue has a safe non-destructive forward fix:
- take that step before ending at diagnosis
- then report what changed, what remains broken, and what user action is still required

## Safety Rules

- Do not stack speculative fixes.
- Do not trust old audit success without revalidation.
- Prefer exact evidence over guesses.
- Keep a rollback path for config changes.
- Never expose tokens, OAuth credentials, API keys, or gateway secrets in logs or chat.
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
- user action needed
- durable lesson

## Memory Update Rules

- write one factual note about the incident in the daily note
- promote durable environment or config lessons to `TOOLS.md` or `MEMORY.md`
- if the same failure pattern repeats, update a skill instead of keeping the lesson only in chat
