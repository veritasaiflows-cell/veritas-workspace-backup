# Market Data Upgrade Plan

## Objective

Upgrade the finance operating system from a solid price-and-catalyst stack into a more decision-grade market-regime stack for **long-term, disciplined, moderate-risk investing**.

The priority is not adding more outputs.
The priority is strengthening the evidence base that supports portfolio, timing, and risk decisions.

## Build principles

1. **Prefer stable public sources over brittle scraping.**
   - Good defaults: existing `yfinance` usage, FRED series, and machine-readable public data where available.
2. **One artifact per new evidence layer.**
   - Avoid hiding new series as stray fields inside unrelated JSON files.
3. **No new dashboard block before the underlying artifact is trustworthy.**
4. **Every new metric must carry freshness and warning logic.**
5. **Proxy is acceptable only when labeled as proxy.**
6. **If a series is manual or partially manual, downstream confidence must downgrade automatically.**

## Phase 0 — harden what already exists first

### 0A. Earnings-date confirmation discipline
Problem:
- timing-sensitive earnings dates still need direct confirmation
- stale roll-forward state can mislead the event calendar

Action:
- define a confirmation workflow for timing-sensitive names before the dates are treated as canonical
- preserve script-discovered changes as evidence until confirmed

Suggested output discipline:
- confirmed
- unconfirmed
- stale-after-print
- changed-needs-check

### 0B. Entry-band maintenance discipline
Problem:
- multiple tracked names already need band review

Action:
- make band review a routine operating checkpoint instead of an occasional cleanup
- keep approval human-gated, but make detection automatic and visible

### 0C. Fed manual dependency removal
Problem:
- macro confidence is degraded by manual Fed-target / FedWatch maintenance

Action:
- create a dedicated policy-expectations layer so macro no longer hand-waves the rates path

## Phase 1 — add a dedicated policy-expectations layer

### Goal
Turn Fed expectations into a first-class artifact instead of a narrative dependency.

### Recommended source posture
- primary working reference: CME FedWatch probabilities for upcoming FOMC expectations
- fallback: explicit manual status if the live source cannot be captured cleanly

### New artifact
- `tmp/policy-expectations.json`

### Suggested script
- `scripts/policy_expectations_refresh.py`

### Minimum fields
- generated time
- source label
- next FOMC meeting date
- current target range
- implied probability distribution for next move
- manual / partial / stale flags
- warnings

### Downstream consumers
- `tmp/market-state.json`
- weekly macro snapshot
- weekly intelligence brief
- dashboard validation / macro confidence layer

## Phase 2 — add a dedicated credit-stress layer

### Goal
Stop relying on equities alone to infer risk appetite.

### Recommended source posture
- primary source family: FRED series for ICE BofA option-adjusted spreads
  - IG OAS: `BAMLC0A0CM`
  - HY OAS: `BAMLH0A0HYM2`
- fallback proxies: HYG, JNK, LQD, and HYG/LQD relative performance if direct spread data is unavailable

### New artifact
- `tmp/credit-spreads.json`

### Suggested script
- `scripts/credit_spread_refresh.py`

### Minimum fields
- IG OAS
- HY OAS
- HY minus IG spread delta
- 5-day and 20-day direction
- stress regime label
- freshness
- warnings

### Downstream consumers
- market state
- regime scoring
- weekly macro snapshot
- deployment trust downgrade rules

## Phase 3 — add a dedicated breadth layer

### Goal
Measure participation instead of confusing index level with internal market strength.

### Source posture
Use a two-tier approach.

#### Tier 1: stable proxy breadth (faster to implement)
- RSP vs SPY for equal-weight vs cap-weight participation
- sector participation count from existing sector universe
- QQQ vs equal-weight tech proxy where available
- new 20-day / 50-day relative-strength checks on major leadership cohorts

#### Tier 2: full breadth metrics (better, but more data-heavy)
- % of S&P 500 above 50DMA
- % of S&P 500 above 200DMA
- new highs / new lows
- advance / decline breadth

### New artifact
- `tmp/breadth-state.json`

### Suggested script
- `scripts/breadth_refresh.py`

### Minimum fields
- equal-weight participation metrics
- major-index breadth regime label
- participation score
- sector participation score
- freshness
- warnings

### Downstream consumers
- market state
- regime scoring
- weekly macro snapshot
- dashboard confidence and readiness language

## Phase 4 — strengthen volatility and positioning context

### Goal
Reduce false confidence during tape-driven moves.

### Recommended additions
- VIX term-structure proxy if a stable public source is available
- realized-vs-implied volatility comparison
- positioning proxies via factor / beta / defensive-leadership relationships
- optional sentiment inputs only if they are stable enough to avoid noise inflation

### Candidate artifact
- `tmp/risk-appetite.json`

### Suggested timing
After policy, credit, and breadth are working.
Not before.

## Phase 5 — revisions and expectation-reset layer

### Goal
Improve post-earnings and thesis-maintenance quality.

### What this would cover
- estimate revision direction
- guide-up / guide-down status
- expectation-reset severity
- post-print re-underwrite state

### Reality check
This is valuable but harder with clean free data.
Treat it as a later-phase overlay unless a stable source is found.

## Proposed implementation sequence

1. `policy_expectations_refresh.py`
2. `credit_spread_refresh.py`
3. `breadth_refresh.py`
4. extend `market_state_refresh.py` to ingest the new artifacts
5. extend `regime_scoring_refresh.py` to consume credit + breadth + policy data
6. extend `validate_dashboard_state.py` so missing new artifacts trigger explicit confidence downgrades
7. update note writers only after the new artifacts are trusted

## Acceptance criteria for each new layer

A layer is not ready because the script runs once.
A layer is ready only when:
- the source is stable
- the artifact has freshness metadata
- warning states are explicit
- dashboard validation understands missing / stale / partial states
- the downstream note layer uses the data honestly
- the workflow still works under failure conditions

## Workflow and automation implications

Once phases 0 to 3 are in place, the clean automation map should be:
- **morning chain:** refresh market state, technicals, regime, breadth, band state, deployment, trigger sheet, dashboard, validator, pre-market snapshot
- **post-close chain:** refresh earnings, market state, technicals, regime, breadth, credit, policy, deployment, trigger sheet, post-earnings prep, dashboard, validator, post-market outputs
- **post-earnings chain:** refresh timing-sensitive event state plus post-earnings interpretation artifacts without rerunning the full stack unnecessarily
- **sunday chain:** full rebuild plus weekly macro and weekly intelligence scaffolding

## Recommendation

Build this in a strict order:
1. harden current weak points
2. add policy expectations
3. add credit spreads
4. add breadth
5. only then expand positioning, sentiment, and more polished surfaces

That sequence gives the biggest lift in decision quality without turning the system into a fragile scraper pile.
