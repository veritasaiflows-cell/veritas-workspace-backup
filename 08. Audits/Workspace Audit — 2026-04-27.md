Workspace Audit — 2026-04-27

  Audit Findings

  What's Working

  Data layer is solid. The script spine is mature and coherent:
  - run_finance_refresh_chain.py — master orchestrator with morning, post-close, post-earnings, sunday chains
  - market_state_refresh.py → tmp/market-state.json (yfinance + FRED + FedWatch)
  - Technical, regime, band, trigger, earnings, deployment, dashboard scripts all wired
  - HTML command center (tmp/veritas-command-center.html) with validation layer
  - Veritas skill stack (7 skills: fundamental, technical, macro, positioning, self-improvement, deck, PDF)
  - Daily Executive Summary format is excellent — the 2026-04-24.md is decision-grade

  What's Broken or Missing

  1. No active cron jobs. MEMORY.md explicitly states: "Cron jobs for morning and post-close chains need to be
  recreated. Prior jobs from April 2026 are no longer present in the scheduler." The entire automated refresh
  infrastructure is dark.

  2. Intelligence layer gap. The data layer (scripts → tmp/*.json) is complete. But the intelligence layer (tmp/*.json →
   Markdown deliverables) is entirely session-driven. Every brief, snapshot, and weekly is hand-written in a live
  session. That breaks when no session is active.

  3. No premarket snapshot script. The morning chain refreshes data but writes nothing to 01. Dashboards/. Randall gets
  nothing until a session opens.

  4. No post-market snapshot script. Post-close chain refreshes data but writes nothing to dashboards.

  5. No autonomous daily executive brief writer. The brief template is excellent but requires a live agent session to
  produce.

  6. No weekly macro snapshot script. The WIB covers macro, but there's no standalone weekly macro artifact at 02.
  Markets/.

  7. No autonomous weekly intelligence brief writer. weekly_review_skeleton.py scaffolds the Positioning Review, but
  nothing writes the full WIB.

  8. FOMC is in 2 days. market_state_refresh.py has NEXT_FOMC_DATE = "2026-04-29" but FED_TARGET_DATE = "2026-04-19" —
  that's fine, but it needs updating the morning of April 30 if they hold or cut.

  9. Dashboard has 3 active warnings. Band staleness (8 names), timing-sensitive earnings unconfirmed, macro manual
  dependency. Dashboard is overall: warning — usable but degraded.

  10. Weekly Intelligence Brief is stale. Last entry is Week of April 14–19. As of April 27 that's >7 days, and a full
  earnings cluster (GOOG, MSFT, AMZN, AMZN) has elapsed since.

  ---
  Action Plan

  Organized into 5 phases. Phases 1–2 are immediate; 3–5 are build work in sequence.

  ---
  PHASE 1 — Fix the Current State (Today)

  No new code. Repair what's broken now.

  1A. Resolve dashboard warnings
  - Run python scripts/apply_band_update.py and review the 8 stale bands (ETN, GOOG, MSFT, NVDA, CVX, PLTR, KTOS, SLV)
  - Confirm or update ETN earnings date (April 30 vs. May 5) via IR or verified source
  - Update scripts/market_state_refresh.py — set NEXT_FOMC_ZQ_TICKER to the correct May contract if April 29 is the live
   meeting

  1B. Refresh the Weekly Intelligence Brief
  - Run python scripts/run_finance_refresh_chain.py sunday to rebuild all data artifacts
  - Write the WIB for Week of April 21–25 with full earnings cluster summary (VRT beat, LMT miss, upcoming
  GOOG/MSFT/AMZN April 29–30)

  1C. Confirm cron environment
  - Verify Python path, script working directory, and Task Scheduler or cron availability on this Windows machine
  - Run one chain manually (morning) and confirm all artifacts write cleanly before scheduling

  ---
  PHASE 2 — Pre-Market and Post-Market Snapshots (2–3 days)

  New scripts. Fill the biggest intelligence gap.

  2A. Build scripts/premarket_snapshot.py

  Reads: tmp/market-state.json, tmp/trigger-sheet.json, tmp/dashboard-validation.json, tmp/earnings-calendar.json

  Writes: 01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md

  Output format:
  # Pre-Market Snapshot — YYYY-MM-DD
  Generated: [timestamp] | Market data as of: [last_trading_day]
  Dashboard trust: [clean / degraded / critical with reason]

  ## Macro and Futures Tone
  - ES: [price] ([+/-]%)  |  NQ: [price] ([+/-]%)
  - VIX: [level] | 10Y: [rate]% | Brent: $[price]
  - Regime read: [one line from market-state]

  ## Actionable Names
  | Ticker | State | Last Close | Pre-Mkt | Entry Band | Gap to Band |
  |--------|-------|-----------|---------|------------|-------------|
  | ETN    | ALMOST | 424.50 | 421.00 | 383–407 | -$14 / -3.3% |
  ... only deployable and almost-deployable names ...

  ## Today's Catalysts
  - [earnings from earnings-calendar.json for today's date]
  - [FOMC or data releases from market-state.json fed block]

  ## Open Protocol
  - No entries in first 15–30 min without a pre-set limit at a defined band level
  - If open is gap-up and name is still outside band, do nothing
  - Re-check only if price reaches a written trigger zone

  2B. Build scripts/postmarket_snapshot.py

  Reads: tmp/market-state.json, tmp/trigger-sheet.json, tmp/dashboard-delta.json, tmp/post-earnings-prep.json,
  tmp/earnings-calendar.json

  Writes: 01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md

  Output format:
  # Post-Market Snapshot — YYYY-MM-DD
  Generated: [timestamp]

  ## Day Summary
  - SPX: [close] ([+/-]%)  |  VIX: [level]  |  DXY: [level]
  - Energy: Brent $[price] | WTI $[price]
  - Sectors: XLI [%] | XLF [%] | XLK [%] | XLE [%]

  ## Tracked Names — Day Results
  | Ticker | State | Close | Day% | vs Entry Band |
  ... all daily-tier names ...

  ## What Changed Since Yesterday
  - [from dashboard-delta.json — state transitions, band breaches]

  ## Open Triggers for Tomorrow
  - [names that are DEPLOYABLE or ALMOST with distance to band]

  ## Earnings Today
  - [from post-earnings-prep.json — any reports today]

  ## Tomorrow's Catalysts
  - [from earnings-calendar.json for tomorrow's date]

  2C. Add both to run_finance_refresh_chain.py
  - Add premarket_snapshot.py at end of morning chain
  - Add postmarket_snapshot.py at end of post-close chain

  ---
  PHASE 3 — Autonomous Daily Executive Brief (3–4 days)

  The highest-value automation. Replaces the need for a live session to produce the daily brief.

  3A. Build scripts/daily_executive_brief.py

  Reads: tmp/market-state.json, tmp/trigger-sheet.json, tmp/technical-refresh.json, tmp/band-proposals.json,
  tmp/post-earnings-prep.json, tmp/dashboard-validation.json, tmp/deployment-check.json, tmp/earnings-calendar.json

  Writes: 01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md

  Critical rule: Does not overwrite an existing file for the same date. If a session-written brief already exists for
  today, the script skips or writes to YYYY-MM-DD-machine.md so the agent version takes precedence.

  Output matches the existing 7-section template exactly:
  1. Executive bottom line (deployment status, confidence grade derived from dashboard-validation)
  2. Execution context (macro, futures, pre-market tone)
  3. What changed since yesterday (from dashboard-delta.json)
  4. Today's catalysts (from earnings-calendar.json filtered for today)
  5. Closest actionable names (from trigger-sheet.json, with dollar/percent distance to band)
  6. Trigger conditions (from trigger-sheet.json — if-then format)
  7. Recommended actions (Do / Watch / Avoid / Open Protocol)

  3B. Add to post-close chain at position after postmarket_snapshot.py

  ---
  PHASE 4 — Weekly Macro Snapshot and Weekly Intelligence Brief (5–7 days)

  Close the last intelligence gap. Makes the full weekly cycle autonomous.

  4A. Build scripts/weekly_macro_snapshot.py

  Reads: tmp/market-state.json, tmp/regime-scores.json, tmp/earnings-calendar.json

  Writes: 02. Markets/Weekly Macro Snapshot/YYYY-Www.md (ISO week folder)

  Sections:
  - Macro Regime Assessment
  - Fed and Rates (2Y/10Y/3M, curves, FedWatch)
  - Inflation and Growth Pulse (last CPI/PCE/GDP from market-state commentary)
  - Energy and Commodities (Brent, WTI, EIA note)
  - FX (DXY)
  - Geopolitical Flags (pulled from prior WIB or market-state notes)
  - Key Events Next Week (earnings + macro from earnings-calendar)
  - Regime Posture Score and portfolio implication

  4B. Build scripts/weekly_intelligence_brief.py

  This is the most complex script. It consumes all weekly data and writes a complete, structured WIB.

  Reads: tmp/market-state.json, tmp/trigger-sheet.json, tmp/earnings-calendar.json, tmp/post-earnings-prep.json,
  tmp/technical-refresh.json, tmp/regime-scores.json, tmp/band-proposals.json, tmp/weekly-review-skeleton.json, existing
   05. Intelligence/Weekly Intelligence Brief.md

  Writes: appends a new dated section to 05. Intelligence/Weekly Intelligence Brief.md

  Behavior: same idempotent pattern as weekly_review_skeleton.py — does not overwrite an existing week's section. If the
   current week already has content, it prints a delta report instead.

  Sections match SOUL.md's weekly intelligence routine:
  1. Macro pulse (from market-state)
  2. Energy sweep (from market-state energy block + EIA data if available)
  3. Geopolitical scan (flagged from prior notes + new material)
  4. Earnings radar (from earnings-calendar — reported this week + upcoming)
  5. Analyst and institutional flow (stubs for manual fill — flag where human input required)
  6. Technical check (from technical-refresh + trigger-sheet)
  7. Sentiment gauge (VIX, put/call where available, fear/greed from market-state)
  8. Recommended actions (from trigger-sheet + deployment-check)

  4C. Add to sunday chain

  Position in sunday chain after weekly_review_skeleton.py:
  ["weekly_macro_snapshot.py"],
  ["weekly_intelligence_brief.py"],

  ---
  PHASE 5 — Cron Job Wiring (implement alongside Phases 2–4)

  Turn the data + intelligence pipeline into a fully autonomous loop.

  Cron schedule (Windows Task Scheduler):

  ┌────────────────────┬────────────────────┬───────────────────────────────────┬──────────────────────────────────┐
  │        Job         │      Schedule      │              Command              │           Description            │
  ├────────────────────┼────────────────────┼───────────────────────────────────┼──────────────────────────────────┤
  │                    │ Mon–Fri 06:30 ET   │ python                            │ Pre-open data refresh +          │
  │ finance-morning    │ (03:30 MST)        │ run_finance_refresh_chain.py      │ pre-market snapshot              │
  │                    │                    │ morning                           │                                  │
  ├────────────────────┼────────────────────┼───────────────────────────────────┼──────────────────────────────────┤
  │                    │ Mon–Fri 16:30 ET   │ python                            │ EOD refresh + post-market        │
  │ finance-post-close │ (13:30 MST)        │ run_finance_refresh_chain.py      │ snapshot + daily brief           │
  │                    │                    │ post-close                        │                                  │
  ├────────────────────┼────────────────────┼───────────────────────────────────┼──────────────────────────────────┤
  │                    │ Sunday 07:00 ET    │ python                            │ Weekly full rebuild + WIB +      │
  │ finance-sunday     │ (04:00 MST)        │ run_finance_refresh_chain.py      │ macro snapshot                   │
  │                    │                    │ sunday                            │                                  │
  ├────────────────────┼────────────────────┼───────────────────────────────────┼──────────────────────────────────┤
  │ finance-heartbeat  │ Every 4 hours      │ heartbeat prompt via OpenClaw     │ Light staleness check + memory   │
  │                    │                    │                                   │ maintenance                      │
  ├────────────────────┼────────────────────┼───────────────────────────────────┼──────────────────────────────────┤
  │ finance-fomc-check │ Day-after-FOMC     │ manual trigger                    │ Update FED_TARGET constants in   │
  │                    │ mornings only      │                                   │ market_state_refresh.py          │
  └────────────────────┴────────────────────┴───────────────────────────────────┴──────────────────────────────────┘

  Windows Task Scheduler notes:
  - Use pythonw.exe or add log output redirection to a file in tmp/logs/YYYY-MM-DD-chain.log
  - Set working directory to workspace root
  - Set "Run whether user is logged on or not" for fully autonomous operation
  - Verify FRED_API_KEY is accessible in the non-interactive environment (set in HKCU registry or system environment,
  which market_state_refresh.py already reads)

  Recommended cron setup method: Use the /schedule skill to register these as OpenClaw cron jobs rather than Windows
  Task Scheduler — this keeps the entire loop inside OpenClaw's agent runtime and makes them auditable from within the
  vault.

  ---
  Deliverable Summary — What Gets Built

  ┌────────────────────┬──────────────────────────────┬─────────────────────────────────────────┬──────────────────┐
  │    Deliverable     │            Script            │               Output Path               │     Trigger      │
  ├────────────────────┼──────────────────────────────┼─────────────────────────────────────────┼──────────────────┤
  │ Pre-market         │ premarket_snapshot.py        │ 01. Dashboards/Pre-Market               │ End of morning   │
  │ snapshot           │                              │ Snapshot/YYYY-MM-DD.md                  │ chain            │
  ├────────────────────┼──────────────────────────────┼─────────────────────────────────────────┼──────────────────┤
  │ Post-market        │ postmarket_snapshot.py       │ 01. Dashboards/Post-Market              │ End of           │
  │ snapshot           │                              │ Snapshot/YYYY-MM-DD.md                  │ post-close chain │
  ├────────────────────┼──────────────────────────────┼─────────────────────────────────────────┼──────────────────┤
  │ Daily executive    │ daily_executive_brief.py     │ 01. Dashboards/Daily Executive          │ End of           │
  │ brief              │                              │ Summary/YYYY-MM-DD.md                   │ post-close chain │
  ├────────────────────┼──────────────────────────────┼─────────────────────────────────────────┼──────────────────┤
  │ Weekly macro       │ weekly_macro_snapshot.py     │ 02. Markets/Weekly Macro                │ sunday chain     │
  │ snapshot           │                              │ Snapshot/YYYY-Www.md                    │                  │
  ├────────────────────┼──────────────────────────────┼─────────────────────────────────────────┼──────────────────┤
  │ Weekly             │ weekly_intelligence_brief.py │ 05. Intelligence/Weekly Intelligence    │ sunday chain     │
  │ intelligence brief │                              │ Brief.md (appended)                     │                  │
  └────────────────────┴──────────────────────────────┴─────────────────────────────────────────┴──────────────────┘

  ---
  Priority Order

  Do immediately (today):
  1. Run apply_band_update.py — clears the dashboard warning and unblocks 8 names
  2. Confirm ETN earnings date
  3. Run the sunday chain to refresh all artifacts
  4. Write the current WIB manually (it's stale; too much happened this week to skip)

  This week (build order):
  1. premarket_snapshot.py — highest daily value, simplest to build (pure data rendering)
  2. postmarket_snapshot.py — second highest, similar complexity
  3. Wire both into run_finance_refresh_chain.py
  4. Set up the cron jobs so these run autonomously starting this week

  Next week:
  5. daily_executive_brief.py — more logic, highest complexity of the three daily scripts
  6. weekly_macro_snapshot.py — straightforward, pulls from already-good market-state output
  7. weekly_intelligence_brief.py — most complex, needs careful section-by-section data binding

  Ongoing:
  - FOMC maintenance: update market_state_refresh.py constants the morning after each FOMC meeting
  - Band refresh: run apply_band_update.py after any significant move or after each earnings report in the tracked
  universe

  ---
  Architecture Principle

  The scripts produce structured, evidence-stamped Markdown that Veritas or you can read in seconds. They do not fake
  judgment — they auto-populate quantitative sections (distances to band, regime scores, earnings calendar, sector
  snapshots) and leave explicit stubs where human interpretation is required. The agent completes or refines those stubs
   in session; the machine handles the data assembly every time.

  The result: every morning you wake up to a pre-market snapshot. Every evening a post-market snapshot and full daily
  brief are waiting. Every Sunday a complete weekly macro and intelligence rebuild is ready before your session starts.