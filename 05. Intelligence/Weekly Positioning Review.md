# Weekly Positioning Review

## Purpose

Use this as the standing weekly operating map.

It sits between the broad Sunday intelligence sweep and the short weekday execution card.

Use it to answer:
- what is the market posture for this week?
- which names matter this week?
- which names are closest to actionable, blocked, or benched?
- which catalysts actually matter this week?
- what portfolio and risk implications matter right now?

Boundary:
- this is the canonical weekly operating map
- summarize only the names and catalysts that matter this week
- do not duplicate full portfolio tables from [[03. Portfolio/Portfolio Snapshot]]
- do not duplicate full gate-by-gate trigger logic from [[03. Portfolio/Deployment Trigger Sheet]]
- let the daily executive summary handle next-session execution detail

Script-backed prep path:
- default to `python scripts/run_finance_refresh_chain.py post-close`
- use narrower script calls only when intentionally validating or debugging one layer
- treat outputs in `tmp/` as evidence inputs, not as automatic final note text

---

## Current operating map — Week of 2026-05-04 to 2026-05-08

### 1) Weekly posture

- **Posture:** Selective risk-on, but with reduced confidence.
- **Confidence level:** Usable with caution. The machine layer is fresh through the 2026-05-06 close, but dashboard validation is warning-grade because **LNG** is the only blocking band-review warning; 16 other band-review items are monitor-only.
- **Operating stance:** Keep the active list narrow. **JPM** and **ETN** are now the deployable-now names in the owner layer; ETN is a Tier 2 conditional add only, not broad AI-power deployment permission. **NVDA** is wait / no-chase after moving above band; **GOOG**, **GS**, and **MSFT** are almost deployable; **BRK.B**, **LMT**, and **XOM** remain do-not-touch / repair.
- **What changed from earlier in the week:** The May 5 ETN / AMD / SMCI cluster has moved from event risk into post-earnings interpretation, oil has cooled from the prior dashboard values, **JPM** has explicit owner-approved deployable-now status, **ETN** was promoted on 2026-05-09 after the fresh band rerun confirmed it remained in band, and **NVDA** remains timing-sensitive into May 20.

---

### 2) Macro regime and confidence

- **Rates / curve:** 2Y 3.93% as of 2026-05-05, 10Y 4.356% as of 2026-05-06, 2s10s +42.6 bps, 3m-10y +75.6 bps. The curve remains positively sloped, but policy is still restrictive.
- **Inflation / energy posture:** Brent 102.06 and WTI 95.82 keep energy pressure alive, but the energy impulse is cooler than the prior note. No fresh CPI/PCE interpretation was added in this pass, so treat the inflation view as still late-cycle and cautionary rather than cleanly improving.
- **Growth / liquidity posture:** The live machine layer still supports a resilient-growth baseline, not a full risk-off regime. Credit is benign and breadth is broad / recovering, but this is not a clean all-clear because the policy layer is still approximate even though it is no longer manually maintained by default.
- **Volatility / sentiment:** SPX 7,365.12 and VIX 17.39 keep the regime in selective risk-on territory, not fear. That supports discipline, not chasing.
- **Confidence limits:** policy expectations remain model-simplified, direct confirmation is still most important for the unresolved NVDA timing path, dashboard validation has one LNG blocking band-review warning, and true pre-market pricing was unavailable from the current yfinance responses.

---

### 3) Weekly deployment map

**Deployable now:**
- **JPM** — Close 314.90. Entry band 306.82–318.12. Stop 301.17. Explicit owner approval landed on 2026-05-07; JPM remains the Tier 1 deployable-now name alongside ETN's Tier 2 conditional add. Keep normal size discipline and no automatic execution.
- **ETN** — Close 401.51. Entry band 395.59–420.31. Stop 383.23. Randall promoted ETN on 2026-05-09 after the fresh rerun confirmed it remained in band. Treat as Tier 2 conditional add only; no automatic execution and no chase above 420.31.

**Wait / no chase — not deployable-now:**
- **NVDA** — Close 215.20. Entry band 197.01–210.84. Stop 190.10. Now above band and still crowded / timing-sensitive into May 20; wait for a pullback or post-earnings reset.

**Almost deployable — pullback / entry discipline still required:**
- **GS** — Close 937.35. Band 878.71–926.76. Above band and still secondary to JPM; the new 10% cash / 25% sector-cap posture keeps it tactical, not deployable-now.

**Post-earnings follow-through, not deployable yet:**
- **GOOG** — Scorecard exists and the report was strong, but close 395.14 is still well above the refreshed 341.96–362.08 band. Improved business read, worse entry location.
- **MSFT** — Scorecard exists and the quarter confirmed thesis quality, but close 413.96 is slightly above the 389.64–412.56 band and the stock remains below the 200-day.

**Do not touch / repair:**
- **BRK.B** — Repair mode remains active.
- **LMT** — Repair mode remains active.
- **XOM** — Scorecard complete, but the setup is still not decision-grade. Follow-through and 50-day reclaim come first.

**Watch / research needed:**
- **AMZN, CAT, LLY, RTX, VRT** — live names, but not current deployment names.

---

### 4) Weekly catalyst map

- **Already hit:** **XOM** reported May 1 and **BRK.B** reported May 2; both remain bench / repair cases.
- **Already hit:** the **May 5 ETN / AMD / SMCI** cluster has shifted into post-earnings interpretation and read-through follow-up.
- **Immediate remaining events:** **LNG** May 7 and April **NFP** May 8.
- **What matters most now:**
  1. keep **XOM** benched even though the scorecard is complete
  2. keep **GOOG/MSFT** off the live board even though the scorecards are explicit — good reports did not magically create good entries
  3. process **ETN** as owner-approved Tier 2 conditional deployment only, not as a broad AI-power chase

---

### 5) Portfolio implications

- **Breadth of opportunity is still narrow.** ETN promotion is a narrow Tier 2 decision, not a broad green light.
- **Live deployable-now opportunity is narrow, not zero.** **JPM** and **ETN** are deployable-now in the owner layer; **NVDA** is wait / no-chase.
- **Best conditional add is ETN, not the extended names, but it still needs strict no-chase discipline and stop awareness.**
- **Energy is not automatically back on the board.** Oil is strong, but **XOM** still needs follow-through and technical requalification.
- **Owner posture is now explicit.** Target cash is 10%, single-sector concentration is capped at 25%, and direct Tech exposure is already at that cap before counting ETN as correlated AI-power exposure.

---

### 6) Risk focus for the week

- **Top process risk:** dashboard validation is warning-grade because **LNG** has a blocking band-review warning; 16 other band-review items are monitor-only.
- **Top catalyst risk:** the unresolved NVDA May 20 timing path still needs cleaner confirmation if it becomes decision-critical.
- **Top market risk:** energy/inflation pressure remains elevated while policy expectations still require approximation caution.
- **Top position risk:** treating **JPM** or **ETN** being deployable now as permission to ignore size, crowding, or concentration discipline.

---

### 7) Priority actions

**Do this week:**
1. Keep the live deployable-now list narrow: **JPM** and **ETN** are the current owner-approved names.
2. Keep **NVDA** in wait / no-chase, not deployable-now; NVDA is above band and remains timing-sensitive.
3. Use the **XOM** scorecard as the canonical post-earnings read, but keep the name benched until follow-through improves.
4. Use the **GOOG** and **MSFT** scorecards as canon, but keep both names off the live board until price location / repair improves.
5. Process the **ETN / AMD / SMCI** follow-up and **LNG** warning without widening scope.

**Avoid this week:**
- Chasing anything above band.
- Treating provider-rolled July earnings dates as automatic blocker clears.
- Treating **XOM** as requalified before the actual post-print follow-through lands.
- Expanding the active list just because the market tape still looks resilient.

---

### 8) Open operating rules for the week

- Warning-grade machine outputs are evidence, not automatic note text.
- A name being in band is necessary, not sufficient.
- Post-earnings revalidation is now explicit for **GOOG** and **MSFT**; that clears the stale blocker wording, not the entry-discipline requirement. **XOM** is interpreted now, but follow-through is still required.
- Keep weekly notes aligned to current evidence, not to the prior catalyst calendar.

---

## Freshness and refresh policy

- **Last updated:** 2026-05-07
- **Data as of:** 2026-05-06 close
- **Next mandatory refresh:** after LNG / NFP follow-up, after Eaton primary-source follow-up if it lands, and after NVDA timing is rechecked no later than 2026-05-13
- **Refresh policy:** update posture, catalyst map, and deployment map when a result or price move materially changes the decision surface. Do not rewrite for noise.
---

## Historical machine archive — Week of 2026-04-27 to 2026-05-01

> Superseded archive material. Do not use this section for current deployment state; use the current operating map above.

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-05-01. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-05-03). Next FOMC 2026-06-17 — 0% cut probability. 2Y 3.880%, 10Y 4.378%, 3M 3.575%.
- **Yield curve:** 2s10s +50 bps, 3m-10y +80 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 16.99, SPX 7,230.12.
- **Dollar / energy:** DXY 98.21, Brent 108.17 $/bbl, WTI 101.94 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-05-01*


**Almost deployable — pullback required (6):**
  - **GS** — close 923.71, band 878.71–926.76 | stop 854.68 | score 18/20
  - **JPM** — close 312.47, band 306.82–318.12 | stop 301.17 | score 19/20
  - **NVDA** — close 198.45, band 188.03–199.28 | stop 182.40 | score 18/20 | earnings in 17d
  - **ETN** — close 425.55, band 395.59–420.31 | stop 383.23 | score 14/20 | earnings in 2d
  - **GOOG** — close 383.22, band 330.01–349.37 | stop 320.33 | score 18/20
  - **MSFT** — close 414.44, band 389.64–412.56 | stop 378.18 | score 18/20

**Do not touch — repair or review (3):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **LMT** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **XOM** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again

**Active watch — no entry band yet (1):**
  - **VRT** — levels are defined, but this execution setup remains watch-only until it is intentionally promoted

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (Apr 27–May 1):** No tracked earnings this week.

**Coming up (next 2 weeks):**
  - **WMB** — earnings 2026-05-04 (in 1d)
  - **PLTR** — earnings 2026-05-04 (in 1d)
  - **EOG** — earnings 2026-05-05 (in 2d)
  - **ET** — earnings 2026-05-05 (in 2d)
  - **MPLX** — earnings 2026-05-05 (in 2d)
  - **LDOS** — earnings 2026-05-05 (in 2d)
  - **ETN** — earnings 2026-05-05 (in 2d)
  - **AMD** — earnings 2026-05-05 (in 2d)
  - **SMCI** — earnings 2026-05-05 (in 2d)
  - **KTOS** — earnings 2026-05-06 (in 3d)
  - **LNG** — earnings 2026-05-07 (in 4d)
  - **AMAT** — earnings 2026-05-14 (in 11d)

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT | 35% max | — |
| Energy | XOM | 35% max | — |
| Financials | GS, JPM, BRK.B | 35% max | — |
| Industrials | ETN | 35% max | — |
| Tech | NVDA, GOOG, MSFT | 35% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 35% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_
---

## Superseded machine archive — Week of 2026-05-04 to 2026-05-08

> Superseded machine-generated material retained for traceability. Do not use this section for current deployment state; use the current operating map above.

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

### 2) Macro regime and confidence

*Machine-populated from market-state.json as of 2026-05-05. Sections marked (judgment) require human/AI interpretation.*

- **Fed / rates:** Target 3.50%–3.75% (confirmed 2026-05-05). Next FOMC 2026-06-17 — 0% cut probability. 2Y 3.950%, 10Y 4.416%, 3M 3.600%.
- **Yield curve:** 2s10s +47 bps, 3m-10y +82 bps. Curve constructive but front-end still restrictive.
- **Volatility / equities:** VIX 17.38, SPX 7,259.22.
- **Dollar / energy:** DXY 98.25, Brent 108.15 $/bbl, WTI 100.72 $/bbl.
- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_

---

### 3) Deployment map

*Data: trigger-sheet.json as of 2026-05-05*


**Almost deployable — pullback required (6):**
  - **ETN** — close 410.86, band 395.59–420.31 | stop 383.23 | score 15/20
  - **GOOG** — close 384.27, band 330.01–349.37 | stop 320.33 | score 18/20
  - **GS** — close 918.89, band 878.71–926.76 | stop 854.68 | score 18/20
  - **JPM** — close 309.40, band 306.82–318.12 | stop 301.17 | score 18/20
  - **MSFT** — close 411.38, band 389.64–412.56 | stop 378.18 | score 19/20
  - **NVDA** — close 196.50, band 188.03–199.28 | stop 182.40 | score 17/20 | earnings in 14d

**Do not touch — repair or review (3):**
  - **BRK.B** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **LMT** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again
  - **XOM** — Repair mode remains active until chart structure and support rebuild make the setup decision-grade again

**Active watch — no entry band yet (1):**
  - **VRT** — levels are defined, but this execution setup remains watch-only until it is intentionally promoted

- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_

---

### 4) Catalyst calendar

**This week (May 4–May 8):**
  - **EOG** — earnings 2026-05-05 (in 0d)
  - **ET** — earnings 2026-05-05 (in 0d)
  - **MPLX** — earnings 2026-05-05 (in 0d)
  - **LDOS** — earnings 2026-05-05 (in 0d)
  - **ETN** — earnings 2026-05-05 (in 0d)
  - **AMD** — earnings 2026-05-05 (in 0d)
  - **SMCI** — earnings 2026-05-05 (in 0d)
  - **KTOS** — earnings 2026-05-06 (in 1d)
  - **LNG** — earnings 2026-05-07 (in 2d)

**Coming up (next 2 weeks):**
  - **AMAT** — earnings 2026-05-14 (in 9d)

- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_
- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_

---

### 5) Sector allocation and risk flags

*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*

| Sector | Names | Risk Cap | Note |
|---|---|---|---|
| Defense | LMT | 35% max | — |
| Energy | XOM | 35% max | — |
| Financials | GS, JPM, BRK.B | 35% max | — |
| Industrials | ETN | 35% max | — |
| Tech | GOOG, MSFT, NVDA | 35% max | — |

- **Concentration check (judgment):** _[Fill: is any sector approaching the 35% cap at current draft weights? What sequencing constraint does that impose?]_
- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_
- **Risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_

---

### 6) Risk rules check

- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_

---

### 7) Key questions to answer this week

- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_

---

### 8) Friday close / week lookback

- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_
