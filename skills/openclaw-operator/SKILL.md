---
name: "openclaw-operator"
description: "Operate OpenClaw status surfaces, fleet posture, skill health, lane coordination, and staged sandbox safety."
---

# OpenClaw Operator

Use this skill when operating and maintaining the OpenClaw workspace and local runtime: startup files, config review, skill validation, gateway/runtime state, skill hygiene, post-update recovery, cached status routing, lane-register checks, and safe workspace hardening.

## Purpose

Keep the OpenClaw workspace lean, valid, and operational without turning core files into a junk drawer or rebuilding heavy control surfaces for shallow requests.

## Inputs To Check First

Read only what is needed:

- `SOUL.md`, `AGENTS.md`, `TOOLS.md`, `USER.md`, and `MEMORY.md` when doctrine/runtime matters
- `migration-review.md` if a migration is active
- `~\.openclaw\openclaw.json` when config matters
- relevant audits in `08. Audits\`
- local or official OpenClaw docs when live behavior or schema details matter

Check live state before claiming runtime state when runtime state is in scope:

- `openclaw status`
- `openclaw config validate`
- `openclaw skills check`
- `openclaw skills search <term>` when comparing local coverage to external patterns
- `openclaw security audit` when security posture is in scope

## Cached Status Card Shallow Status Route

For shallow direct-session status requests such as `Status?`, `status`, `quick status`, or a simple greeting/status check, prefer the cached status card:

```powershell
python scripts\status_card_packet.py --read-only --render --validate
```

The read-only renderer is the chat path. It must not write files, regenerate PM/cron packets, refresh workflow capsules, inspect the lane register, read daily memory live, or run runtime/gateway status commands.

If the cached card is missing or validation is critical, use exactly one fallback command:

```powershell
python scripts\startup_brief_packet.py --write --validate
```

Refresh the rich cached card only outside the shallow status reply path, such as after meaningful work, closeout, heartbeat, cron, or an explicit `refresh status` request:

```powershell
python scripts\status_card_packet.py --write --validate
```

Treat stale status-card inputs as summary context, not automatic permission to rebuild the control plane. Drill into PM, cron, workflows, memory, lane register, gateway, or runtime only when Randall asks for material workflow detail/action, cached status validation is critical, or stale/missing data blocks a specific requested decision.

The cached status card and startup fallback are review-only. They must preserve: no capital deployment approval, no trade/execution approval, no paper/live execution authority, no brokerage/account action, no config/auth/runtime mutation, no customer/external delivery, and no owner approval inference.

For implementation changes that touch this route, run:

```powershell
python scripts\status_card_packet.py --write --validate
python scripts\status_card_packet.py --read-only --render --validate
python scripts\test_status_card_packet.py
python scripts\test_startup_brief_packet.py
python scripts\changed_file_validator_router.py --write --validate
```

Stop line: do not answer shallow `Status?` by rebuilding PM/cron/workflow/lane/gateway surfaces. Status should be a cached dashboard read unless Randall explicitly asks for a live refresh or material drilldown.

## Procedure

1. Inspect before editing.
2. Separate constitutional rules from procedures.
3. Keep core files short and durable: identity, hierarchy, hard boundaries, startup/routing contracts, and user preferences.
4. Route procedures/history/tool minutiae to skills, owner notes, procedures, or memory.
5. Move repeatable workflows into focused skills or procedures.
6. Prefer references or scripts inside skills over bloated core files.
7. For boot/core slimming, measure before/after when practical and do not weaken finance, paper/live, account, config/auth, or external-action stop lines.
8. Use `windows-powershell-workspace` for native Windows, PowerShell syntax, wrappers, encoding, approvals, startup, or scheduled-chain behavior.
9. Validate config and skill state after changes.
10. Record major operator architecture changes in the correct continuity surface.

## Cross-Surface Implementation Lane Audit

When checking whether Telegram, WebChat, main, helper, isolated, or cron-adjacent sessions are doing implementation work, inspect both runtime state and the durable lane register.

Runtime visibility is advisory:

- `sessions_list` may be tree-scoped and omit unrelated WebChat or Telegram sessions.
- visible subagent lists only prove active/recent child lanes visible to the requester session.

Durable coordination state is authoritative for implementation collision checks:

```powershell
python scripts\concurrent_lane_manager.py --status --write --validate
```

Interpretation:

- Active lane count `0` means no implementation lane has been leased in the durable register.
- If another surface is editing/writing while active lane count is `0`, that surface did not follow the lane-register protocol.
- `created_at_utc` is lane lifecycle/planning time.
- `started_at_utc` is actual running start time for new lanes.
- `ended_at_utc` / `completed_at_utc` is terminal closeout timing.
- Legacy lanes without `started_at_utc` cannot prove runtime duration.

For operator hardening or after-session audits, report active lane count, latest active/running lanes and write surfaces, latest completed implementation job when a ledger exists, latest daily-memory completion entry only when requested and lane-owned, and mismatch between runtime session activity and lane-register state.

If a mismatch suggests a session bypassed the register, classify it as a governance gap, not proof that runtime visibility is broken.

## ClawHub / Discovery Rule

External skills are pattern sources, not doctrine. Do not install or import third-party skills unless Randall explicitly approves the exact skill and dependency posture.

When scouting external patterns:

- use `openclaw skills search <term>` first
- summarize useful patterns
- route adopted behavior into a Veritas-owned skill, procedure, validator, or queue item
- preserve finance/control-plane doctrine over generic advice

## Post-Update Recovery Protocol

When OpenClaw was updated or reinstalled:

1. Confirm runtime is alive with `openclaw status`, `openclaw doctor`, and `openclaw config validate`.
2. Confirm persistent control surfaces survived: config, approvals, workspace skills, startup/gateway persistence surfaces.
3. Re-check skill publication and plugin health with `openclaw skills check`.
4. On Windows plugin-skill link errors, treat symlink privilege failures as environment issues before declaring skills missing.
5. Re-validate custom workspace posture such as exact-command durable approvals, custom skill visibility, and startup launcher requirements.
6. Write one short daily-note or continuity bullet only when the lane owns that surface.

## Classification Rule

- identity, doctrine, values, boundaries -> `SOUL.md` or `IDENTITY.md`
- durable facts or preferences -> `MEMORY.md` or `USER.md`
- environment facts or global tool rules -> `TOOLS.md`
- repeatable procedures -> `skills\` or operating procedures
- historical session facts -> `memory\YYYY-MM-DD.md`
- uncertain or contested material -> review note or migration review

## Allowed Operator Work

Allowed without authority expansion:

- inspect local runtime/control surfaces
- check lane register before concurrent write work
- route through exact workspace scripts and proof artifacts
- maintain local-only operator surfaces inside approved boundaries
- validate skills/config/status when in scope

## Blocked Operator Work

Blocked without exact approval:

- config/auth/network/channel/credential/startup/service/plugin/runtime mutation outside approved scope
- destructive cleanup, moves, deletes, archive action, or broad cleanup
- external/public action
- brokerage/account action
- paper/live execution
- money movement
- finance canon/portfolio/cash/sizing/risk mutation
- owner approval inference

## Stop Lines

Stop for lane collision, ambiguous active session ownership, authority-gated runtime mutation, missing proof, destructive operation, external exposure, credential/config/runtime implication, or finance/paper/live/account implication.

## Validation / Proof

Use lane register, PM/cron packets, local validators, and exact command output. Record active lane count, write surfaces, proof artifacts, and terminal lane state when the task involved implementation or runtime control.

## Safety Rules

- Prefer reversible changes.
- Do not keep stale pseudo-protection in config or notes.
- Do not delete uncertain files in the same pass that discovers them.
- Validate after edits.
- Treat third-party skills as untrusted until reviewed.
- Do not mutate config/auth/network/service/startup, credentials, external/public state, finance canon/portfolio, paper/live/account state, or destructive cleanup without exact authority.

## Output Format

Report issue or goal, evidence, proposed or completed change, risk or open question, validation result, lane status when relevant, and remaining owner-gated decisions.

## Seven-Agent Fleet Operations

Operate Veritas Main plus six configured isolated agents: Research Scout, QA Red-Team, Finance Source Scout, Finance Red-Team, Implementation-Builder, and Docs Continuity Editor. Main remains sole router, final QC owner, acceptance owner, final judgment owner, and final user-facing integrator.

Use General: Main -> Research when needed -> Builder -> QA -> Main acceptance -> Docs -> Main closeout. Use Finance: Main -> Finance Source when needed -> Main analysis -> Finance Red-Team -> Main judgment. Keep distinct workspace agents advisory/bounded: no self-routing, self-acceptance, external delivery, direct cross-agent delegation, cron, runtime/config, or authority expansion.

### Fleet Posture Read

For shallow status, use the cached card first. Its Fleet Posture must show configuration/utilization, attribution coverage and partiality, outcomes, QA/rework, OAuth advisory capacity, and sandbox state. It is not billing evidence, quota authorization, automatic throttle control, or sandbox proof.

When a material fleet concern requires live checks, use only the necessary read-only surfaces: agent list, bindings, config validation, skills check, and lane register. Expect explicit model routes and zero external bindings unless separately approved. Keep isolation honestly labeled as organizational until actual sandbox proof exists.

### Sandbox Change Gate

Docker availability is not authorization to enable sandbox. Before an expressly approved config patch, capture a rollback-ready configuration snapshot, verify Docker/Linux-container readiness, inspect sandbox explain for each isolated agent, pilot one read-only agent without host workspace access, then run positive proof plus negative smokes for forbidden exec/write/cron/messaging/gateway/cross-session/spawn actions. Main remains host-side and final acceptance authority. Do not claim hard containment or expand the pilot before proof is clean.

Do not mutate config/auth/network/channel/credential/startup/service/plugin/runtime, sandbox policy, cron, or bindings within normal operator work. Do not infer finance, capital, paper/live/account, portfolio/canon, external-delivery, or approval authority from a green Fleet Posture.

