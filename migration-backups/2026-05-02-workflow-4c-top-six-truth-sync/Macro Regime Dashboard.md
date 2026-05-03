# Macro Regime Dashboard

## Purpose

This note defines the current macro environment in plain language.

Use it to anchor market views, portfolio posture, and sector preferences.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before major macro refresh passes
- use `tmp/market-state.json` as an evidence input for live market levels and curve context
- keep final regime interpretation human-authored and judgment-based

## Current regime

- Status: refreshed **2026-04-28**, data as of **2026-04-27 close**
- Inflation posture: above target but not spiraling. Headline elevated by the Hormuz oil whipsaw — Brent rallied from $90 (April 17) to $102 (April 27). The April CPI print (May 12) is the next read on whether the second pass of energy-driven headline inflation shows up.
- Growth posture: slowing but resilient. Q1 2026 GDP advance estimate releases April 30 — the Hormuz shock hit in March and will partially show. Labor is softening at the margin but not breaking (March payrolls +178k, unemployment 4.3%).
- Rates posture: still restrictive. **FOMC meets April 29.** No cut expected. Powell's tone into all-time-high equity markets is the real variable. Fed funds futures imply roughly one cut in all of 2026, possibly zero. With oil above $100, the bar for any dovish signal is high.
- Yield curve posture: positively sloped but the steepening is at the wrong end. **2s10s at +55.6 bps** (up from +48 last week — long rates rising, not short rates falling). **3M-10Y at +74.6 bps**. Long-end yields elevated at 4.336%, keeping duration pressure alive.
- Dollar posture: **DXY at 98.53** as of April 27 — soft, below 100 for the first time in extended recent history. A weak dollar with oil above $100 is a mixed but inflation-amplifying combination.
- Energy posture: ⚠️ **Hormuz disruption renewed.** Brent has rallied from the post-ceasefire $90 low (April 17) to $102 (April 27). WTI to $96.89. Iran ceasefire is NOT holding — Trump suspended negotiations; Pakistani-mediated proposal is on the table. Brent/WTI spread $5.21 reflects ongoing route-disruption premium. **XOM May 1 earnings is now the requalification gate** — earnings quality should be substantially better than when the repair call was made at WTI $84.
- Liquidity posture: not abundant. Selectivity still required.
- Risk-on / risk-off: selective risk-on, but symmetry has tightened. **SPX 7,173.91**. **VIX 18.02** — moderate, not complacent. Approaching the densest catalyst window of the cycle (FOMC + GOOG/MSFT/AMZN earnings April 29).

## Working data points (live, as of 2026-04-27 close unless noted)

- Fed policy range: **3.5% to 3.75%** (hold, hardcoded — confirmed 2026-04-19; manual update required after April 29 FOMC decision)
- Fed cut probability: FedWatch unwired (ZQK26 fetch failing); manual read is roughly one cut in 2026 at best, possibly zero given oil resurgence
- 2-year Treasury: **3.78%** as of 2026-04-24 (FRED DGS2; FRED publishes with 1-day lag — expected behavior)
- 10-year Treasury: **4.336%** as of 2026-04-27 (yfinance ^TNX) — up from 4.31% last week
- 3M T-bill: **3.59%** as of 2026-04-27 (yfinance ^IRX)
- 2s10s curve spread: **+55.6 bps** (FRED DGS2 + yfinance ^TNX) — widened ~7 bps from last week
- 3M-10Y spread: **+74.6 bps**
- SPX: **7,173.91** as of 2026-04-27 (yfinance ^GSPC) — at/near all-time highs, four consecutive up weeks
- VIX: **18.02** as of 2026-04-27 (yfinance ^VIX) — moderate fear, slightly elevated relative to ATH tape
- DXY: **98.53** as of 2026-04-27 (yfinance DX-Y.NYB)
- Brent crude: **$102.10** as of 2026-04-27 (yfinance BZ=F) — up ~$12 from $90.38 on April 17
- WTI crude: **$96.89** as of 2026-04-27 (yfinance CL=F) — up ~$13 from $83.85 on April 17
- Sector tape (2026-04-27): XLI +0.02%, XLF +0.76% (strongest), XLK +0.22%, XLE -0.18% (weakest despite oil at $102 — possibly pricing Hormuz resolution hope or rate-rotation headwind)

## Macro events in the immediate window

| Date | Event | Significance |
|---|---|---|
| **April 29** | FOMC decision + presser | Densest single-day catalyst — also AMZN/GOOG/MSFT after close |
| **April 30** | Q1 2026 GDP advance + CAT earnings | Growth read + industrial demand read |
| **May 1** | XOM + CVX earnings | Energy requalification gate |
| **May 2** | BRK.B earnings (date corrected from May 4) | Ballast read |
| **May 5** | ETN, AMD, SMCI, EOG, LDOS earnings | AI power + chip equipment + energy |
| **May 12** | April CPI release | Second pass of Hormuz oil into headline |
| **May 20** | NVDA earnings (date corrected from May 27) | AI infrastructure |

## Base interpretation

- What regime are we in?
  - **Late-cycle, restrictive-policy, resilient-growth regime with renewed energy/inflation tail risk.**
  - The April 14–19 baseline (oil collapsing, ceasefire holding) is no longer current. Hormuz disruption has materially returned. Stagflationary pressure-set is higher now than two weeks ago.

- What should outperform?
  - high-quality equities with real earnings durability
  - large-cap leaders with balance-sheet strength
  - selective financials if the curve continues to normalize without a sharp credit break
  - energy and defense when geopolitics and supply constraints matter — but defense names (LMT, RTX) are in repair mode despite the geopolitical tailwind, so the read-through is muted
  - cash-flowing businesses over story stocks when rates stay real

- What should struggle?
  - long-duration speculative equities without earnings support
  - weak balance-sheet companies that need easy money
  - crowded narrative trades if macro data stay mixed and rates remain restrictive
  - businesses heavily exposed to demand slowdown without pricing power

- What would invalidate the view?
  - a sharp labor-market deterioration (jobless claims breaking through 220k)
  - a clean and fast inflation collapse that opens the door to materially easier policy (low-probability with oil at $102)
  - a renewed inflation reacceleration that forces more hawkish repricing (becoming more likely with energy)
  - a credit event or geopolitical shock that abruptly shifts the regime into full risk-off
  - a confirmed Hormuz ceasefire breakthrough — would reverse the energy gains in days

## Key signals to monitor

- Fed funds futures (still need FedWatch wiring — currently manual)
- 2Y, 10Y, and 30Y Treasury yields
- 2s10s and 3m10y curve shape
- CPI, PPI, PCE
- Unemployment and payrolls
- DXY
- Credit spreads
- VIX
- Oil, gold, and copper
- **Hormuz status** (Pakistani-mediated negotiations specifically)

## Sector implications

### Prefer
- large-cap technology with real earnings power, not pure hype (post-April 29 prints will discriminate)
- selective financials (JPM and GS the cleanest tracked names; both no near-term earnings)
- energy with caveats — XOM and CVX should benefit from oil at $97–102, but XOM/CVX both report May 1 and chart structure hasn't followed the oil move yet
- defense and aerospace — but LMT and RTX in repair mode despite geopolitical tailwind
- quality industrial and infrastructure names tied to durable spend (CAT, ETN, VRT)

### Neutral
- broad index exposure
- healthcare
- consumer names with pricing power and resilient demand
- bonds, but mainly as a tactical or diversification tool until rate clarity improves

### Avoid or underweight
- profitless speculative growth
- highly leveraged businesses
- low-quality small caps that depend on easy liquidity
- weak thematic trades with no valuation discipline

## Open questions

- **April 29 FOMC tone:** Is Powell willing to acknowledge the energy-driven inflation tail risk explicitly, or does the Fed try to look through it as supply-side noise? A hawkish acknowledgment would create equity pressure at all-time highs.
- **GOOG / MSFT / AMZN earnings (April 29):** Three core portfolio names report into the FOMC day. Are AI monetization and cloud growth still accelerating, or is the second-derivative slowing? Decision framework: beat + constructive guidance = reassess band; miss or guide down = extend block or move to bench.
- **Q1 GDP April 30:** Does the Hormuz shock show up in the data? Consensus +1.5–2.0% annualized.
- **Hormuz negotiations:** Is the Pakistani-mediated proposal a genuine opening or a delaying tactic? Either way, oil structure is fragile.
- **XOM/CVX May 1:** With WTI at $97, earnings quality should be much better than at $84. Does the chart finally follow the oil move?
- **April CPI (May 12):** Does the energy whipsaw show up cleanly in headline, or is the timing too tight for the May print?

## Sources behind this baseline

- St. Louis Fed remarks, 2026-04-01, describing a highly uncertain outlook, policy hold at 3.5% to 3.75%, and baseline growth near potential
- BLS releases showing March 2026 CPI, payrolls, unemployment, and PPI
- BEA February 2026 Personal Income and Outlays summary
- Dallas Fed Trimmed Mean PCE update for February 2026
- Live yfinance + FRED inputs via `tmp/market-state.json` (refreshed 2026-04-28)
- Geopolitical context from 2026-04-27 WIB section

## Freshness and refresh policy

- Last updated: **2026-04-28** — full refresh to 2026-04-27 close data. Updated all working data points, regime framing updated to reflect Hormuz re-disruption (Brent $90 → $102), FOMC approach, energy tape lagging the oil move, and the April 29 catalyst density.
- Data as of: 2026-04-27 close (script-backed market-state refresh via `tmp/market-state.json`)
- Refresh cadence: after CPI, PPI, PCE, payrolls, FOMC, or any material regime-breaking move in yields, oil, dollar, credit, or volatility
- Next refresh due: **April 29 evening — post-FOMC + post-megacap-earnings**. Mandatory refresh before May 12 CPI print.
- Refresh policy: update only when the regime framing, key data points, or portfolio implications materially change. Do not rewrite for noise.
- Note on 2Y lag: FRED DGS2 publishes with a 1-day lag. The 2Y showing Apr 24 when other fields show Apr 27 is expected behavior, not a data failure.

## Last updated

- 2026-04-19 — initial baseline established
- 2026-04-20 — market-state script now supports FRED-backed 2Y Treasury and true 2s10s calculation
- 2026-04-26 — full refresh to Apr 24 close data. Oil recovery flagged ($84→$94 WTI / $90→$99 Brent week of Apr 21-24).
- 2026-04-28 — full refresh to Apr 27 close data. Hormuz re-disruption confirmed (Brent $102, WTI $97). Sector tape note added (XLE underperforming despite oil rally — meaningful signal). FOMC + megacap earnings April 29 framed as densest catalyst window. RTX added to repair-mode list alongside LMT.
