# Agent Harness Landscape — OpenClaw, Hermes, and Similar Runtimes

Research date: 2026-09-18. Source: research-scout agent (Grok 4.6), web-only scan of official docs, GitHub releases/issues, security research, blogs, HN. Full summary delivered to Randall via Telegram 2026-09-18 ~15:20 MST.

Legend: **[V]** verified from repo docs/releases · **[A]** anecdote/secondary · **[C]** contradiction · **[G]** evidence gap.

## Bottom line

By mid-to-late 2026 the "advanced / future-ready" personal-agent pattern is no longer a chat wrapper. It is a **resident control plane** (always-on gateway, channels, cron, skills, memory, approvals) plus an **agent loop** that can spawn specialists. OpenClaw and Nous Hermes Agent are the two dominant self-hosted implementations, with opposite centers of gravity:

| | OpenClaw | Hermes Agent |
|---|---|---|
| Center | Gateway / control plane [V] | Agent loop (plan→act), gateway is a surface [V] |
| Language | TypeScript [V] | Python [V] |
| Skills | Human-authored, ClawHub marketplace [V] | Agent-authored from completed work + Skills Hub [V] |
| Memory | Markdown workspace + dreaming + optional wiki [V] | Five-layer (context, skills, retrieval, Honcho, FTS5) [V]/[A] |
| Latest cut | v2026.8.1 = OpenClaw 2.0, 2026-08-30 [V] | v0.21.0 Pantheon 2026-08-31; v0.21.2 patch 2026-09-11 [V] |

**Name collision:** "Hermes" is both Hermes Agent (the harness) and Hermes 4 (Nous model family). Related by vendor, not the same product.

## 1. OpenClaw ecosystem — what people are actually building

**What it is [V]:** local-first assistant on your own infrastructure; Gateway is the always-on control plane; Discord/Google Chat/iMessage/Mattermost/Signal/Slack/Telegram/WebChat/WhatsApp + plugins; model-agnostic; multi-agent routing per channel/account/task, each with own workspace. Stewardship: OpenClaw Foundation (independent 501(c)(3)); OpenAI is a donor, not owner. Formerly Clawdbot/Moltbot (Jan-Feb 2026) [A].

**OpenClaw 2.0 (v2026.8.1, 2026-08-30) [V]:** 16,977 PRs / 987 contributors per release notes (blog says 933 incl. 569 first-timers) [C]; rebuilt Control UI; onboarding detects existing sign-ins/API keys/local models; **sessions/transcripts moved to SQLite**; shared cloud sessions (multiplayer); memory recall across the agent's other private conversations with inspect/import/remove; Skill Workshop (proposals, checks, decisions, applied history); automations unified under `openclaw automations` (`cron` alias); security hardening — approvals bound to exact request/command/session/person, secret store, Docker/Podman sandboxing.

**ClawHub:** 9.3k skills listed (community docs 2026-06-18) [A]; users report ~1,000–1,200 in active use; one thread cites 824 skills / 341 forks (X 2026-07-12) [A]. De-facto skill store; most production multi-agent teams pull from it.

**Memory & continuity:** SQLite sessions (v2026.8.1); daily "dreaming" consolidation + memory-wiki plugin is the standard pattern; a 13-agent Mac-mini setup (openclawlab.xyz tutorial, 2026-08-15) holds 4-week context via compaction + wiki [A].

## 2. Hermes Agent (Nous Research)

MIT Python agent loop; the gateway is just a surface. **v0.21.0 Pantheon (2026-08-31):** Bot Mode, `hermes peer` DMs, cron-with-memory (`continuity=true`), live subagent steering. **v0.21.2 (2026-09-11):** state.db WAL patch. **v0.15.0 (2026-05-28):** kanban/swarm view, FTS search 4500× faster and free.

**Skills:** the agent writes its own SKILL.md after completing hard tasks, plus a Skills Hub (agentskills.io). Self-evolution experiments (DSPy + GEPA) are Phase 1 only (repo 2026-03-09). `hermes claw migrate` imports from OpenClaw.

**Memory — five layers (CrabTalk, 2026-03-15):** context; procedural skills; vector retrieval; Honcho user model; FTS5. Skill-creation trigger remains undocumented [G].

## 3. What separates advanced setups from toy demos

Durable memory with promotion/provenance · cron that remembers across runs · skills as governed schemas (pin/scan/sandbox) · orchestrator + specialists with file handoff and live steer/stop · human-in-the-loop gates on send and money · per-task model routing across providers · eval gates (memory-gate, GEPA) · compaction budgets · always-on host (Mac mini / VPS) + SQLite persistence.

## 4. Failure modes and frontier

**Reported failures:** memory drift (OpenClaw #48711, open 2026-08-14; Hard Fork's "Newton" experiment 2026-01-30); Anthropic blocked Claude Code subscriptions ~Apr 2026; **ClawHavoc** — 341–1,184 malicious/bad skills found on ClawHub Feb–Jun 2026 (Unit42, 2026-06-23); cron without chat-bridge (#30243); compaction vs token budgets vs unbounded sessions; provider model-deprecation churn (xAI retire 2026-05-15); sandboxes off by default.

**Community's next steps:** eval-gated memory writes, provenance wikis, cron continuity, default-on hardening, and hybrids — OpenClaw gateway + Hermes loop.

## Sources (title · date)

OpenClaw 2.0 blog · 2026-08-30 · v2026.8.1 release notes · 2026-08-30 · OpenClaw Memory/Dreaming/Wiki/Cron docs · live 2026-09-18 · GitHub #48711 · 2026-03-17 · #30243 · 2026-03-01 · Unit42 ClawHub research · 2026-06-23 · HN Claude-Code-sub ban · ~Apr 2026 · Hard Fork "Newton" · 2026-01-30 · Hermes README v2026.5.7 · v0.15.0 notes 2026-05-28 · v0.21.0 notes 2026-08-31 · v0.21.2 notes 2026-09-11 · CrabTalk memory post · 2026-03-15 · fwdslash Hermes writeup · upd 2026-08-31 · GIGAZINE · 2026-09-09 · Hermes self-evolution repo · 2026-03-09 · DEV skills post · 2026-09-08 · AI Journal · 2026-09-16
