# Macro Regime Dashboard

## Purpose

This note defines the current macro environment in plain language.

Use it to anchor market views, portfolio posture, and sector preferences.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before major macro refresh passes
- use `tmp/market-state.json` as an evidence input for live market levels and curve context
- keep final regime interpretation human-authored and judgment-based

## Current regime

- **Status:** refreshed against the 2026-05-17 artifact layer, with market prices/data as of the 2026-05-15 close and policy confirmation as of 2026-05-17.
- **Operating regime:** restrictive pause, resilient-but-cooling growth, selective risk-on with large-cap quality bias.
- **Confidence:** usable with caution / medium. The market, policy, credit, breadth, and weekly macro snapshot layers are current enough for review and presentation, but the source freshness layer still classifies the overall trust state as `manual_dependency` / `review_required` because portfolio posture remains human-maintained and premarket fields are unavailable outside the premarket window.
- **Inflation posture:** inflation is the main macro constraint. April CPI was reported at +0.6% m/m and +3.8% y/y, core CPI +0.4% m/m and +2.8% y/y. March PCE was +0.7% m/m and +3.5% y/y, core PCE +0.3% m/m and +3.2% y/y. Energy CPI rose +3.8% m/m and +17.9% y/y. Brent/WTI strength confirms inflation risk has re-intensified rather than faded.
- **Growth posture:** resilient but slower, not recessionary. April nonfarm payrolls were +115k with unemployment unchanged at 4.3%; weekly claims remain a monitoring input rather than a regime breaker. Q1 real GDP +2.0% SAAR supports resilience, but inflation and labor cooling argue against a clean broad-risk-on read.
- **Rates posture:** restrictive pause. Fed target remains 3.50%–3.75%, confirmed 2026-05-17; next FOMC is 2026-06-17; current policy artifact shows 0% cut probability / 100% hold probability for the next meeting.
- **Yield curve posture:** positively sloped but not easing-friendly. 2Y 3.820%, 10Y 4.595%, 3M bill 3.588%; 2s10s +77.5 bps and 3M-10Y +100.7 bps. Long rates are high enough to keep valuation and duration discipline necessary.
- **Dollar posture:** DXY 99.27. Firm but not yet a stress signal; watch a sustained push above roughly 101 as the first warning zone for multinationals and risk appetite.
- **Energy posture:** energy is an active macro pressure point. Brent $109.26 and WTI $101.02, EIA crude/gasoline inventory draws, and XLE relative strength confirm a real supply/geopolitical premium. This supports energy relevance but does not clear XOM or other repair-mode names by itself.
- **Risk-on / risk-off:** selective risk-on / defensive-neutral. Credit is benign and breadth is recovering, so the tape is not risk-off. Hot inflation, oil supply premium, firming dollar, deteriorating RSP/SPY, and NVDA earnings risk argue against broad deployment or chase behavior.

## Working data points

Live artifact basis: `tmp/market-state.json` generated 2026-05-17T17:00:34Z; `tmp/macro-regime.json` generated 2026-05-17T17:00:35Z; dashboard validation generated 2026-05-18T03:41:57Z. Market data is as of 2026-05-15 close unless noted.

- **Fed policy range:** 3.50% to 3.75%, confirmed 2026-05-17 via FRED DFEDTARL/DFEDTARU policy artifact.
- **Next FOMC:** 2026-06-17.
- **Cut probability next meeting:** 0%; hold probability 100% per 30-day Fed Funds futures artifact (`ZQM26`).
- **2-year Treasury:** 3.820% as of 2026-05-15, yfinance `2YY=F` same-day proxy because FRED DGS2 was lagged at 2026-05-14.
- **10-year Treasury:** 4.595% as of 2026-05-15, yfinance `^TNX`.
- **3M T-bill:** 3.588% as of 2026-05-15, yfinance `^IRX`.
- **2s10s curve spread:** +77.5 bps.
- **3M-10Y spread:** +100.7 bps.
- **SPX:** 7,408.50.
- **VIX:** 18.43.
- **DXY:** 99.27.
- **Brent crude:** $109.26.
- **WTI crude:** $101.02.
- **Brent/WTI spread:** $8.24.
- **Credit:** benign; IG OAS 0.76, HY OAS 2.76 as of 2026-05-14; HY tightening.
- **Breadth:** broad / recovering; 8 of 11 sectors above 50DMA; participation 72.7%; RSP/SPY 5-day change -1.4517%, which keeps the breadth read mixed rather than clean.
- **Sector leadership vs SPY:** strongest XLE (+3.6% relative), weakest XLK (-0.6% relative) in the current artifact.

## Macro events in the immediate window

| Date | Event | Significance |
|---|---|---|
| **May 8** | April Employment Situation / NFP | Reported; +115k payrolls and 4.3% unemployment support resilient-but-cooling labor, not a growth break. |
| **May 12** | April CPI | Reported; hot headline/core and energy inflation confirm inflation reacceleration risk. |
| **May 13** | EIA weekly petroleum status for week ended May 8 | Reported; crude and gasoline draws support the oil supply-premium read. |
| **May 15** | Baker Hughes rig count | Reported; U.S. rigs +3 w/w, oil rigs +5 w/w, but supply response is not enough to neutralize the energy premium. |
| **May 20** | NVDA earnings | Dominant tracked-universe event risk for W21; do not treat macro selective-risk-on as clearance to chase through this catalyst. |
| **May 21** | Weekly jobless claims | Near-term labor cooling monitor; not expected to override the regime alone unless claims shock materially. |
| **May 22** | BLS State Employment and Unemployment / BAH earnings | Secondary macro/labor context plus tracked-universe earnings event. |
| **May 28** | BEA Q1 GDP second estimate and April Personal Income/Outlays | Next major growth/PCE confirmation point after W21. |
| **June 17** | FOMC | Next formal policy reset point; current artifact prices 0% cut probability / 100% hold probability. |

## Base interpretation

- **What regime are we in?**
  - Restrictive pause, resilient-but-cooling growth, selective risk-on / defensive-neutral.
  - Benign credit and recovering breadth prevent a risk-off label.
  - Hot CPI/PCE, elevated oil, firming DXY, and high long-end yields prevent a clean risk-on label.
  - Practical read: selective exposure is still supportable, but price discipline and event-risk discipline matter more than macro optimism.

- **What should still work best?**
  - high-quality large caps with real earnings durability and clean entry discipline
  - selective financials while credit remains benign and the curve avoids hard re-tightening
  - industrial / electrification exposure where chart, catalyst calendar, and valuation band agree
  - tactical AI exposure only after catalyst and price-risk checks, especially around NVDA's 2026-05-20 earnings
  - energy as a macro-relevant monitor while oil supply premium persists, but only for names whose own rules and charts clear

- **What should still struggle?**
  - weak balance-sheet stories that require easy money or falling rates
  - long-duration / valuation-sensitive names being chased into elevated long yields
  - profitless speculative growth
  - repair-mode names rationalized by oil, defense, or geopolitical headlines alone
  - broad market deployment claims that ignore RSP/SPY deterioration and event risk

- **What would invalidate the view?**
  - a genuine growth break: payroll/claims deterioration, credit stress, or earnings guidance reset strong enough to move the regime from selective-risk-on to risk-off
  - fresh inflation acceleration that forces hawkish repricing, pushes the 10Y materially higher, or moves DXY above the stress watch zone
  - oil premium reversal: Hormuz/Middle East risk fades and inventories build, undercutting the current energy squeeze read
  - credit stress: HY/IG OAS deterioration that overrides the benign-credit pillar
  - breadth failure: participation rolls over and RSP/SPY weakness broadens beyond large-cap leadership rotation

## Portfolio implications / guardrails

- Core quality growth remains favored, but no-chase discipline stays active because rates and NVDA earnings risk can punish extended entries.
- Financials can remain selective-supportive while credit is benign and the curve remains positive; monitor for any credit-spread widening.
- Energy has macro support from oil and inventories, but XOM remains repair/blocked until its own conditions clear; oil strength is not a shortcut around rules.
- Defense/geopolitical beta remains thematic only; LMT repair/below-stop state should not be overridden by headlines.
- Cash patience remains justified: the regime supports selective review, not forced broad deployment.
- Machine deployment/readiness surfaces are advisory/review-only and do not grant trade, sizing, account, or owner-approval authority.

## Key signals to monitor

- Fed target updates and any future degradation in the policy artifact or approximation path
- 2Y, 10Y, and 30Y Treasury yields
- 2s10s and 3m10y curve shape
- CPI, PPI, PCE, GDP, payrolls, and jobless claims
- DXY, especially a sustained move above the stress watch zone
- credit spreads
- VIX
- oil, gold, copper, and inventory/rig-count signals
- NVDA / AI-power read-through into MSFT, GOOG, VRT, AMD, SMCI, and ETN


## Research and sector opportunity cue ? 2026-05-21 post-close

Artifact basis: `tmp/research-freshness-opportunity-review.json` generated 2026-05-21T21:10:21Z and `tmp/full-portfolio-view-validation.json` generated 2026-05-21T20:22:10Z. The cue is **review-only** and degraded-but-usable because sector expansion remains degraded; no portfolio action, promotion, sizing/sleeve/cash change, trade/account action, or owner approval is inferred.

- Improving leadership from the current sector/opportunity layer: **Consumer Discretionary, Consumer Staples, Energy, Financials, Health Care, Real Estate, Technology**.
- Underexposed lanes to keep in the research radar: **Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, Utilities**.
- Candidate queue shape: portfolio review **CME, ITA, LIN, META, PH, VRT**; conditional watch **ECL, GE, NFLX, TMUS, VMC, WMB**; blocked/deferred **CAT, ETN, GS, JPM, LLY, NVDA**.
- Small/mid-cap ETF posture remains deteriorating / review-only with no improving small/mid candidates; **USO** remains the only current commodity review candidate and requires explicit macro/correlation/volatility review before any proposal.
- **Boundary:** Review-only cue: no promotion, sizing, sleeve, cash, deployment, trade, account action, or owner approval is inferred from this cron output.

## Sector implications

### Prefer / allow selective review
- large-cap quality technology only when entry discipline holds
- selective financials if credit stays benign and the curve avoids a hard re-tightening shock
- quality industrial / infrastructure names when the chart and catalyst calendar agree
- AI-power / electrification only when concentration and price discipline agree

### Conditional / case-by-case
- energy — macro backdrop is supportive, but repair-mode names still require their own chart/thesis clearance
- defense — thematic support exists, but current tracked charts are still not clean
- commodities / macro diversifiers — review-only while oil/inflation pressure persists

### Avoid or underweight
- profitless speculative growth
- highly leveraged balance sheets
- extended names being chased far above band
- repair-mode names dressed up as macro calls

## Open questions

- Does NVDA's 2026-05-20 event validate or reset the AI/semiconductor/AI-power sleeve?
- Does ETN remain inside band while AI-power correlation remains elevated, or does it need patience despite being the cleanest in-band candidate?
- Does oil stay above the current pressure zone long enough to justify a fresh energy/commodity review, or reverse enough to weaken that thesis?
- Does the RSP/SPY deterioration remain a manageable quality-bias signal or become a broader breadth warning?
- Does the LMT/defense gap get solved through ETF validation rather than forcing a broken single-name setup?

## Freshness and refresh policy

- **Last updated:** 2026-05-17 / 2026-05-18 review window.
- **Data as of:** market data 2026-05-15 close; policy artifact confirmed 2026-05-17; dashboard-validation artifact generated 2026-05-18T03:41:57Z.
- **Machine evidence status:** current enough for review/presentation, usable with caution. Market, policy, credit, breadth, technical, deployment, earnings, fundamentals, and fundamental-IR sources are current/fresh in the validation artifact; portfolio config remains a manual dependency.
- **Known blockers / trust limits:**
  - overall source classification is `manual_dependency` / `review_required`, not clean autonomous sync
  - portfolio config is human-maintained and manual; it must not be treated as an automated freshness source
  - premarket fields are unavailable outside the premarket window, so futures/market-phase details should not be described as live premarket precision
  - 2Y Treasury uses yfinance `2YY=F` same-day proxy because FRED DGS2 lagged
  - one event-risk band freeze remains: NVDA; it is review-only / non-applyable through the catalyst window
- **Refresh cadence:** refresh after CPI, PPI, PCE, payrolls, FOMC, GDP/PCE updates, claims shocks, material yield/oil/dollar/credit/volatility moves, or after NVDA/BAH event-risk windows if they change portfolio posture.
- **Next refresh due:** after NVDA earnings on 2026-05-20 if it materially changes risk appetite or the AI/large-cap quality sleeve; otherwise after the next claims/GDP/PCE confirmation window or any regime-breaking move.
- **Refresh policy:** update only when the regime framing, key data points, or portfolio implications materially change. Do not keep stale future-tense event language once an event has passed.

## Authority boundary

This note is decision support only. It does not authorize trade/account action, paper/live orders, cash movement, sizing/sleeve changes, canonical portfolio mutation, or inferred owner approval. Portfolio/canon maintenance, when allowed, must still route through the approved WF64/WF56 gated validator path.
