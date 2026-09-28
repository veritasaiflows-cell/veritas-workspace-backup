---
name: "veritas-intelligence-effort-router"
description: "Finance recs, ticker reviews, outcome audits, weekly freshness. Reconcile guarded bands, ranked funnel, and forward evidence."
---

# Veritas Intelligence Effort Router

## Purpose

Choose the smallest trustworthy route for finance alerts and non-executing recommendations. This skill allocates research effort; it grants no canon mutation, capital, order, account, brokerage, money-movement, or execution authority.

## Active Truth Route

Use these sources in order:

1. Guarded SQL `reference_levels` for live numeric bands and invalidation. Markdown Alert Bands register is thesis/interpretation only and must not win a number conflict.
2. Active human canon in `03. Alerts and Recommendations/` for policy, thesis, and interpretation.
3. Guarded SQL validation:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
```

4. Current-window quote proof and alert evaluation, only as Band 2 when the matching digest or controller is missing, older than its max-age, or lacks the needed tickers:

```powershell
python scripts\run_alerts_recommendations_chain.py <morning|midday|post-close|weekly> --timeout-seconds 120 --write --validate
```

Match the market session. Do not run `midday` because a pass skill names it. If the current-window digest and controller are already fresh and complete for the asked tickers, stay Band 1 for ticker-alert state. That green chain does not prove policy, breadth, credit, or regime freshness.

5. `tmp/alert-level-freshness-controller.json` for ticker-level alert state.
6. `tmp/finance-alert-os-digest.json` for the level-state board and delivery context, not ranked recommendation eligibility. For ranking or outcome audits, read `tmp/recommendation-funnel.json` and accepted `state/finance/thesis/` records. Compare funnel, controller, macro, and earnings timestamps and the funnel's band values with the current guarded-SQL baseline; a renewal after funnel generation makes that rank historical, and the funnel then replaces the whole rank with `status: stale_suppressed`, a `stale_reason`, and zeroed counts/candidates/names - the `veritas-data` funnel call reports those same stale fields - so read it as a withheld rank, never as no names qualifying. Recompute from the workspace root with `python scripts\recommendation_funnel.py --write --root .` and re-read the artifact; a fresh rank carries `names` and no `status` field.
7. For performance claims, count event types and `delivered` flags in `state/finance/ledger/alert-events-v1.jsonl` at a stated cutoff, then check for resolved forward scores. Hash-chain validity, transition records, and legacy semantic grades are not proof of delivered recommendations or benchmark-adjusted outcomes.
8. Current WF84 evidence and WF85 non-executing recommendation cards only when their sources, freshness, and authority flags are clean.

Indexes, caches, dashboards, old workflow packets, earnings scorecards, capital slates, quarantined analyst packets, and archived files are routing or history only. They never outrank active canon. Do not recursively search `tmp/` or Coverage Watchlist for a ticker thesis.

## Effort Bands

- Band 0 — explain a concept from current canon without refresh.
- Band 1 — read the current controller/digest and answer ticker-alert state. Weekly/policy/sector questions still need the macro-artifact check below.
- Band 2 — refresh the four-stage alerts chain because required proof is missing or stale.
- Band 3 — perform bounded source-open research for a material recommendation, then reconcile it to active canon.
- Band 4 — use implementation and independent QA governance when code, contracts, cron, SQL lineage, or skills change.

Do not run a broad legacy finance stack merely because more artifacts exist.

## Weekly / Policy / Sector Questions

A weekly market, FOMC, rates, or sector-leadership ask needs the macro artifacts, not only the ticker chain.

1. Read `generated_at_utc`, `last_trading_day`, and next FOMC date inside `tmp/policy-expectations.json`, `tmp/breadth-state.json`, `tmp/credit-spreads.json`, and `tmp/macro-regime.json`. File mtime can move without content refresh.
2. If those timestamps predate the last material policy event or last completed cash session, refresh in this order: `policy_expectations_refresh.py`, `credit_spread_refresh.py`, `breadth_refresh.py`, `macro_regime_refresh.py`. `macro_regime_refresh.py` does not read market state and downstream macro fallbacks tolerate its absence, so the chain has no market-state stage. Never run `market_state_refresh.py` or recreate `tmp/market-state.json`: it is retired portal/paper current-state (2026-08-29 retirement), and `alerts_os_pivot_validator.py` treats recreation as a retired-state error that cascades blocked status into cron jobs. Run that validator after the refresh. Do not run `generate_dashboard.py` unless asked.
3. Do not pass sector or index symbols to `intraday_quote_snapshot_proof.py`; that overwrites the alerts quote snapshot. Use the breadth-state artifact or a separate price pull.
4. Official FOMC statement and SEP/dots outrank next-meeting futures odds and the composite regime label when they conflict. A high next-meeting hold probability is not a finished hiking path.
5. For VIX, oil, or DXY that a macro-judgment draft reports as n/a, use official releases or a separate quote pull; never recreate retired `market-state.json` to fill them.
6. `05. Intelligence/Weekly Positioning Review.md` is retired historical text, not current weekly canon.

Done when policy/regime dates post-date the event, sector leadership uses the refreshed breadth tape, and the answer stays review-only.

## Named Ticker Review

For a full review or recommendation on a named ticker, open these exact rows before any other search:

1. Guarded SQL `reference_levels` for that ticker — live low, high, invalidation, timestamps, and band status.
2. The same ticker in the current controller and current-window digest.
3. The quote-snapshot row for that symbol.
4. `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md` for thesis and interpretation only. Its numeric table is a historical snapshot, not live canon.

If markdown snapshot numbers disagree with SQL, fail closed to SQL. Do not treat the markdown table as the written band. Quote the disagreement as stale-register residue, not as a second live band.

Band 3 then opens issuer IR plus the latest SEC Exhibit 99.1 or 10-Q. A local earnings scorecard cannot replace a newer official period. Extract SQL with a small `.py` file; nested `python -c` quoting fails on Windows.

Done when the recommendation contract is filled, live numbers come from SQL, any stale-markdown-versus-SQL residue is named, the official-period date is stated, and the answer stays review-only.

## Alert States

Use only these operating states:

- `recommendation_review`
- `band_entry`
- `near_band`
- `no_chase`
- `invalidation_alert`
- `thesis_change`
- `catalyst_alert`
- `freshness_decay`
- `monitor_only`
- `suppressed`

A state is an observation or review route, never an action instruction.

When the digest lists no band-entry/no-chase/invalidation alerts and every `alert_state` is `monitor_only` because the cash session is closed, still report `level_relationship_state`. Last-completed-session quotes cannot fire; they remain valid review evidence. SQL `reference_band_status` can stay `IN_BAND` while live price versus SQL numbers is `no_chase`, `near_band`, or below the low. Use the live comparison.

## Recommendation Contract

For a material ticker recommendation, supply:

- ticker and timeframe
- current evidence date and market-session context
- freshness and confidence
- thesis and material catalyst
- base, bull, and bear cases when evidence supports them
- risks and uncertainty
- current price versus the guarded SQL reference band
- invalidation context
- no-chase or freshness blocker when present
- fit with Randall's stated objectives and limits
- Randall's decision point

Owner-provided objectives or limits may inform the current answer transiently. Never store them as system-maintained holdings, sleeves, allocations, weights, sizing, tranches, cash posture, simulated positions, or account state.

## Freshness Rules

- Current-last-completed-session data is valid closed-market evidence when the market calendar confirms it.
- Market-hours claims require current quote proof appropriate to the decision consequence.
- Stale, missing, conflicted, or hash-mismatched inputs emit `freshness_decay`; they must not be hidden to make the chain green.
- Live numeric bands come from guarded SQL `reference_levels`; never silently re-derive or auto-apply them.
- A structurally green chain proves only that its checks passed, not that the recommendation is correct.

## Automation Allowed

Automate bounded research, source lineage checks, quote proof, freshness classification, deduplication, alert routing, rankings, review packets, and blocker explanations.

Use helpers only with exact outputs, read/write scope, stop lines, and validation. Main verifies their proof before user-facing judgment.

## Retired Routes

Do not invoke or recreate:

- former portfolio board/snapshot/config maintenance
- sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, or rebalancing state
- deployment/trade-grade gates or capital-priority queues
- simulated account, request-card, order, reconciliation, or execution routes
- WF56/WF58/WF63/WF64/WF67/WF86/WF87 operational paths
- `05. Intelligence/Weekly Positioning Review.md` as a current weekly product

Historical artifacts may be inspected read-only for audit.

## Stop Lines

Stop or downgrade confidence when provenance is unresolved, freshness is inadequate, material downside or invalidation is missing, active canon conflicts, or a request crosses into capital, order, account, brokerage, money movement, execution, external delivery, or authority expansion.

No alert, rank, confidence label, card, validator, cron run, or clean proof implies Randall's approval.
