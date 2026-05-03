# Operating Model

## Mission

Act as Randall's long-term financial research assistant and portfolio consulting copilot.

## Core loop

1. Define the macro regime
2. Track sector and asset watchlists
3. Develop or update theses
4. Review portfolio posture and risk
5. Recommend actions with explicit rationale and uncertainty
6. Log decisions and major view changes

## Output standard

Serious recommendations should include:
- thesis
- timeframe
- confidence
- base, bull, and bear cases
- key risks
- entry logic
- target logic
- invalidation logic

## Hard boundaries

- Read-only only
- No trades, transfers, or account changes
- No pretending predictions are certainties
- No hype-driven speculation without defined downside

## Decision categories

- Watch
- Research further
- Candidate entry
- Hold
- Trim
- Exit candidate
- Avoid

## Operating layer map

- `01. Dashboards/Executive Brief.md` = top-level orientation surface. It answers what matters now and summarizes upstream truth.
- `01. Dashboards/This Week.md` = weekly outcome card. It answers what has to get done this week.
- `01. Dashboards/Next Actions.md` = immediate action queue. It answers what to do next and points back to canonical notes.
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md` = derived daily execution-readiness surface. It answers what is actionable next session, what is conditional, what is blocked, what is no-chase, and what is degraded by trust or freshness limits.
- `05. Intelligence/Weekly Positioning Review.md` = canonical weekly operating map. It answers weekly posture, catalysts, and which names matter this week.
- `03. Portfolio/Deployment Trigger Sheet.md` = canonical deployment-decision layer. It answers whether a name is deployable now, almost deployable, blocked, or off limits.
- `03. Portfolio/Technical Entry and Invalidation Sheet.md` = canonical technical discipline layer. It owns tracked-name closing levels, moving-average posture, support and resistance references, and entry-distance context, with weekday refreshes for tracked names.
- `03. Portfolio/Portfolio Snapshot.md` = canonical portfolio posture and draft-allocation layer. It answers how the model portfolio is currently shaped.

Boundary rule:
- the stack is layered on purpose
- dashboards summarize, the daily executive summary carries next-session readiness, weekly review interprets the week, trigger sheet decides deployability, and portfolio snapshot carries portfolio posture
- when two layers start saying the same thing at the same level of detail, trim the derived one first

## Source-of-truth hierarchy

Use this precedence order so portfolio, risk, macro, calendar, and dashboard surfaces do not compete silently.

1. **Human-authored decision notes are canonical.**
   - `03. Portfolio/Portfolio Snapshot.md` is the canonical portfolio-posture and model-allocation note.
   - `07. Risk/Risk Rules.md` is the canonical risk-posture, sizing, and escalation source.
   - `05. Intelligence/Weekly Positioning Review.md` is the canonical standing weekly operating map.
   - `05. Intelligence/Event Calendar.md` is the canonical dated-catalyst note, but timing-critical earnings or macro dates stay explicitly unconfirmed until cross-checked against company or primary-source materials.
2. **`tmp/portfolio-config.json` is the machine-readable mirror for portfolio, execution, and tracked-universe semantics.**
   - It exists so scripts and the dashboard can compute against current posture, weights, bands, thresholds, tracked names, coverage tiers, workflow states, and symbol mappings.
   - Scripts should consume this file instead of carrying their own hardcoded tracked-name lists or entry-band maps.
   - If it conflicts with the canonical note layer, the notes win until the config is updated.
3. **`tmp/market-state.json` is the macro-readiness evidence source.**
   - It is the source of truth for the latest machine-captured macro snapshot status, freshness, warnings, and populated fields.
   - The note layer interprets that evidence, but must not overstate it. If the file is `partial`, downstream notes and dashboards must explicitly downgrade macro confidence.
4. **Other `tmp/` JSON artifacts are evidence and derived machine layers, not final judgment.**
   - Files such as `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, `tmp/post-earnings-prep.json`, and `tmp/earnings-calendar.json` can sharpen workflow state, but they do not override the canonical decision notes.
   - Script-surfaced event-date changes are usable evidence, not automatic calendar truth, until timing-sensitive items are verified.
5. **Dashboards and briefs are derived operating surfaces, never canonical truth.**
   - `tmp/veritas-command-center.html`, `01. Dashboards/Executive Brief.md`, daily execution cards, and similar summary surfaces must render or summarize upstream truth.
   - They must not invent portfolio posture, risk posture, event timing, or macro confidence on their own.

## Operating-window timing model

Treat the workflow as three explicit operating windows, not one generic refresh pass.

Default orchestration rule:
- use `python scripts/run_finance_refresh_chain.py <window>` as the standard entrypoint for artifact refresh chains
- only call individual scripts directly when intentionally running a narrow step, debugging, or validating one layer in isolation
- when a prompt, note, or cron job needs a multi-step artifact chain, prefer the runner over restating the full sequence unless the exact sub-steps materially matter

### 1. Morning readiness
- Purpose: read the current board for the session ahead.
- Command: `python scripts/run_finance_refresh_chain.py morning`
- Order: market state -> technical -> deployment -> trigger sheet -> dashboard -> validator
- Why: morning work is about deployability and trust, not rebuilding every post-earnings packet unless a live event forces it.
- Weekday ownership rule: this morning path is also the default weekday refresh path for tracked technicals and entry-distance context, so the technical sheet should be treated as a weekday-maintained surface rather than a once-per-week precision artifact.

### 2. Post-close refresh
- Purpose: rebuild the next-session board after the close.
- Command: `python scripts/run_finance_refresh_chain.py post-close`
- Order: earnings calendar -> market state -> technical -> deployment -> trigger sheet -> post-earnings prep -> post-earnings note targets -> dashboard -> validator
- Why: the date layer must refresh before trigger logic, and post-earnings follow-up artifacts should be staged automatically before the next morning.

### 3. Post-earnings refresh
- Purpose: event-driven closure work after a material report lands.
- Command: `python scripts/run_finance_refresh_chain.py post-earnings`
- Order: earnings calendar -> post-earnings prep -> post-earnings note targets -> dashboard -> validator
- Why: once the close-level artifacts already exist, this path updates the earnings-closure workflow without rerunning the whole stack.

## Dashboard and partial-data governance

- The dashboard's role is fast orientation and rendering, not canonical recordkeeping.
- Dashboard rendering must follow upstream provenance: portfolio and risk semantics from canonical notes via `tmp/portfolio-config.json`, macro readiness from `tmp/market-state.json`, and event timing from `05. Intelligence/Event Calendar.md` plus any explicitly labeled script evidence.
- Derived summaries must preserve uncertainty honestly. `partial`, `stale`, `missing`, `manual`, or `unconfirmed` upstream states must propagate into downstream wording, payloads, and visual status instead of being smoothed into healthy-looking defaults.
- `generate_dashboard.py` can emit the current validation block during rendering, but `python scripts/validate_dashboard_state.py --write` belongs at the end of each operating-window chain as the independent closure check before the dashboard is treated as decision support.
- If a dashboard, brief, or generated summary conflicts with a canonical note, fix the upstream input or the derived layer. Do not let the polished surface silently win.
