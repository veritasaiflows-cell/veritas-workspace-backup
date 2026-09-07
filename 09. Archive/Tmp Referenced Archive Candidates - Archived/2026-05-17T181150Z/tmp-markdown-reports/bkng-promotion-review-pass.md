# BKNG Promotion-Review Pass — Review-Only

- **Generated:** 2026-05-10
- **Ticker:** BKNG
- **Company:** Booking Holdings Inc.
- **Primary listing:** NASDAQ Global Select Market
- **Country / domicile:** United States / Delaware
- **Operational verdict:** **promotion-review candidate**, not deployable
- **Authority stop line:** no deployment, no sizing, no owner-approval inference, no trade execution, no probability / expected-return / model-ranked claims.

## 1. Resolved entity and data-quality scorecard

**Resolved entity:** Booking Holdings Inc. (`BKNG`), NASDAQ-listed online travel platform. The SEC 8-K for April 28, 2026 identifies Booking Holdings Inc. and common stock trading symbol `BKNG` on NASDAQ.

**Data-quality scorecard**

| Field | Judgment |
|---|---|
| Coverage | ~85% for this bounded promotion-review pass: entity, recent earnings, FY 2025 results, balance sheet, cash flow, valuation, portfolio fit, and technical state covered. |
| Source quality | Strong for operating results and balance sheet: SEC-hosted Q1 2026 8-K / Exhibit 99.1 and SEC-hosted FY 2025 earnings release. Valuation uses StockAnalysis as Tier 2 market-data support. |
| Freshness | Latest company-reported quarter: Q1 2026, reported Apr 28, 2026. Workspace technical data as of 2026-05-08 close. |
| Conflicts | 0 material source conflicts found in this bounded pass. The prior workspace earnings-state gap has been resolved to `CLEAR` from the generated earnings-calendar artifact; deployment timing remains blocked by repair-mode technical state. |
| Confidence cap | **Medium-high for fundamentals**, **low for deployment timing** because the technical layer is repair-mode, below-stop, and below all major moving averages even though catalyst/date state is now known. |

## 2. Fundamental view

### Business quality

BKNG screens as a high-quality, asset-light travel marketplace rather than a speculative consumer story. Q1 2026 company results showed:

- Room nights: **338M**, up **6%** year over year.
- Gross bookings: **$53.8B**, up **15%** reported / ~**8% constant currency**.
- Revenue: **$5.5B**, up **16%** reported / ~**10% constant currency**.
- Adjusted EBITDA: **$1.3B**, up **19%**.
- Adjusted EBITDA margin: **23.3%**, versus **22.9%** in Q1 2025.

The business has scale, direct-channel strength, strong platform economics, and high-margin conversion of travel demand into earnings and cash flow. FY 2025 results support durability: revenue **$26.9B** (+13%), adjusted EBITDA **$9.9B** (+20%), and adjusted EBITDA margin **36.9%**.

### Balance sheet and leverage

Balance sheet is acceptable but not risk-free:

- Q1 2026 cash and equivalents: **$16.0B**.
- Short-term debt: **$3.0B**.
- Long-term debt: **$15.4B**.
- Total current assets: **$20.9B** versus current liabilities **$19.8B**.
- StockAnalysis reports current ratio **1.06**, quick ratio **0.99**, debt / EBITDA **1.80**, and interest coverage **8.01**.

The company has meaningful debt and negative book equity due to buybacks, but cash generation and coverage appear strong enough that financing risk is not the dominant thesis breaker under normal conditions. Debt maturity / interest coverage should still remain part of the next deeper review before any deployment-grade recommendation.

### Cash flow and capital allocation

Cash flow is the strongest part of the case:

- Q1 2026 operating cash flow: **$3.2B**.
- Q1 2026 free cash flow: **$3.1B**, down **2%** year over year but still very strong.
- FY 2025 operating cash flow: **$9.4B**, up **13%**.
- FY 2025 free cash flow: **$9.1B**, up **15%**.
- Q1 2026 share repurchases: **$3.6B**.
- Remaining repurchase authorization at Mar. 31, 2026: **$18.2B**.
- Q2 dividend declared: **$0.42/share**, post-split.

Capital allocation is shareholder-return heavy. That works when cash generation persists; it becomes a risk if travel demand weakens while the stock is still technically broken.

### Valuation

Valuation is reasonable for quality, but not a standalone reason to override technical repair.

StockAnalysis as of May 8, 2026:

- Market cap: **$128.6B**.
- Enterprise value: **$131.4B**.
- Trailing P/E: **21.8x**.
- Forward P/E: **15.5x**.
- Price / FCF: **14.2x**.
- EV / EBITDA: **12.7x**.
- LTM revenue: **$27.7B**.
- LTM free cash flow: **$9.0B**.

For a high-ROIC, high-FCF online travel leader, that valuation is not obviously stretched. The catch is cyclicality: the market may be discounting travel/geopolitical demand risk and the current chart damage. This is a **good-business / potentially interesting-stock** setup, not a deployable setup yet.

### Recent earnings / guidance / catalysts

Q1 2026 was fundamentally solid but came with explicit macro/geopolitical caution:

- Management said Middle East conflict reduced room-night growth by roughly **2 percentage points** and impacted bookings / revenue growth.
- Q2 2026 guidance assumes the conflict impact continues through June.
- FY 2026 guidance assumes recovery in bookings in the second half of 2026.
- Management warned that sustained disruption could pressure jet fuel, airline capacity, traveler sentiment, and broader travel demand.

Catalyst read: the earnings report supports promotion review, but the guidance caveat is real. The travel thesis is not broken, but the next decision layer must monitor geopolitical and consumer demand sensitivity.

## 3. Sector / diversification fit

BKNG is the cleanest Consumer Discretionary diversifier identified in the current screen because it is not a Tech bridge name like AMZN and does not add to the already capped direct Technology sleeve.

Workspace sector context:

- Consumer Discretionary / XLY is **0% represented** in the model portfolio.
- XLY is above its 50DMA but underperforming SPY over 1d, 5d, and 20d in the sector-expansion board.
- Direct Technology is already at the **25% sector cap**.
- Tech + AI-power correlated sleeve is already warning-grade at **32% including ETN**.

Fit judgment: BKNG deserves research-board attention because it adds cleaner Consumer Discretionary / travel exposure and would diversify away from Tech concentration if later promoted. But XLY is not leading; this is selective quality review, not broad sector deployment.

Correlation caveats:

- Travel is economically sensitive and can behave as risk-on consumer beta.
- Geopolitical disruption, fuel prices, airline capacity, FX, and consumer confidence can hit the same time.
- BKNG diversifies sector classification, but it does not provide defensive ballast.

## 4. Technical / entry state from workspace artifacts

BKNG is **not deployable** under the current technical layer.

From `tmp/band-proposals.json` as of the 2026-05-08 data date:

- Coverage lane: **watch**.
- Workflow state: **REPAIR**.
- Entry policy: **repair_mode**.
- Close: **165.93**.
- MA20 / MA50 / MA200: **177.08 / 174.19 / 198.30**.
- Trend stack: **BELOW_ALL_MAS**.
- Band status: **BELOW_STOP**.
- Suggested reclaim band: **198.30–206.38**.
- Earnings state: **CLEAR** (`days_to_earnings=80`, provider estimate 2026-07-29; not primary-confirmed).
- Canonical apply eligible: **false**.

From the live Watchlist / Coverage Universe:

- BKNG is active watch / Consumer Discretionary Tier 1 research candidate.
- Technical repair is required.
- No deployment until reclaim / hold of **174–177**.
- Preserve **161–164** support.
- No capital deployment while below the 20/50/200DMA structure.

Repair requirements before any future deployment review:

1. Reclaim and hold the **174–177** repair zone.
2. Stop making lower-risk entries impossible by staying below all major MAs.
3. Treat earnings/catalyst state as known-but-not-primary-confirmed: `CLEAR`, 80 days to provider-estimated 2026-07-29.
4. Re-run technical levels after repair; do not auto-apply the current reclaim band as a live entry band.
5. Keep risk envelope explicit before any promotion beyond research/watch status.

## 5. Final operational bucket

**Final bucket: promotion-review candidate.**

BKNG is stronger than research-only because the business quality, cash flow, valuation, and diversification fit justify continued work. It is not merely watch-only in the sense of a vague idea. But it is also clearly not deployable because the chart is in repair, below all major moving averages, flagged below-stop, and the current band remains a repair-mode / below-stop wait-state rather than an applyable execution setup.

## 6. Explicit stop lines

- No deployment.
- No sizing.
- No owner approval inference.
- No trade execution.
- No canonical note mutation from this artifact.
- No probability, expected-return, or model-ranked claim.
- Do not treat strong fundamentals as a technical trigger.
- Do not let Consumer Discretionary underexposure become an excuse to buy a broken setup.

## 7. BKNG band-staleness / trust-warning recommendation

Recommended handling: **keep BKNG in a manual wait-state and mark the current warning as an accepted repair-mode blocker**, not as a stale band requiring canonical application.

Rationale:

- The BKNG band row is fresh (`band_last_set` 2026-05-10, trading days old 0), but it is blocking because the name is in **REPAIR**, **repair_mode**, **BELOW_STOP**, **below all major MAs**, and canonical application remains false despite `earnings_state=CLEAR`.
- This is not a normal stale-band update. It is a correct fail-closed condition for a watch-lane name whose fundamentals merit review but whose technical state is not decision-grade.
- Applying the suggested reclaim band to canonical notes would overstate readiness. The right owner-layer interpretation is: research continues; deployment remains blocked until repair.

Implemented cleanup path: `tmp/band-proposals.json` now carries `accepted_repair_mode_blockers` and dashboard validation uses it to distinguish true unresolved stale-band debt from deliberately accepted repair-mode wait-states. This does not mutate canonical portfolio/deployment notes and does not make BKNG deployable.

## Sources used

Primary / Tier 1:

- SEC 8-K, Booking Holdings Inc., Apr. 28, 2026, Exhibit 99.1 Q1 2026 earnings release.
- SEC-hosted Q4 / FY 2025 earnings release, Feb. 18, 2026.

Tier 2 support:

- StockAnalysis BKNG Statistics & Valuation, fetched May 10, 2026, for market cap, valuation multiples, LTM margins, current ratio, debt / EBITDA, interest coverage, and share/price statistics.

Workspace artifacts:

- `tmp/band-proposals.json`
- `tmp/consumer-discretionary-candidate-screen.md`
- `02. Markets/Watchlist.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `07. Risk/Risk Rules.md`
- `tmp/sector-expansion-board.json`
- `tmp/sector-correlation-check.json`
- `04. Research/Coverage Universe.md`
