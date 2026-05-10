# Macro Regime Dashboard

## Purpose

This note defines the current macro environment in plain language.

Use it to anchor market views, portfolio posture, and sector preferences.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before major macro refresh passes
- use `tmp/market-state.json` as an evidence input for live market levels and curve context
- keep final regime interpretation human-authored and judgment-based

## Current regime

- **Status:** refreshed against the 2026-05-06 artifact layer
- **Operating regime:** restrictive pause, resilient growth baseline, selective risk-on
- **Confidence:** usable with caution. The machine layer is fresh and the policy artifact is primary-sourced, but the policy model is still a simplified futures approximation and true pre-market tape remains weak.
- **Inflation posture:** still above-target risk, but energy pressure cooled from the prior note. Brent 102.06 and WTI 95.82 keep the inflation tail live without the same late-April acceleration signal.
- **Growth posture:** still treated as resilient rather than recessionary. Credit is benign and breadth is broad / recovering, but this is not a full-clearance regime.
- **Rates posture:** still restrictive. The Fed target remained 3.50%–3.75% as of 2026-05-06. Next FOMC is 2026-06-17, and the current machine layer shows 0% cut probability.
- **Yield curve posture:** 2s10s +42.6 bps and 3m-10y +75.6 bps. The curve is positively sloped, but long rates remain high enough to keep duration and valuation pressure alive.
- **Dollar posture:** DXY 97.96. Soft enough not to be the dominant tightening force, but not a reason to ignore rates and oil.
- **Energy posture:** still live, but weaker than the prior dashboard values. Stronger oil than normal supports energy relevance, while XOM remains a post-print follow-through / repair case rather than a requalified deployment name.
- **Risk-on / risk-off:** selective risk-on with a large-cap quality bias. Broad risk appetite exists, but the actionable list is narrow.

## Working data points (live, as of 2026-05-06 close unless noted)

- **Fed policy range:** 3.50% to 3.75% (confirmed in the live policy artifact; no current manual-dependency flag)
- **Next FOMC:** 2026-06-17
- **Cut probability next meeting:** 0%
- **2-year Treasury:** 3.93% as of 2026-05-05
- **10-year Treasury:** 4.356% as of 2026-05-06
- **3M T-bill:** 3.600% as of 2026-05-06
- **2s10s curve spread:** +42.6 bps
- **3M-10Y spread:** +75.6 bps
- **SPX:** 7,365.12
- **VIX:** 17.39
- **DXY:** 97.96
- **Brent crude:** 102.06
- **WTI crude:** 95.82
- **Credit:** benign in the current machine layer (IG OAS 0.79, HY OAS 2.77 as of 2026-05-05)
- **Breadth:** broad / recovering in the current machine layer

## Macro events in the immediate window

| Date | Event | Significance |
|---|---|---|
| **May 5** | ETN / AMD / SMCI and related AI-infrastructure cluster | Reported; now a read-through and post-earnings-follow-up lane, not a future setup window |
| **May 7** | LNG earnings | Immediate energy / LNG-complex read-through; also the only current blocking band-review warning |
| **May 8** | April NFP | Near-term growth and rates confirmation point |
| **May 12** | CPI | Next major inflation confirmation point |
| **June 17** | FOMC | Next formal policy reset point |

## Base interpretation

- **What regime are we in?**
  - Restrictive pause, resilient growth, selective risk-on.
  - The tape still supports quality and selective exposure, but not careless expansion.
  - Energy keeps the inflation tail alive, and high long-end yields keep discipline necessary.

- **What should still work best?**
  - high-quality large caps with real earnings durability
  - selective financials if credit stays benign and the curve avoids a hard re-tightening shock
  - tactical AI exposure only when price and timing line up
  - energy only when the business backdrop and chart quality both agree

- **What should still struggle?**
  - weak balance-sheet stories that need easy money
  - late entries into already-extended names
  - names still in repair mode being rationalized by macro narrative alone

- **What would invalidate the view?**
  - a real growth break, not just a softer headline
  - a fresh inflation reacceleration that forces more hawkish repricing
  - a credit-stress event
  - an abrupt oil reversal that breaks the current energy backdrop

## Key signals to monitor

- Fed target updates and any future degradation in the policy artifact or approximation path
- 2Y, 10Y, and 30Y Treasury yields
- 2s10s and 3m10y curve shape
- CPI, PPI, PCE, GDP, payrolls, and jobless claims
- DXY
- credit spreads
- VIX
- oil, gold, and copper
- timing-sensitive earnings dates that affect deployment timing

## Sector implications

### Prefer
- large-cap technology with real earnings power, but only when entry discipline holds
- selective financials, especially clean pullback setups
- quality industrial / infrastructure names when the chart and catalyst calendar agree

### Conditional / case-by-case
- energy — macro backdrop supportive, but note-layer interpretation still matters
- defense — thematic support exists, but current tracked charts are still not clean

### Avoid or underweight
- profitless speculative growth
- highly leveraged balance sheets
- extended names being chased far above band
- repair-mode names dressed up as macro calls

## Open questions

- Does XOM stay benched after the May 1 report and weaker energy tape, or does later follow-through justify a real requalification review?
- Does the ETN / AMD / SMCI cluster support the AI power / infrastructure sleeve enough to tighten conviction, or only enough to maintain it?
- Does the still-unconfirmed NVDA May 20 timing path change any near-term deployment judgment once a cleaner primary confirmation path lands?
- Does the LNG blocking band-review warning clear without turning the 16 monitor-only band reviews into fake blockers?

## Freshness and refresh policy

- **Last updated:** 2026-05-07
- **Data as of:** 2026-05-06 close
- **Refresh cadence:** after CPI, PPI, PCE, payrolls, FOMC, or any material regime-breaking move in yields, oil, dollar, credit, or volatility
- **Next refresh due:** after the next meaningful catalyst window or sooner if macro conditions materially change
- **Refresh policy:** update only when the regime framing, key data points, or portfolio implications materially change. Do not keep stale future-tense event language once the event passed.
