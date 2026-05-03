# Market Data Coverage Matrix

## Purpose

This note is the explicit market-data coverage map for the finance operating system.
It exists so the workspace can tell the difference between:
- data we actually collect
- data we infer from proxies
- data we still need
- surfaces that should not speak more confidently than the underlying evidence allows

## Design standard

The target is not maximum raw return.
The target is long-term, disciplined, **risk-adjusted** return generation with a moderate-risk posture.

External design cues used in this structure:
- IPS-style governance discipline: scope, governance, objectives, and risk management should be explicit rather than implied
- CME FedWatch as a working model for policy-expectation evidence rather than hand-waving Fed assumptions
- FRED/ICE BofA spread series as working models for daily credit-stress evidence rather than narrative-only credit commentary

## Coverage matrix

| Decision area | Current metrics / evidence | Current source / script layer | Current artifact(s) | Cadence | Current trust level | Main gap | Priority |
|---|---|---|---|---|---|---|---|
| Macro regime | SPX, VIX, Treasury context, DXY, energy, futures, sector snapshot, actionable-name context | `market_state_refresh.py`, `regime_scoring_refresh.py` | `tmp/market-state.json`, `tmp/regime-scores.json` | daily / operating window | Moderate | policy expectations still partly manual; breadth and credit not first-class | High |
| Policy expectations | partial Fed-target context | partly manual within macro workflow | embedded in macro layer only | inconsistent | Low | no dedicated, machine-readable policy-expectations artifact | High |
| Credit stress | indirect risk read-through only | none dedicated | none dedicated | none | Low | no IG OAS / HY OAS / spread-delta series | High |
| Equity breadth | indirect via index and sector action | none dedicated | none dedicated | none | Low | no breadth-state artifact; no % above key MAs, equal-weight comparison, or highs/lows layer | High |
| Volatility regime | VIX inside macro layer | `market_state_refresh.py` | `tmp/market-state.json` | daily | Moderate | no term-structure or realized-vs-implied view | Medium |
| Sector leadership | sector snapshot inside macro layer | `market_state_refresh.py` | `tmp/market-state.json` | daily | Moderate | no persistent participation score or breadth-by-sector layer | Medium |
| Earnings and catalysts | next earnings dates, date-change warnings, event-window context | `earnings_calendar_enrichment.py`, note layer | `tmp/earnings-calendar.json`, `05. Intelligence/Event Calendar.md` | post-close / event-driven | Moderate | timing-sensitive dates still require direct confirmation and roll-forward discipline | High |
| Technical posture | close, MA20/50/200 posture, stop and entry-distance context | `technical_refresh.py` | `tmp/technical-refresh.json` | weekday / operating window | Moderate to High | no broader breadth integration; depends on entry-band maintenance staying fresh | High |
| Entry discipline | band drift, proposal workflow, entry status HTML | `band_refresh.py`, `apply_band_update.py`, `entry_band_fetch.py`, `generate_entry_band_status.py` | `tmp/band-proposals.json`, `tmp/band-update-log.txt`, entry-band outputs | weekday / review-driven | Moderate | multiple tracked names currently need review; maintenance cadence is not yet tight enough | High |
| Deployment state | deployable / almost deployable / blocked | `deployment_check.py`, `trigger_sheet_refresh.py` | `tmp/deployment-check.json`, `tmp/trigger-sheet.json` | operating window | Moderate | quality is bounded by macro, breadth, credit, and band freshness | High |
| Portfolio risk posture | note-layer rules and allocation posture | `03. Portfolio/Portfolio Snapshot.md`, `07. Risk/Risk Rules.md`, `tmp/portfolio-config.json` | canonical notes + config mirror | manual / session-driven | High for governance, Moderate for automation | no automated exposure monitor yet | Medium |
| Positioning and flow | narrative only, partial observation | none dedicated | none dedicated | none | Low | no systematic factor leadership, flow, or crowding layer | Medium |
| Estimate revisions / analyst drift | ad hoc only | none dedicated | none dedicated | none | Low | no structured revisions or expectation-reset layer | Medium |
| Post-earnings interpretation | structured packet and note-target staging | `post_earnings_prep.py`, `post_earnings_note_targets.py`, `post_earnings_scorecard.py` | `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json` | event-driven | Moderate | dependent on confirmed dates and refreshed technical context | Medium |
| Dashboard trust and contradiction checks | validation warnings, contradiction checks, trust block | `generate_dashboard.py`, `validate_dashboard_state.py`, `test_dashboard_acceptance.py` | `tmp/dashboard-validation.json`, related dashboard artifacts | operating window | High for integrity checks | still limited by upstream data coverage | High |

## Current highest-impact gaps

1. **Policy expectations need a first-class evidence layer.**
   - Fed assumptions should not live as a semi-manual side detail inside macro narrative.
2. **Credit is under-modeled.**
   - Without IG/HY spread context, risk-on and risk-off calls can become too equity-price-centric.
3. **Breadth is under-modeled.**
   - Index strength without participation data is not decision-grade regime work.
4. **Entry-band maintenance needs tightening.**
   - The system already knows bands are drifting; that should become a scheduled operating habit.
5. **Surface growth must stay subordinate to the evidence layer.**
   - New briefs and dashboards are justified only when the underlying series are fresh, explicit, and validated.

## Minimum acceptance standard for a new series

Before a new market-data series is allowed to influence the dashboard, deployment state, or a formal recommendation, it should have:
- a named source
- a defined cadence
- a freshness rule
- a warning or fallback state
- one clear owning artifact
- explicit downstream consumers
- a statement of what the series does **not** tell us

## Current recommendation

Next data-expansion work should focus on:
1. policy expectations
2. credit spreads
3. equity breadth
4. sector participation
5. positioning proxies

In that order.
