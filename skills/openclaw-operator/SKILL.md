---
name: openclaw-operator
description: Operate and maintain the OpenClaw workspace and local runtime. Use when auditing startup files, reviewing config, validating skills, checking gateway or runtime state, tightening core-file architecture, or performing safe workspace hardening and cleanup.
---

# OpenClaw Operator

## Purpose

Keep the OpenClaw workspace lean, valid, and operational without turning core files into a junk drawer.

## When to Use

Use this skill when the work is about:
- OpenClaw config review or hardening
- startup-file cleanup or condensation
- workspace architecture changes
- skill allowlists, skill inventory, or skill hygiene
- local runtime checks on Windows
- gateway, dashboard, and control-surface verification
- deciding whether instructions belong in core files, skills, memory, or daily notes

## Inputs to Check First

Read only what is needed:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `MEMORY.md`
- `migration-review.md` if a migration is active
- `~/.openclaw/openclaw.json`
- relevant audits in `08. Audits/`
- local OpenClaw docs and the official docs when live behavior or schema details matter

Check live state before claiming anything about runtime:
- `openclaw status`
- `openclaw config validate`
- `openclaw skills list`
- `openclaw skills check`
- `openclaw security audit`

## Procedure

1. Inspect before editing.
2. Separate constitutional rules from procedures.
3. Keep core files short and durable.
4. Move repeatable workflows into focused skills.
5. Prefer references or scripts inside skills over bloated core files.
6. Back up every file before modifying it.
7. Validate config and skill state after changes.
8. Record major architecture changes in the current daily note.

For major protocol or skill-governance changes, also make the checkpoint decision explicit before calling the pass closed.

## Classification Rule

Use this routing test:
- identity, doctrine, values, boundaries -> `SOUL.md` or `IDENTITY.md`
- durable facts or preferences -> `MEMORY.md` or `USER.md`
- environment facts or global tool rules -> `TOOLS.md`
- repeatable procedures -> `skills/`
- historical session facts -> `memory/YYYY-MM-DD.md`
- uncertain or contested material -> `migration-review.md` or another review note

## Safety Rules

- Prefer reversible changes.
- Do not keep stale pseudo-protection in config or notes.
- Do not delete uncertain files in the same pass that discovers them.
- Validate after edits instead of assuming success.
- Treat third-party skills as untrusted until reviewed.

## Files This Skill May Read

- core files
- `migration-review.md`
- `08. Audits/*.md`
- `scripts/README.md`
- `~/.openclaw/openclaw.json`
- local or official OpenClaw docs

## Files This Skill May Edit

- `TOOLS.md`
- `AGENTS.md`
- `migration-review.md`
- `~/.openclaw/openclaw.json`
- workspace skills under `skills/`
- daily notes when major operator work happened

## Output Format

Report in this order:
- issue or goal
- evidence
- proposed or completed change
- risk or open question
- validation result

## Memory Update Rules

- log major workspace or config changes in `memory/YYYY-MM-DD.md`
- promote durable operator policy to `TOOLS.md` or `MEMORY.md`
- if a workflow becomes repeatable, create or improve a skill instead of bloating a core file
