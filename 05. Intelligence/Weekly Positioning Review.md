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

## Week of 2026-04-27 to 2026-05-03

### 1) Weekly posture

- **Posture:** Selective risk-on, but with reduced confidence.
- **Confidence level:** Usable with caution. The machine layer is fresh through the 2026-05-01 close and the dashboard validation surface is clean again, but policy interpretation still uses a simplified futures approximation and a narrow earnings-timing residue remains.
- **Operating stance:** Keep the active list narrow. **JPM** and **NVDA** are now in band. **ETN** remains pullback-only. **GOOG** and **MSFT** are now explicitly revalidated, but still not deployable because GOOG is extended above band and MSFT still needs cleaner repair. **XOM** is interpreted now, but still not requalified.
- **What changed from earlier in the week:** The Apr 29 FOMC event is behind us, the Fed target remains 3.50%–3.75%, oil is higher again (Brent 108.17 / WTI 101.94 as of May 1), **JPM** and **NVDA** have moved into band, and **XOM** has shifted from post-report review to interpreted-but-benched.

---

### 2) Macro regime and confidence

- **Rates / curve:** 2Y 3.88% as of 2026-04-30, 10Y 4.378% as of 2026-05-01, 2s10s +49.8 bps, 3m-10y +80.3 bps. The curve remains positively sloped, but policy is still restrictive.
- **Inflation / energy posture:** Brent 108.17 and WTI 101.94 keep energy pressure alive. No fresh CPI/PCE interpretation was added in this pass, so treat the inflation view as still late-cycle and cautionary rather than cleanly improving.
- **Growth / liquidity posture:** The live machine layer still supports a resilient-growth baseline, not a full risk-off regime. Credit is benign and breadth is recovering, but this is not a clean all-clear because the policy layer is still approximate even though it is no longer manually maintained by default.
- **Volatility / sentiment:** SPX 7,230.12 and VIX 16.99 keep the regime in selective risk-on territory, not fear. That supports discipline, not chasing.
- **Confidence limits:** policy expectations remain model-simplified, direct confirmation is still most important for the unresolved NVDA timing path, and true pre-market pricing was unavailable from the current yfinance responses.

---

### 3) Weekly deployment map

**Deployable now:**
- **JPM** — Close 312.47. Entry band 306.82–318.12. Stop 301.17. Cleaner quality setup than the rest of the board, but still not a license to force size.
- **NVDA** — Close 198.45. Entry band 188.03–199.28. Stop 182.40. Still crowded, so treat it as a disciplined Tier 2 setup, not a free pass.

**Almost deployable — pullback still required:**
- **ETN** — Close 425.55. Band 395.59–420.31. Best chart in the sheet, but still above band and now only 3 days from May 5 earnings.

**Post-earnings follow-through, not deployable yet:**
- **GOOG** — Scorecard now exists and the report was strong, but the stock is still well above the written band. Improved business read, worse entry location.
- **MSFT** — Scorecard now exists and the quarter confirmed thesis quality, but the stock is still below the 200-day and only marginally above band.

**Do not touch / repair:**
- **BRK.B** — Repair mode remains active.
- **LMT** — Repair mode remains active.
- **XOM** — Scorecard complete, but the setup is still not decision-grade. Follow-through and 50-day reclaim come first.

**Watch / research needed:**
- **AMZN, CAT, GS, RTX, VRT** — live names, but not current deployment names.

---

### 4) Weekly catalyst map

- **Sat May 2:** **BRK.B** earnings.
- **Already hit:** **XOM** reported May 1. Scorecard is complete, but the name stays benched until post-print follow-through gets cleaner.
- **Next week (May 4–8):** **WMB, PLTR, EOG, ET, MPLX, LDOS, ETN, AMD, SMCI, KTOS, LNG**.
- **What matters most now:**
  1. keep **XOM** benched even though the scorecard is now complete
  2. keep **GOOG/MSFT** off the live board even though the scorecards are now explicit — good reports did not magically create good entries
  3. manage the **ETN** May 5 catalyst without chasing extension

---

### 5) Portfolio implications

- **Breadth of opportunity is still narrow.** One live in-band name is not a broad green light.
- **Live in-band opportunity is still narrow.** **JPM** and **NVDA** are the only names with current gate alignment on paper.
- **Best conditional add remains ETN, not the extended names.**
- **Energy is not automatically back on the board.** Oil is strong, but **XOM** still needs follow-through and technical requalification.
- **Concentration discipline still matters.** The tech/AI cluster remains the easiest place to outrun risk rules if discipline slips.

---

### 6) Risk focus for the week

- **Top process risk:** 17 entry-band review warnings are still live. Do not act as if every written band is equally clean.
- **Top catalyst risk:** the unresolved NVDA timing path still needs cleaner confirmation if it becomes decision-critical.
- **Top market risk:** energy/inflation pressure remains elevated while policy expectations still require manual caution.
- **Top position risk:** treating **JPM** and **NVDA** being in band as permission to ignore size, crowding, or concentration discipline.

---

### 7) Priority actions

**Do this week:**
1. Keep **JPM** and **NVDA** as the only live in-band board.
2. Keep **ETN** conditional only into May 5 earnings.
3. Use the **XOM** scorecard as the canonical post-earnings read, but keep the name benched until follow-through improves.
4. Use the new **GOOG** and **MSFT** scorecards as canon, but keep both names off the live board until price location / repair improves.
5. Process **BRK.B** today and the **ETN / AMD / SMCI** cluster next week without widening scope.

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

- **Last updated:** 2026-05-03
- **Data as of:** 2026-05-01 close
- **Next mandatory refresh:** after the BRK.B result is assessed and again after the ETN / AMD / SMCI cluster next week
- **Refresh policy:** update posture, catalyst map, and deployment map when a result or price move materially changes the decision surface. Do not rewrite for noise.
---

## Week of 2026-04-27 to 2026-05-01

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
