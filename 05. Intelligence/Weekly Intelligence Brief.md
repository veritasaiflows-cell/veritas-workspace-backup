# Weekly Intelligence Brief

## Purpose

Run this as the recurring market sweep.

Use it to synthesize macro, sector, company, sentiment, and event-driven signals into an actionable brief.

Script-backed prep path:
- run `python scripts/market_state_refresh.py` before refreshing this note
- optionally run `python scripts/earnings_calendar_enrichment.py` when the earnings map may have changed materially
- run `python scripts/trigger_sheet_refresh.py` when deployment status may have changed
- run `python scripts/post_earnings_prep.py` after material reports so the interpretation pass starts from a clean structured packet
- run `python scripts/post_earnings_note_targets.py` before editing notes so update scope stays selective
- treat script outputs in `tmp/` as evidence inputs, not as automatic final note text

---

## Current-state notice ? WF72 weekly-surface demotion approved 2026-05-22

> **Canonical freshness warning:** this note is now demoted to an archive/scaffold pointer. The body below contains older May 4?10 prose and draft-only machine skeleton text; do **not** use it as current portfolio judgment.
>
> Current weekly strategy lives in [[05. Intelligence/Weekly Positioning Review]]. Current portfolio/action state lives in [[03. Portfolio/Execution Board]], [[03. Portfolio/Portfolio Snapshot]], [[04. Research/Coverage and Watchlist]], and the latest generated artifacts.
>
> 2026-06-28 Sunday sync: current artifact layer is accepted with no stop line. Use `tmp/run-summary-sunday.json`, `tmp/current-window-artifacts.json`, `tmp/dashboard-validation.json`, `tmp/deployment-readiness-surface.json`, `tmp/research-freshness-opportunity-review.json`, `tmp/fundamental-metrics-current.json`, `tmp/fundamental-ir-reconciliation-packets.json`, `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`, and `tmp/reports/weekly-intelligence-brief-printable-latest.json` for current review-only proof. Dashboard validation is clean except for the known info-grade active-weight accounting gap where active weights plus cash sum to 90% because 10% is suspended legacy model weight. The generated weekly intelligence layer wrote to `05. Intelligence/Weekly Intelligence Brief - machine.md` as a machine-sidecar only; canonical mutation remains blocked. The weekly macro snapshot is complete and presentation-gate clear, but deployment readiness remains presentation-blocked/review-only. WF65 fundamentals are evidence only and require SEC/IR manual review where flagged; they grant no portfolio, sizing, sleeve, cash, execution, paper/live order, trade/account, or owner-approval authority.
>
> Research-opportunity radar should not be duplicated here. Current radar proof is `tmp/research-freshness-opportunity-review.json` generated 2026-06-28T16:54:51Z, degraded only because `tmp/sector-expansion-board.json` is degraded. Use the current weekly strategy surface plus that artifact for review-only cues: improving leadership in Consumer Staples, Financials, Health Care, Industrials, Materials, Real Estate, and Utilities; underexposed lanes in Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, and Utilities; portfolio-review candidates CME, ITA, LIN, META, PH, VRT, and XLB; conditional-watch names ECL, GE, NFLX, TMUS, VMC, and WMB; blocked/deferred CAT, ETN, GS, JPM, LLY, and NVDA.
>
> Boundary: review-only pointer; no promotion, sizing, sleeve, cash, deployment, trade, account action, portfolio/canon mutation, or owner approval is inferred.

---

## Week of May 4–May 8, 2026

*Refreshed 2026-05-07. Data as of 2026-05-06 close unless noted. Machine evidence came from `tmp/market-state.json`, `tmp/trigger-sheet.json`, `tmp/technical-refresh.json`, `tmp/dashboard-validation.json`, current post-earnings packets, and the latest run summaries. Canonical mutation remains owner-gated: dashboard validation is warning-grade because LNG is the only blocking band-review warning; 16 other band-review items are monitor-only.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75%, confirmed 2026-04-29. Next FOMC 2026-06-17.
- **Fed cut expectations:** 0% cut probability in the current machine layer.
- **2Y Treasury:** 3.930% as of 2026-05-05.
- **10Y Treasury:** 4.356% as of 2026-05-06.
- **3M T-bill:** 3.600% as of 2026-05-06.
- **2s10s spread:** +42.6 bps.
- **3M-10Y spread:** +75.6 bps.
- **Dollar:** DXY 97.96 as of 2026-05-06.
- **Volatility / tape:** SPX 7,365.12 and VIX 17.39.

**Regime read:** Restrictive pause, resilient growth baseline, selective risk-on. That is still the right base case, but confidence is not clean because policy expectations remain simplified, dashboard validation has one LNG blocking warning, and energy is still elevated enough to keep inflation risk alive.

---

### 2. Energy sweep

- **Brent crude:** 102.06 as of 2026-05-06.
- **WTI crude:** 95.82 as of 2026-05-06.
- **Brent/WTI spread:** 6.24.
- **Portfolio implication:** energy pricing is still strong enough to matter, but it cooled from the prior note and does **not** automatically make energy names deployable. The live decision still runs through post-earnings interpretation plus chart quality.
- **XOM implication:** the market backdrop is better for the business than it was when oil was in the low 90s, and the scorecard now says the quarter was stronger than the GAAP headline. That still does **not** put XOM back on the active board. It stays benched until post-print follow-through gets cleaner.

---

### 3. Geopolitical scan

- **What the machine layer can honestly say:** elevated oil still implies a live geopolitical or supply-premium backdrop.
- **What this pass does *not* claim:** no fresh external geopolitical sweep was run inside this bounded truth-sync pass, so do not pretend a clean Iran/Hormuz update was freshly revalidated here.
- **Practical read-through:** keep energy and defense sensitivity on the radar, but do not write narrative certainty that the evidence did not refresh.

---

### 4. Earnings radar

**Just reported / immediate review:**
- **XOM** — reported 2026-05-01. Scorecard complete. Underlying quarter was stronger than the GAAP headline, but the name remains *closed with follow-up*, not requalified.

**Just processed from the May 5 window:**
- **ETN** — Q1 2026 interpreted from secondary evidence after direct primary-source fetch did not land cleanly. Beat / revenue upside / raised-guidance evidence is constructive, but guidance and reaction nuance keep ETN **almost deployable**, not promoted.
- **AMD** — Q1 2026 primary-source confirmed. Revenue $10.253B (+38% YoY), non-GAAP EPS $1.37, Data Center revenue $5.8B (+57% YoY). Constructive AI infrastructure read-through, but no standalone portfolio deployment trigger.
- **SMCI** — Q3 2026 interpreted from secondary evidence after IR fetch was blocked. EPS beat / upbeat forward-demand signal is constructive for AI servers, but company-specific risk and missing primary details keep this read-through only.

**Next immediate window:**
- **KTOS** — 2026-05-06
- **LNG** — 2026-05-07
- **April NFP** — 2026-05-08

**Key earnings judgment for the week:**
- The May 5 AI-infrastructure cluster supports the demand regime, but it does **not** unlock capital deployment by itself.
- ETN remains an almost-deployable post-earnings candidate pending primary-source confirmation and next-session price confirmation.
- AMD and SMCI are read-through evidence for the AI infrastructure sleeve, especially NVDA / server / power-enabler demand, not direct deployment triggers.

---

### 5. Analyst and institutional flow

- No fresh, trustworthy analyst-flow or 13F pass was added in this bounded truth-sync.
- Do **not** recycle older upgrade/downgrade language as if it were current.
- If analyst-flow matters for a live decision this week, pull it fresh instead of inheriting stale April commentary.

---

### 6. Technical check

**Closest actionable names:**
- **ETN** — deployable now / owner-promoted conditional add after the 2026-05-08 close remained inside the written band; manual-only, no chase above 420.31.
- **JPM** — owner approval landed on 2026-05-07, but the latest 2026-05-08 close is below the formal band and close to invalidation; trigger is not live until reclaim or explicit band review.
- **NVDA** — wait / no-chase; above the written band, with crowding, sizing, and May 20 timing risk still requiring discipline.
- **GOOG** — almost deployable on thesis, but close is extended above the refreshed band; no chase.
- **GS** — almost deployable; above band, tactical secondary to JPM, and still not deployable-now just because the cash/cap posture is now resolved.
- **MSFT** — almost deployable; slightly above band and still needs cleaner repair / promotion.

**Blocked / repair names that still matter:**
- **BRK.B, LMT, XOM** — do not touch / repair.

**Important caveat:**
- Dashboard validation is warning-grade because **LNG** is the only blocking band-review warning.
- The other 16 band-review items are monitor-only, not deployment blockers.
- That means the technical layer is usable, but not clean enough to justify loose interpretation.

---

### 7. Sentiment gauge

- **VIX:** 17.39.
- **S&P 500:** 7,365.12.
- **Breadth:** the machine layer says breadth is broad / recovering.
- **Read:** the tape still supports selective risk-on, but this is not a low-risk “buy everything” environment. The live setup list is narrow and the one-warning validation surface is still doing real work.

---

### 8. Recommended actions

**Posture:** Selective risk-on, reduced confidence.

**Highest-priority actions this week:**
1. **Treat deployable-now as narrow, not broad.** **ETN** is the only current deployable-now / conditional-add name in the owner layer, and it remains manual-only.
2. **Keep JPM approval separate from a live trigger.** Approval is recorded, but price must reclaim the formal band or receive explicit band review before it is green again.
3. **Keep NVDA in wait / no-chase** and do not widen one approved ETN setup into a broad green light; timing sensitivity and crowding still matter.
4. **Use AMD and SMCI as constructive AI-infrastructure read-through**, not as standalone portfolio triggers.
5. **Use the XOM scorecard as the canonical read and keep energy benched until follow-through improves.**

**Avoid:**
- Overriding blocked status just because provider next-earnings dates rolled forward.
- Treating XOM’s May 1 report as immediate requalification just because the scorecard is written.
- Treating warning-grade machine output as canonical language.

---

## Freshness and refresh policy

- **Last updated:** 2026-05-07
- **Data as of:** 2026-05-06 close plus May 5 ETN / AMD / SMCI post-earnings interpretation
- **Next refresh due:** after Eaton and SMCI primary-source follow-up is captured, LNG / NFP follow-up is processed, and NVDA timing is rechecked no later than 2026-05-13
- **Refresh policy:** rewrite only the sections whose truth changed. Do not drag stale prior-week language forward just because it already exists.

---

## Draft-only machine skeleton — Week of May 4–10, 2026

> **Draft-only / not canonical:** this auto-generated block contains unfilled judgment placeholders and stale row values. Do not use it for current deployment state. Use `05. Intelligence/Weekly Intelligence Brief - machine.md`, the Execution Board, and Regime Matrix until this block is reviewed and promoted.

*Auto-generated by `scripts/weekly_intelligence_brief.py` on 2026-05-10 22:23. Data label claimed 2026-05-11 close, but this block is now quarantined because its rows and judgment sections are incomplete/stale. Sources: tmp/market-state.json, tmp/trigger-sheet.json, tmp/earnings-calendar.json, tmp/post-earnings-prep.json, tmp/technical-refresh.json, tmp/regime-scores.json. Sections marked _judgment_ require human/AI completion.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75% (confirmed 2026-05-10). Next FOMC 2026-06-17.
- **Fed cut expectations:** 0% cut probability.
- **2Y Treasury:** 3.920% as of 2026-05-07 (FRED DGS2).
- **10Y Treasury:** 4.364% as of 2026-05-08 (yfinance ^TNX).
- **3M T-bill:** 3.595% as of 2026-05-08 (yfinance ^IRX).
- **2s10s spread:** 44.4 bps.
- **3M-10Y spread:** 76.9 bps.
- **Inflation (judgment):** _[Fill: latest CPI/PCE prints, MoM and YoY]_.
- **Growth (judgment):** _[Fill: latest GDP estimate, jobless claims, payrolls]_.
- **Dollar:** DXY 98.12 as of 2026-05-11.

**Regime read (judgment):** _[Fill: 2-3 sentence synthesis tying the above into a regime read for the week]_.

---

### 2. Energy sweep

- **Brent crude:** $105.40 as of 2026-05-11 (yfinance BZ=F).
- **WTI crude:** $99.88 as of 2026-05-11 (yfinance CL=F).
- **Brent/WTI spread:** $5.52.
- **EIA inventory (judgment):** _[Fill: latest weekly crude / gasoline / distillate actual vs. consensus, refinery utilization]_.
- **Rig count (judgment):** _[Fill: latest Baker Hughes if available]_.
- **XOM / CVX implication (judgment):** _[Fill: how does current oil structure change earnings setup or entry framing?]_

---

### 3. Geopolitical scan

- **Hot items (judgment):** _[Fill: Iran/Hormuz, Russia/Ukraine, China/Taiwan, sanctions, election cycles]_.
- **Defense / energy implication (judgment):** _[Fill: which tracked names get tailwind or headwind from current geopolitics?]_
- **Key watch:** _[Fill: 1-2 specific developments that would shift conviction this week]_.

---

### 4. Earnings radar

**Reported this week (May 04–May 10):**
- No tracked-universe reports captured this week (or post-earnings packets not staged).

**Earnings this week (calendar — tracked universe):**
- **EOG** — 2026-05-05.

**Coming next week (May 11–May 17):**
- **AMAT** — 2026-05-14.

---

### 5. Analyst and institutional flow

- **Upgrades / downgrades (judgment):** _[Fill: notable rating changes on tracked names this week]_.
- **13F flow (judgment):** _[Fill: institutional positioning changes if any are in the cycle]_.
- **Insider activity (judgment):** _[Fill: notable Form 4 prints]_.

---

### 6. Technical check

*Data: tmp/technical-refresh.json + tmp/trigger-sheet.json.*

| Ticker | Close | MA20 | MA50 | MA200 | Posture | State | Notes |
|---|---|---|---|---|---|---|---|
| ETN | 401.51 | 410.59 | 381.80 | 361.25 | above 50d and 200d, below 20d | DEPLOYABLE NOW | in band |
| JPM | 302.10 | 310.61 | 299.30 | 302.76 | above 50d, below 20d and 200d | ALMOST DEPLOYABLE | -1.5% below band bot (306.82) |
| GOOG | 397.05 | 355.00 | 322.07 | 286.07 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +9.7% above band top (362.08) |
| MSFT | 415.12 | 416.14 | 398.15 | 464.37 | above 50d, below 20d and 200d | ALMOST DEPLOYABLE | +0.6% above band top (412.56) |
| LMT | 506.51 | 546.02 | 600.64 | 521.91 | below all MAs | DO NOT TOUCH | -7.7% below band bot (548.51) |
| BRK.B | 475.94 | 472.76 | 479.91 | 489.76 | above 20d, below 50d and 200d | DO NOT TOUCH | in band |
| XOM | 144.57 | 150.16 | 154.89 | 127.83 | above 200d, below 20d and 50d | DO NOT TOUCH | -3.8% below band bot (150.24) |
| NVDA | 215.20 | 203.18 | 188.65 | 184.72 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +2.1% above band top (210.84) |
| AMZN | 272.68 | 259.60 | 231.24 | 228.52 | above all MAs -- bullish 20>50>200 stack |  | no band |
| BKNG | 165.93 | 177.08 | 174.19 | 198.30 | below all MAs |  | no band |
| VRT | 339.97 | 319.58 | 284.75 | 197.28 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +0.5% above band top (338.33) |
| RTX | 176.09 | 182.98 | 193.76 | 178.57 | below all MAs |  | no band |
| CAT | 897.45 | 836.28 | 763.28 | 600.94 | above all MAs -- bullish 20>50>200 stack |  | no band |
| GS | 936.48 | 921.32 | 871.57 | 831.19 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +1.0% above band top (926.76) |
| CVX | 181.62 | 187.39 | 193.18 | 165.51 | above 200d, below 20d and 50d |  | no band |
| PLTR | 137.80 | 141.23 | 145.70 | 163.93 | below all MAs |  | no band |
| AMD | 455.19 | 326.23 | 254.51 | 217.35 | above all MAs -- bullish 20>50>200 stack |  | no band |
| LNG | 240.11 | 260.30 | 264.78 | 229.11 | above 200d, below 20d and 50d |  | no band |
| LLY | 948.45 | 924.64 | 941.78 | 914.68 | above all MAs |  | no band |

**Technical reads (judgment):** _[Fill: 2-3 sentences summarizing where the universe sits structurally and which names are closest to actionable]_.

---

### 7. Sentiment gauge

- **VIX:** 17.19 as of 2026-05-08.
- **S&P 500:** 7,398.93 as of 2026-05-08.
- **Put/call ratio (judgment):** _[Fill if available]_.
- **Breadth (judgment):** _[Fill: % of SPX above 50d/200d, advance/decline if available]_.
- **Sentiment read (judgment):** _[Fill: complacent / neutral / fearful and what that implies for entry timing]_.

---

### 8. Recommended actions

**Posture (judgment):** _[Selective risk-on / Defensive-neutral / Defensive — state basis]_.

**Highest-priority actions this week:**

1. **Almost-deployable watch.** GOOG, GS, JPM, MSFT, NVDA are conditional on pullbacks into band. No chase above the written entry zone.
2. **Repair / do-not-touch.** BRK.B, LMT, XOM stay off the board until structure repairs.
3. _[Fill judgment-driven priority — what's the single most important call for this week?]_

**Avoid:**
- Chasing any name extended above its band.
- Treating geopolitical situations as resolved without explicit evidence.

---

## Week of June 22–28, 2026

*Auto-generated by `scripts/weekly_intelligence_brief.py` on 2026-06-28 08:12. Data as of 2026-06-26 close. Sources: tmp/market-state.json, tmp/trigger-sheet.json, tmp/earnings-calendar.json, tmp/post-earnings-prep.json, tmp/technical-refresh.json, tmp/deployment-check.json, tmp/portfolio-config.json, tmp/regime-scores.json. Sections marked _judgment_ require human/AI completion.*

---

### 1. Macro pulse

- **Fed funds rate:** 3.50%–3.75% (confirmed 2026-06-28). Next FOMC 2026-07-29.
- **Fed cut expectations:** 0% cut probability.
- **2Y Treasury:** 4.070% as of 2026-06-26 (official Treasury daily yield curve XML).
- **10Y Treasury:** 4.372% as of 2026-06-26 (yfinance ^TNX).
- **3M T-bill:** 3.663% as of 2026-06-26 (yfinance ^IRX).
- **2s10s spread:** 30.2 bps.
- **3M-10Y spread:** 70.9 bps.
- **Inflation (judgment):** _[Fill: latest CPI/PCE prints, MoM and YoY]_.
- **Growth (judgment):** _[Fill: latest GDP estimate, jobless claims, payrolls]_.
- **Dollar:** DXY 101.36 as of 2026-06-26.
- **Credit:** HY OAS 2.78%, IG OAS 0.76% (benign; status ok).

**Regime read (judgment):** _[Fill: 2-3 sentence synthesis tying the above into a regime read for the week]_.

---

### 2. Energy sweep

- **Brent crude:** $72.60 as of 2026-06-26 (yfinance BZ=F).
- **WTI crude:** $69.23 as of 2026-06-26 (yfinance CL=F).
- **Brent/WTI spread:** $3.37.
- **EIA inventory (judgment):** _[Fill: latest weekly crude / gasoline / distillate actual vs. consensus, refinery utilization]_.
- **Rig count (judgment):** _[Fill: latest Baker Hughes if available]_.
- **XOM / CVX implication (judgment):** _[Fill: how does current oil structure change earnings setup or entry framing?]_

---

### 3. Geopolitical scan

- **Tariff/trade risk flag:** manual review required after U.S.-China / tariff-policy headlines; do not mark trade-risk clear without sourced evidence.
- **Hot items (judgment):** _[Fill: Iran/Hormuz, Russia/Ukraine, China/Taiwan, sanctions, election cycles]_.
- **Defense / energy implication (judgment):** _[Fill: which tracked names get tailwind or headwind from current geopolitics?]_
- **Key watch:** _[Fill: 1-2 specific developments that would shift conviction this week]_.

---

### 4. Earnings radar

**Reported this week (Jun 22–Jun 28):**
- No tracked-universe reports captured this week (or post-earnings packets not staged).

**Earnings this week (calendar — tracked universe):**
- None on calendar.

**Coming next week (Jun 29–Jul 05):**
- None on calendar.

**Treasury auctions next week (official FiscalData):**
- 2026-06-29 — 13-Week Bill (92000000000).
- 2026-06-29 — 26-Week Bill (79000000000).
- 2026-06-30 — 6-Week Bill (80000000000).

**NVDA options/implied-move read:**
- Manual review required: missing spot or option chain rows

---

### 5. Analyst and institutional flow

- **Upgrades / downgrades (judgment):** _[Fill: notable rating changes on tracked names this week]_.
- **13F flow (judgment):** _[Fill: institutional positioning changes if any are in the cycle]_.
- **Insider activity (judgment):** _[Fill: notable Form 4 prints]_.

---

### 6. Technical check

*Data: tmp/technical-refresh.json + tmp/trigger-sheet.json.*

| Ticker | Close | MA20 | MA50 | MA200 | Posture | State | Notes |
|---|---|---|---|---|---|---|---|
| ETN | 402.68 | 406.69 | 406.03 | 368.74 | above 200d, below 20d and 50d | DEPLOYABLE NOW | in band |
| JPM | 329.05 | 318.03 | 311.11 | 306.17 | above all MAs -- bullish 20>50>200 stack | ALMOST DEPLOYABLE | +4.1% above band top (315.95) |
| GOOG | 334.69 | 358.64 | 366.47 | 312.99 | above 200d, below 20d and 50d | DO NOT TOUCH | STOP BREACHED: 6.38 below stop 341.07 |
| MSFT | 372.97 | 400.11 | 410.52 | 446.27 | below all MAs | DO NOT TOUCH | STOP BREACHED: 5.21 below stop 378.18 |
| LMT | 507.40 | 519.35 | 523.72 | 533.70 | below all MAs | DO NOT TOUCH | STOP BREACHED: 24.23 below stop 531.63 |
| BRK.B | 498.66 | 486.29 | 480.46 | 490.09 | above all MAs | DO NOT TOUCH | +0.1% above band top (498.19) |
| XOM | 136.54 | 144.70 | 148.44 | 133.77 | above 200d, below 20d and 50d | DO NOT TOUCH | STOP BREACHED: 9.60 below stop 146.14 |
| NVDA | 192.53 | 207.71 | 209.92 | 190.43 | above 200d, below 20d and 50d | DO NOT TOUCH | STOP BREACHED: 0.42 below stop 192.95 |
| AMZN | 232.69 | 244.03 | 256.13 | 232.77 | below all MAs | BELOW STOP | STOP BREACHED: 12.12 below stop 244.81 |
| BKNG | 181.46 | 169.28 | 168.82 | 188.69 | above 20d and 50d, below 200d | BENCH | +6.2% above band top (170.91) |
| VRT | 303.95 | 314.25 | 324.04 | 228.85 | above 200d, below 20d and 50d | PROMOTION REVIEW | in band |
| RTX | 187.99 | 182.16 | 179.52 | 182.01 | above all MAs | ENTRY POLICY REVIEW | in band |
| CAT | 997.47 | 939.66 | 895.31 | 683.47 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +15.1% above band top (866.48) |
| GS | 1,019.61 | 1,060.41 | 988.31 | 877.66 | above 50d and 200d, below 20d | PROMOTION REVIEW | in band |
| CVX | 171.06 | 181.88 | 184.68 | 169.65 | above 200d, below 20d and 50d | BELOW STOP | STOP BREACHED: 11.10 below stop 182.16 |
| PLTR | 112.93 | 132.18 | 136.46 | 158.85 | below all MAs | BELOW STOP | STOP BREACHED: 18.36 below stop 131.29 |
| AMD | 521.58 | 512.39 | 439.12 | 270.47 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +52.3% above band top (342.53) |
| LNG | 241.64 | 235.02 | 244.79 | 229.21 | above 20d and 200d, below 50d | BELOW STOP | STOP BREACHED: 11.81 below stop 253.45 |
| LLY | 1,208.12 | 1,121.78 | 1,030.62 | 973.37 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +24.6% above band top (969.88) |
| LIN | 519.62 | 511.38 | 506.29 | 465.85 | above all MAs -- bullish 20>50>200 stack | PROMOTION REVIEW | +2.7% above band top (506.11) |
| ECL | 283.65 | 264.50 | 260.82 | 268.88 | above all MAs | WATCH / RESEARCH NEEDED | +1.7% above band top (278.98) |
| VMC | 311.35 | 290.55 | 285.45 | 290.82 | above all MAs | WATCH / RESEARCH NEEDED | +3.4% above band top (300.98) |
| META | 550.25 | 582.99 | 612.43 | 648.86 | below all MAs | BELOW STOP | STOP BREACHED: 105.30 below stop 655.55 |
| NFLX | 73.81 | 79.25 | 86.03 | 97.04 | below all MAs | BELOW STOP | STOP BREACHED: 26.43 below stop 100.24 |
| TMUS | 182.68 | 183.20 | 187.97 | 203.50 | below all MAs | BELOW STOP | STOP BREACHED: 24.43 below stop 207.11 |
| PH | 968.92 | 908.30 | 905.90 | 878.73 | above all MAs -- bullish 20>50>200 stack | PROMOTION REVIEW | +6.6% above band top (908.98) |
| GE | 369.00 | 340.11 | 312.78 | 307.15 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +18.3% above band top (311.84) |
| CME | 221.00 | 251.69 | 272.90 | 275.11 | below all MAs | BELOW STOP | STOP BREACHED: 55.68 below stop 276.68 |
| WMB | 77.92 | 72.60 | 73.38 | 66.17 | above all MAs | WATCH / RESEARCH NEEDED | +3.2% above band top (75.50) |
| XLI | 181.20 | 176.62 | 173.97 | 162.99 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +4.5% above band top (173.40) |
| XLB | 51.60 | 51.22 | 51.15 | 47.82 | above all MAs -- bullish 20>50>200 stack | PROMOTION REVIEW | in band |
| XLC | 106.18 | 110.52 | 113.99 | 114.55 | below all MAs | BELOW STOP | STOP BREACHED: 6.53 below stop 112.71 |
| PAVE | 58.84 | 57.61 | 56.59 | 51.43 | above all MAs -- bullish 20>50>200 stack | WATCH / RESEARCH NEEDED | +4.5% above band top (56.28) |
| XLF | 53.57 | 52.68 | 51.98 | 52.12 | above all MAs | WATCH / RESEARCH NEEDED | +0.9% above band top (53.07) |
| XLE | 53.84 | 55.93 | 56.81 | 50.45 | above 200d, below 20d and 50d | BELOW STOP | STOP BREACHED: 0.99 below stop 54.83 |
| ITA | 236.78 | 233.54 | 226.80 | 221.51 | above all MAs -- bullish 20>50>200 stack | PROMOTION REVIEW | +6.0% above band top (223.44) |
| VAW | 232.13 | 231.35 | 231.34 | 217.76 | above all MAs -- bullish 20>50>200 stack | ENTRY POLICY REVIEW | in band |
| VXUS | 84.48 | 85.12 | 84.05 | 77.83 | above 50d and 200d, below 20d | WATCH / RESEARCH NEEDED | +1.3% above band top (83.36) |

**Technical reads (judgment):** _[Fill: 2-3 sentences summarizing where the universe sits structurally and which names are closest to actionable]_.

---

### 7. Sentiment gauge

- **VIX:** 18.41 as of 2026-06-26.
- **S&P 500:** 7,354.02 as of 2026-06-26.
- **Put/call ratio (judgment):** _[Fill if available]_.
- **Breadth (judgment):** _[Fill: % of SPX above 50d/200d, advance/decline if available]_.
- **Sentiment read (judgment):** _[Fill: complacent / neutral / fearful and what that implies for entry timing]_.

---

### 8. Recommended actions

**Posture (judgment):** _[Selective risk-on / Defensive-neutral / Defensive — state basis]_.

**Highest-priority actions this week:**

1. **Almost-deployable watch.** JPM are conditional on pullbacks into band. No chase above the written entry zone.
2. **Repair / do-not-touch.** BRK.B, GOOG, LMT, MSFT, NVDA, XOM stay off the board until structure repairs.
3. _[Fill judgment-driven priority — what's the single most important call for this week?]_

**Avoid:**
- Chasing any name extended above its band.
- Treating geopolitical situations as resolved without explicit evidence.

---

### 9. Fundamental quality and capital-allocation tracker

- **WF65 coverage:** 289 equity rows; capital-allocation counts {'caution': 237, 'bank_manual_review': 2, 'tracked': 50, 'not_applicable': 11}; anomaly counts {'capital_return_exceeds_fcf': 118, 'debt_funded_capital_return_risk': 98, 'leverage_elevated': 95, 'bank_fcf_not_applicable': 2, 'eps_fcf_per_share_divergence': 59, 'sbc_offsets_buybacks': 29, 'capital_returns_with_negative_fcf': 59, 'share_count_dilution': 28, 'buybacks_with_net_dilution': 41, 'low_roic_proxy': 56, 'net_share_issuance': 29}.
- **Validation:** critical 0, warning 20; SEC conflicts: LYB.
- **Capital-allocation caution queue:** ETN, GOOG, MSFT, LMT, XOM, AMZN, BKNG, CAT, CVX, KTOS, AMD, LNG.
- **Bank manual-review queue:** JPM, GS require CET1/ROTCE/NIM/deposit/credit-quality review; industrial FCF/debt gates are suppressed.
- **Structured anomaly queue:** ETN, JPM, GOOG, MSFT, LMT, XOM, AMZN, BKNG, CAT, GS, CVX, KTOS.
- **Boundary:** buybacks, share-count improvements, FCF/share growth, ROIC proxy, and valuation context are evidence only; they do not create deployability, owner approval, sizing, sleeve, account, or trade authority.
