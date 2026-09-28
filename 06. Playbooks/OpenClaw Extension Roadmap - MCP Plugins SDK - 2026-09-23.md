# OpenClaw Extension Roadmap - MCP Plugins SDK - 2026-09-23

- **Status (reconciled 2026-09-27):** Extension roadmap and historical decision record. The approved local `veritas-data` MCP server is installed and registered with seven allowlisted read-only tools; further expansion remains proposal-only. This note grants no new approval for config, plugin, credential, or runtime changes.
- **Initial owner decision (2026-09-23):** Randall selected "Roadmap doc only" at creation; later that day he approved the own-server path (see the dated decision log). The initial zero-install decision is historical, not current status.
- **Current expansion owner:** [Veritas MCP Expansion Continuity Plan - 2026-09-27](<Project Continuity/Veritas MCP Expansion Continuity Plan - 2026-09-27.md>) owns expansion sequencing, trust gaps, acceptance gates, and next actions. This roadmap retains the broader extension options and dated decisions.
- **Version anchor:** OpenClaw 2026.9.4 (3a9d69d), Windows native, gateway `RQs_Business`.
- **Sources:** shipped docs at `C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw\docs` - `tools/mcp.md`, `cli/mcp.md`, `cli/mcp/registry.md`, `plugins/manage-plugins.md`, `plugins/plugin-inventory.md`, `plugins/sdk-overview.md`, `gateway/external-apps.md`. Registry command syntax rechecked against installed 2026.9.4 docs on 2026-09-27; re-verify at execution time because updates may move surfaces.

## 1. Current state (reconciled 2026-09-27)

- **MCP servers: 1 configured and enabled.** Read-only config inspection on 2026-09-27 confirms local stdio `veritas-data` with exactly seven names in `toolFilter.include`: `get_reference_band`, `get_thesis`, `get_recommendation_funnel`, `get_thesis_review`, `get_gap_repair_report`, `get_weekly_renewal_packet`, and `verify_alert_ledger`.
- **Implementation and proof:** `scripts/veritas_mcp_server.py`, official Python MCP SDK `mcp` 1.30.0. The current expansion owner records same-day standalone doctor/probe success and an earlier 22-test passing baseline. This documentation correction did not rerun probes or tests; registration and read-only hints do not prove complete freshness, lineage, or access-control guarantees.
- **Acceptance limits:** The original three-consecutive-day probe record is incomplete for 2026-09-24/25. Expansion is not implemented; current reliability gaps and the next proposal-only action belong to the expansion continuity plan, not the original phase order below.
- **Custom SDK plugins / external MCP exposure:** The 2026-09-27 expansion review records no custom Veritas Plugin SDK package and no MCP endpoint exposed outside the local workspace.

**Historical baseline (measured at roadmap creation, 2026-09-23; not a current inventory):**

- **MCP servers: 0 configured at that time.** `openclaw mcp status --verbose` returned "No MCP servers configured" before the later approved installation.
- **Plugins enabled: 16 bundled at that time** - anthropic, codex, diagnostics-otel, memory-core, ollama, openai, telegram, google, microsoft, memory-wiki, kimi, meta, browser, xai, zai, opencode-go. `plugins.deny: [openrouter]`. No external packages were installed at that measurement; plugin inventory was not re-audited for this documentation correction.

## 2. The three extension surfaces

### Surface A - MCP servers (borrow tools from other programs)

An MCP server is an external program that exposes tools (data retrieval, docs lookup, database queries). OpenClaw connects to it and its tools appear alongside built-in agent tools.

- Transports: stdio (local command), SSE, Streamable HTTP (remote). OAuth supported via `openclaw mcp login`.
- Key fact: MCP tools go through the same tool-profile and tool-policy controls as everything else. Connecting a server does not bypass our guardrails.
- `toolFilter.include` and `toolFilter.exclude` control which of a server's tools actually reach agents.
- Definitions live under `mcp.servers` in config; changes hot-reload; verify reachability with `openclaw mcp doctor <name> --probe` (saving a definition proves nothing - the probe does).
- Reverse direction: `openclaw mcp serve` exposes OpenClaw conversations TO other MCP clients (see Surface C).

### Surface B - Plugins (install packaged capabilities)

Shipped inventory (2026.9.4): 59 plugins bundled in core, 91 official external packages, 3 source-only.

- Install: `openclaw plugins install clawhub:<pkg>` (or `npm:`, `git:`, local path, `npm-pack:`). Third-party code triggers a capability-consent review; installs restart the Gateway (managed gateway auto-restarts).
- Enable/disable is config-only and can be hot; code changes are not.
- Relevant external candidates for us (not endorsements - vet before install):
  - **Efficiency:** `tokenjuice` (compacts exec/tool results), `diffs` (read-only diff viewer).
  - **Search providers:** brave, tavily, exa, perplexity, searxng, firecrawl, duckduckgo, parallel. We already have built-in `web_search`/`web_fetch`; only add if builtins prove insufficient.
  - **Memory:** `memory-lancedb` (vector long-term memory). We already run memory-core + memory-wiki; adding this is a capability decision, not an obvious win.
  - **Observability:** `diagnostics-prometheus` (OTEL exporter already enabled).
  - **Channels:** slack, discord, whatsapp, signal, etc. Only on real need; every channel is exposure. The Telegram owner-allowlisted exception does not authorize channel expansion.

### Surface C - SDK + outbound APIs (build our own; expose Veritas outward)

Two distinct build paths:

1. **Plugin SDK** - typed contract (`openclaw/plugin-sdk/*`) for packaging our own capabilities: agent tools, custom commands, providers, channels, hooks, HTTP routes, Gateway methods, widgets. All plugin APIs are **experimental** - pin to our OpenClaw version, test every host upgrade, never assume a build supports future releases.
2. **Gateway integrations for external apps** - the "build the future" lever. `openclaw mcp serve` makes Veritas an MCP server for any MCP-capable client (IDEs, other agents); Gateway HTTP APIs (`docs/gateway/external-apps.md`, `openai-http-api.md`, `openresponses-http-api.md`) let external apps, scripts, dashboards, and CI run agents through our Gateway. Our workspace becomes a backend other AI tools can call - the strategic direction for "future of AI" work.

Publishing to ClawHub/npm exists if we ever want to distribute; not a current goal.

## 3. Phased plan (each phase gated on Randall's explicit approval)

These are the original extension proposals, retained for history and future options, not the current MCP execution queue. The later own-server decision changed the order; the linked expansion continuity plan now owns MCP sequencing and next actions. No proposal or documented rollback command authorizes execution.

### Phase 1 - First MCP server pilot: docs retrieval (lowest risk, highest leverage)

Goal: one remote docs-retrieval MCP server so any agent turn can pull current library/framework docs - direct fuel for SDK/plugin building.

1. Verify the candidate server's current endpoint, tool names, and auth model against its live docs at execution time (do not trust a stale list).
2. Add with a narrow tool filter, e.g. `openclaw mcp add <name> --url <endpoint> --transport streamable-http --include '<tool-allowlist>'`.
3. Verify: `openclaw mcp doctor <name> --probe` lists exactly the expected tools.
4. Confirm tool-policy posture: tools visible but policy-gated; per-session denial available via Control UI `+ -> Connectors -> Tool access`.
5. Rollback, only with explicit approval: `openclaw mcp unset <name>` removes the saved server definition (not installed dependencies); alternatively, `enabled: false` keeps the definition but excludes it from embedded runtime discovery.

Success criteria: probe green 3 consecutive days; at least one real task used the tools; zero policy surprises.

### Phase 2 - Vetted finance data MCP + efficiency plugins

Goal: extend the alerts/research evidence base without weakening security.

- Finance MCP vetting scorecard (before ANY install): maintainer identity + release activity + issue health; auth model (keyless/read-only first; credentials via secret store, never config literals); read-only tools first; toolFilter allowlist limited to what the alerts chain actually needs; probe-green 3 days before wiring into any workflow. Candidates to score at execution time: SEC EDGAR-style, market-data community servers - score, don't assume.
- `tokenjuice` if context waste is measurable after Phase 1 (official catalog, consent-reviewed).
- Search-provider plugin only if builtin search demonstrably fails a recurring task.

**Phase 2 finance-MCP candidate shortlist (researched 2026-09-23 via live web search; re-verify maintenance state at install time):**

| Candidate | Data | Traction (measured 09-23) | Auth | Verdict per scorecard |
|---|---|---|---|---|
| `narumiruna/yfinance-mcp` | Yahoo quotes, OHLCV, dividends, splits, earnings dates, analyst recs, options | 182 stars, 67 forks, MIT, since 2025-03 | keyless | Best first pilot: free, read-only, matches our existing Yahoo data family. Risks: single maintainer; Yahoo endpoint fragility (we hit Yahoo nulls 09-22/23) |
| `alphavantage/alpha_vantage_mcp` (official vendor repo) | quotes, fundamentals, FX, indicators, earnings | 206 stars, MIT, vendor org since 2025-07 | API key; free tier heavily rate-limited, real 32-name use likely needs paid tier | Strong second: vendor-backed maintenance, best data quality posture. Key via secret store only; remote HTTP at mcp.alphavantage.co or stdio |
| `birthday-tools/edgarmcp` (pypi `mcp-edgar`) | SEC EDGAR filings/fundamentals/insider trades, FRED, ETF/index data | beta, ~0 stars | keyless | Data is exactly the thesis-evidence gap (14/32 names lack thesis) but packaging too young to install per scorecard; revisit, or build a thin EDGAR reader in Phase 3 |
| FRED macro servers (`US-Macro-MCP`, `fred-mcp-server`) | 58 US macro indicators, FOMC calendar | ~0 stars each | FRED key (free) | Same: too young now; macro spine could adopt a vetted FRED source later |

Notes: the official MCP registry (registry.modelcontextprotocol.io) is still in preview with no canonical finance catalog - manual scorecard vetting stays mandatory. Stdio servers execute third-party code on the gateway host; small-repo installs stay blocked by the scorecard. Remote HTTP servers (Alpha Vantage) avoid local code but send queries + key to the vendor - acceptable for public market data. None of these touch capital/execution; all are read-only research evidence and never canon authority.

### Phase 3 - Build-out

Goal: from consumer to builder.

1. **First SDK plugin:** package ONE proven, stable, read-only workspace capability (thin wrapper over an already-proven script). Never start with anything finance-canon-touching or capital-adjacent. Pin SDK to current OpenClaw version; compatibility-test on every gateway update.
2. **Outbound exposure:** pilot `openclaw mcp serve` so Randall's other MCP-capable tools can call Veritas sessions; evaluate Gateway HTTP APIs for external app/dashboard work.
3. Reassess: second plugin only after the first survives one OpenClaw update cycle.

## 4. Guardrails that never move

- Every install/enable/config/credential change needs Randall's explicit approval first (SOUL.md hard boundary; ask_user choice counts when specific).
- Third-party plugins: capability-consent review is not optional; prefer official catalog sources (`clawhub:`/verified first-party).
- Secrets go in the secret store, never config literals.
- MCP/plugin tools never bypass tool policy, exec approvals, or finance authority boundaries.
- Plugin code installs restart the Gateway - schedule around active runs (alert windows, cron proof windows).
- SDK is experimental: pin, test, and expect migrations between OpenClaw releases.

## 5. Decision log

Editorial note (2026-09-27): dated decisions and measured outcomes below are preserved. Rollback command spelling is corrected from the originally written `remove` to the installed docs' `unset`; this is a documentation correction, not a rollback or renewed approval.

- **2026-09-23:** Roadmap created from shipped docs + live config evidence. Randall chose "Roadmap doc only" - zero installs. Next action when ready: approve Phase 1 docs-MCP pilot.
- **2026-09-23 ~20:30 MST, Main review (Randall asked to review the five dashboard sessions' MCP/plugin/SDK recommendations):**
  - **Third-party finance MCPs: do not install now.** `yfinance-mcp` duplicates the in-house Yahoo pipeline and the installed `yfinance` 1.3.0 behind third-party stdio code (star counts in the shortlist were not independently verified). Alpha Vantage reverses the Yahoo-only cost decision and its free tier is too thin. The EDGAR and FRED packagings fail the scorecard, and the premise that we lack EDGAR is wrong: `fundamental_metrics_refresh.py` and related scripts already read SEC companyfacts. The real fundamentals gap was a dead dependency on the retired `tmp/portfolio-config.json`, fixed 2026-09-23; a weekly fundamentals + thesis review cron now exists.
  - **Build our own read-only MCP server first (recommended Phase 3 step 1, ahead of the Plugin SDK).** `veritas-data`: stdio, our code only, official Python MCP SDK, exposing typed read-only tools over existing proven artifacts: bands/confidence for a ticker (guarded SQL read), thesis record, recommendation funnel, thesis review flags, gap-repair report, weekly renewal packet, ledger verify. Value: isolated helper agents (claude-cli children have MCP tools but no filesystem) and dashboard sessions get the same evidence with argument validation, without shell. Why before the Plugin SDK: stable protocol, runs out-of-process (no Gateway restart, no in-gateway host trust), no experimental API; it can be wrapped as a plugin later if needed.
  - Needs owner approval: `pip install mcp` (new host dependency) and `openclaw mcp add veritas-data ... --include <tool list>` (config change), then `openclaw mcp doctor veritas-data --probe` and a 3-day green window. Rollback: `openclaw mcp unset veritas-data`.
  - Phase 1 docs-retrieval MCP: low priority; OpenClaw docs are already local. `openclaw mcp serve` and Active Memory: defer until there is a concrete consumer or measured need.
- **2026-09-23 ~21:05 MST:** Randall approved the own-server path. `veritas-data` built (`scripts/veritas_mcp_server.py`, official Python MCP SDK `mcp` 1.30.0), 7 read-only tools with readOnlyHint annotations, 8 tests; registered via `openclaw mcp add veritas-data` with an include allowlist; `openclaw mcp doctor veritas-data --probe` ok. Config preimage `tmp/openclaw.json.pre-veritas-mcp-20260923`. 3-day green window ends 2026-09-26. Rollback: `openclaw mcp unset veritas-data`.
- **2026-09-27, documentation reconciliation:** Reconciled the opening status with the approved installation and current seven-tool registration, separated the original inventory from current evidence, corrected registry syntax, and linked the current expansion owner. No rollback, MCP/runtime/config change, or installation was performed.
