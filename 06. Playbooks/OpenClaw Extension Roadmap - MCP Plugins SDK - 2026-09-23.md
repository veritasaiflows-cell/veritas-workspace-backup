# OpenClaw Extension Roadmap - MCP Plugins SDK - 2026-09-23

- **Status:** Roadmap / proposal. Nothing installed or enabled by this note. Every phase gate below requires Randall's explicit approval before any config, plugin, credential, or runtime change.
- **Owner decision (2026-09-23):** Randall selected "Roadmap doc only" - no MCP servers, plugins, or SDK work started today.
- **Version anchor:** OpenClaw 2026.9.4 (3a9d69d), Windows native, gateway `RQs_Business`.
- **Sources:** shipped docs at `C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw\docs` - `tools/mcp.md`, `cli/mcp.md`, `plugins/manage-plugins.md`, `plugins/plugin-inventory.md`, `plugins/sdk-overview.md`, `gateway/external-apps.md`. Re-verify against current docs at execution time; OpenClaw updates may move surfaces.

## 1. Current state (measured 2026-09-23)

- **MCP servers: 0 configured.** `openclaw mcp status --verbose` -> "No MCP servers configured". The entire MCP surface is greenfield.
- **Plugins enabled: 16 bundled** - anthropic, codex, diagnostics-otel, memory-core, ollama, openai, telegram, google, microsoft, memory-wiki, kimi, meta, browser, xai, zai, opencode-go. `plugins.deny: [openrouter]`. No external packages installed.
- **Custom SDK plugins: none.** Nothing we have built ships as a plugin package.

## 2. The three extension surfaces

### Surface A - MCP servers (borrow tools from other programs)

An MCP server is an external program that exposes tools (data retrieval, docs lookup, database queries). OpenClaw connects to it and its tools appear alongside built-in agent tools.

- Transports: stdio (local command), SSE, Streamable HTTP (remote). OAuth supported via `openclaw mcp login`.
- Key fact: MCP tools go through the same tool-profile and tool-policy controls as everything else. Connecting a server does not bypass our guardrails.
- `toolFilter` include/expose controls which of a server's tools actually reach agents.
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

### Phase 1 - First MCP server pilot: docs retrieval (lowest risk, highest leverage)

Goal: one remote docs-retrieval MCP server so any agent turn can pull current library/framework docs - direct fuel for SDK/plugin building.

1. Verify the candidate server's current endpoint, tool names, and auth model against its live docs at execution time (do not trust a stale list).
2. Add with a narrow tool filter, e.g. `openclaw mcp add <name> --url <endpoint> --transport streamable-http --include '<tool-allowlist>`.
3. Verify: `openclaw mcp doctor <name> --probe` lists exactly the expected tools.
4. Confirm tool-policy posture: tools visible but policy-gated; per-session denial available via Control UI `+ -> Connectors -> Tool access`.
5. Rollback: `openclaw mcp remove <name>` (or disable to keep the definition).

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

- **2026-09-23:** Roadmap created from shipped docs + live config evidence. Randall chose "Roadmap doc only" - zero installs. Next action when ready: approve Phase 1 docs-MCP pilot.
- **2026-09-23 ~20:30 MST, Main review (Randall asked to review the five dashboard sessions' MCP/plugin/SDK recommendations):**
  - **Third-party finance MCPs: do not install now.** `yfinance-mcp` duplicates the in-house Yahoo pipeline and the installed `yfinance` 1.3.0 behind third-party stdio code (star counts in the shortlist were not independently verified). Alpha Vantage reverses the Yahoo-only cost decision and its free tier is too thin. The EDGAR and FRED packagings fail the scorecard, and the premise that we lack EDGAR is wrong: `fundamental_metrics_refresh.py` and related scripts already read SEC companyfacts. The real fundamentals gap was a dead dependency on the retired `tmp/portfolio-config.json`, fixed 2026-09-23; a weekly fundamentals + thesis review cron now exists.
  - **Build our own read-only MCP server first (recommended Phase 3 step 1, ahead of the Plugin SDK).** `veritas-data`: stdio, our code only, official Python MCP SDK, exposing typed read-only tools over existing proven artifacts: bands/confidence for a ticker (guarded SQL read), thesis record, recommendation funnel, thesis review flags, gap-repair report, weekly renewal packet, ledger verify. Value: isolated helper agents (claude-cli children have MCP tools but no filesystem) and dashboard sessions get the same evidence with argument validation, without shell. Why before the Plugin SDK: stable protocol, runs out-of-process (no Gateway restart, no in-gateway host trust), no experimental API; it can be wrapped as a plugin later if needed.
  - Needs owner approval: `pip install mcp` (new host dependency) and `openclaw mcp add veritas-data ... --include <tool list>` (config change), then `openclaw mcp doctor veritas-data --probe` and a 3-day green window. Rollback: `openclaw mcp remove veritas-data`.
  - Phase 1 docs-retrieval MCP: low priority; OpenClaw docs are already local. `openclaw mcp serve` and Active Memory: defer until there is a concrete consumer or measured need.
- **2026-09-23 ~21:05 MST:** Randall approved the own-server path. `veritas-data` built (`scripts/veritas_mcp_server.py`, official Python MCP SDK `mcp` 1.30.0), 7 read-only tools with readOnlyHint annotations, 8 tests; registered via `openclaw mcp add veritas-data` with an include allowlist; `openclaw mcp doctor veritas-data --probe` ok. Config preimage `tmp/openclaw.json.pre-veritas-mcp-20260923`. 3-day green window ends 2026-09-26. Rollback: `openclaw mcp remove veritas-data`.
