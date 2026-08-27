# Agent Knowledge Base

## Purpose

This folder is the shared, auditable reference layer for persistent isolated agents.
It explains how agents should find authoritative sources, use bootstrap packets,
and preserve boundaries while working for Veritas.

It is guidance only. It does not grant approval, override doctrine, mutate
configuration, authorize customer/public delivery, or replace generated proof.

## Authority

Authority remains:

1. `SOUL.md`
2. `AGENTS.md`
3. `IDENTITY.md`
4. `USER.md`
5. `TOOLS.md`
6. live skills, continuity notes, playbooks, and owner artifacts
7. `MEMORY.md` and daily memory
8. generated proof packets and bootstrap feeds

This knowledge base sits in the playbook layer. If it conflicts with a higher
authority, the higher authority wins.

## How Agents Use This Folder

The shared source folder is:

```text
C:\Users\Veritas\.openclaw\workspace\06. Playbooks\Agent Knowledge Base\
```

Persistent isolated agents can read this folder by absolute path when their
tool policy and sandbox posture allow file reads. They do not receive the whole
folder automatically in every prompt.

The expected flow is:

1. Veritas main maintains this central reference.
2. `scripts\agent_bootstrap_generator.py` points each agent bootstrap packet at
   the relevant pages.
3. Each agent reads only the pages needed for the assigned task.
4. The agent closes out against proof commands and stop lines.

## Folder Map

| Path | Purpose |
|---|---|
| `contracts/authority-boundaries.md` | Shared no-second-authority and owner-gated boundary rules. |
| `contracts/capability-manifest.schema.json` | JSON schema reference for `agent.capabilities.json`. |
| `runbooks/spawn-contract.md` | Assignment template for isolated-agent and sub-agent work. |
| `runbooks/direct-agent-communication.md` | How Veritas main should route tasks to agents without external bindings. |
| `self-improvement/latest-agent-delta.md` | Current metadata-only change feed for agents. |
| `agent-templates/research-scout.md` | Research Scout role template. |
| `agent-templates/qa-redteam.md` | QA Red-Team role template. |

## Non-Goals

- No config, auth, credential, channel, plugin, service, startup, or runtime mutation.
- No external messaging, webhook, Telegram, Discord, email, or customer/public delivery.
- No cron schedule creation or mutation.
- No raw prompt, raw response, hidden reasoning, raw tool payload, secret, customer/private,
  brokerage/account, or external telemetry capture.
- No finance execution, account action, money movement, paper/live order action, or capital
  deployment approval.

## Source Proof

This folder is backed by:

- `skills/veritas-isolated-agent-contract/SKILL.md`
- `scripts/agent_bootstrap_generator.py`
- `scripts/agent_bootstrap_linter.py`
- `state/ai-drop-service-os/team-board.json`
- `tmp/agent-bootstrap/*.json`
- `memory/2026-07-03.md`

