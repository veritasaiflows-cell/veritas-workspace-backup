# Scripts

Durable repeatable helpers for the finance operating system.

## Rules

- Keep `scripts/` for supported tooling only.
- Keep `tmp/` for generated artifacts and staged render outputs only.
- Default to read-only behavior unless a script intentionally updates vault files.
- Prefer explicit inputs, explicit outputs, and visible freshness or warning states.
- Archive one-off diagnostics, scratch helpers, and superseded planning notes instead of leaving them in the active operator surface.

## Requirements

```bash
pip install yfinance
```

That is the only required dependency for the current supported script surface.

Optional dependencies for richer report generation:
```bash
pip install python-docx pillow
```

## Boundary note

- `scripts/` root remains the stable CLI surface documented across the workspace.
- Selected operator-only implementations now live under `scripts/operators/`.
- Root entrypoints such as `python scripts/apply_band_update.py` are intentionally preserved as thin compatibility wrappers so existing docs and operator habits do not break.
- Do not assume everything in `scripts/` root is chain-active; use `run_finance_refresh_chain.py` as the authoritative chain map.

## Supported active tooling

### `technical_refresh.py`

Status: live

Fetches closing prices and 20/50/200-day moving averages for tracked names, classifies posture, checks entry-band and stop status, and flags near-term earnings-blocked names.

Run:
```bash
python scripts/technical_refresh.py
```

Writes:
- `tmp/technical-refresh.json`

### `market_state_refresh.py`

Status: live

Fetches the core macro and market snapshot used by the operating stack, including SPX, VIX, Treasury context, DXY, energy, futures, sector snapshots, and actionable-name context. Supports partial-success reporting and freshness warnings.

Run:
```bash
python scripts/market_state_refresh.py
```

Writes:
- `tmp/market-state.json`

### `policy_expectations_refresh.py`

Status: live first-version policy layer

Builds the dedicated policy-expectations artifact used to separate Fed-path evidence from general macro narrative. The first version still carries explicit manual dependencies for the current target range and next FOMC date, but it fetches live FedWatch-style futures expectations when available and writes honest warning states when it cannot.

Run:
```bash
python scripts/policy_expectations_refresh.py
```

Writes:
- `tmp/policy-expectations.json`

Notes:
- this is the first dedicated policy layer, not the finished automation state
- the current target range and next FOMC meeting date are still manually maintained in the script until the broader policy workflow is wired
- the meeting distribution is a single-step 25bp approximation from one 30-day Fed Funds futures contract, not a full multi-outcome FedWatch tree

### `credit_spread_refresh.py`

Status: live first-version credit layer

Builds the dedicated credit-spread artifact used to add credit-stress context to regime and deployment work. Primary sourcing uses FRED / ICE BofA OAS series for investment-grade and high-yield spreads. When direct coverage is incomplete, the script degrades honestly into partial status and uses HYG/JNK/LQD proxy behavior to preserve directional context.

Run:
```bash
python scripts/credit_spread_refresh.py
```

Writes:
- `tmp/credit-spreads.json`

Notes:
- direct ICE BofA OAS series can lag by a trading day in FRED
- first version uses heuristic stress-regime thresholds and proxy degradation logic rather than a full credit model
- downstream consumers should treat non-`ok` output as lower-confidence credit state

### `deployment_check.py`

Status: live

Reads cached technical and market-state outputs and produces a ranked deployment-readiness summary with freshness checks.

Run:
```bash
python scripts/deployment_check.py
```

Writes:
- `tmp/deployment-check.json`

### `earnings_calendar_enrichment.py`

Status: live

Refreshes next confirmed earnings dates for the coverage universe and flags watchlist date changes or newly confirmed dates.

Run:
```bash
python scripts/earnings_calendar_enrichment.py
```

Writes:
- `tmp/earnings-calendar.json`

### `trigger_sheet_refresh.py`

Status: live

Builds the machine-readable trigger layer from cached technical, deployment, macro, and earnings artifacts.

Run:
```bash
python scripts/trigger_sheet_refresh.py
```

Writes:
- `tmp/trigger-sheet.json`

### `post_earnings_prep.py`

Status: live

Builds a structured post-earnings interpretation packet from cached trigger, deployment, technical, earnings, and macro artifacts.

Run:
```bash
python scripts/post_earnings_prep.py
```

Writes:
- `tmp/post-earnings-prep.json`

### `post_earnings_note_targets.py`

Status: live

Translates post-earnings packets into selective candidate note updates and update intents.

Run:
```bash
python scripts/post_earnings_note_targets.py
```

Writes:
- `tmp/post-earnings-note-targets.json`

### `band_refresh.py`

Status: live

Reads `tmp/technical-refresh.json` and `tmp/portfolio-config.json` to detect stale or miscalibrated entry bands. For each name with a defined band, computes days since the band was last set, MA20 drift from the band midpoint, price drift from the band midpoint, and ATR-14 from yfinance. Proposes updated bands anchored to current MA structure. Flags `needs_review=true` if a band is more than 7 trading days old or price has moved more than 5% from the band midpoint.

Read-only. Does not modify `portfolio-config.json` or the note layer. All changes require human approval via `apply_band_update.py`.

Run:
```bash
python scripts/band_refresh.py
```

Writes:
- `tmp/band-proposals.json`

Depends on:
- `tmp/technical-refresh.json` (must be fresh)
- `tmp/portfolio-config.json` (must contain `band_last_set` in each entry_bands entry)

Band proposal review workflow:
1. Run `band_refresh.py` - review `tmp/band-proposals.json` for any `needs_review=true` entries
2. If levels look reasonable, run `apply_band_update.py` to apply approved changes
3. Update `03. Portfolio/Technical Entry and Invalidation Sheet.md` using `tmp/band-update-log.txt`

### `apply_band_update.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/apply_band_update.py`
- underlying implementation now lives at `scripts/operators/apply_band_update.py`

Human-gated applier for band proposals generated by `band_refresh.py`. Reads `tmp/band-proposals.json`, presents each `needs_review=true` proposal for confirmation (or accepts all with `--all`), writes approved changes back to `tmp/portfolio-config.json`, and writes a formatted summary to `tmp/band-update-log.txt` for pasting into the Technical Entry and Invalidation Sheet.

Approved updates now stamp `band_last_set` from the proposal/trading data date when available, instead of the current UTC wall-clock date, so Arizona-session note sync does not drift a day ahead.

Never auto-commits without human review unless `--all` is explicitly passed.

Run:
```bash
# Review and confirm each proposal interactively
python scripts/apply_band_update.py

# Apply only specific tickers
python scripts/apply_band_update.py --tickers ETN NVDA

# Preview without writing
python scripts/apply_band_update.py --dry-run

# Accept all needs_review proposals non-interactively
python scripts/apply_band_update.py --all
```

Writes:
- `tmp/portfolio-config.json` (updated entry bands and band_last_set dates)
- `tmp/band-update-log.txt` (formatted note-layer update summary)

After running: use `python scripts/band_note_sync.py` to generate an exact note-sync report, then update `03. Portfolio/Technical Entry and Invalidation Sheet.md` from the helper output and `tmp/band-update-log.txt`.

### `band_note_sync.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/band_note_sync.py`
- underlying implementation now lives at `scripts/operators/band_note_sync.py`

Thin note-sync helper for entry-band upkeep. Compares `tmp/portfolio-config.json` against the canonical `03. Portfolio/Technical Entry and Invalidation Sheet.md` and emits a review report showing exact band/stop lines that need syncing. It does not rewrite the note layer.

Run:
```bash
python scripts/band_note_sync.py
```

Writes:
- `tmp/band-note-sync.md`
- `tmp/band-note-sync.json`

Use this after `apply_band_update.py` or any direct band/config edit when you want a precise note-sync checklist without trusting a silent automatic rewrite. The JSON sidecar is the bounded machine-readable parity surface for workbook/export visibility; it is not permission to rewrite the canonical note layer automatically.

### `generate_dashboard.py`

Status: live

Builds the normalized dashboard payload, computes the delta vs the prior run, runs trust and contradiction checks, and renders the staged dashboard surface from the static template.

Trust rules now enforced in the generator:
- degraded, partial, stale, missing, manual, and unconfirmed inputs must stay visible in payload and UI
- integrity warnings are emitted instead of being silently smoothed away
- business logic for trust, contradictions, compliance checks, and operator warnings lives in Python rather than the template where practical

Run:
```bash
python scripts/generate_dashboard.py
```

Writes:
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/veritas-command-center.html`

Depends on:
- `scripts/dashboard-template.html`
- upstream JSON artifacts in `tmp/`
- `tmp/portfolio-config.json`

### `validate_dashboard_state.py`

Status: live

Runs the dashboard trust and integrity validator without rendering HTML. Use this as the lightweight closure check before trusting the derived dashboard after note, config, or script changes.

Run:
```bash
python scripts/validate_dashboard_state.py --write
```

Optional strict mode:
```bash
python scripts/validate_dashboard_state.py --strict
```

Writes when `--write` is used:
- `tmp/dashboard-validation.json`

Exit codes:
- `0` = no critical issues
- `1` = warnings present in `--strict` mode
- `2` = critical contradictions detected

### `test_dashboard_acceptance.py`

Status: live

Runs the formal dashboard acceptance harness against controlled temporary mutations of the current `tmp/` artifacts, then restores the originals.

Covers:
- missing market field
- partial macro feed
- stale source
- contradiction surfacing
- earnings-date change visibility
- coherent blocker or stop or in-band state transition behavior

Run:
```bash
python scripts/test_dashboard_acceptance.py
```

Writes:
- `tmp/dashboard-acceptance-report.json`

Use this before declaring future dashboard hardening work accepted.

### `equity_visual_report.py`

Status: live reusable report generator

Builds a reusable visual Word report core for a public equity using live market data, analyst context, valuation metrics, real ticker-level annual history when available from yfinance, and auto-generated PNG panels staged in `tmp/`.

Run:
```bash
python scripts/equity_visual_report.py RTX
python scripts/equity_visual_report.py MSFT --out "06. Playbooks\\MSFT Visual Report.docx"
```

Writes:
- `tmp/<ticker>-price-panel.png`
- `tmp/<ticker>-history-panel.png`
- `tmp/<ticker>-visual-report-data.json`
- Word report output path, defaulting to `06. Playbooks/<TICKER> Visual Report - <date>.docx`

Notes:
- this is the reusable report core, not the full company-specific earnings or segment overlay system
- ticker-specific earnings, guidance, and segment panels can be layered on top when curated quarter data exists
- use this when you want a decision-grade visual report shell without rebuilding layout logic each time

### `equity_ppt_report.py`

Status: live generic first-version PowerPoint generator

Builds a PowerPoint deck from the generated visual-report assets and staged JSON payloads.

Run:
```bash
python scripts/equity_ppt_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> Deck - <date>.pptx`

Notes:
- current version now supports a generic deck path for any ticker with generated visual-report assets
- optional ticker-specific overlays such as earnings and segment panels are included automatically when matching PNG assets exist in `tmp/`
- use this when the user wants a presentation rather than a memo or Word report

### `premarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached morning-chain artifacts and produces the daily Pre-Market Snapshot deliverable. Quantitative sections auto-populate; no judgment slots are emitted at this stage - the daily executive brief is the place for narrative.

Run:
```bash
python scripts/premarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
- `tmp/premarket-snapshot.json`

Idempotency:
- If a session-written file already exists at the canonical path, the script writes to `YYYY-MM-DD-machine.md` so the human/agent version takes precedence.
- Re-runs over a machine-owned file overwrite in place.

### `postmarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached post-close artifacts and produces the daily Post-Market Snapshot - day summary, tracked-name day results, what changed since the prior dashboard run, open triggers for tomorrow, and tomorrow's catalysts.

Run:
```bash
python scripts/postmarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-delta.json`
- `tmp/post-earnings-prep.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-validation.json`

Writes:
- `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`
- `tmp/postmarket-snapshot.json`

Idempotency: same session-precedence rule as `premarket_snapshot.py`.

### `daily_executive_brief.py`

Status: live intelligence-layer writer

Generates the autonomous Daily Executive Summary in the established 7-section template. Quantitative sections auto-populate (executive bottom line, execution context, what changed since yesterday, today's catalysts, closest actionable names with dollar/percent gap to band, trigger conditions, recommended actions). Confidence grade is derived from the dashboard validation summary.

Run:
```bash
python scripts/daily_executive_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/post-earnings-prep.json`
- `tmp/dashboard-validation.json`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`
- `tmp/daily-executive-brief.json`

Critical rule: never overwrite a session-written brief. If the canonical file exists and was NOT auto-generated by this script, the script writes to `YYYY-MM-DD-machine.md` so the agent version takes precedence.

### `weekly_macro_snapshot.py`

Status: live intelligence-layer writer

Generates the Weekly Macro Snapshot with 8 sections - regime assessment, Fed and rates, inflation/growth pulse, energy and commodities, FX, geopolitical flags, key events next week, regime posture and portfolio implication. Sections requiring qualitative narrative (inflation/growth detail, geopolitical flags, posture call) are emitted with explicit `_[judgment]_` placeholders.

Run:
```bash
python scripts/weekly_macro_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/regime-scores.json`
- `tmp/earnings-calendar.json`

Writes:
- `02. Markets/Weekly Macro Snapshot/YYYY-Www.md` (ISO week label)
- `tmp/weekly-macro-snapshot.json`

Idempotency: same session-precedence rule. Re-runs over a machine-owned file overwrite in place.

### `weekly_intelligence_brief.py`

Status: live intelligence-layer writer

Appends a structured, machine-populated section to `05. Intelligence/Weekly Intelligence Brief.md`. Mirrors the SOUL-defined 8-section weekly intelligence routine: macro pulse, energy sweep, geopolitical scan, earnings radar, analyst/institutional flow, technical check, sentiment gauge, recommended actions. Sections requiring qualitative interpretation are emitted with `_[judgment]_` placeholders.

Run:
```bash
python scripts/weekly_intelligence_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/earnings-calendar.json`
- `tmp/post-earnings-prep.json`
- `tmp/technical-refresh.json`
- `tmp/regime-scores.json`
- `05. Intelligence/Weekly Intelligence Brief.md` (read for idempotency)

Writes:
- `05. Intelligence/Weekly Intelligence Brief.md` (new section appended)
- `tmp/weekly-intelligence-brief.json`

Idempotency: if the current week's heading is already present in the WIB, the script prints a delta report and does NOT overwrite or duplicate the section. Same pattern as `weekly_review_skeleton.py`.

### `equity_pdf_report.py`

Status: live first-version PDF brief generator

Builds a fixed-layout PDF brief from the generated visual-report JSON and PNG assets.

Run:
```bash
python scripts/equity_pdf_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> PDF Brief - <date>.pdf`

Notes:
- this is the first PDF path for printable/shareable finance briefs
- it reuses the report JSON and generated PNG panels rather than duplicating the full research workflow
- use this when the user wants a clean PDF deliverable instead of Word or PowerPoint

### `positioning_ranking_refresh.py`

Status: live structured ranking artifact builder

Builds `tmp/positioning-ranking.json` as the structured capital-priority source for workbook exports and future positioning surfaces.

Run:
```bash
python scripts/positioning_ranking_refresh.py
```

Reads:
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/regime-scores.json`

Writes:
- `tmp/positioning-ranking.json`

Notes:
- merges regime score totals with deployability context and event risk into one ranking artifact
- intended to replace markdown parsing as the priority-rank source
- now wired into the refresh chains after `trigger_sheet_refresh.py`

### `workbook_export.py`

Status: live workbook export normalizer

Builds workbook-ready CSV exports from the current `tmp/` artifact stack for the minimum-viable Veritas operating workbook.

Run:
```bash
python scripts/workbook_export.py
```

Writes:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Notes:
- normalizes raw machine labels into workbook vocabularies instead of exposing raw JSON states directly
- leaves unavailable fields blank rather than inventing fake precision
- intended to run after validation, not during half-built chains
- consumes `tmp/band-note-sync.json` when present so workbook surfaces can show note-parity gaps like missing technical-note sections without mutating the canonical note
- export manifest now carries per-export checksum, row-count, file-size, and source-freshness metadata so later workbook packaging can detect stray CSV edits instead of trusting `tmp/` blindly
- now wired into the `morning`, `post-close`, `post-earnings`, and `sunday` refresh chains immediately after `validate_dashboard_state.py --write`

### `workbook_template.py`

Status: live first-version workbook generator

Boundary note:
- stays in `scripts/` root because `python scripts/run_finance_refresh_chain.py <window> --build-workbook` can call it as a manual packaging tail

Builds the first `.xlsx` workbook template from the current workbook CSV exports.

Run:
```bash
python scripts/workbook_template.py
```

Manual chain-tail parity path:
```bash
python scripts/run_finance_refresh_chain.py morning --build-workbook
```

Reads:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Writes:
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- `tmp/workbook-build-validation.json`

Notes:
- uses a control-panel sheet plus four filtered operating-table sheets
- includes first-pass conditional formatting for deployable / blocked / stale / priority states
- includes a control-panel legend plus basic date/number formatting for cleaner scanning
- designed as the first workbook template, not a final styled reporting product
- consumes the live export layer rather than parsing raw JSON directly
- validates manifest row counts and SHA-256 checksums before packaging; missing or mismatched export inputs abort the build instead of silently packaging stray CSV state
- surfaces package age and upstream warning-grade status inside the workbook control panel so stale/manual packaging remains visible
- remains an operator-invoked staging package by default; scheduled workbook packaging stays fail-closed until the Workflow 5 trust contract is upgraded explicitly

### `run_finance_refresh_chain.py`

Status: live operating-window runner

Runs explicit refresh chains by operating window instead of treating the whole workflow as one generic pass.

Supported windows:

1. `morning`
   - data spine: `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `premarket_snapshot.py` - writes `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
2. `post-close` (default)
   - data spine: `earnings_calendar_enrichment.py`, `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`, `post_earnings_prep.py`, `post_earnings_note_targets.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `postmarket_snapshot.py` - writes `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`; `daily_executive_brief.py` - writes `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md` (machine-sidecar pattern preserves any session-written brief)
3. `post-earnings`
   - `earnings_calendar_enrichment.py`
   - `post_earnings_prep.py`
   - `post_earnings_note_targets.py`
   - `generate_dashboard.py`
   - `validate_dashboard_state.py --write`
4. `sunday`
   - data spine: full earnings + market + technical + regime score rebuild, plus `weekly_review_skeleton.py`, band, entry-band, deployment, trigger, post-earnings, `call_log_sync.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `weekly_macro_snapshot.py` - writes `02. Markets/Weekly Macro Snapshot/YYYY-Www.md`; `weekly_intelligence_brief.py` - appends a new section to `05. Intelligence/Weekly Intelligence Brief.md` (idempotent on week-heading); plus `postmarket_snapshot.py` and `daily_executive_brief.py` so the Sunday session opens with a primed daily brief as well
5. `full`
   - alias for `post-close` to preserve compatibility with the older one-shot command

Run:
```bash
python scripts/run_finance_refresh_chain.py
python scripts/run_finance_refresh_chain.py morning
python scripts/run_finance_refresh_chain.py post-earnings
python scripts/run_finance_refresh_chain.py --list
python scripts/run_finance_refresh_chain.py morning --dry-run
python scripts/run_finance_refresh_chain.py morning --build-workbook
```

### `dashboard-template.html`

Status: live support file

Static presentation shell consumed by `generate_dashboard.py`. Presentation belongs here, not business logic.

### `prompts/post_earnings_vault_update_v1.md`

Status: live support file

Reusable prompt artifact for the agent-driven post-earnings vault update pass.

## Generated artifact contract

`tmp/` is the machine-artifact surface. Active expected outputs currently include:
- `tmp/technical-refresh.json`
- `tmp/market-state.json`
- `tmp/band-proposals.json` - band staleness proposals from `band_refresh.py`
- `tmp/band-update-log.txt` - formatted note-layer summary from `apply_band_update.py`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/trigger-sheet.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/premarket-snapshot.json` - structured summary from `premarket_snapshot.py`
- `tmp/postmarket-snapshot.json` - structured summary from `postmarket_snapshot.py`
- `tmp/daily-executive-brief.json` - structured summary from `daily_executive_brief.py`
- `tmp/weekly-macro-snapshot.json` - structured summary from `weekly_macro_snapshot.py`
- `tmp/weekly-intelligence-brief.json` - structured summary from `weekly_intelligence_brief.py`
- `tmp/run-summary-morning.json` - workflow-level closure summary for the morning window
- `tmp/run-summary-post-close.json` - workflow-level closure summary for the post-close window
- `tmp/run-summary-post-earnings.json` - workflow-level closure summary for the post-earnings window
- `tmp/run-summary-sunday.json` - workflow-level closure summary for the sunday window
- `tmp/workbook-build-validation.json` - manifest/checksum validation result for workbook packaging

Generated artifacts are evidence and staging surfaces. They do not outrank the canonical note layer.
Report visuals generated into `tmp/` are presentation assets, not canonical research truth by themselves.

`tmp/portfolio-config.json` is the machine-readable portfolio and execution config spine. It now carries tracked-universe policy, yfinance symbol mapping, coverage tiers, workflow semantics, and entry-band metadata. Scripts should read tracked names and execution semantics from this file instead of hardcoding local universe lists or band maps.

## Operating-window sequence

Use the chain that matches the real decision window.

The refresh runner is now the default orchestration entrypoint. Prefer it over manually calling long script sequences in cron prompts or ad hoc operator instructions.

Workbook packaging rule:
- default chain runs stop at `workbook_export.py`
- add `--build-workbook` only when you intentionally want a manual staging workbook package after the export layer is fresh
- leaving the flag off preserves the current fail-closed posture for scheduled workbook packaging

### Morning readiness

Use before the session or pre-open when the goal is to read the current board, not rebuild every catalyst workflow.

```bash
python scripts/run_finance_refresh_chain.py morning
```

### Post-close refresh

Use after the close as the default full rebuild for the next session. This is the main convenience path.

```bash
python scripts/run_finance_refresh_chain.py post-close
```

This refreshes the earnings-date layer before trigger generation, then stages post-earnings prep and note-target artifacts so they are not left to memory.

### Post-earnings refresh

Use after a material company report lands when the close-level artifacts already exist and the main need is closure-state follow-up.

```bash
python scripts/run_finance_refresh_chain.py post-earnings
```

### Sunday weekly rebuild

Use once on Sunday to fully prime the next week - full earnings + market + technical + regime score rebuild, weekly positioning review scaffold, weekly macro snapshot, weekly intelligence brief append, and a primed daily executive brief. Designed so the Sunday weekly review session opens against a complete artifact set.

```bash
python scripts/run_finance_refresh_chain.py sunday
```

### Validation placement

`generate_dashboard.py` still emits the inline validation payload used by the dashboard, but the independent closure check now belongs at the end of each operating-window chain:

```bash
python scripts/validate_dashboard_state.py --write
```

That final validator run is the last trust gate before the derived dashboard is treated as decision support.

Scheduled-window closure now has one more layer after validation:
- `run_summary_refresh.py --window <window>` writes the machine-readable workflow summary
- `dashboard_run_summary_consumer.py --window <window>` propagates that trust state into the command center payload and rendered HTML

This keeps stop lines, missing required outputs, and fallback/manual dependencies visible instead of letting a rendered dashboard fake success.

### Operator rule

If a workflow needs more than one artifact-refresh script in sequence, default to `run_finance_refresh_chain.py` unless there is a concrete reason to run a narrower step directly.

## Governance note

The active operator surface above is intentionally narrow. Temporary diagnostics, scratch helpers, historical raw dumps, and superseded implementation plans belong in archive if they still matter, not in `scripts/` or `tmp/`.
