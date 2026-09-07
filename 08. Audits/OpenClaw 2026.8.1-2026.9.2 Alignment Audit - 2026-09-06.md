# OpenClaw 2026.8.1 / 9.1 / 9.2 Alignment Audit

Date: 2026-09-06 America/Phoenix  
Runtime: official OpenClaw `2026.9.2` (`3928bad`)  
Posture: review-only. No config, gateway, cron, finance, or archive mutation in this pass.  
Lane: `AUDIT::openclaw-912-alignment-20260906`

## Conclusion

The Gateway is on current stable and already using several 9.2 wins (Astra/Muse Spark, 6h heartbeat, explicit agent-to-agent allowlist, skills healthy). It is **not yet aligned** with the 9.2 shared-Gateway security default, the new service-env model, or a fast control plane. The biggest speed/correctness risks are cron scheduler failures, Swarm/session-visibility defaults, a stub `HEARTBEAT.md` that no longer matches git or the live heartbeat prompt, and leftover 2026.7.1-fork assumptions.

Do not run `openclaw doctor --fix` from an in-Gateway chat. It stops the Gateway.

## Sources

- Browser: `openclaw browser` opened and snapshotted https://docs.openclaw.ai/releases/2026.9.2
- Docs: https://docs.openclaw.ai/releases/2026.8.1, `/2026.9.1`, `/2026.9.2`
- GitHub: https://github.com/openclaw/openclaw/releases/tag/v2026.8.1, `v2026.9.1`, `v2026.9.2`
- Local: `CHANGELOG.md` in the 2026.9.2 npm install
- Live: `openclaw --version`, config validate, skills check, security audit, doctor lint, gateway status, cron control packet, runtime scorecard, concurrent lane register
- Web search: blocked (Ollama 429). Browser + docs/GitHub used instead.

## What changed in these releases (workspace-relevant)

### 2026.8.1 (OpenClaw 2.0)

- Rebuilt Control UI, session search, progress cards, dashboards/widgets, structured questions.
- Sessions/transcripts moved toward SQLite.
- Skill Workshop as the skill lifecycle.
- Protected credentials (`secrets`) and recurring automation approvals.
- Breaking: OpenProse removed; `codex/*` model refs migrate to `openai/*`.
- SDK subpath deprecations dated 2026-09-01.

### 2026.9.1

- Mermaid in chat.
- Safer `openclaw update` (rollback if post-update Doctor fails).
- Gateway stays up under load; Windows stays online after agent restart.
- Personal skill libraries; durable Codex “Allow Always”.
- Lower overhead on long conversations and large installs.

### 2026.9.2 (current)

- Chat/history work moved off the Gateway event loop (this is the main speed gift).
- GPT-6 Astra + Muse Spark 1.3.
- More settings apply without restart.
- **Default change:** omitted `tools.sessions.visibility` is now `all`; omitted `tools.agentToAgent.enabled` is now `true`. Shared Gateways must set these explicitly.
- Swarm enabled by default for eligible agents (opt-out in Labs).
- HEARTBEAT.md is treated as a legacy file to migrate into cron scratch.
- Doctor SQLite diagnostics improved; managed service env should load at runtime, not inline secrets in `gateway.cmd`.

## Live workspace vs those changes

| Area | Live proof | Alignment |
|---|---|---|
| Version | CLI and gateway `2026.9.2` | Aligned |
| Config / skills | config valid; 110 skills, 74 eligible, 0 missing reqs | Aligned |
| Models | Astra primary, Sol fallback, Muse Spark 1.3 in fleet | Aligned |
| Heartbeat cadence | `agents.defaults.heartbeat.every=6h`, `lightContext=true`, timeout 90s | Cadence aligned; file is not |
| HEARTBEAT.md | Isolated-agent stub (`2026-09-04.role-bound-models.v4`); git still has the Main heartbeat | Misaligned |
| Heartbeat prompt | Real checkpoint lives in config (`heartbeat_priority_handoff.py`) | Working, but split-brain with the md file |
| Session visibility | `tools.sessions.visibility=all` | 9.2 default, **too open** for this fleet |
| Agent-to-agent | enabled=true; allowlist of 8 agents (missing `oxalpha-functional-lab`) | Explicit, keep; do not leave omitted |
| Swarm | no explicit `tools.swarm` key | Default-on; specialists can fan out |
| Gateway service | `gateway.cmd` still inlines managed Telegram env | Not 9.2-clean; needs external `gateway install --force` |
| ACLs | security audit 0 critical after 2026-09-06 harden | Aligned |
| Doctor lint | snapshot-cleanup error; 30 checks skipped | Windows 9.2 bug, not workspace-owned |
| Custom 2026.7.1 fork | overwritten by stock 9.2 | Isolated-lane token attribution unproven |
| Cron | 31 enabled; 8 fresh; 9 blocked; 11 last-run exceptions; 9 escalations | Control-plane not fast/clean |
| Runtime scorecard | 36/54 ok, 18 blocked Go/SQL helper probes | Pre-existing helper-route debt |
| Lanes | 1735 register rows; 4 expired fleet leases; harness closeout still leased | Register bloat + collision risk |
| Auth | google-gemini-cli expired; xAI OAuth short-lived | Owner re-auth |

## Findings

### P1. Shared-Gateway session visibility is `all`

Evidence: live config `tools.sessions.visibility=all`; 9.2 docs upgrade note.  
Impact: any agent with session tools can list/read/search other agents’ transcripts. Finance red-team and builder sessions are in the same Gateway.  
Recommendation: set `tools.sessions.visibility` to `agent` (Main still sees Main sessions) unless Randall explicitly wants cross-agent transcript search. Keep the existing `tools.agentToAgent.allow` list.  
Stop line: config mutation needs explicit approval.  
Acceptance: `openclaw config get tools.sessions.visibility` returns `agent` or `self`; `openclaw config validate` passes.

### P1. Gateway service still embeds a managed Telegram env value

Evidence: `openclaw gateway status --deep`.  
Impact: 9.2 wants runtime-loaded secrets; the scheduled-task wrapper still inlines them. Restart required.  
Recommendation: from an **external** PowerShell: `openclaw gateway install --force`. Then prove Telegram + Control UI reconnect.  
Stop line: do not run this from WebChat.  
Acceptance: gateway status no longer reports inline managed env keys.

### P1. Cron control plane is noisy and slow

Evidence: `tmp/cron-control-packet.json` 2026-09-06T21:25:53Z: 9 blocked jobs, 11 scheduler exceptions, should_wake_main=true. Recurring classes: timeouts, `CronSessionLifecycleClaimError`, blocked finance/OTEL/wiki jobs.  
Impact: 9.2’s faster Gateway is wasted if 31 jobs keep error-retrying.  
Recommendation: next dedicated cron pass (not this audit): inspect the 9 escalation jobs, disable or repair only those with repeated scheduler failures, do not force-run retired jobs.  
Stop line: no schedule mutation here.  
Acceptance: blocked_count drops; next natural runs are `ok` without timeout storms.

### P2. HEARTBEAT.md is the wrong document

Evidence: live file is an isolated-agent stub; git HEAD still has the Main heartbeat; config prompt already owns heartbeat. Doctor wants cron-scratch migration.  
Impact: 9.2 doctor `--fix` would archive the stub, not restore Main doctrine.  
Recommendation: restore git `HEARTBEAT.md` **or** delete/ignore the stub and keep the config prompt. Do not `doctor --fix` heartbeat until that choice is made.  
Acceptance: file and `agents.defaults.heartbeat.prompt` describe the same checkpoint.

### P2. Swarm default-on vs isolated-agent contract

Evidence: 9.2 enables Swarm by default; no explicit opt-out in config.  
Impact: specialists may spawn extra children; more tokens, more session noise.  
Recommendation: opt out Swarm on finance/QA agents; leave Main able to use `collect=true` only when asked.  
Stop line: config/labs mutation needs approval.

### P2. 2026.7.1 fork residue

Evidence: MEMORY.md updated 2026-09-06; stock 9.2 is live.  
Impact: isolated-lane token attribution and `memory_search` phase budget are unproven on this build.  
Recommendation: one bounded isolated-agent canary with usage proof; do not reinstall the fork.

### P2. Expired fleet lanes collide with new writes

Evidence: four `FLEET-ALIGNMENT-20260905` leases expired; harness closeout still holds `memory/2026-09-06.md`. This audit therefore did not write the daily note.  
Recommendation: Main closes or re-leases those four lanes; keep harness closeout exclusive on the daily file until accepted.

### P3. Doctor lint snapshot cleanup

Windows temp SQLite copy cannot finish cleanup. Monitor; do not patch `dist`.

### P3. Runtime scorecard 18 blocked Go/SQL probes

These are helper-route/parity gates, not 9.2 regressions. Keep them off the OpenClaw-update critical path.

### Already good (do not “fix”)

- Loopback bind.
- Helper `skill_workshop` denies.
- Custom Codex `appServer.command` to bundled `codex.exe`.
- SQL canon guard clean; alerts OS still non-executing.
- Security ACL criticals cleared earlier today.

## Efficiency plan (ranked)

Goal: keep 9.2’s event-loop offload, then stop the workspace from fighting itself.

### Wave 0 — owner actions today (no workspace code)

1. External terminal: `openclaw gateway install --force`. Prove Telegram + UI.
2. Re-auth google-gemini-cli. Refresh xAI before the OAuth window dies.
3. Decide session visibility: recommended `agent`.
4. Decide HEARTBEAT.md: restore git Main file vs config-prompt-only.

### Wave 1 — config alignment after Wave 0 (explicit approval)

1. Set `tools.sessions.visibility=agent` (or `self` if even tighter).
2. Keep `tools.agentToAgent.allow` explicit; add `oxalpha-functional-lab` only if that lab must talk.
3. Opt Swarm off on finance/QA agents; leave Main explicit.
4. Do **not** migrate secrets, bind, or skill_workshop denies in the same change.

Acceptance: `openclaw config validate`; no gateway restart unless the setting still requires it (9.2 applies many live).

### Wave 2 — make the control plane cheap

1. Close expired fleet lanes.
2. Cron: repair or disable the 9 blocked escalations; first targets are session-claim collisions and 90s timeouts, not finance canon.
3. Stop treating historical `error (Nx)` badges as new 9.2 defects when last error is `interrupted by gateway restart`.
4. Leave Go/SQL scorecard blockers on their own helper-route lane.

### Wave 3 — use 9.2 instead of reinventing it

1. Prefer no-restart config patches.
2. Use session search, progress cards, and task-workspace panels instead of new dashboards.
3. Keep heartbeat at 6h + `lightContext`.
4. Re-prove `memory_search` and isolated-lane usage on stock 9.2 before any fork nostalgia.
5. Pin plugin npm specs later (P3 supply chain), not in the speed path.

## Stop lines

- No `doctor --fix` from this session.
- No gateway install/restart from WebChat.
- No archive/delete of `~\.openclaw\npm` caches.
- No finance/canon/cron schedule mutation without a separate gate.
- No Skill Workshop publish in this audit.

## Intentionally not checked

- Full 16k-PR 8.1 section pages.
- Plugin SDK consumer migration for third-party plugins.
- Disk size of session SQLite / conversation archives.
- Independent QA of fleet bootstraps (`FLEET-ALIGNMENT-20260905`).
- Live xAI/Gemini re-auth (owner).

## Next concrete action

Randall: pick Wave 0 items 3 and 4 (visibility + HEARTBEAT), then run `openclaw gateway install --force` in an external PowerShell. After the UI reconnects, I can apply the approved config slice only.
