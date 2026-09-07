# Macro Regime Dashboard refresh draft — audit remediation

Prepared as a replacement draft for `02. Markets/Macro Regime Dashboard.md` sections only. Uses current workspace artifacts generated 2026-05-17, with market data as of 2026-05-15 unless otherwise stated. Review-only; no portfolio/trade/account authority.

## Replacement: Current regime

- **Status:** refreshed against the 2026-05-17 artifact layer, with market prices/data as of the 2026-05-15 close and policy confirmation as of 2026-05-17.
- **Operating regime:** restrictive pause, resilient-but-cooling growth, selective risk-on with large-cap quality bias.
- **Confidence:** usable with caution / medium. The market, policy, credit, breadth, and weekly macro snapshot layers are current enough for review and presentation, but the source freshness layer still classifies the overall trust state as `manual_dependency` / `review_required` because portfolio posture remains human-maintained and premarket fields are unavailable outside the premarket window. Canonical note mutation is not automatically allowed by freshness alone.
- **Inflation posture:** inflation is the main macro constraint. April CPI was reported at +0.6% m/m and +3.8% y/y, core CPI +0.4% m/m and +2.8% y/y; March PCE was +0.7% m/m and +3.5% y/y, core PCE +0.3% m/m and +3.2% y/y. Energy CPI rose +3.8% m/m and +17.9% y/y, and Brent/WTI strength confirms that inflation risk has re-intensified rather than faded.
- **Growth posture:** resilient but slower, not recessionary. April nonfarm payrolls were +115k with unemployment unchanged at 4.3%; weekly claims remain a monitoring input rather than a regime breaker. Q1 real GDP +2.0% SAAR supports resilience, but inflation and labor cooling argue against a clean broad-risk-on read.
- **Rates posture:** restrictive pause. Fed target remains 3.50%–3.75%, confirmed 2026-05-17; next FOMC is 2026-06-17; current policy artifact shows 0% cut probability / 100% hold probability for the next meeting.
- **Yield curve posture:** positively sloped but not easing-friendly. 2Y 3.820%, 10Y 4.595%, 3M bill 3.588%; 2s10s +77.5 bps and 3M-10Y +100.7 bps. Long rates are high enough to keep valuation and duration discipline necessary.
- **Dollar posture:** DXY 99.27. Firm but not yet a stress signal; watch a sustained push above roughly 101 as the first warning zone for multinationals and risk appetite.
- **Energy posture:** energy is an active macro pressure point. Brent $109.26 and WTI $101.02, EIA crude/gasoline inventory draws, and XLE relative strength confirm a real supply/geopolitical premium. This supports energy relevance but does not clear XOM or other repair-mode names by itself.
- **Risk-on / risk-off:** selective risk-on / defensive-neutral. Credit is benign and breadth is recovering, so the tape is not risk-off. Hot inflation, oil supply premium, firming dollar, deteriorating RSP/SPY, and NVDA earnings risk argue against broad deployment or chase behavior.

## Replacement: Working data points (live, as of 2026-05-15 close unless noted)

- **Artifact generation:** `tmp/market-state.json` generated 2026-05-17T17:00:34Z; `tmp/macro-regime.json` generated 2026-05-17T17:00:35Z; weekly macro snapshot generated 2026-05-17 12:40.
- **Source trust:** `tmp/dashboard-validation.json` generated 2026-05-18T03:41:57Z; overall warning/manual-dependency state, stop_line=false, presentation_allowed=true, canonical_note_mutation_allowed=false, owner_review_required=true.
- **Fed policy range:** 3.50% to 3.75%, confirmed 2026-05-17 via FRED DFEDTARL/DFEDTARU policy artifact.
- **Next FOMC:** 2026-06-17.
- **Cut probability next meeting:** 0%; hold probability 100% per 30-day Fed Funds futures artifact (`ZQM26`).
- **2-year Treasury:** 3.820% as of 2026-05-15, yfinance 2YY=F same-day proxy because FRED DGS2 was lagged at 2026-05-14.
- **10-year Treasury:** 4.595% as of 2026-05-15, yfinance ^TNX.
- **3M T-bill:** 3.588% as of 2026-05-15, yfinance ^IRX.
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
- **Actionable contract in machine layer:** ETN, GOOG, GS, MSFT, NVDA. Treat as review-only, not execution authority.

## Replacement: Macro events in the immediate window

| Date | Event | Significance |
|---|---|---|
| **May 8** | April Employment Situation / NFP | Reported; +115k payrolls and 4.3% unemployment support resilient-but-cooling labor, not a growth break. Remove future-tense language. |
| **May 12** | April CPI | Reported; hot headline/core and energy inflation confirm inflation reacceleration risk. Remove future-tense language. |
| **May 13** | EIA weekly petroleum status for week ended May 8 | Reported; crude and gasoline draws support the oil supply-premium read. |
| **May 15** | Baker Hughes rig count | Reported; U.S. rigs +3 w/w, oil rigs +5 w/w, but supply response is not enough to neutralize the energy premium. |
| **May 20** | NVDA earnings | Dominant tracked-universe event risk for W21; do not treat macro selective-risk-on as clearance to chase through this catalyst. |
| **May 21** | Weekly jobless claims | Near-term labor cooling monitor; not expected to override the regime alone unless claims shock materially. |
| **May 22** | BLS State Employment and Unemployment / BAH earnings | Secondary macro/labor context plus tracked-universe earnings event. |
| **May 28** | BEA Q1 GDP second estimate and April Personal Income/Outlays | Next major growth/PCE confirmation point after W21. |
| **June 17** | FOMC | Next formal policy reset point; current artifact prices 0% cut probability / 100% hold probability. |

## Replacement: Base interpretation

- **What regime are we in?**
  - Restrictive pause, resilient-but-cooling growth, selective risk-on / defensive-neutral.
  - Benign credit and recovering breadth prevent a risk-off label.
  - Hot CPI/PCE, elevated oil, firming DXY, and high long-end yields prevent a clean risk-on label.
  - The practical read is: selective exposure is still supportable, but price discipline and event-risk discipline matter more than macro optimism.

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

- **Portfolio implications / guardrails:**
  - Core quality growth remains favored, but no-chase discipline stays active because rates and NVDA earnings risk can punish extended entries.
  - Financials can remain selective-supportive while credit is benign and the curve remains positive; monitor for any credit-spread widening.
  - Energy has macro support from oil and inventories, but XOM remains repair/blocked until its own conditions clear; oil strength is not a shortcut around rules.
  - Defense/geopolitical beta remains thematic only; LMT repair/below-stop state should not be overridden by headlines.
  - Cash patience remains justified: the regime supports selective review, not forced broad deployment.
  - Machine deployment/readiness surfaces are advisory/review-only and do not grant trade, sizing, account, or owner-approval authority.

## Replacement: Freshness and refresh policy

- **Last updated:** proposed canonical refresh date 2026-05-17 / 2026-05-18 review window.
- **Data as of:** market data 2026-05-15 close; policy artifact confirmed 2026-05-17; dashboard-validation artifact generated 2026-05-18T03:41:57Z.
- **Machine evidence status:** current enough for review/presentation, usable with caution. `market`, `policy`, `credit`, `breadth`, `technical`, `deployment`, `earnings`, `fundamentals`, and `fundamental_ir` sources are current/fresh in the validation artifact; portfolio config remains a manual dependency.
- **Known blockers / trust limits:**
  - `canonical_note_mutation_allowed=false` in dashboard validation; any canonical edit still needs main-session review and the appropriate patch/validation gate.
  - Overall source classification is `manual_dependency` / `review_required`, not clean autonomous sync.
  - Portfolio config is human-maintained and manual; it must not be treated as an automated freshness source.
  - Premarket fields are unavailable outside the premarket window, so futures/market-phase details should not be described as live premarket precision.
  - 2Y Treasury uses yfinance 2YY=F same-day proxy because FRED DGS2 lagged; cite this rather than implying a fully official same-day government source.
  - One event-risk band freeze remains: NVDA. It is review-only / non-applyable through the catalyst window.
- **Refresh cadence:** refresh after CPI, PPI, PCE, payrolls, FOMC, GDP/PCE updates, claims shocks, material yield/oil/dollar/credit/volatility moves, or after NVDA/BAH event-risk windows if they change portfolio posture.
- **Next refresh due:** after NVDA earnings on 2026-05-20 if it materially changes risk appetite or the AI/large-cap quality sleeve; otherwise after the next claims/GDP/PCE confirmation window or any regime-breaking move.
- **Validation suggestions before applying to canonical note:**
  - Re-run `python scripts/market_state_refresh.py` immediately before final apply if the canonical update is delayed beyond the artifact stale window.
  - Re-run dashboard/source validation and confirm `stop_line=false`, market/policy/credit/breadth sources are current, and no new blocker appeared.
  - Diff the canonical dashboard replacement sections against this draft before applying; do not rewrite unrelated sections in the same pass.
  - Preserve review-only language: no trade/account/sizing/owner-approval implication, and no canonical mutation unless the main-session gated path approves it.
