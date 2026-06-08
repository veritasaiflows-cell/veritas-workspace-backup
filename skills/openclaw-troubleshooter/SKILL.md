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

After an OpenClaw reinstall, update, gateway restart, or environment rebuild, also verify the recovery spine before resuming finance work:
- `python --version`
- `obsidian-cli --version` or `obsidian --version`
- `sqlite3 --version`
- `rg --version`
- `jq --version`
- `openclaw skills check`
- live cron list/history for scheduled workflows that must survive restart
- wrapper/path facts in `TOOLS.md`
Treat reinstall recovery as incomplete until binaries, skills, retrieval tools, and scheduled jobs are live-proven, not merely installed.

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
   - `openclaw config get <changed.path>` for each changed value
   - if the command output says restart is required, or if `openclaw doctor` still reports the old value, treat the fix as unapplied until the gateway restarts
   - after restart, rerun the exact failing check, usually `openclaw doctor`, and confirm the specific warning disappeared
   - use `openclaw status` only as supporting evidence; it does not replace the original failing check
10. For runtime-loaded warning fixes such as bootstrap limits, model runtime routing, plugins, channels, or message behavior:
   - do not claim fixed from config validity alone
   - distinguish `written`, `valid`, `runtime-applied`, and `doctor-clean`
   - if a restart is aborted or interrupted, say so and leave the item in `written/valid but not runtime-proven` state
11. If runtime does not match the default setting, inspect override surfaces before guessing:
   - `openclaw config get agents.list --json`
12. For stuck `agent:main:main` lanes, do not rely on gateway restart alone:
   - restart reloads persisted session state from `sessions.json` and transcript `.jsonl` files
   - first target the exact stuck key with `sessions.abort` and `sessions.reset`, or send `/new` through `sessions.send` when abort/reset does not clear the lane
   - in PowerShell, generate RPC params with `ConvertTo-Json -Compress`; do not hand-type fragile JSON through `.cmd` shims
   - verify with `openclaw sessions --active 120 --json` and `openclaw status`; look for a new `sessionId`, cleared active/queued work, and lower current context, not just disappeared checkpoint badges
   - use targeted hard cleanup of only `~/.openclaw/agents/main/sessions` entries for `agent:main:main` only after stopping the gateway and backing up the session directory
13. Interpret compaction and plugin evidence carefully:
   - compaction/checkpoint counts can be persisted history and are not by themselves proof that the current session context is still bloated
   - distinguish gateway feature/channel plugins from model-provider plugin inventory; verbose provider registration noise does not mean those providers are being called or burning tokens
   - when removing plugin load noise, prefer an explicit `plugins.allow` plus `plugins.bundledDiscovery="allowlist"` after confirming required providers remain available
14. For Codex app-server idle timeouts:
   - exact symptom: `codex app-server turn idle timed out waiting for turn/completed`
   - first run `python scripts\codex_app_server_timeout_diagnostics.py --write --validate`
   - inspect the generated `tmp/codex-app-server-timeout-diagnostics.json`; do not guess OAuth or model failure before checking trajectory evidence
   - if events show `yieldDetected=false`, treat it as a Codex app-server progress/completion idle-guard problem, often amplified by long context, upstream latency, broad tool output, or missing appServer timeout overrides
   - check current config with `openclaw config get plugins.entries.codex --json`
   - check schema/manifest for `appServer.requestTimeoutMs`, `appServer.turnCompletionIdleTimeoutMs`, and `appServer.postToolRawAssistantCompletionIdleTimeoutMs`
   - changing those values is runtime/plugin config mutation; get owner approval before applying it
   - after any approved change, validate with `openclaw config validate`, restart/reload the gateway if required, rerun `openclaw status`, and confirm a long Codex turn no longer creates new `turn_completion_idle_timeout` events
15. For reinstall/restart recovery, reconstruct the minimum return-to-service sequence in order:
   - runtime and model route sanity
   - Python / package dependencies
   - retrieval tools: Obsidian CLI, SQLite, `rg`, `jq`
   - skill visibility and plugin-symlink warnings
   - cron/scheduled job survival and next-run proof
   - finance-chain smoke proof before acting on stale artifacts
   - continuity/control-surface updates for any changed job IDs, tool paths, or trust limits
16. Record the real lesson in the correct file.

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
