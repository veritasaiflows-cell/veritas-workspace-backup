# Market State Refresh, implementation plan

## Goal

Create a reliable Python-backed refresh helper that captures the core market and macro state used by the finance operating system.

This is not a prediction engine.
It is the evidence-input layer.

## First implementation target

The first usable version should refresh a compact state snapshot for:

- Fed funds target range
- FedWatch cut probabilities or nearest policy-path expectation
- 2Y Treasury yield
- 10Y Treasury yield
- 2s10s curve spread
- VIX level
- S&P 500 level
- Brent crude
- WTI crude
- optional DXY later

## Why these fields first

They cover the current operating model directly:

- rates and Fed path drive macro posture
- 2Y and 10Y define front-end and long-end pressure
- curve posture matters for JPM and overall regime interpretation
- VIX measures risk appetite and stress
- S&P 500 gives market-level context
- Brent and WTI matter directly for XOM and the broader energy read

This is enough to materially strengthen the weekly intelligence brief, executive summary, macro dashboard, and deployment decisions.

## Recommended output shape

Write structured JSON to:
- `tmp/market-state.json`

Recommended top-level schema:

```json
{
  "generated_at_utc": "...",
  "status": "ok|partial|error",
  "notes": [],
  "data": {
    "fed": {
      "target_range": "3.50%-3.75%",
      "cut_probability_next_meeting": 0.48,
      "source": "...",
      "as_of": "..."
    },
    "treasuries": {
      "2y": 3.81,
      "10y": 4.31,
      "curve_2s10s_bps": 50,
      "source": "...",
      "as_of": "..."
    },
    "volatility": {
      "vix": 19.12,
      "source": "...",
      "as_of": "..."
    },
    "equities": {
      "spx": 7041.28,
      "source": "...",
      "as_of": "..."
    },
    "energy": {
      "brent": 96.0,
      "wti": 93.0,
      "source": "...",
      "as_of": "..."
    }
  }
}
```

## Recommended source strategy

Use the most reliable available source per field, not one source for everything.

### Preferred source classes

- Official / primary source where realistic
- Large stable public market-data endpoints second
- Browser verification path when needed for spot checks

### Practical source recommendations

#### Fed target range
- Prefer Federal Reserve or a stable summary source if the Fed page is cumbersome to parse directly.

#### FedWatch / cut probability
- Prefer CME FedWatch if accessible in a parseable way.
- If the site is difficult to scrape cleanly, use a validated fallback source and record that fallback in `notes`.

#### Treasury yields
- Prefer Treasury or stable financial-market endpoints with recent close data.

#### VIX and S&P 500
- Prefer stable market quote endpoints or verified public quote pages.

#### Brent and WTI
- Prefer stable quote endpoints or public commodity quote pages.

## First build philosophy

Keep the first usable version conservative:

- support partial success
- record source and as-of metadata for every field
- never silently fabricate missing data
- write `status: partial` when some fields fail
- put fetch issues in `notes`

## Integration path

This script should feed, directly or indirectly:

- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`
- future regime scorecard work

Do not make the script edit those notes directly in version 1.
Version 1 should produce clean structured output first.

## Phase plan

### Phase 1, scaffold to usable data fetch
- Implement actual fetch logic for the core fields
- Produce `tmp/market-state.json`
- Support partial failure cleanly
- Validate sample outputs manually
- Status: completed for SPX, VIX, 10Y, 3M, Brent, WTI, and FRED-backed 2Y / true 2s10s when `FRED_API_KEY` is available

### Phase 2, vault integration
- Use the JSON output in cron-driven workflows and note refresh prompts
- Add light sanity checks, stale-data flags, and source freshness checks
- Status: largely in place for cron-driven workflows, freshness metadata, and macro-note consumption

### Phase 3, expand coverage
- Add credit proxy, for example HYG or spreads
- Add breadth indicators
- Add sector performance snapshot
- Add a better Fed path input, ideally CME FedWatch or a reliable fallback with explicit source labeling
- Status: DXY is now live via yfinance `DX-Y.NYB`

## FedWatch implementation note

As of 2026-04-20, the CME FedWatch landing page is reachable, but the underlying probability payload path is not yet wired cleanly and direct scripted inspection proved flaky enough to time out. Do not bolt on a fragile parser just to say FedWatch is integrated.

Preferred approach:
1. find a stable CME data endpoint or embedded JSON path
2. parse only the next-meeting probability needed for recurring notes
3. record source and as-of metadata explicitly
4. if CME remains unstable for automation, use a clearly labeled fallback source rather than pretending precision

Current recommendation:
- keep `cut_probability_next_meeting` null until a stable path is verified
- prioritize correctness and source labeling over completeness theater

## Success criteria

Version 1 is successful if:

- it runs repeatably without manual intervention
- it outputs clean structured data
- missing fields are obvious rather than hidden
- the weekly intelligence brief and daily executive summary can consume it meaningfully
- it reduces manual re-checking of basic market-state facts

## Do not do yet

- no ML
- no forecasting layer
- no opaque composite score
- no direct note rewrites from the script
- no dependency explosion without need

## Recommendation

This foundation is now live and materially useful.
The next best macro-source priorities are:
1. better Fed path / FedWatch input, but only after the data path is stable enough to trust
2. optional labor or inflation series from FRED if they will actually improve recurring notes
3. credit or breadth context if recurring notes actually need it
