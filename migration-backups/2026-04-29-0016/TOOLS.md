# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics, the stuff that's unique to your setup.

## Local setup

### Model routing

### OpenClaw config posture

- Bundled skills should be explicitly allowlisted instead of left wide open after resets or reinstalls
- Current intended bundled-skill allowlist is: `github`, `healthcheck`, `node-connect`, `skill-creator`, `taskflow`, `taskflow-inbox-triage`, and `weather`
- Workspace custom finance skills remain the primary operating layer; bundled skills should stay narrow and mission-relevant
- Remove stale or ineffective `gateway.nodes.denyCommands` entries rather than keeping a false security signal; if node-command restrictions are needed later, re-add only exact supported command IDs
- `temp-skill-inspect/` is scratch inspection material, not an active skill root, and should not be treated as part of the live skill surface

- Primary model for new sessions: `openai-codex/gpt-5.4`
- Primary model for spawned sub-sessions: `openai-codex/gpt-5.4`
- Use OpenAI Codex OAuth-backed routing by default
- Treat `openai-codex/gpt-5.4` as the only active model in core workspace guidance
- Do not assume `openai/gpt-5.4` works unless `OPENAI_API_KEY` is intentionally configured, and do not keep alternate active-model guidance in core files

### Obsidian

- Obsidian vault: workspace root (`C:\Users\Veritas2.0\.openclaw\workspace`)
- Read `TOOLS.md` at the start of every new session along with the main startup stack so local setup, active skill stack, and environment-specific rules are always loaded before work begins
- Never register `.obsidian/` itself as a vault
- Home note: `Home.md`
- Continuity protocol: `Continuity Protocol.md`
- Daily notes folder: `memory/`
- Long-term memory note: `MEMORY.md`
- No active root `templates/` directory right now. Legacy templates were archived to `09. Archive/Templates - Archived/`. Recreate `templates/` only when active finance-first templates actually exist.

### Finance operating defaults

### Veritas finance skill stack

Core custom skills now in the workspace:
- `skills/veritas-fundamental-pass/SKILL.md`
  - use for business quality, balance-sheet safety, cash-flow durability, valuation discipline, and peer ranking
- `skills/veritas-technical-pass/SKILL.md`
  - use for support, resistance, moving-average posture, entry bands, invalidation, and the four-state technical model: Deployable, Blocked, Repair mode, Watch-only
- `skills/veritas-macro-pass/SKILL.md`
  - use for macro regime, rates/inflation/growth posture, evidence-quality disclosure, and portfolio implications
- `skills/veritas-positioning-pass/SKILL.md`
  - use to translate macro, fundamentals, technicals, and risk rules into portfolio actions like add, prepare, hold, trim, bench, or avoid
- `skills/veritas-self-improvement/SKILL.md`
  - use for reflection, correction capture, routing lessons into the correct canonical files, and deciding when new scripts, validators, or skills should exist
- `skills/veritas-investment-deck/SKILL.md`
  - use to convert equity reports and research notes into presentation-ready slide structure with decision-first logic, readable hierarchy, and portfolio-relevant conclusions
- `skills/veritas-pdf-brief/SKILL.md`
  - use to convert report assets into printable fixed-layout PDF briefs without turning them into bloated slideware or raw note dumps

Working rule:
- for serious finance work, prefer the Veritas skill stack over generic third-party finance skills unless Randall explicitly wants inspection or comparison work
- use fundamentals to decide whether a business belongs on the serious board
- use technicals to decide whether the setup is disciplined enough to act on
- use macro to decide whether the broader regime supports or tempers the idea
- use positioning to convert the three analytical layers into portfolio decisions

- Read-only posture for any brokerage, exchange, or portfolio system
- Never execute trades, transfers, or account changes through OpenClaw
- Prefer reliable primary sources: company filings, central bank releases, government data, reputable financial media, exchange data
- Cross-check important market views across multiple sources before treating them as decision-grade
- Do not install unaudited third-party skills for finance workflows without Randall's approval
- Treat speculative assets, especially crypto and leveraged products, as high-risk domains requiring explicit caution
- Treat `tmp/market-state.json` as the macro-readiness source of truth for briefs and command views; if it is partial or warning-heavy, downgrade confidence explicitly
- Treat futures snapshots and latest live cash snapshots as execution context only; do not label them true pre-market data unless the source actually provides `pre_market_price`
- For action-oriented morning work, the top execution context tickers currently wired into `market_state_refresh.py` are `ETN`, `JPM`, and `NVDA`, and the sector snapshot set is `XLI`, `XLF`, `XLK`, `XLE`
- Current finance automation stack beyond the base refresh scripts:
  - `python scripts/trigger_sheet_refresh.py` → writes `tmp/trigger-sheet.json`
  - `python scripts/post_earnings_prep.py` → writes `tmp/post-earnings-prep.json`
  - `python scripts/post_earnings_note_targets.py` → writes `tmp/post-earnings-note-targets.json`
  - `python scripts/generate_dashboard.py` → writes `tmp/dashboard-data.json`, `tmp/dashboard-delta.json`, `tmp/dashboard-validation.json`, and `tmp/veritas-command-center.html`
  - `python scripts/validate_dashboard_state.py --write` → validates dashboard trust/integrity state and refreshes `tmp/dashboard-validation.json`
  - `python scripts/equity_visual_report.py <TICKER>` → writes reusable Word-report assets, including `tmp/<ticker>-price-panel.png`, `tmp/<ticker>-history-panel.png`, and `tmp/<ticker>-visual-report-data.json`
  - `python scripts/equity_ppt_report.py <TICKER>` → writes `06. Playbooks/<TICKER> Deck - <date>.pptx`
  - `python scripts/equity_pdf_report.py <TICKER>` → writes `06. Playbooks/<TICKER> PDF Brief - <date>.pdf`
- Rendered dashboard path: `tmp/veritas-command-center.html` (generated surface, not canonical note content)
- Dashboard trust rule: if `tmp/dashboard-validation.json` or the payload shows manual, unconfirmed, partial, stale, or missing upstream dependencies, treat the dashboard as degraded orientation only, not clean execution truth
- Working rule: scripts prepare hard data, trigger buckets, validation warnings, reusable report visuals, and candidate note targets; final interpretation, recommendation, and selective note edits stay agent-driven
- Multi-format deliverables should share one staged data and visual core, with separate renderers for Word, PowerPoint, and PDF instead of one-off document logic per format
- Real ticker-level annual history should come from live financial statements when available. Do not present placeholder EPS or revenue history in deliverables once a reusable workflow exists

## What Goes Here

Things like:

- approved data source preferences
- brokerage/platform names for read-only review
- finance dashboard links
- SSH hosts and aliases
- preferred voices for TTS
- device nicknames
- anything environment-specific

## Web chat response style

- In web chat, prefer highly readable formatting with short sections, **bold labels**, bullets, and sparse useful emojis.
- Do not overuse giant tables in chat replies when bullets are clearer.
- Default startup/status replies should be scannable in under 20 seconds.
- Use emoji only to improve scanability, not decoration spam.

## Browser capability note

- The built-in browser tool is the primary browser/search capability.
- Treat browser readiness as separate from skill availability.
- Verify browser status before assuming live chart or web UI inspection is available.
- If browser is installed but not running, start it rather than claiming browser work is blocked.

## Subagent spawn cheat sheet

Use this default pattern for detached OpenClaw subagent work:
- `runtime: "subagent"`
- `agentId: "main"` unless `agents_list` shows another allowed id
- `model: "openai-codex/gpt-5.4"`
- `thinking: "medium"`
- `mode: "run"` for one-shot detached work
- `sandbox: "inherit"` unless isolation is specifically needed
- `cleanup: "keep"` when you may want to inspect the child result later

Common mistakes to avoid:
- using the model name as `agentId`
- passing `streamTo` to `runtime: "subagent"`
- assuming spawned work failed just because the first spawn call had bad parameters

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
