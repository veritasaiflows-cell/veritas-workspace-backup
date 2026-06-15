# Operating Model

## Purpose

This note is the finance operating system control plane.
It defines layer boundaries, source-of-truth rules, operating windows, validation gates, and current data-coverage limits.

Identity, mission, safety boundaries, and recommendation standards belong in `SOUL.md`, `AGENTS.md`, `USER.md`, `MEMORY.md`, and the finance skills.

## Design objective

Build a decision-grade investment research OS that aims for maximum **risk-adjusted** returns inside the risk envelope defined by the canonical risk layer.

Operating standard:
- no surface outranks the evidence beneath it
- no generated summary becomes canonical by looking polished
- no output layer should grow faster than the data and validation spine that supports it

## Execution ownership posture

- Veritas main session is Randall's live financial truth surface: it interprets the workspace file layer as the durable canonical financial database, reconciles evidence, and makes final judgment traceable.
- Veritas is the orchestrator, auditor, and product owner/manager (PoM) for the operating system.
- Queue movement, categorization, delegation, and final integration stay with Veritas.
- Substantial work expected to exceed roughly five minutes, touch multiple artifacts, require broad inspection, or need independent QA should default to a spawned `openai-codex/gpt-5.5` high-thinking helper lane with file-grounded context; the main session should stay with orchestration, QC, quick bounded fixes, and final merge work.
- When a helper lane finishes, the main session checks the live queue, integrates proof, and either spawns the next safe helper, completes the next quick bounded task, records a real blocker, or asks Randall a concrete question when direction is ambiguous.
- Claude CLI and Gemini Flash are standby parallel lanes for judgment-heavy review and bounded audit work when the contract is explicit.
- Research, audit/QA, and workbook/packaging work are the first parallel categories to open when ownership boundaries are clean.
- Parallel execution should accelerate evidence gathering and verification, not dilute final judgment ownership.

## Canonical layer map

### 1. Orientation surfaces
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`
- `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
- `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`

These are derived operating surfaces. They summarize upstream truth and current readiness.

### 2. Intelligence layer
- `05. Intelligence/Weekly Positioning Review.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Event Calendar.md`
- `02. Markets/Weekly Macro Snapshot/YYYY-Www.md`

This layer interprets the market week, catalyst map, and macro regime.

### 3. Portfolio decision layer
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `03. Portfolio/Execution Board.md`

This layer owns posture, deployability, and execution discipline.

### 4. Risk layer
- `07. Risk/Risk Rules.md`

This is the canonical risk envelope, sizing discipline, and escalation layer.

### 5. Machine evidence layer
- `tmp/portfolio-config.json`
- `tmp/market-state.json`
- `tmp/technical-refresh.json`
- `tmp/earnings-calendar.json`
- `tmp/deployment-check.json`
- `tmp/trigger-sheet.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `tmp/dashboard-validation.json`
- related `tmp/*.json` support artifacts

This layer is machine-readable evidence and staging, not final judgment.

### 6. Orchestration layer
- `scripts/run_finance_refresh_chain.py`
- supporting scripts in `scripts/`
- finance skills in `skills/`

This layer refreshes evidence and derived surfaces. It should stay procedural so the note layer can stay judgmental.

Boundary rule:
- canonical notes decide
- machine artifacts inform
- validators prove or challenge
- dashboards summarize
- scripts orchestrate
- Active Workflows owns live workflow state
- workflow continuity notes own resume context
- memory owns material history only
- archive owns retired material only after approval
- when two layers say the same thing at the same level of detail, trim the more derived one first

Locked operating spine:
- script proof -> validator -> canonical owner note -> continuity checkpoint

Operator procedure:
- use `06. Playbooks/Operating Procedures/Portfolio Truth Surface Ownership Procedure.md` whenever portfolio notes, generated artifacts, dashboards, or workflow surfaces disagree.

Deployment ranking is informational. It does not authorize execution-lane promotion. The valid promotion path is: candidate packet schema -> fail-closed gate checks -> Promotion Review Queue row when required -> explicit canonical owner decision. A clean ranking score alone is not permission to mutate the Execution Board, Portfolio Snapshot, or lane state.

## Source-of-truth hierarchy

1. **Canonical human-authored notes win.**
   - `03. Portfolio/Portfolio Snapshot.md`
   - `07. Risk/Risk Rules.md`
   - `05. Intelligence/Weekly Positioning Review.md`
   - `05. Intelligence/Event Calendar.md` for dated catalysts, with timing-sensitive items explicitly unconfirmed until checked against primary sources
2. **`tmp/portfolio-config.json` is the machine-readable portfolio and execution mirror.**
   - tracked universe
   - symbol mapping
   - weights and workflow semantics
   - entry-band metadata
3. **`tmp/market-state.json` is the macro-readiness evidence source.**
   - downstream notes must propagate `partial`, `stale`, `missing`, `manual`, and warning states honestly
4. **Other `tmp/` artifacts are evidence, not automatic truth.**
   - script-surfaced earnings-date shifts and similar timing changes require direct confirmation before the note layer treats them as settled
5. **Dashboards and briefs are derived surfaces, never canonical truth.**
   - if a polished surface conflicts with a canonical note or validator warning, fix upstream truth rather than trusting the prettier output

## Operating windows

Default orchestration rule:
- use `python scripts/run_finance_refresh_chain.py <window>` for any multi-step refresh
- only call individual scripts directly for debugging, narrow maintenance, or isolated validation

### Morning
- command: `python scripts/run_finance_refresh_chain.py morning`
- purpose: current-session readiness, deployability, trust, and pre-open context

### Post-close
- command: `python scripts/run_finance_refresh_chain.py post-close`
- purpose: rebuild the next-session board after the close and stage post-earnings follow-up

### Post-earnings
- command: `python scripts/run_finance_refresh_chain.py post-earnings`
- purpose: event-closure maintenance after a material report lands without rerunning the full stack unnecessarily

### Sunday weekly rebuild
- command: `python scripts/run_finance_refresh_chain.py sunday`
- purpose: prime the next week with full refresh, weekly intelligence scaffolding, and readiness outputs

## Script, data, and gap matrix

| Layer | Current scripts | Primary artifacts / outputs | What the layer covers now | Known gaps / failure modes |
|---|---|---|---|---|
| Macro and market regime | `market_state_refresh.py`, `regime_scoring_refresh.py`, `weekly_macro_snapshot.py` | `tmp/market-state.json`, `tmp/regime-scores.json`, weekly macro snapshot note | SPX, VIX, Treasury context, DXY, energy, futures, sector snapshot, regime scoring | Macro still carries a manual Fed / FedWatch dependency; breadth, credit spreads, vol term structure, and positioning are not yet first-class |
| Technical and execution posture | `technical_refresh.py`, `band_refresh.py`, `apply_band_update.py`, `entry_band_fetch.py`, `generate_entry_band_status.py` | `tmp/technical-refresh.json`, `tmp/band-proposals.json`, `tmp/band-update-log.txt`, entry-band status output | Close, MA20/50/200 posture, entry-band distance, stop context, stale-band detection | Entry bands can drift faster than maintenance; current validator already shows multiple names needing review |
| Event and earnings timing | `earnings_calendar_enrichment.py`, `post_earnings_prep.py`, `post_earnings_note_targets.py`, `post_earnings_scorecard.py` | `tmp/earnings-calendar.json`, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json` | Next earnings dates, date-change warnings, selective post-earnings follow-up staging | Timing-sensitive date changes still require direct confirmation; roll-forward hygiene can lag after prints |
| Deployment and trigger state | `deployment_check.py`, `trigger_sheet_refresh.py` | `tmp/deployment-check.json`, `tmp/trigger-sheet.json` | Deployable / almost deployable / blocked state, trigger logic, execution-readiness ranking | Quality depends on freshness of macro, technical, and event layers; stale inputs can make the ranking look cleaner than it is |
| Dashboard trust and derived control surface | `generate_dashboard.py`, `validate_dashboard_state.py`, `test_dashboard_acceptance.py` | `tmp/dashboard-data.json`, `tmp/dashboard-validation.json`, `tmp/dashboard-acceptance-report.json`, `tmp/veritas-command-center.html` | Contradiction checks, trust warnings, summary rendering | Derived surfaces can still multiply faster than upstream evidence if not actively trimmed |
| Daily and weekly operating outputs | `premarket_snapshot.py`, `postmarket_snapshot.py`, `daily_executive_brief.py`, `weekly_intelligence_brief.py`, `weekly_review_skeleton.py`, `call_log_sync.py` | dashboard notes, weekly brief append, weekly review scaffold, call-log sync artifact | Turns machine artifacts into session-ready note surfaces | Too many writer surfaces can create maintenance drag if they outrun the evidence spine |
| Report packaging | `equity_visual_report.py`, `equity_ppt_report.py`, `equity_pdf_report.py` | Word, PowerPoint, PDF outputs plus staged visual assets | Reusable deliverables for single-name analysis | Presentation quality can exceed evidence quality if upstream thesis work is weak or stale |

## Current known gaps that matter

1. **Event-date trust is not fully hardened.**
   - Timing-sensitive earnings changes still need direct confirmation.
2. **Macro confidence is not fully automated.**
   - Manual Fed-target or FedWatch-style maintenance remains a real weak point.
3. **Execution maintenance is drifting.**
   - Entry-band review cadence is not yet tight enough for the tracked universe.
4. **Breadth, credit, and positioning are under-modeled.**
   - The current macro layer is useful, but not yet complete enough for a fully decision-grade market-regime stack.
5. **Surface sprawl must stay controlled.**
   - New dashboards or briefs are only justified when they improve decisions more than they increase upkeep.

## Validation gates

Before treating the OS as decision support for a session:
- the relevant operating-window chain should complete successfully
- `tmp/dashboard-validation.json` should be reviewed, not ignored
- timing-sensitive earnings dates should be treated as unconfirmed until directly checked
- stale or drifted entry bands should be reviewed before pretending the trigger layer is current
- partial or manual macro states must downgrade confidence in downstream notes

## Maintenance rule

Keep this note thin.
If a section becomes a long procedure, move that procedure into `scripts/README.md` or the relevant skill and leave only the control-plane rule here.
