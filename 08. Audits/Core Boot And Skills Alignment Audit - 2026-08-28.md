# Core Boot And Skills Alignment Audit - 2026-08-28

## Outcome

The core boot surface is now a thin control layer, while reusable procedure and exact command detail live in skills or their references. No OpenClaw runtime, config, auth, channel, service, plugin, model-dispatch, finance, portfolio, paper, live-account, or external-delivery mutation was made.

The previously proposed model-routing attribution repair was not implemented.

## Measured Result

| Surface | Before | After | Result |
|---|---:|---:|---|
| Six core boot files (`SOUL`, `AGENTS`, `USER`, `TOOLS`, Continuity, Heartbeat) | 52,522 bytes | 20,438 bytes | 61.1% smaller |
| `06. Playbooks/Startup Truth Index.md` | 12,390 bytes | 4,531 bytes | 63.4% smaller |
| Workspace skill bodies | 51 | 51 | no new skill or duplicate procedure owner |
| OpenClaw skill eligibility | 69 eligible / 68 command-visible | 69 eligible / 68 command-visible | 0 blocked; 0 missing requirements |
| Core skill proof | 13 audited | 13 Tier 2 local proof | 0 blocked; 0 warnings |
| Skill body guard | 51 audited | 51 clean | 0 errors; 0 warnings |

A normalized core-to-skill instruction scan found zero exact duplicate blocks and zero high-similarity blocks at the 0.68 threshold after migration. Small authority reminders remain intentionally repeated where a local stop line must fail closed.

## Canonical Ownership

| Surface | Retained responsibility |
|---|---|
| `SOUL.md` | identity, mission, standards, and hard finance/safety boundaries |
| `AGENTS.md` | thin startup, action boundary, orchestration, and response-shape control |
| `USER.md` | stable Randall preferences, goals, and approval boundaries |
| `TOOLS.md` | environment truth, fast front doors, and runtime/config change boundary |
| `Continuity Protocol.md` | compact continuity routing and canonical state homes |
| `HEARTBEAT.md` | heartbeat-only behavior |
| Skills and references | reusable procedures, exact commands, validators, model/lane rules, templates, and stop lines |

There is no live root `IDENTITY.md`. `SOUL.md` remains the sole identity owner, and the boot-size guard now treats any future `IDENTITY.md` as an optional mirror rather than a required duplicate.

## Skill Updates Applied Through Skill Workshop

- `workspace-governor`: added the boot-surface ownership matrix and placement rules.
- `openclaw-operator`: clarified identity ownership and added `references/workspace-route-map.md` for exact current commands.
- `memory-continuity-manager`: added canonical continuity homes and the thin startup/resume route.
- `veritas-model-routing-helper-lanes`: aligned model-free/Luna/Terra/Sol boundaries, fail-closed transport proof, on-demand efficiency evidence, and no fixed cohort minimum.
- `disciplined-implementation`: aligned live routing, lane/validator commands, and core ownership.
- `workspace-qa-pass`: aligned route proof and made explicit that QA is not execution authority.
- `cron-automation-manager`: aligned current cron validators, delivery semantics, quiet output, and authority limits.
- `veritas-isolated-agent-contract`: removed three encoding-residue sequences without changing procedure or authority.

The old pending proposal `veritas-prompt-book-operator-20260708-042e68ee7e` was not applied. Its extra per-answer bookkeeping would add latency and operating overhead. It remains pending because reject/quarantine was not authorized.

## Validator Alignment

- `boot_surface_size_guard.py`: recognizes `SOUL.md` as canonical identity and does not require a duplicate `IDENTITY.md`.
- `skill_core_proof_tier_audit.py`: validates the current model-free/Luna/Terra/Sol and authority contracts instead of obsolete model names.
- `skill_workshop_body_guard.py`: now detects malformed encoding residue in live and proposed skill bodies.

## Remaining Limits And Resolution

1. Resolved 2026-08-28: preservation commit `b2046aa` captured the pre-compaction state, then `MEMORY.md` was reduced from 18,269 to 5,059 bytes. Duplicate core doctrine, stale status snapshots, and generated promotion excerpts were removed by pointer; the boot-size guard now reports zero hard failures.
2. The project implementation router correctly protects `SOUL.md`, `AGENTS.md`, and `TOOLS.md` from helper writes, but it also lacks a clean explicit owner-authorized Main route for protected-core maintenance. That routing gap was not changed because the model-routing repair was declined.
3. The worktree contains unrelated pre-existing changes and generated artifacts. This pass did not archive, delete, or normalize them.
4. The semantic Graphify skill graph was used only as a routing aid and was not treated as current authority. One bounded `graphify update .` attempt timed out after 64 seconds; no matching process remained, and Graphify was not used as acceptance proof.

## Proof

- `tmp/skill-core-proof-tier-audit.json`
- `tmp/skill-workshop-body-guard.json`
- `tmp/boot-surface-size-guard.json`
- `openclaw skills check --json`
