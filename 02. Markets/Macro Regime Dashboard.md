# Macro Regime Dashboard

## Purpose

This note defines the current macro environment in plain language.

Use it to anchor market views, portfolio posture, and sector preferences.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before major macro refresh passes
- use `tmp/market-state.json` as an evidence input for live market levels and curve context
- keep final regime interpretation human-authored and judgment-based

## Current regime

- **Status:** refreshed 2026-05-02, data as of 2026-05-01 close
- **Operating regime:** restrictive pause, resilient growth baseline, selective risk-on
- **Confidence:** reduced but usable; the machine layer is fresh, but policy expectations still carry manual dependencies and several dashboard warnings remain live
- **Inflation posture:** still above target risk, with energy pressure elevated again. Brent 108.17 and WTI 101.94 keep the inflation tail from disappearing.
- **Growth posture:** still treated as resilient rather than recessionary. Credit is benign and breadth is recovering, but this is not a full-clearance regime.
- **Rates posture:** still restrictive. The Fed target remained 3.50%–3.75% on 2026-04-29. Next FOMC is 2026-06-17, and the current machine layer shows 0% cut probability.
- **Yield curve posture:** 2s10s +49.8 bps and 3m-10y +80.3 bps. The curve is positively sloped, but long rates remain high enough to keep duration and valuation pressure alive.
- **Dollar posture:** DXY 98.21. Soft enough not to be the dominant tightening force, but not a reason to ignore rates and oil.
- **Energy posture:** still live, still important, still not permission to skip chart quality. Strong oil helps the energy thesis backdrop, but the note layer still needs explicit post-earnings interpretation before treating XOM as requalified.
- **Risk-on / risk-off:** selective risk-on with a large-cap quality bias. Broad risk appetite exists, but the actionable list is narrow.

## Working data points (live, as of 2026-05-01 close unless noted)

- **Fed policy range:** 3.50% to 3.75% (confirmed 2026-04-29; machine layer still flags manual maintenance)
- **Next FOMC:** 2026-06-17
- **Cut probability next meeting:** 0%
- **2-year Treasury:** 3.88% as of 2026-04-30
- **10-year Treasury:** 4.378% as of 2026-05-01
- **3M T-bill:** 3.575% as of 2026-05-01
- **2s10s curve spread:** +49.8 bps
- **3M-10Y spread:** +80.3 bps
- **SPX:** 7,230.12
- **VIX:** 16.99
- **DXY:** 98.21
- **Brent crude:** 108.17
- **WTI crude:** 101.94
- **Credit:** benign in the current machine layer
- **Breadth:** broad / recovering in the current machine layer

## Macro events in the immediate window

| Date | Event | Significance |
|---|---|---|
| **May 2** | BRK.B earnings | Ballast / quality read-through |
| **May 4–8** | ETN, AMD, SMCI, EOG, ET, MPLX, WMB, PLTR, KTOS, LNG cluster | Next real decision window for several tracked sleeves |
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

- Fed target updates and the still-manual policy layer
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

- Does XOM stay benched after the May 1 report, or does the post-earnings interpretation justify a real requalification review?
- Does the ETN / AMD / SMCI cluster next week support the AI power / infrastructure sleeve enough to tighten conviction, or only enough to maintain it?
- Do the still-live date mismatches change any timing-sensitive decisions once they are directly confirmed?
- Does the warning stack shrink after band review work, or is the current reduced-confidence posture still the right one?

## Freshness and refresh policy

- **Last updated:** 2026-05-02
- **Data as of:** 2026-05-01 close
- **Refresh cadence:** after CPI, PPI, PCE, payrolls, FOMC, or any material regime-breaking move in yields, oil, dollar, credit, or volatility
- **Next refresh due:** after the next meaningful catalyst window or sooner if macro conditions materially change
- **Refresh policy:** update only when the regime framing, key data points, or portfolio implications materially change. Do not keep stale future-tense event language once the event passed.
