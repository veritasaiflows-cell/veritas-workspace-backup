---
name: "openclaw-operator"
description: "Operate lean boot, status, runtime, lane, and workspace routes safely."
---

# OpenClaw Operator

## Purpose

Operate startup, cached status, runtime inspection, lane coordination, skill validation, post-update recovery, and exact workspace routes without bloating core doctrine or widening authority.

Read `references\workspace-route-map.md` for exact first-hop commands.

## Status

For shallow status:

```powershell
python scripts\status_card_packet.py --read-only --render --validate
```

If missing or critical, use the one-command fallback:

```powershell
python scripts\startup_brief_packet.py --write --validate
```

Do not rebuild PM, cron, workflows, memory, lanes, gateway, or runtime for a shallow status reply.

## Material Work

1. read only the relevant owner surfaces
2. inspect live state before claiming it
3. check the concurrent lane register before writes; `--lease` replaces lane fields instead of merging, so pass `--owner` with all `--allowed-write` values in one call and re-verify admission
4. separate doctrine from procedure
5. use the smallest exact command
6. validate proportionally
7. update continuity when the lane owns it
8. report proof and unresolved trust limits

Runtime session visibility is advisory; the durable lane register owns write-collision proof.

## Discovery

External skills are pattern sources only. Do not install or activate one without exact approval and security/governance review.

## Provider Model Registration

When a user explicitly approves adding a provider model after completing authentication, inspect the provider profile, model definition, and global model allowlist before changing anything. Register only the missing model or policy entry; never alter authentication material. Validate the effective OpenClaw configuration afterward, and report whether a gateway restart is actually required rather than assuming one.

## Post-Update Recovery

Check runtime status, doctor, config validity, skills, persistent approvals, workspace skills, and startup/gateway persistence. Treat Windows link/PATH failures as environment issues until verified.

## Active Finance Route

Current finance work starts with guarded SQL and the direct alerts/recommendations chain. Old portfolio maintenance, paper operation, data-plane, finance-state, and ticker-card/full-answer routes are retired history, not operator front doors.

## Allowed

Read-only inspection, cached status, exact local proof routes, lane validation, and approved bounded workspace maintenance.

## Stop Lines

Stop for lane collision, destructive scope without authorization, active-reference conflict, missing rollback/proof, config/auth/network/channel/credential/startup/service/plugin/runtime change, external delivery, customer data, account access, money, capital, orders, or execution.

## Fleet

Main remains router, final QC, acceptance, judgment, and user-facing owner. Helper lanes are bounded and untrusted until verified. A model label is not proof of the actual route. Sandbox, bindings, config, and runtime changes require explicit approval.

## Skill Workshop Proposal Queue

When applying or rejecting skill proposals:

- Agent-side `skill_workshop apply` may refuse migrated or user-authored skills with `does not own this skill path`; the operator CLI is the working route: `openclaw skills workshop apply <proposal-id>` (same for reject).
- Proposals are hash-bound: a live-skill rewrite after proposal creation marks the proposal `stale` at apply, and stale is terminal. Recover still-wanted content by extracting a merged `PROPOSAL.md` and recreating it with `openclaw skills workshop propose-update <skill> --proposal <path>`, then apply the fresh proposal and verify the changed sections plus a clean `openclaw skills check`.
- Judge propose/apply/reject success by the `Applied` or `pending` output line, never the exit code; these CLI calls may exit nonzero on unrelated warnings (plugin chatter, SQLite hold notes).
- Count queue entries by matching the status token (`" pending "`) or `--json` output, never by output line count: wrapped list entries (for example `[previous workspace]` tags) double-count lines.

## Closeout

Report conclusion, evidence, change, validators, lane state, risk, rollback, and any owner-gated decision.
