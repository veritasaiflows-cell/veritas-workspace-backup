---
name: veritas-weekly-brief
description: Orchestrate the Sunday weekly rebuild and intelligence routine. Use this to run the full Sunday refresh chain, synthesize macro and positioning views, and produce the Weekly Intelligence Brief (WIB) and Weekly Macro Snapshot. It ensures the transition from historical data to a forward-looking game plan is evidence-backed and synchronized.
---

# Veritas Weekly Brief

This skill owns the **Sunday transition.** It is the primary engine for creating the "Forward View" while ensuring no technical or macro drift has occurred over the weekend.

## 1. The Sunday Data Spine

1. **Execute the Rebuild:**
   Run `python scripts/run_finance_refresh_chain.py sunday`.
2. **Audit Freshness:**
   - Verify `tmp/weekly-macro-snapshot.json` and `tmp/weekly-intelligence-brief.json` were successfully generated.
   - Check `tmp/dashboard-validation.json` for any "Critical" contradictions or stale source warnings (e.g., FedWatch unwired).
3. **Consolidate Inputs:**
   Read the previous week's [[01. Dashboards/This Week]] and [[05. Intelligence/Weekly Positioning Review]] to understand the "Starting State."

## 2. Intelligence Synthesis (The WIB)

The goal is to move from `_[judgment]_` placeholders in the machine output to a finalized, high-conviction brief.

1. **Macro Pulse:**
   Invoke `veritas-macro-pass` to interpret the regime data from `tmp/regime-scores.json`. Focus on the "Second-Order Effects" (e.g., how the Hormuz oil rally impacts the Fed's terminal rate view).
2. **Earnings Radar:**
   Identify the "Density Centers" of the coming week. Match them against [[02. Markets/Watchlist]] priority.
3. **Technical Check:**
   Invoke `veritas-technical-pass` to audit the "Actionable Names" identified in `tmp/trigger-sheet.json`.
4. **Append the Brief:**
   Update `05. Intelligence/Weekly Intelligence Brief.md`. Ensure the heading matches the ISO week (e.g., `## 2026-W18`). If the section already exists, provide a "Delta Report" instead of duplicating.

## 3. The Operating Board Sync

A weekly brief is only complete if the operating notes are synchronized for Monday morning.

1. **Update [[01. Dashboards/Monday Game Plan]]**:
   Summarize the 3 most important execution priorities for the week.
2. **Update [[01. Dashboards/This Week]]**:
   List the core catalysts, earnings dates, and macro releases.
3. **Audit the Watchlist**:
   Read [[02. Markets/Watchlist]] and flag any names that should be "Benched" or "Promoted" based on the new technical/macro regime.
4. **Refresh [[01. Dashboards/Executive Brief]]**:
   Reset the "Current Focus" and "What Matters Now" sections to reflect the Sunday findings.

## 4. Quality Standards

- **Evidence First:** Every directional claim must cite a data point from the Sunday refresh (e.g., "10Y yield at 4.336% implies...").
- **Judgment vs. Summary:** Do not merely restate the JSON. If the machine says "Risk-On," but the technical pass shows 11 names extended >5% above bands, highlight the **divergence.**
- **The "So What":** Every section of the brief must conclude with an "Implication for Portfolio" statement.

## Execution Procedure

When Randall asks for the "Weekly Review" or "Sunday Refresh":
1. `Research`: Run the Sunday script chain and ingest all generated JSONs.
2. `Analysis`: Activate the Macro and Technical passes to fill judgment slots.
3. `Drafting`: Prepare the Weekly Macro Snapshot and Weekly Intelligence Brief sections.
4. `Sync`: Update the Dashboard and Portfolio notes to match the new Sunday "Truth."
5. `Validate`: Run `python scripts/validate_dashboard_state.py --write` and report the final Confidence Grade.
