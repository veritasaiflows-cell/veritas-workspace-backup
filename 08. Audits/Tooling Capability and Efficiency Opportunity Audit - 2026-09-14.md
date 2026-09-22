# Tooling Capability and Efficiency Opportunity Audit - 2026-09-14

**Scope:** What new tools/integrations we should plug into the OpenClaw workspace, and where we can gain real speed and capability.
**Runtime:** OpenClaw 2026.9.4 (3a9d69d), Windows 11, workspace `C:\Users\Veritas\.openclaw\workspace`, branch `operating-procedure-spine`.
**Status:** Review only. Nothing was mutated. Every item below is proposal-stage and needs explicit approval.

---

## Bottom Line

The workspace is not short on skills or scripts — it has 51 workspace skills and 1,490 Python scripts. It is short on **three things**:

1. **Two real context-control gaps — not four.** `tools.toolSearch`, `agents.defaults.contextPruning`, `agents.defaults.compaction`, and `agents.defaults.params.cacheRetention` are all unset in `openclaw.json`, but **unset does not mean inactive**. See the REVISION note below: `compaction.mode` already resolves to `safeguard`, and Anthropic routes already get pruning from a plugin smart default. The genuine gaps are **context pruning on our non-Anthropic primary route** and **prompt caching**. Config-only and reversible.
2. **Zero external tool surface.** `openclaw mcp list` returns nothing. MCP is the mechanism OpenClaw uses to absorb new third-party capability, and we have not adopted it at all. 19 of 65 stock plugins are disabled, including two (`llm-task`, `oc-path`) that directly serve the finance mission at near-zero risk.
3. **Storage has never been garbage-collected.** `tmp/` is **7.1 GB across ~211,000 files**, with contents dating to May 4. The main agent database is **1,605 MB** — 38x the next-largest agent. This is the most plausible source of real turn latency and it is why `git status` reports 536 dirty files.

Fixing #1 is cheap and fast. #2 is where new capability comes from. #3 is where the speed is.

---

## Evidence

Measured live 2026-09-14, not recalled.

| Fact | Value | How verified |
|---|---|---|
| `tools.toolSearch` | **ABSENT** | direct read of `openclaw.json` |
| `agents.defaults.contextPruning` | unset; **active on Anthropic routes** via plugin smart default, **off** on primary Astra route | `config get` + `docs/concepts/session-pruning.md:108-115` |
| `agents.defaults.compaction.mode` | unset but **resolves to `safeguard`** — no action needed | `openclaw config get` |
| `agents.defaults.params` (cacheRetention) | **ABSENT**; Anthropic direct seeded `short` | direct read + `docs/reference/prompt-caching.md:99` |
| `mcp` config block | **ABSENT** | direct read + `openclaw mcp list` |
| `tools.sessions.visibility` | `"all"` | direct read |
| Plugins | 46 enabled / 65 total | `openclaw plugins list --json` |
| `tmp/` size | **7,097 MB** | PowerShell recursive sum |
| Main agent DB | **1,605 MB** | `Get-Item` length |
| `state/openclaw.sqlite` | 186 MB (+ byte-identical 186 MB `.bak-leasefix-20260913`) | `Get-Item` length |
| Always-loaded boot context | 41,103 bytes (~10–11k tokens/turn) | file sizes, 8 files |
| Cron | 44 jobs, 43 ok, 1 error | `openclaw cron list` |
| Git | 536 dirty files | `git status --porcelain` |

Docs consulted: `docs/tools/tool-search.md`, `docs/concepts/session-pruning.md`, `docs/concepts/compaction.md`, `docs/reference/prompt-caching.md`, `docs/tools/mcp.md`, `docs/tools/llm-task.md`, `docs/plugins/*`, `docs/reference/memory-config.md`.

---

## Tier 1 — Context Controls (highest ROI, config-only, reversible)

> ### REVISION 2026-09-14 (same day, before any apply)
>
> While preparing the patch I verified these four keys against the runtime with `openclaw config get` and read the docs line-by-line. **Three of the four original recommendations were wrong or overstated.** Corrected findings:
>
> | Item | Original claim | Verified reality |
> |---|---|---|
> | `compaction.mode` | "absent, should set" | **Already resolves to `safeguard`.** Setting it is a no-op. **Dropped.** |
> | `contextPruning` | "we use none of it" | Anthropic/Claude-CLI routes **already have it** — the bundled Anthropic plugin auto-seeds `cache-ttl` + `ttl 1h`. Gap is **only** the non-Anthropic primary route (`openai/gpt-6-astra`). **Kept, with a trap fix.** |
> | `tools.toolSearch` | "do this first" | **Experimental**; Codex harness runs ignore it entirely. Its value scales with catalog size and we have **zero MCP servers**, so today it is indirection for no gain. **Deferred to bundle with MCP adoption.** |
> | `params.cacheRetention` | "turn on caching" | Correct. Direct Anthropic is seeded `short`; OpenAI gets no explicit marker. **Kept.** |
>
> **The trap:** authoring `contextPruning.mode` stops the Anthropic plugin from seeding its defaults. An unset `ttl` then falls back to **5m**, which is *tighter* than the **1h** Anthropic routes get today — a silent regression. The patch sets `ttl: "1h"` explicitly to prevent this.
>
> Net: the Tier 1 patch is **two keys**, not four. Sections 1.1–1.4 below are kept for the reasoning trail; the revision above governs.

### 1.1 Enable Tool Search — `tools.toolSearch`
**What:** Defers tool schemas until needed instead of loading every schema every turn.
**Why it matters most:** It is also the **precondition** for everything in Tier 2. Adding MCP servers or the `workboard` plugin (~35 tools) without Tool Search will bloat every turn and make the workspace slower, not faster.
**Config:** `tools.toolSearch: true`, or `{mode:"tools", searchDefaultLimit:8, maxSearchLimit:20}`.
**Risk:** Low. A tool the model cannot find is a recoverable miss, not a data risk.
**Doc:** `docs/tools/tool-search.md`.

### 1.2 Enable context pruning — `agents.defaults.contextPruning.mode: "cache-ttl"`
**What:** Server-side clearing of stale tool results on direct Anthropic API routes.
**Why:** Documented as the largest single cost lever. Our long finance/implementation sessions accumulate large tool results that stay resident for the whole session.
**Risk:** Low–moderate. Pruned tool output is gone from context; a session that re-reads its own earlier output will re-read from disk. Worth a canary session before making it default.
**Doc:** `docs/concepts/session-pruning.md`.

### 1.3 Set explicit compaction — `agents.defaults.compaction`
**What:** `{mode, enabled, keepRecentTokens}` (default `keepRecentTokens` 20000).
**Why:** `safeguard` mode is the default for *new* configs; ours predates that and has no explicit block, so behavior is implicit. Long-work sessions are exactly where compaction policy should be deliberate, not inherited.
**Risk:** Low. Setting it explicitly makes current behavior legible.
**Doc:** `docs/concepts/compaction.md`.

### 1.4 Turn on prompt caching — `agents.defaults.params.cacheRetention`
**What:** `none | short | long`, merged global → per-model → per-agent.
**Why:** We re-send 41 KB of boot doctrine (`AGENTS.md` + `SOUL.md` + `USER.md` + `MEMORY.md` + Startup Truth Index + others) on **every single turn**. That is the ideal cache target — large, stable, and repeated.
**Risk:** Low. Cache misses cost nothing but the normal price.
**Doc:** `docs/reference/prompt-caching.md`.

> **Note on the boot set:** 41 KB is reasonable in absolute terms and the prior compaction pass (2026-08-11, 42.4 KB → 30.0 KB) already did the trimming work. The remaining win is **caching** it, not cutting it further. Do not re-run a doctrine-compaction exercise.

---

## Tier 2 — New Tool Surface (where new capability actually comes from)

### 2.1 Adopt MCP — currently zero servers
This is the direct answer to "plug in to keep up with updated capabilities." MCP is how OpenClaw absorbs third-party tools, and we have not started.

**Config shape:** `mcp.servers.<name>` = `{url | command+args+cwd, transport: "stdio"|"sse"|"streamable-http", enabled, connectionTimeoutMs, requestTimeoutMs, toolFilter:{include,exclude}}`.

**Add:** `openclaw mcp add <name> --command node --arg ./server.js --cwd <dir>`
**Then always:** `openclaw mcp doctor <name> --probe` — saving config proves nothing.
**Also available:** `mcp status --verbose`, `mcp probe`, `mcp login`, `mcp reload`, `mcp configure <server> --approval approve|prompt|auto`.

**Discipline this needs, given our mission:**
- Use `toolFilter.include` aggressively. Do not import a server's whole tool surface.
- Set `--approval prompt` for anything that touches network or writes. Our default full-permission posture will **not** prompt otherwise.
- Any MCP server that returns market data is an **evidence source with a freshness obligation**, not an oracle. It enters the same confidence/freshness discipline as every other finance input — it does not get to bypass the alerts-OS gates.

**Ignore mcporter.** `docs/cli/mcp/registry.md:19` is explicit that OpenClaw's `mcp` commands do not read `config/mcporter.json`. No such file exists here and the `mcporter` skill is disabled. Dead path.

**Uncertainty (stated plainly):** the docs are **silent** on measured per-server startup latency. Only `connectionTimeoutMs` exists. So I cannot promise MCP adoption is free — adopt one server, measure, then decide. Do not bulk-add.

### 2.2 Enable `llm-task` — best mission fit on the list
**What:** An isolated, zero-tool, JSON-Schema-validated single LLM call.
**Why:** Deterministic structured extraction from filings, transcripts, and releases — exactly the finance work we currently do with ad-hoc prompting. Schema validation means output is checkable, not vibes.
**Needs two changes:** `plugins.entries.llm-task.enabled: true` **and** `tools.alsoAllow: ["llm-task"]` (our `tools` block has no `alsoAllow` key today).
**Risk:** Low — no transcript, no hooks, no channel delivery.
**Caveat:** nested `openclaw.invoke` from embedded Lobster is documented as unreliable. Call it directly.

### 2.3 Enable `oc-path` — lowest-risk item in this audit
**What:** Byte-preserving addressed reads/writes into md/jsonc/jsonl/yaml via `oc://`.
**Why:** We edit structured workspace files constantly; byte-preservation reduces diff noise and accidental reformatting.
**Risk:** Effectively zero — in-process in the CLI, `onStartup:false`, no network sockets, no Gateway dependency. Costs nothing until invoked.

### 2.4 Enable `policy` — fits the existing governance lane
**What:** Authors `policy.jsonc`; `openclaw policy check` / `doctor --lint` reports drift on tool posture, sandbox posture, MCP posture, gateway exposure, data handling.
**Why:** It makes the boundaries in `SOUL.md`/`AGENTS.md` machine-checkable instead of prose-only. Becomes more valuable the moment we adopt MCP (2.1).
**Important limit:** **config-conformance reporting only — no runtime enforcement.** It does not replace approval gates.
**Risk:** Zero operational risk.

### 2.5 Conditional — worth considering, not yet recommended

| Plugin | Value | Blocker / cost |
|---|---|---|
| `active-memory` | Pre-reply deep recall on recall-intent | **Blocked by our setup:** `memory.search.rememberAcrossConversations` defaults **off** because `session.dmScope` is `per-channel-peer`; must be set `true` explicitly. Adds worst-case `timeoutMs + setupGraceTimeoutMs + 3000ms` of **blocking** latency to replies. Do not enable while chasing speed. |
| `workboard` | Kanban + Gateway-side dispatch, SQLite-backed | Registers ~35 tools. **Only after Tool Search (1.1).** Needs Gateway restart. |
| `onepassword` | SecretRef resolver + audited secret broker | Needs `op` CLI + service-account token file. Relevant given the known inline-Telegram-secret issue, but that is better fixed by `gateway install --force`. |
| `imap` | Email → isolated agent | Real prompt-injection surface. Needs a dedicated restricted agent (`sandbox.mode:"all"`, `workspaceAccess:"none"`, `tools.profile:"minimal"`). Only if we actually want inbound email. |

### 2.6 Explicitly NOT recommended

- **`webhooks`** — despite the promising name, the docs are clear: it creates/advances TaskFlow *records* only, and **"Neither operation starts an agent."** For external event → agent turn we would want Gateway HTTP hooks, not this plugin. Requires network exposure for no gain.
- **`admin-http-rpc`** — shared-secret bearer grants full operator control; `x-openclaw-scopes` is ignored. We have no caller that needs it. Net risk increase.
- **`logbook`** — periodic screen snapshots to a vision model, `captureEnabled` defaults **true** on enable. High privacy cost, no finance value.
- **`beam`** (team session mirroring), **`a2a`/`reef`** (extra inbound channels), **`bonjour`** (mDNS advertising), **`crabbox`** (cloud worker CLI), **`vault`** (we use no HashiCorp), **`migrate-claude`/`migrate-hermes`** (one-time importers), **`openrouter`** (provider already removed — note it currently emits a config warning: disabled but config present; worth cleaning).

---

## Tier 3 — Where the Actual Speed Is

Tier 1 reduces per-turn cost. Tier 3 is what makes the machine feel fast.

### 3.1 `tmp/` is 7.1 GB and ~211,000 files — never garbage-collected
Contents date back to **May 4**. Largest offenders: `tmp\compaction-upstream-20260906` (3,333 MB), `tmp\loop-repair-20260912` (1,140 MB), `tmp\harness-convergence-20260905` (639 MB). It also holds 124 MB of Go build artifacts (`tmp\go-binaries`) and an 84 MB `vector-memory.sqlite` — in a directory named "temporary."

**Impact:** slows every recursive scan in the workspace, and is the main driver of the 536-file dirty git status.
**Proposal:** an age-based retention policy (e.g. 14 days) with an explicit keep-list, run as a cron job.
**Gate:** deletion is destructive and needs approval per `AGENTS.md`. Route through the DB/lifecycle path — `db_lifecycle_manifest.py --write --validate` first, archive/delete only after reference proof and rollback. **Do not bulk-delete.** Some of these directories may hold in-progress lane work.

### 3.2 Main agent DB is 1,605 MB — 38x every other agent
`~\.openclaw\agents\main\agent\openclaw-agent.sqlite` vs implementation-builder (42 MB) and qa-redteam (29 MB).

**Hypothesis, not proof:** vector search and history reads scale with this, so it is the most likely source of real turn latency. I have **not** measured latency attribution to this file — that measurement should come before any maintenance action.
**Known hazard:** per prior findings, a stale `agent_database_leases` row is unreapable on Windows due to an `EPERM` bug, and stopping the gateway does not clear it. Any vacuum/maintenance attempt must account for that or it will fail the same way. The byte-identical `.bak-leasefix-20260913` (186 MB) is an artifact of that episode — do **not** delete it without confirming the lease issue is resolved.

### 3.3 ~750 MB of pure duplication
- `graphify-out` exists three times: `scripts\graphify-out` (334 MB), root `graphify-out` (199 MB), `tmp\merged-graphify-out` (93 MB) — plus a stray `skills\graphify-out` polluting the skills namespace (it is not a skill and should not be there).
- `finance-canon.sqlite` (6.4 MB) has **6 identical copies** in one backup folder, and 40+ more archived.
- `skills\sec\.venv` puts a 108 MB Python virtualenv inside the skills tree — which is why `skills/` reads as 108 MB when the actual instruction content is 250 KB.

None of this is loaded at runtime, so the win is scan speed and legibility, not memory. Low priority but easy.

### 3.4 Memory search tuning (optional)
`memory.search.query.maxResults` (6) and `minScore` (0.35) are at defaults. `memory.search.experimental.sessionMemory` with `sources:["memory","sessions"]` would index transcripts — plausible value, but note `tools.sessions.visibility` is `"all"`, which the 2026-09-06 alignment audit already flagged for tightening to `agent`. **Tighten visibility before widening indexing**, not after.
Confirmed non-options: hybrid/MMR/decay are fixed and non-tunable; `memory.search.sync.watch` does not exist.

---

## What I Am Deliberately Not Re-Recommending

Already implemented — verified in prior audits:
- OTEL collector watchdog cron + Scheduled Task + starvation detector (applied 2026-09-14).
- Main model = Astra with explicit 6-model fallback (2026-09-04).
- `veritas.execution_efficiency_policy.v1` and boot-surface compaction (2026-08-11).
- `disciplined-implementation` merge + `workspace-governor` retargeting (2026-08-31).

Previously declined by the owner — not reopened here:
- New dashboards or a second voice UI (use existing Control UI surfaces).
- `doctor --fix` or broad plugin updates without a scoped diff.
- Skill/doctrine rewrites as a *first* remedy; soft tool-call budget increases.
- Standing unattended code/config mutation authority (`pm-autonomy-policy.json`).
- Automatic model route promotion.

Still open from prior audits and **higher priority than most of this audit** — this document does not supersede them:
1. Preflight harness + finishable-slice dispatch gate (Long Work Orchestration, ranks 1–2).
2. Graphify fixes F1–F9 / E1–E7 — fully diagnosed, unimplemented, with a job failing silently.
3. `tools.sessions.visibility` → `agent`; `gateway install --force` to stop inlining the Telegram secret.
4. Cron hygiene: 9 blocked escalations, 4 expired fleet leases, failureAlert on Graphify `d1f906e9`.

---

## Recommended Sequence

| # | Action | Type | Risk | Gate |
|---|---|---|---|---|
| 1 | Tier 1 patch: `contextPruning {cache-ttl, 1h}` + `params.cacheRetention: long` — dry-run validated | config | low | **awaiting approval** |
| 2 | Enable `oc-path`, `llm-task` (+ `tools.alsoAllow`) | plugin | low | approval |
| 3 | Measure latency attribution of the 1.6 GB agent DB | read-only | none | none |
| 4 | `tmp/` retention policy via lifecycle manifest | destructive | **high** | explicit approval + rollback |
| 5 | Add **one** MCP server + `tools.toolSearch` together, `mcp doctor --probe`, measure | integration | mod | approval |
| 6 | Enable `policy`, author `policy.jsonc` | plugin | none | approval |
| 7 | Dedupe graphify-out / finance-canon copies | destructive | mod | approval |
| — | ~~`agents.defaults.compaction` explicit~~ | — | — | **dropped — already `safeguard`** |

Step 1 is prepared as `config-patch-tier1-20260914.json5` (companion file) and passes `openclaw config patch --dry-run` with 3 validated updates. Step 4 is where the felt speed is, and it is the one that most needs care. Tool Search moved from first to step 5 because it only pays off once there is a catalog to compact.

---

## Honest Limits of This Audit

- I did **not** measure turn latency before/after anything. The claim that the 1.6 GB DB drives latency is a well-supported hypothesis, not proof. Step 9 exists to settle it.
- The docs give **no** measured MCP startup-latency figure. Adopt one server and measure rather than trusting the plan.
- I did not enumerate specific third-party MCP servers worth adopting — that depends on which data gaps you actually feel, and picking them is a separate pass.
- Plugin enablement claims come from the shipped docs at `AppData\Roaming\npm\node_modules\openclaw\docs`. Docs can lag the binary; `mcp doctor --probe` and a canary session are the real proof.
- No capital, trading, account, or execution implication anywhere in this document.
