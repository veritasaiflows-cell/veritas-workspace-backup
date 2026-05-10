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
- post-update or post-reinstall recovery back to the known-good workspace posture
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
- `openclaw skills search <term>` when comparing local coverage to ClawHub patterns or scouting missing governance capabilities
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

## ClawHub / discovery rule

When external skill scouting matters:
- prefer the native `openclaw skills search <term>` path to inspect ClawHub registry candidates
- if normal web search is unavailable, use direct page fetches only as supporting evidence and say the web-search gap plainly
- treat external skills as idea sources for local hardening, not as doctrine to import blindly over the workspace's existing rules
- when recurring automation clearly belongs to one local skill, tighten the local skill and the cron packet before considering a new external dependency

## Post-update / post-reinstall recovery protocol

When OpenClaw was updated or reinstalled, run this bounded recovery checklist before trusting the environment:

1. Confirm the runtime is alive:
   - `openclaw status`
   - `openclaw doctor`
   - `openclaw config validate`
2. Confirm the persistent control surfaces survived:
   - `~/.openclaw/openclaw.json`
   - `~/.openclaw/exec-approvals.json`
   - workspace `skills/`
   - startup / gateway persistence surfaces noted in `TOOLS.md`
3. Re-check skill publication and plugin health:
   - `openclaw skills check`
   - if plugin-skill publication errors mention `~/.openclaw/plugin-skills` or `EPERM` / `WinError 1314`, treat that as a Windows symlink-privilege problem, not a missing skill definition
4. On Windows, verify plugin skill links can be created again before assuming browser or other plugin skills are healthy:
   - preferred durable fix: enable Windows Developer Mode so non-elevated symlink creation is allowed
   - fallback: run the relevant OpenClaw process elevated long enough to recreate the managed links
   - if elevated OpenClaw is unavailable, create only the exact managed browser skill directory symlink from an Administrator PowerShell session, then rerun `openclaw skills check`:
     ```powershell
     New-Item -ItemType Directory -Force "C:\Users\Veritas\.openclaw\plugin-skills"
     New-Item -ItemType SymbolicLink -Path "C:\Users\Veritas\.openclaw\plugin-skills\browser-automation" -Target "C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw\dist\extensions\browser\skills\browser-automation"
     openclaw skills check
     ```
   - if the manual symlink command returns `ResourceExists`, do not delete anything first; rerun `openclaw skills check` and inspect whether `browser-automation` is already a valid symlink to the packaged skill target.
   - do not paper over this with copied skill folders or junctions unless the runtime contract explicitly changes
5. Re-validate the custom workspace posture that reinstalls often disturb:
   - `openclaw skills check`
   - `openclaw approvals get --json`
   - `openclaw status`
   - cron inventory / critical job presence when automation matters
6. Spot-check the highest-risk local customizations rather than assuming they persisted:
   - exact-command durable approvals for scheduled finance chains
   - custom workspace skills and their visibility
   - pinned version / update posture notes in `TOOLS.md`
   - any known startup launcher or gateway persistence requirements
7. Write one short daily-note bullet naming what broke, what was restored, and what still needs manual follow-up.

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
