# Market Data Coverage Matrix

## Purpose

This note is the evidence-coverage map for the alerts-and-recommendations OS. It distinguishes data that is collected, inferred, stale, missing, or unsuitable for a recommendation so confidence never outruns proof.

## Design standard

Truth, freshness, lineage, efficiency, and speed are first-class controls. A green pipeline means its validators passed; it does not mean every market input is fresh or every recommendation is constructive.

## Coverage matrix

| Evidence area | Current evidence | Active source / proof | Cadence | Trust state | Main gap |
|---|---|---|---|---|---|
| Macro regime | SPX, VIX, Treasury context, DXY, energy, futures, sector context | macro refresh and regime-scoring proofs | daily / operating window | Moderate | policy, credit, and breadth need stronger first-class series |
| Policy expectations | partial Fed-target context | macro evidence layer | inconsistent | Low | no dedicated machine-readable expectations artifact |
| Credit stress | indirect risk read-through | no dedicated active series | none | Low | IG/HY spread levels and deltas are missing |
| Equity breadth | index and sector context | no dedicated active series | none | Low | participation, equal-weight, and highs/lows evidence are missing |
| Volatility regime | VIX and related macro context | macro refresh proof | daily | Moderate | term structure and realized-versus-implied context are missing |
| Sector leadership | sector and theme evidence | macro/sector evidence proofs | daily / weekly | Moderate | persistent participation and breadth-by-sector scoring are incomplete |
| Earnings and catalysts | event dates, date-change warnings, catalyst context | earnings and event-calendar proofs | post-close / event-driven | Moderate | timing-sensitive dates still need direct confirmation |
| Technical context | close, moving averages, alert-band distance, invalidation context | guarded SQL, explicit quote proof, alert freshness controller | market window / post-close | Moderate to High | confidence decays when quote or source lineage is stale |
| Alert-level truth | canonical levels, threshold state, freshness and suppression | `finance_sql_canon_access.py`, `intraday_quote_snapshot_proof.py`, `alert_level_freshness_controller.py` | operating window | High when validation is clean | all current levels require exact provenance and hash-matched source lineage |
| Recommendation state | thesis, timeframe, evidence, risks, confidence, uncertainty, owner decision point | alert/recommendations chain and digest | morning, midday, post-close, weekly | Bounded by inputs | stale or incomplete evidence must suppress or downgrade output |
| Market sentiment and flow | narrative and partial public evidence | research/macro evidence | irregular | Low | no systematic factor, flow, or crowding layer |
| Estimate revisions | analyst-consensus evidence | analyst consensus refresh | weekly | Moderate when current | revisions and expectation resets need broader coverage |
| Post-earnings interpretation | source-backed thesis and catalyst deltas | post-earnings evidence route | event-driven | Moderate | depends on confirmed dates and current technical context |
| Output integrity | schema, contradiction, lineage, freshness, and suppression checks | chain validators and pivot boundary validator | every run | High for covered checks | validators prove only their declared scope |

## Highest-impact gaps

1. Add a first-class policy-expectations evidence layer.
2. Add named IG/HY credit-spread evidence with freshness rules.
3. Add market-breadth and sector-participation evidence.
4. Preserve explicit quote/session-age gates for every alert evaluation.
5. Keep new outputs subordinate to source lineage, freshness, confidence, and suppression.

## Minimum acceptance standard for a new series

Before a new series can influence an alert or recommendation, it must have:

- a named source and source date;
- a defined cadence and maximum age;
- a warning, suppression, or fallback state;
- one owning proof artifact;
- explicit downstream consumers;
- a confidence rule and uncertainty statement;
- a statement of what the series does not establish.

The OS does not own or maintain sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, simulated positions, order packages, or execution state. Owner-provided objectives or limits may be used transiently as recommendation context and do not become maintained finance state.

## Current recommendation

Prioritize policy expectations, credit spreads, equity breadth, sector participation, and sentiment/flow proxies—in that order—while preserving the guarded-SQL and explicit-quote boundary.
